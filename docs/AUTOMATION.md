# 自動化更新現行做法

> 現況基準日：2026-08-09。本檔用途是讓新的工作階段一次看懂「資料怎麼進來、誰負責跑、人要做什麼」。
> 元件的設計理由與取捨見 `docs/ARCHITECTURE.md`；操作步驟見 `README.md`，本檔只描述現行運作狀態。

專案絕對路徑：`/Volumes/MAC SSD/dev/Projects/nursing-coursetw-lin`
（`~/Projects/nursing-coursetw-lin` 是同一份的 symlink，非兩份工作樹）

## 來源分三類，共 12 家

| profile | 家數 | 來源代碼 | 誰負責跑 |
|---|---|---|---|
| cloud | 9 | nuna、critical、psy、tnna、tnma、ni、ahqroc、hospice、itri | GitHub Actions |
| local | 2 | jct、tnpa | 本機 Mac Mini |
| manual | 1 | twna | 人工另存頁匯入 |

jct 與 tnpa 走本機的原因：GitHub Actions 機房 IP 被這兩家擋（jct 逾時、tnpa 回 403），必須用台灣住宅 IP 才抓得到。
twna 走人工的原因：該站 robots.txt 全站 Disallow，專案守則不對它發出任何自動請求，程式只讀維護者親手另存的本機檔案。

查詢各 profile 實際包含哪些來源：

```bash
.venv/bin/python -c "from scripts.sources import select_source_codes; print({p: select_source_codes(profile=p) for p in ('cloud','local','manual')})"
```

## 四個自動化元件

### 1 雲端每日爬取

`.github/workflows/update.yml`，每天 UTC 07:17（台北 15:17）跑 `scripts/update.py --profile cloud`，有變更才 commit push，GitHub Pages 隨之自動重建。**只跑 cloud profile，不會碰 jct、tnpa、twna。**

### 2 本機每日更新

LaunchAgent `com.lin.nursing-local-update`，每天 16:00 跑 `scripts/local_update.py`。四步驟：收雲端最新結果、匯入 twna 另存頁、補爬 jct 與 tnpa、推送上線。

- 狀態：`runs=7`、`last exit code=0`，運作正常
- 日誌：`/tmp/nursing-local-update.log`

### 3 手動更新按鈕

`scripts/run_local_update.command`，在 Finder 按兩下即開終端機跑同一支 `local_update.py`。運作正常。

- 日誌：`~/Library/Logs/nursing-course-update.log`

### 4 twna 即時監看

LaunchAgent `com.lin.twna-watch`，2026-08-09 安裝並實測通過（先前 plist 已在 repo 但未掛載）。

機制是 launchd 的 `WatchPaths` 對 `download-twna/` 註冊 kqueue 檔案系統事件，屬事件驅動而非輪詢，平時無常駐行程、零 CPU。存檔瞬間核心通知 launchd，叫起 `scripts/twna_watch.py` 跑一次即結束。`ThrottleInterval=30` 防抖，30 秒內最多觸發一次。

辨識邏輯見 `scripts/twna_watch.py` 的 `is_twna_page()`：要同時命中 GridView 容器 id 與站台特徵字串兩個訊號才認定，避免誤匯入其他 ASP.NET 網站的另存頁。不是 twna 頁就安靜結束，因此往該資料夾丟任何檔案都不會出事。

- 實測：投放一份真的另存頁，14 秒內完成認頁、匯入、去重、歸檔
- 日誌：`/tmp/twna-watch.log`

### 附帶：每週人工核對提醒

LaunchAgent `com.lin.twna-reminder`，週日 14:00 與 15:00，在本週更新週期尚未匯入或確認時顯示 macOS 對話框。目前 `last exit code=1` 尚未釐清，推測是對話框被關閉或 60 秒逾時所致（見 `scripts/twna_reminder.py` 的 `handle_choice()`，非正常按鈕路徑一律回 1）。要重現需在螢幕前配合按鈕。

## twna 人工流程（唯一需要人做的事）

```
瀏覽器開課程頁 → 另存新檔（僅 HTML）到 download-twna/ → 完事
```

**關鍵陷阱**：務必存到 `download-twna/`，不可存進 `download-twna/twna-imported/`。後者是匯入完成後的歸檔區；`scan_folder()` 用 `iterdir()` 只掃最外層、不遞迴，存錯位置會完全不被發現，且沒有任何錯誤訊息，只在日誌留下一行「尚未核對，本次沿用上次資料」。2026-08-08 就因此漏掉一次，隔天才由人工補匯入。

備援手動指令（不依賴監看器）：

```bash
.venv/bin/python scripts/import_twna_page.py <另存的.html>
```

匯入器會合併新資料並保留手動修過的既有條目。來源頁只標月份而無確切日期的列（如 `115/9`）會被跳過，屬預期行為，等官網公布日期後下次匯入自動收錄。

## 已知限制

**自動匯入不等於自動上站。** `twna_watch.process()` 只做匯入與本機重建 `index.html`，沒有 git push。網站要等當天 16:00 的 `local_update` 推送，或人工按 `run_local_update.command`。README 方式三寫的「立刻上站」與實際有落差。

**重開機後監看是否存活未驗證。** `WatchPaths` 指向外接 SSD，而外接卷宗掛載晚於 launchd 啟動，有註冊失敗且不自動復活的風險（同族教訓見 `~/.claude/rules/LESSONS.md` 的 L-2026-08-06-001）。驗證與修復：

```bash
launchctl print gui/$(id -u)/com.lin.twna-watch | grep -A3 "event triggers"
```

看得到 `com.apple.launchd.WatchPaths` 即正常；失效則重跑：

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.lin.twna-watch.plist
```

## 監控機制

`.github/workflows/freshness-watchdog.yml` 每天台北 09:13 跑 `scripts/check_freshness.py`，只讀 repo 內的 `data/status.json` 與 `data/manual_twna.json`，不載入 parser、零網路請求。

新鮮窗：jct 與 tnpa 各 2 天（容忍一次沒開機），twna 8 天（週節奏加一天寬限）。逾期、缺漏、格式錯誤或時間位於未來，Actions 皆亮紅。

2026-08-04 至 08-09 曾因 twna 停在 07-26 連紅六天，08-09 匯入後轉綠，下次時限 2026-08-17。

## 修改 workflow 檔的前置條件

`.github/workflows/` 底下的檔案需要 token 具備 `workflow` scope 才推得動，僅有 `repo` 會被 GitHub 拒絕（訊息為 `refusing to allow an OAuth App to create or update workflow ... without workflow scope`）。本機帳號已於 2026-08-09 執行 `gh auth refresh -h github.com -s workflow` 補上，此為永久性設定。
