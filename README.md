# 學會活動彙整站模板（society events aggregator template）

把多個學會網站的繼續教育課程與學術活動，自動彙整成一頁可搜尋、可篩選的靜態網站。
零後端、零資料庫、零框架、零維運成本：內容更新靠 GitHub Actions 排程爬蟲，發布靠 GitHub Pages。

做法逆向自 [Taiwan_Neurology](https://tlan1012.github.io/Taiwan_Neurology/) 彙整站，
架構參考同作者 MIT 授權的 [Taiwan_Nurse_CNT](https://github.com/TLAN1012/Taiwan_Nurse_CNT) 重新通用化實作。
完整拆解與設計決策見 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。

```
GitHub Actions cron（每週日台北 15:00）
  → scripts/update.py --profile cloud：只跑 8 個可從雲端抓取的公開來源
  → 正規化、去重合併、時間窗過濾 → data/events.json
  → 來源健康快照 → data/status.json
  → scripts/build.py：注入 templates/index.html.tpl → index.html（自包含單檔）
  → 有變更才自動 commit push → GitHub Pages 自動重新發布

本機 launchd（每週日台北 16:00）
  → 匯入專案 `download-twna/` 內的 twna 另存頁 → 從住宅 IP 抓 jct/tnpa → commit push

GitHub Actions watchdog（每週一台北 09:00）
  → 完全離線檢查 jct/tnpa/twna 新鮮度；逾期就讓 Actions 亮紅
```

## 快速開始（本機，不需網路）

需求：macOS／Linux、Python 3.10 以上。

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 scripts/update.py --sources demo   # 用離線示範資料跑通整條 pipeline
python3 -m http.server 8000                # 開 http://localhost:8000 預覽
```

跑測試（全部離線）：

```bash
pytest -q
```

## 三種來源執行模式

每個 `config/site.py` 來源都有 `execution`，用執行位置而非抓取技巧分流：

| 模式 | 來源 | 執行方式 |
|---|---|---|
| `cloud` | nuna、critical、psy、tnna、tnma、ni、ahqroc、hospice | 週日 15:00 GitHub Actions 執行 `scripts/update.py --profile cloud` |
| `local` | jct、tnpa | 週日 16:00 Mac 住宅 IP 執行；雲端 workflow 不會嘗試 |
| `manual` | twna | 程式只讀人工另存後的本機 JSON，永不自動請求 TWNA |

指定模式可用 `.venv/bin/python scripts/update.py --profile cloud|local|manual`；診斷單一來源則用
`--sources code1,code2`。兩者互斥，避免同時指定後執行範圍含糊。

## 換成你的學會（最重要的一節）

`config/site.py` 是唯一的「換主題開關」，全部是純資料設定，照註解改即可：

| 設定 | 改什麼 |
|---|---|
| `SITE` | 網站標題、副標、免責聲明 |
| `THEME` | 整站配色（CSS 變數） |
| `CATEGORIES` | 活動類別與自動歸類關鍵字（保留 `other`） |
| `CREDIT_TYPES` | 積分別（護理師／專師／醫師／長照…依你的領域定義） |
| `REGIONS` | 地區與推斷關鍵字（保留 `online` 與 `tbd`） |
| `SOURCES` | 要彙整哪些學會：代碼、名稱、列表頁網址、是否啟用 |
| `SCRAPE` | 時間窗、請求延遲、User-Agent（請填上你的聯絡方式） |

程式碼（`scripts/`）與版面（`templates/index.html.tpl`）在換主題時原則上不用動。

## 新增一個學會來源（SOP）

1. 確認該學會的活動列表頁「免登入」就看得到。需要會員登入的網站不要爬：`enabled` 設 `False`、`note` 註明，改人工維護。
2. 在 `config/site.py` 的 `SOURCES` 加一筆（代碼用小寫英文，如 `twna`）。
3. 建 `scripts/sources/<代碼>.py`，實作 `fetch() -> list[dict]`：用 `base.download()` 抓頁面（內建禮貌延遲與 UA），解析邏輯放在純函式 `parse(html)` 裡，事件用 `base.make_event()` 建構。
4. 存一份真實頁面快照到 `tests/fixtures/<代碼>_list.html`，在 `tests/test_parsers.py` 加離線測試。
5. 本機驗證：`python3 scripts/update.py --sources <代碼>`，確認筆數與內容合理。
6. 驗證通過後把該來源 `enabled` 改 `True`。

### 請 Claude Code 幫你寫 parser 的提示語範本

```
我在維護一個學會活動彙整站（本 repo），要新增資料來源「{學會名稱}」。
活動列表頁（已確認免登入可看）：{URL}
請先讀 scripts/sources/base.py、demo.py 與 tests/test_parsers.py 理解介面，
然後：
1. 實作 scripts/sources/{代碼}.py：fetch() 用 base.download() 抓頁，
   解析放在純函式 parse(html)，事件用 base.make_event() 建構；
   積分對映到 config CREDIT_TYPES 既有代碼，細項說明放 ctext。
2. 把實際頁面存到 tests/fixtures/{代碼}_list.html，補離線測試。
3. 跑 pytest 與 python3 scripts/update.py --sources {代碼} 驗證，回報結果。
注意爬蟲禮貌：所有請求走 base.download()，開發過程總請求控制在 20 次內，
且對外實跑以 2 次為上限（偵察 1＋最終驗收 1），中間迭代一律餵本地快取檔；
多條驗收指令共用同一次實跑的輸出，不要各自重抓。
```

### 手動維護來源（robots 禁爬或需登入的學會）

有些學會網站的活動頁 `robots.txt` 全站 `Disallow`，或整個活動列表都要會員登入才看得到。
遇到這種情況不要繞過限制硬爬，改用「手動維護」模式：由你自己瀏覽官網、手動把課程資訊
填進一份 JSON，程式只負責讀檔轉換成事件，完全不發出網路請求（範例見 `twna` 來源）。

**建立方式**：

1. `config/site.py` 的 `SOURCES` 該筆設為 `execution: "manual"`；資料未備妥前維持
   `enabled: False`，備妥後才改為 `True`。`note` 註明「robots 禁爬／需登入、手動維護」與
   判定依據（哪天測的、robots.txt 內容）。
2. 建 `data/manual_<代碼>.json`，格式：

   ```json
   {
    "comment": "一行說明這份清單怎麼維護、資料來源是什麼",
    "manual_imported_at": "",
    "manual_checked_at": "",
    "events": []
   }
   ```

3. 建 `scripts/sources/<代碼>.py`，`fetch()` 讀這份 JSON 的 `events` 陣列，每筆用
   `base.make_event(**item)` 轉成標準事件；檔案不存在或 JSON 壞掉要讓例外往外拋（不要
   `try/except` 吞掉），讓 registry 記成該來源 `status=error`，錯誤才看得見；`events` 是
   空清單則回傳空 list，這是合法狀態（`status=empty`），不是失敗。

`manual_imported_at` 記錄最近一次成功解析並匯入另存頁的時間（即使新增 0 筆也會更新）；
`manual_checked_at` 記錄最近一次人工確認官網沒有新內容的時間。兩欄都是含時區的 ISO 時間，
watchdog 取兩者較新者判斷資料是否仍新鮮；不要用自動排程時間假裝人工檢查時間。

**`events` 陣列每筆物件欄位**（對應 `base.make_event()` 的參數，除 `date`／`title`／`url`
外皆可省略，省略就套用該函式的預設值）：

| 欄位 | 必填 | 說明 |
|---|---|---|
| `date` | 是 | `YYYY-MM-DD`（西元 ISO 格式；民國日期要先自己換算） |
| `title` | 是 | 活動標題 |
| `url` | 是 | 活動原始網址（供使用者點回官網報名） |
| `location` | 否 | 地點文字，留空則 `region` 會落 `tbd` |
| `credits` | 否 | 積分物件，key 須為 `config/site.py` 的 `CREDIT_TYPES` 既有代碼，如 `{"pro": 3}` |
| `cat` | 否 | 類別代碼，省略則依標題關鍵字自動推斷 |
| `region` | 否 | 地區代碼，省略則依 `location`＋`title` 關鍵字自動推斷 |
| `online` | 否 | 是否為線上活動，預設 `false` |
| `ondemand` | 否 | 是否為隨選（不受時間窗限制），預設 `false` |
| `ctext` | 否 | 補充說明文字（如積分細節、報名限制） |

**範例一筆**（假資料，示範格式用）：

```json
{
 "comment": "台灣護理學會（twna）robots.txt 全站禁爬，手動維護；資料來源：官網課程公告頁人工核對",
 "events": [
  {
   "date": "2026-10-05",
   "title": "【示範】社區護理繼續教育研習會",
   "url": "https://www.twna.org.tw/example-course-page",
   "location": "台北市中正區",
   "credits": {"pro": 3},
   "ctext": "積分以官方公告為準，此為示範資料"
  }
 ]
}
```

4. 填完真實課程資料後，把 `config/site.py` 該來源的 `enabled` 改成 `true`，跑
   `python3 scripts/update.py --sources <代碼>` 驗證能正常併入 `data/events.json`。之後每次要更新，方式一是
   直接編輯這份 JSON；不想手動打字的話，twna 來源另外準備了方式二（見下）。

### 方式二：另存網頁匯入（推薦，較省力；以 twna 為例，寫給非工程師看）

twna（台灣護理學會）不用你逐欄手動打字抄課程資訊，改用瀏覽器「另存」＋一個小工具自動整理，
全程不連網（工具只讀你另存到電腦裡的檔案，不會主動連去 twna 網站，符合它 robots.txt 全站
禁爬的限制）：

1. 用瀏覽器開啟 twna 課程列表頁（活動報名頁）。
2. 瀏覽器按 `⌘S`（或選單「檔案」→「另存新檔」），**格式選「網頁，僅 HTML」**（不要選
   「網頁，完整」），存到專案的 `download-twna/`：

   `/Volumes/MAC SSD/dev/Projects/nursing-coursetw-lin/download-twna`
3. 打開終端機（Terminal），切到專案資料夾，執行（把路徑換成你實際存檔的位置）：

   ```bash
   .venv/bin/python scripts/import_twna_page.py download-twna/你存的檔名.html
   ```

   執行完會印出一行「新增 N 筆、略過重複 M 筆、解析失敗 K 筆」。新課程已經自動整理寫進
   `data/manual_twna.json`；已經存在的活動、或你之前手動修改過的內容，不會被覆蓋掉。
4. 執行 `python3 scripts/update.py --sources twna`，把新資料併入網站。
5. 打開 `index.html` 確認新課程有出現，沒問題再照一般流程 commit push。

### 方式三：全自動監看（最省力；你只剩「另存」一個動作）

安裝一次之後，流程變成：**瀏覽器開課程頁 → 另存新檔到專案的 `download-twna/` → 完事**。
系統會自動認出這是 twna 課程頁、匯入去重、重建網站、跳桌面通知，原始檔自動歸檔到
`download-twna/twna-imported/`。合規不變：程式永遠只讀你另存的本機檔案，不對該站發任何請求；
「開頁面、存檔」這步依守則保留為人類動作。

安裝（一次性，每台機器各裝一次）：

```bash
cp "scripts/launchd/com.lin.twna-watch.plist" ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.lin.twna-watch.plist
```

- 手動單次掃描（不裝監看也能用）：`.venv/bin/python scripts/twna_watch.py`
- 看執行紀錄：`tail /tmp/twna-watch.log`
- 移除：`launchctl unload ~/Library/LaunchAgents/com.lin.twna-watch.plist && rm ~/Library/LaunchAgents/com.lin.twna-watch.plist`
- 注意：plist 內的路徑指向本專案在外接 SSD 的位置，專案搬家或換機時要同步修改；
  且必須用專案 venv 的 Python（系統 Python 在 launchd 下讀外接 SSD 會被權限擋）。

### 每週人工核對提醒（已採用）

週日 14:00 與 15:00，`com.lin.twna-reminder` 會在本週日更新週期尚未匯入／確認時顯示對話框；
前一個星期日的匯入不會壓掉新一週提醒。
「開啟課程頁」必須由你明確點選才會交給瀏覽器；程式本身不下載或自動存取 TWNA。
另存成「僅 HTML」到專案的 `download-twna/` 後，16:00 的本機更新會自動匯入。若官網確實沒有新課，
按「本週已確認」只更新 `manual_checked_at`；「稍後提醒」則保留逾期狀態，15:00 再提醒。

安裝或更新前，必須先把含 `scripts/twna_reminder.py` 的版本整合到正式專案；不要從暫時的
worktree 直接載入。下列命令固定指向 `/Volumes/MAC SSD/dev/Projects/nursing-coursetw-lin`，並在
改變 launchd 狀態前確認正式 venv 與腳本都存在：

```bash
PROJECT="/Volumes/MAC SSD/dev/Projects/nursing-coursetw-lin"
AGENT="$HOME/Library/LaunchAgents/com.lin.twna-reminder.plist"
test -x "$PROJECT/.venv/bin/python" || { echo "找不到正式專案 venv" >&2; exit 1; }
test -f "$PROJECT/scripts/twna_reminder.py" || { echo "正式專案尚未整合 twna reminder" >&2; exit 1; }
mkdir -p "$HOME/Library/LaunchAgents"
cp "$PROJECT/scripts/launchd/com.lin.twna-reminder.plist" "$AGENT"
launchctl bootout "gui/$(id -u)" "$AGENT" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$AGENT"
launchctl print "gui/$(id -u)/com.lin.twna-reminder"
```

- 紀錄：`tail /tmp/nursing-twna-reminder.log`
- 移除：`launchctl bootout "gui/$(id -u)" ~/Library/LaunchAgents/com.lin.twna-reminder.plist && rm ~/Library/LaunchAgents/com.lin.twna-reminder.plist`
- 外接 SSD 必須掛載；若路徑搬移，先修改 plist 再重新 bootstrap。

## 部署到 GitHub Pages

> 本專案已於 2026-07-10 部署：repo `Healon/nursing-coursetw-lin`、
> 網站 https://healon.github.io/nursing-coursetw-lin/ 。以下步驟保留給「套用本模板到
> 新主題」時參考（若模板資料夾位於其他 git repo 內，先搬到獨立位置如 `~/Projects/` 再進行）。

1. 建立 GitHub repo（Pages 免費方案需 public）並推上去：

   ```bash
   git init && git add -A && git commit -m "feat: society events aggregator"
   gh repo create <你的帳號>/<repo名> --public --source . --push
   ```

2. GitHub 網頁 → repo → Settings → Pages → Build and deployment：
   Source 選「Deploy from a branch」，Branch 選 `main`、資料夾 `/(root)`，存檔。
3. 一到兩分鐘後網站上線：`https://<你的帳號>.github.io/<repo名>/`。
4. 啟用自動更新：repo → Actions → 啟用 workflows → 選「update-events」→「Run workflow」手動跑第一次，確認流程綠燈（或亮紅時查頁尾與 log）。之後每週日台北 15:00 自動執行。
5. 上線前清掉示範資料：`config/site.py` 把 `demo` 的 `enabled` 改 `False`，執行
   `python3 scripts/update.py --reset`，確認頁面只剩真實來源後 commit push。

## 本機更新（一個指令）

雲端每週日 15:00 只更新 8 家 `cloud` 來源，不執行會擋 GitHub 機房 IP 的醫策會 jct、
專科護理師學會 tnpa（LESSONS L-2026-07-10-008），也不執行 robots 禁爬的 twna。
後三家的本機資料由**同一個指令**補完：

```bash
.venv/bin/python scripts/local_update.py
```

它會自動做完全部：收雲端最新結果（git pull）→ 掃專案的 `download-twna/` 匯入 twna 另存頁 →
補爬 jct＋tnpa → 重建 → commit → push → 桌面通知。同一天兩家都已成功抓過就不重爬；
隔天執行可再次抓取，符合課程可能每日更新的需求。只有明知需要重驗時才用 `--force`。
工作區有非資料檔的改動會先中止，保護你改到一半的東西。

**Finder／Dock 一鍵執行**：在 Finder 雙擊 `scripts/run_local_update.command`，或把它拖到
Dock 右側的檔案區，之後點一下即可執行同一套流程；同一天已成功的來源仍由
`local_update.py` 判斷並跳過，不會重複抓取。完整輸出會附加到
`~/Library/Logs/nursing-course-update.log`，方便事後查看。

**自動化**：每週日 16:00 由 launchd 自動跑同一支（接在雲端週更之後，pull 恰好收到最新）。
安裝一次即可：

```bash
cp scripts/launchd/com.lin.nursing-local-update.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.lin.nursing-local-update.plist
```

- 看執行紀錄：`tail /tmp/nursing-local-update.log`
- 移除：`launchctl unload ~/Library/LaunchAgents/com.lin.nursing-local-update.plist && rm ~/Library/LaunchAgents/com.lin.nursing-local-update.plist`
- 排程時 Mac 只是睡眠會在喚醒後補跑；完全關機錯過不保證補跑，週一 watchdog 會亮紅提醒改按一鍵。
- twna 即時監看（方式三）為選配：另存後想「立刻」上站才需要；平常靠本節的週排程即可。

### 週一 09:00 失聯偵測

`.github/workflows/freshness-watchdog.yml` 每週一台北 09:00 執行
`scripts/check_freshness.py`。它只讀 repo 裡的 `data/status.json` 與 `data/manual_twna.json`，
不載入 parser、不連來源網站；jct/tnpa 與 twna 必須在剛開始的星期日更新週期內成功，否則
（含缺漏、格式錯誤或時間位於未來）Actions 會亮紅。也可在 Actions 頁手動 Run workflow。

### 本機更新失敗時

- **工作區髒檔**：訊息會列出非資料產物。先用 `git status` 確認，將自己的程式／文件改動 commit
  或暫存後再按一鍵；不要直接刪除不認得的檔案。
- **watchdog 過期**：先看本機 log 與 Actions。twna 請人工另存或按「本週已確認」；jct/tnpa
  則在住宅網路執行一鍵更新。不要用 proxy、偽裝 header 或把來源放回雲端。
- **push 遇到一般競速**：程式會自動做一次 `pull --rebase` 後重推。若 rebase 衝突，程式會 abort
  並通知，不會無限重試；用 `git status` 確認已無 rebase，再人工整合遠端變更後重跑。
- **log**：Finder/Dock 一鍵看 `~/Library/Logs/nursing-course-update.log`；launchd 排程看
  `/tmp/nursing-local-update.log`；提醒看 `/tmp/nursing-twna-reminder.log`。

## 出錯時你會看到什麼（刻意設計，不會靜默失敗）

| 情況 | 呈現 |
|---|---|
| 某來源抓失敗或 0 筆 | 頁首黃色橫幅＋頁尾警示徽章（含原因與最後成功日期）；該來源舊資料保留不清空 |
| 全部來源失敗 | 頁首紅色橫幅；Actions 亮紅（`status.py --check` exit 1）通知維護者；頁面照常發布 |
| 樣板壞掉、token 殘留 | build 直接報錯非零退出，不會發布半成品頁面 |

Actions 亮紅時：開 repo → Actions → 點該次執行看哪個來源失敗，通常是來源網站改版，
依上面 SOP 請 Claude Code 讀新版頁面修 parser 即可。

## 爬蟲禮貌守則（請遵守）

- 排程每週最多一次；手動測試時勿反覆狂打。
- 所有請求一律走 `base.download()`：內建 1 至 2.5 秒隨機延遲與表明身分的 User-Agent（請到 `SCRAPE["user_agent"]` 填上聯絡方式）。極少數老憑證網站改走 `base.download_curl()`（同樣完整驗證憑證，見該函式 docstring）；**禁止**用 verify=False 關閉憑證驗證。
- 只抓公開、免登入頁面；需登入的來源不爬，改人工維護。
- 每張活動卡保留回連原始報名頁，不轉載全文，資料著作權歸各學會。
- 新增來源前先看該站 `robots.txt`；被明確禁止就不要爬（實例：台灣護理學會，改手動維護）。
- 開發新 parser 時，對外實跑以 2 次為上限（偵察 1 次＋最終驗收 1 次），中間迭代一律餵本地快取檔，不重抓（2026-07-10 教訓：把驗收步驟也各自實跑會讓請求量翻倍破預算）。

## 專案結構

```
config/site.py           唯一設定檔（換學會改這裡）
scripts/sources/         來源 parser：base.py 共用工具、demo.py 離線示範、<code>.py 各學會
scripts/update.py        pipeline 入口（scrape → normalize → 寫檔 → build）
scripts/normalize.py     純函式：驗證、去重合併、時間窗
scripts/status.py        來源健康快照與 CI 閘門（--check）
scripts/build.py         樣板注入，產出 index.html
templates/index.html.tpl 版面樣板（改版面改這裡）
data/events.json         活動資料（單一事實來源，自動產生）
data/status.json         來源健康狀態（自動產生）
index.html               發布頁（自動產生，勿手改）
tests/                   離線測試（fixture 驅動，不連網）
.github/workflows/update.yml  每週自動更新流程
docs/ARCHITECTURE.md     逆向拆解報告與設計決策
```

## 授權

程式碼與樣板採 MIT 授權（見 LICENSE）。活動資訊著作權歸各主辦學會／單位所有。
