# nursing-coursetw-lin：GitHub 可重用方案評估

日期：2026-07-13
範圍：僅評估 `nursing-coursetw-lin` 的 `twna`、`jct`、`tnpa` 與雲端／本機排程協調。

## 結論

不建議為目前問題更換爬蟲框架或導入完整自動化平台。現有 parser、正規化、健康狀態、靜態站與
本機補抓流程已經完成；真正缺口是「來源執行環境分流」與「本機補抓失聯偵測」。

建議保留現有 Python + GitHub Actions + launchd，吸收外部專案的設計經驗，但不整包導入：

1. 雲端 workflow 不再嘗試 `jct`、`tnpa`，由既有 `local_update.py` 單獨負責。
2. GitHub Actions 增加不連來源站的 freshness watchdog，偵測本機補抓是否逾期。
3. `twna` 保持零自動請求，另記人工資料的最後匯入／核對日期。
4. 不在目前 public repo 的 Mac Mini 上安裝 GitHub self-hosted runner。

## 已確認的問題邊界

- `twna` 的 robots.txt 對所有 UA `Disallow: /`；任何 GitHub 專案或瀏覽器框架都不能改變此合規邊界。
- `jct` 在 GitHub-hosted runner 連線逾時，`tnpa` 回 403；相同 parser 在 Mac 的台灣住宅 IP 已成功。
- 2026-07-12 本機 launchd 於台北 16:00 成功補抓，但當日 GitHub 排程延遲至 16:59 才開始，之後把
  遠端 `jct`、`tnpa` 狀態改回 `error`。舊事件仍被 merge 保留，問題主要是執行分流與狀態競態。
- macOS `launchd.plist(5)` 說明 `StartCalendarInterval` 在電腦睡眠錯過時間時會於喚醒後補跑；
  文件沒有保證完全關機跨重開機後一定補跑，因此仍需要 GitHub 端的逾期監測。

## 候選專案

以下授權與維護狀態以 2026-07-13 GitHub repo/API 為準。

| 專案 | 授權／狀態 | 能幫助什麼 | 決定 |
|---|---|---|---|
| [TLAN1012/Taiwan_Nurse_CNT](https://github.com/TLAN1012/Taiwan_Nurse_CNT) | MIT；2026-07-12 有更新 | 護理課程資料模型、靜態站與 workflow 參考 | 已被本專案吸收；不整包導入 |
| [TLAN1012/Taiwan_Neurology](https://github.com/TLAN1012/Taiwan_Neurology) | repo 未提供 LICENSE；2026-07-12 有更新 | 架構與 UX 概念 | 只參考概念，不複製程式碼 |
| [actions/runner](https://github.com/actions/runner) | MIT；活躍維護；支援 macOS | 可讓 workflow 從住宅 IP 執行，並用 job dependency 排序 | 有條件候選，預設不採用 |
| [nektos/act](https://github.com/nektos/act) | MIT；活躍維護 | 在本機 Docker 執行 GitHub Actions workflow | 不採用；仍需 launchd 排程且增加 Docker 層 |
| [changedetection.io](https://github.com/dgtlmoon/changedetection.io) | Apache-2.0；Python；活躍維護 | CSS/XPath/Playwright 頁面變更通知 | 僅可作 parser 改版哨兵，非主 pipeline |
| [Scrapy](https://github.com/scrapy/scrapy) | BSD-3-Clause；活躍維護 | retry、節流、crawler middleware | 不遷移；不能解決 IP 封鎖，重寫成本高 |
| [Crawlee for Python](https://github.com/apify/crawlee-python) | Apache-2.0；活躍維護 | HTTP／Playwright crawler、queue 與持久化 | 不遷移；目前頁面不需要瀏覽器，且不能改變來源 IP |
| [Huginn](https://github.com/huginn/huginn) | MIT；Ruby/Rails；活躍維護 | 排程、網站監測、通知 | 不採用；重複既有功能並增加 DB/worker 維運 |
| [n8n](https://github.com/n8n-io/n8n) | Sustainable Use License；活躍維護 | 視覺化工作流與排程 | 不採用；非一般開源授權且系統過重 |

GitHub 官方的 [Secure use reference](https://docs.github.com/en/actions/reference/security/secure-use)
明確指出 self-hosted runner 幾乎不應直接用於 public repositories，因為不受信任 workflow 可能持久化
入侵 runner 並取得 secrets。官方 [self-hosted runner reference](https://docs.github.com/en/actions/reference/runners/self-hosted-runners)
也要求 runner 常駐、維護更新並保持與 GitHub 的網路連線。

因此 self-hosted runner 並沒有消除 Mac 依賴；它只把 Mac 上的 launchd orchestration 換成 Mac 上的
GitHub runner orchestration。若未來真的要採用，最低條件是獨立的隔離 VM／專用帳號，或 private
orchestration repo、最小權限 token、只允許受信任的 schedule/manual workflow，且必須完全取代
現有 launchd，不能兩套同時抓取。

## 推薦設計

### 1. 明確標示來源執行模式

在來源設定加入 `execution` 或等價欄位：

- `cloud`：一般公開、GitHub-hosted runner 可抓的來源。
- `local`：`jct`、`tnpa`，只能由住宅 IP 的既有 `local_update.py` 執行。
- `manual`：`twna`，只讀人工匯入檔，永不對來源站發請求。

GitHub workflow 使用 `cloud` profile，不再對 `jct`、`tnpa` 製造預期失敗。未執行來源沿用既有
event 與 status，避免雲端晚到時覆寫本機成功結果。

### 2. 保留 launchd，補上跨環境防護

- 保留現有「同日成功就不重抓」護欄。
- local commit 前重新同步遠端；若雲端剛好推送，做一次受控 rebase/retry，避免 non-fast-forward。
- 不靠固定的「雲端 15:00、本機 16:00」順序保證正確性。兩邊應可交換先後而不覆寫對方來源狀態。

### 3. GitHub 端 freshness watchdog

新增只讀 `data/status.json` 的輕量 workflow，不連任何學會網站：

- 在預期本機補抓後（例如每週一）檢查 `jct`、`tnpa` 的 `last_success`。
- 超過約 8 天未成功時讓 Actions 明確失敗，透過既有 GitHub 通知提醒維護者。
- 檢查 twna 時使用 `manual_imported_at`／`manual_checked_at`，不能把「JSON 可讀」當成「官網資料剛更新」。

### 4. 不導入完整第三方平台

`changedetection.io` 可在未來獨立做網頁 DOM 變更提醒，但不應介入抓取、去重與發布主流程。
Scrapy、Crawlee、Playwright、Huginn、n8n 與 act 都無法讓 GitHub-hosted runner 變成台灣住宅 IP，
也不能合法繞過 robots；現在導入只會增加依賴與維運面。

## 驗收方向

1. 所有單元測試維持全綠，新增 execution profile、未執行來源狀態保留、freshness 邊界與 git push
   競態的離線測試。
2. GitHub cloud workflow log 中不再出現對 `jct`、`tnpa` 的請求。
3. 本機補抓不論發生在 cloud workflow 之前或之後，遠端最終 `jct`、`tnpa` 都保持最近一次本機成功狀態。
4. watchdog 對 8 天內成功回 0，超過門檻回非零；整個測試不連來源站。
5. `twna` 仍保持零自動請求，頁面／狀態能區分 parser 成功與人工資料的新鮮度。
6. 禁止 `verify=False` 應用 Python AST 或離線測試檢查實際函式呼叫，不用會命中說明文字的 grep 零結果。
