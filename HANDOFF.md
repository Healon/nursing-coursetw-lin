# HANDOFF — 護理教育訓練網站（2026-07-13）

> 給下一個 session 的 agent：先讀本檔與 `README.md`，再讀 `docs/ARCHITECTURE.md`。
> 正式專案路徑是 `/Volumes/MAC SSD/dev/Projects/nursing-coursetw-lin`。

## 現行更新架構

| 時間（台北） | 執行位置 | 工作 |
|---|---|---|
| 週日 14:00、15:00 | Mac launchd `com.lin.twna-reminder` | twna 本週日更新週期尚未人工處理才提醒；只有 Lin 點按才開瀏覽器 |
| 週日 15:00 | GitHub Actions `update-events` | `scripts/update.py --profile cloud`，只更新 8 個 cloud 來源 |
| 週日 16:00 | Mac launchd `com.lin.nursing-local-update` | 匯入專案 `download-twna/` 的 twna 另存頁、以住宅 IP 抓 jct/tnpa、commit、push |
| 週一 09:00 | GitHub Actions `local-source-freshness` | 離線確認 jct/tnpa/twna 均在剛開始的星期日更新週期成功；否則亮紅 |
| 隨時 | Finder/Dock 一鍵 | `scripts/run_local_update.command`，執行同一套本機更新 |

來源的 `config/site.py` `execution` 是固定邊界：

- `cloud`：nuna、critical、psy、tnna、tnma、ni、ahqroc、hospice。
- `local`：jct、tnpa；GitHub Actions 不嘗試，僅在台灣住宅 IP 執行。
- `manual`：twna；只讀 `data/manual_twna.json`，沒有自動抓取路徑。

## 絕對不能退回的作法

- 不得讓 cloud workflow 執行 jct/tnpa，也不得用 proxy、住宅代理、輪替 IP、偽裝 header 或 cookie
  繞過機房 IP 封鎖。
- 不得對 `act.e-twna.org.tw` 發出任何自動化請求。其 robots.txt 全站 `Disallow: /`；提醒工具
  只有在使用者明確按「開啟課程頁」時才呼叫瀏覽器，另存仍是人工動作。
- 不得使用 `verify=False`。老憑證站使用 `scripts/sources/base.py` 的 `download_curl()`，保持完整驗證。
- 不得在測試中實跑來源；parser 開發維持「fixture 迭代、單一來源對外最多偵察 1 次＋驗收 1 次」。

## 操作語意

- jct/tnpa 同一天都成功過，一鍵或排程會跳過網站請求；隔天允許再抓。`--force` 只供明確重驗。
- twna 成功匯入另存頁時，同時更新 `manual_imported_at` 與 `manual_checked_at`，新增 0 筆也算完成核對；
  對話框按「本週已確認」只更新 `manual_checked_at`。watchdog 取兩者較新者。
- `local_update.py` 發現非資料產物的髒檔會中止。push 被一般 non-fast-forward 拒絕時只做一次
  `pull --rebase`＋重推；衝突會 abort 並交由人處理，禁止無限重試。
- `.command` 與 launchd 都呼叫同一支 `local_update.py`，沒有第二套更新邏輯。

## 安裝狀態與檢查

- `com.lin.nursing-local-update`：既有週日 16:00 排程，必須保留。
- `com.lin.twna-reminder`：2026-07-13 曾確認週日 14:00、15:00 triggers 正確，審查時因正式 main
  尚未整合腳本而已 bootout；最終控制者須先整合本分支，再依 README preflight 後重新 bootstrap。
  plist 固定指向外接 SSD 正式路徑，禁止載入 worktree 路徑。
- `com.lin.twna-watch`：選配的專案 `download-twna/` 即時監看，不是每週流程必要條件。
- 一鍵 log：`~/Library/Logs/nursing-course-update.log`；本機排程 log：`/tmp/nursing-local-update.log`；
  twna 提醒 log：`/tmp/nursing-twna-reminder.log`。

## 故障處理順序

1. `git status` 檢查髒檔；使用者改動先 commit 或暫存，不刪除未知檔案。
2. `gh run list` 看兩個 Actions；`tail /tmp/nursing-local-update.log` 看住宅 IP 更新。
3. watchdog 指向 twna 時人工另存／確認；指向 jct/tnpa 時在住宅網路按一鍵。不要改執行邊界。
4. rebase 衝突先確認自動流程已 abort，再人工整合遠端；不要反覆觸發排程。
5. 宣稱完成前跑 `.venv/bin/python -m pytest -q`、plist lint、shell syntax 與 AST `verify=False` audit。

正式網站：<https://healon.github.io/nursing-coursetw-lin/>；repo：`Healon/nursing-coursetw-lin`。
