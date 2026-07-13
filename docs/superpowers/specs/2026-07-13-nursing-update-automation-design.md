# nursing-coursetw-lin 自動更新與一鍵備援設計

日期：2026-07-13
狀態：Lin 已批准設計方向，等待書面規格審閱
範圍：`/Volumes/MAC SSD/dev/Projects/nursing-coursetw-lin`

## 1. 目標

在不繞過來源網站限制的前提下，讓護理課程網站具備：

1. 一般來源由 GitHub Actions 每週自動更新。
2. `jct`、`tnpa` 由 Mac 的台灣住宅 IP 每週自動補抓。
3. `twna` 保留人工開頁、另存 HTML 的必要步驟，其後匯入、去重、建站與推送自動完成。
4. 平常無需操作；自動排程失敗時可從 Finder 或 Dock 一鍵補跑。
5. 雲端與本機不論誰先執行，都不會覆寫對方的成功狀態或製造重複抓取。
6. 本機整週未成功時，由 GitHub 端的 watchdog 主動亮紅提醒。

## 2. 不可變更的合規邊界

- `twna` 的 robots.txt 全站 `Disallow: /`。程式不得對該站發出自動化請求。
- 不使用 proxy、住宅代理、輪替 IP、偽裝 User-Agent、cookie 重放或 header 欺騙。
- 不使用 `verify=False`；老憑證站維持 `download_curl()` 完整驗證。
- `jct`、`tnpa` 只從維護者本人的住宅網路執行，仍使用表明身分的專案 User-Agent。
- 新 parser 的對外實跑仍遵守每來源最多兩次；本設計不修改三家的 parser。

## 3. 已選定方案

採用「GitHub 雲端更新 + Mac launchd 本機補抓 + GitHub watchdog + 一鍵備援」。

不採 GitHub self-hosted runner：它仍依賴 Mac 開機與住宅網路，而且 GitHub 官方不建議將
self-hosted runner 直接掛在 public repository。候選專案與授權評估見
`docs/research/2026-07-13-github-reuse-options.md`。

## 4. 每週時間線

| 台北時間 | 執行位置 | 行為 |
|---|---|---|
| 週日 14:00 | Mac launchd | 若本週尚未人工核對／匯入 twna，顯示提醒對話框 |
| 週日 15:00 | GitHub Actions | 只跑 `cloud` 來源，重建並推送；不執行 jct、tnpa、twna |
| 週日 15:00 | Mac launchd | twna 第二次提醒機會；已核對或已匯入則安靜退出 |
| 週日 16:00 | Mac launchd | 執行既有本機更新：匯入 twna 另存頁、抓 jct/tnpa、建站、commit、push |
| 週一 09:00 | GitHub Actions | watchdog 只讀 repo 資料，檢查本機與人工來源是否逾期 |
| 隨時 | Finder／Dock | 一鍵執行與 16:00 完全相同的本機更新流程 |

`StartCalendarInterval` 在 Mac 睡眠錯過時會於喚醒後補觸發。完全關機跨重開機沒有同等保證，
因此週一 watchdog 是必要的外部保險。

## 5. 來源執行模式

`config/site.py` 的每個來源增加 `execution` 欄位：

- `cloud`：GitHub-hosted runner 可正常抓取的公開來源。
- `local`：`jct`、`tnpa`，只能由 Mac 住宅 IP 執行。
- `manual`：`twna`，只讀本機人工匯入的 JSON，永不自動抓來源站。

`scripts/update.py` 增加 profile 選擇能力。`--sources` 仍保留給開發與單來源診斷；正式 workflow
使用 profile，避免來源清單同時散落在 Python 與 YAML。

雲端 workflow 只執行 `cloud`。`status.compute()` 既有「本輪未執行來源沿用先前狀態」語意保留，
因此雲端晚於本機執行時也不會把 `jct`、`tnpa` 改回 error。未執行來源的舊 events 同樣由現有
merge 流程保留。

## 6. twna 人工提醒與資料新鮮度

### 6.1 提醒方式

新增獨立的 twna reminder 程式與 launchd plist，使用 macOS 內建 `osascript` 顯示對話框，
不加入第三方通知套件。

提醒內容：

> 台灣護理學會資料需要人工核對。請開啟課程頁，選擇「檔案 → 另存新檔 → 僅 HTML」，存到下載資料夾。

按鈕：

- `開啟課程頁`：只有使用者明確點擊後，才交給預設瀏覽器開頁；程式本身不下載內容，也不標記完成。
- `稍後提醒`：不寫入完成狀態；15:00 的第二次排程仍會提醒。
- `本週已確認`：由使用者聲明已人工查看且沒有需要匯入的新內容，記錄核對時間。

提醒前先檢查：

- 最近七天是否已成功匯入 twna 另存頁；或
- 最近七天是否已按下「本週已確認」；或
- `~/Downloads` 是否已存在等待處理的 twna HTML。

符合任一條件即安靜退出，不重複打擾。

### 6.2 新鮮度欄位

`data/manual_twna.json` 增加頂層欄位：

- `manual_imported_at`：最後一次成功處理另存頁的台北時間；即使沒有新增事件，也代表已取得並核對新版頁面。
- `manual_checked_at`：最後一次人工確認官網狀態的台北時間。

成功匯入另存頁時同步刷新兩欄。按下「本週已確認」只刷新 `manual_checked_at`。

既有檔案升級時不得用安裝日偽裝成最近核對：依目前資料註記，`manual_imported_at` 初始值採
`2026-07-10`，`manual_checked_at` 留空，直到使用者真的核對或再次匯入。

這兩欄和來源 parser 的 `last_success` 分開：JSON 可讀只代表程式正常，不代表官網資料已在當天核對。

### 6.3 16:00 本機更新結果

- 找到 twna HTML：匯入、去重、更新新鮮度、歸檔原始檔；有新事件時重建 twna 資料。
- 沒有 HTML 但最近七天已人工確認：顯示「twna 本週已確認，無新匯入檔」。
- 沒有 HTML且未確認：沿用舊資料，通知「twna 尚未核對，本次沿用上次資料」；不把它誤記為新鮮。

任何情況都不對 twna 發出網路請求。

## 7. jct／tnpa 本機更新

保留現有 `scripts/local_update.py` 與週日 16:00 plist，不改成 18:00。

保留「同一天成功就不重抓」：

- 同一天自動排程已成功，再按一鍵時跳過 jct／tnpa 網路請求。
- 隔天再按允許重新抓，因官網可能每天新增課程。
- `--force` 保留給明確需要重抓的維護操作。
- 即使跳過 jct／tnpa，仍掃描並處理新的 twna 本機檔案。

本機流程維持：工作區保護 → pull → twna 匯入 → jct/tnpa 同日護欄 → 更新 → 健康檢查 →
diff-gated commit/push → 桌面通知。

### Git 競態處理

若本機抓取期間 GitHub workflow 剛好 push：

1. 本機先建立自己的資料 commit。
2. 第一次 push 若為 non-fast-forward，僅允許一次 `pull --rebase` 與重試 push。
3. rebase 無衝突才重試；有衝突就中止 rebase、保留診斷紀錄並通知使用者，不自動猜測合併結果。
4. 競態處理不得再次抓 jct／tnpa。

## 8. Finder／Dock 一鍵備援

提供一個可雙擊並可拖到 Dock 的 `.command` 入口；它只負責找到專案與 venv，然後呼叫
`scripts/local_update.py`。所有業務邏輯仍只有一份，不另寫第二套更新流程。

一鍵流程會：

1. 檢查外接 SSD、專案目錄與 `.venv`。
2. 執行既有本機更新。
3. 同日已成功時不重抓 jct／tnpa。
4. 成功或失敗皆顯示 macOS 通知。
5. 完整輸出追加到 `~/Library/Logs/nursing-course-update.log`。

工作區有未提交的非資料修改時沿用既有保護並中止，避免一鍵操作碰到開發中的程式。

## 9. GitHub freshness watchdog

新增週一 09:00（UTC 01:00）的 workflow。它不安裝爬蟲依賴、不連學會網站，只 checkout repo 並
執行離線 freshness 檢查。

檢查規則：

- `jct`、`tnpa`：`last_success` 距檢查日超過 8 天，視為失聯並非零退出。
- `twna`：`manual_imported_at` 與 `manual_checked_at` 兩者較新者距檢查日超過 8 天，視為尚未人工核對並非零退出。
- 其他來源不在此 watchdog 範圍，仍由既有雲端健康三態負責。

失敗只影響維護者的 GitHub Actions 通知，不在公開頁顯示詳細錯誤；符合既有「公開頁保持中性、
維護錯誤走 Actions／桌面通知」決策。

## 10. 錯誤處理

- twna reminder 無法顯示：寫入本機 log，不改任何完成時間。
- twna HTML 解析失敗：原始檔不歸檔、不更新新鮮度；本機更新失敗並通知。
- jct 或 tnpa 單來源失敗：保留既有資料與 last_success，狀態顯示 error；另一來源繼續。
- git pull、commit、rebase、push 任一步失敗：停止後續發布，保留 log 與桌面通知。
- watchdog 讀不到或解析不了狀態檔：視為失敗，不可默認正常。
- 通知失敗不是資料流失敗，但必須留 log。

## 11. 測試設計

全部開發迭代使用 fixture 或 mock，不連來源站。

新增測試至少涵蓋：

1. execution profile 正確選出 cloud/local/manual。
2. cloud profile 不載入或執行 jct、tnpa、twna。
3. 本輪未執行來源保留舊 events、status 與 last_success。
4. 雲端先／本機先兩種順序得到相同的來源狀態。
5. `sources_fresh_today()`：同日跳過、隔日允許、任一來源未成功則執行。
6. twna 最近七天已匯入／已確認／有待處理檔時不提醒。
7. reminder 三個按鈕不會在未明確點擊時開啟網頁或寫入完成時間。
8. twna 匯入即使新增 0 筆也更新人工核對時間；解析失敗不更新。
9. watchdog 的 8 天門檻與缺檔／壞 JSON。
10. push non-fast-forward 只重試一次，且不重新呼叫任何 source fetch。
11. 一鍵入口缺 SSD、缺 venv、工作區髒檔的錯誤呈現。
12. 以 AST 或等價離線檢查確認沒有函式呼叫傳入 `verify=False`；不使用會命中說明註解的 grep 零結果。

## 12. 上線與驗收

1. 先完成全部離線測試；現有基準為 170 passed。
2. 上線前處理目前未追蹤的 `HANDOFF_CODEX_BLOCKED_SOURCES.md`；由維護者決定納入版本控制或移出
   repo。不可讓它留在工作區，否則既有髒檔保護會阻止 `local_update.py` 執行。
3. 安裝／更新 launchd plist 前先用 `plutil -lint` 驗證。
4. 用測試資料演練 reminder、watchdog、一鍵入口與 git 競態，不連學會站。
5. 2026-07-12 已完成本週 jct／tnpa 真實抓取，因此開發完成後不立即重抓。
6. 下一個正常週日排程做一次端到端驗收，作為該週唯一正常實跑。
7. 驗收確認：
   - 雲端 log 不出現 jct／tnpa／twna 的來源請求。
   - 14:00 提醒只在需要時出現，按「開啟課程頁」才開瀏覽器。
   - 16:00 本機更新成功，jct／tnpa 各自刷新 last_success。
   - 同一天再按一鍵不重抓 jct／tnpa。
   - 隔天的一鍵演練以 mock 驗證允許重抓，不為驗收額外打來源站。
   - 週一 watchdog 對新鮮資料通過，對測試中的逾期資料失敗。
   - 遠端最終資料沒有重複事件、重複 commit 或被雲端改回 error。

## 13. 不在本次範圍

- 讓 twna 自動抓取。
- 導入 proxy、Playwright、Scrapy、Crawlee、Huginn、n8n 或 self-hosted runner。
- 改寫 jct、tnpa parser；除非新的證據顯示住宅 IP 也無法解析。
- 把週日自動排程改成每日。本設計只允許使用者隔日主動一鍵重抓。
- 在公開頁顯示維護者錯誤細節。
