# 拆解報告：Taiwan_Neurology 逆向工程與本模板設計決策

- 日期：2026-07-10
- 逆向對象：https://tlan1012.github.io/Taiwan_Neurology/ （及其公開 repo `TLAN1012/Taiwan_Neurology`）
- 架構參考：同作者 MIT 授權的 `TLAN1012/Taiwan_Nurse_CNT`
- 本模板定位：把上述做法通用化成「換一份設定檔就能套用到任何學會主題」的可重用骨架

---

## 1. 參考站的本質（逆向工程結論）

Taiwan_Neurology 看起來像有後台的資料庫網站，實際上是一條**零後端的靜態流水線**：

```
GitHub Actions cron（每週日 07:00 UTC＝台北 15:00）
  → 一支 Python 爬蟲（純標準庫＋系統 curl，53KB 單檔）
  → 爬 13 個神經科相關學會網站的公開活動頁
  → 去重、分類、正規化
  → 重新產生「自包含單檔 index.html」：約 200 筆活動直接內嵌成 const EVENTS = [...]
  → 有變更才自動 commit push（內建 GITHUB_TOKEN，permissions: contents: write）
  → GitHub Pages（legacy branch 部署：main 分支根目錄）自動重建發布
```

關鍵觀察（皆經網站實測與 repo 原始碼佐證）：

- 前端零框架、零第三方庫、零打包工具、零追蹤碼；一個 `<style>`、一個 `<script>` 包辦全部。
- 沒有資料庫、沒有 API、沒有獨立 JSON：資料就寫死在 HTML 內，每次更新整頁重產。
- 搜尋、排序、三組複選篩選、月份分組、倒數天數、積分徽章、「加入 Google 行事曆」
  （純前端組 `calendar.google.com/calendar/render` URL 參數，不呼叫任何 API）全部在瀏覽器記憶體內完成。
- 所謂「後台」就是 GitHub Actions 的排程任務。維運成本為零，仰賴的服務只有 GitHub。

同作者後來把同一套做法套到護理領域（`Taiwan_Nurse_CNT`，2026-07 建立），並在該版做了兩個重要演進：
程式拆模組（sources／scrape／build／update）、資料改存獨立 `data/events.json`、credits 改為物件支援多積分別。
本模板以該演進版為基底再通用化。

### 授權判斷（決定了實作策略）

| repo | 授權 | 對本模板的意義 |
|---|---|---|
| Taiwan_Neurology | 無 LICENSE（預設保留著作權） | 只取「做法與功能設計」概念，不複製其程式碼 |
| Taiwan_Nurse_CNT | MIT（README 聲明僅涵蓋程式碼） | 架構與頁面結構知識可參考；本模板程式仍為重新實作 |

活動資料的著作權歸各學會，彙整站只列摘要欄位並回連原始報名頁。

## 2. 參考站 vs 本模板對照

| 面向 | Taiwan_Neurology 原版 | 本模板 |
|---|---|---|
| 程式結構 | 單檔 53KB 爬蟲，HTML 以 Python 字串樣板硬編在程式裡 | 設定（config）／邏輯（scripts）／版面（templates）三層分離 |
| 主題設定 | 學會清單、類別、積分寫死在程式與 HTML 兩處 | `config/site.py` 單一事實來源，標籤只定義一處 |
| 資料存放 | 直接寫回 index.html | `data/events.json` 為單一事實來源，index.html 是 build 產物 |
| 積分 | 單一數字 | `credits` 物件，支援多積分別（沿用 Nurse_CNT 的刻意延伸） |
| 依賴 | 零 pip 依賴（標準庫＋curl） | requests＋beautifulsoup4（換取解析可讀性；demo 與測試仍零網路） |
| 來源失敗 | 頁尾筆數可觀察，無顯式警示 | 三態健康快照＋頁首橫幅＋頁尾警示徽章＋CI 亮紅（見第 4 節） |
| 測試 | 無 | pytest 離線測試（normalize／status／build／parsers，fixture 驅動） |
| 部署 | GitHub Pages legacy branch 部署 | 相同（main 分支根目錄），另加 `.nojekyll` |

## 3. 資料層設計

### 事件 schema（`data/events.json` 內 `events[]` 每筆）

| 欄位 | 型別 | 說明 |
|---|---|---|
| `date` | str `YYYY-MM-DD` | 活動起始日 |
| `title` | str | 標題（必填，空白摺疊） |
| `location` | str | 地點文字，可空 |
| `credits` | dict | 積分別代碼→點數，只留 >0；可為 `{}`（積分依公告） |
| `cat` | enum | 類別代碼，必在 `CATEGORIES`，否則落 `other` 並警告 |
| `src` | enum | 來源代碼（registry 統一補上），必在 `SOURCES` |
| `online` | bool | 是否線上活動 |
| `ondemand` | bool | 線上隨選（不受時間窗限制） |
| `region` | enum | 地區代碼，必在 `REGIONS`，否則落 `tbd` 並警告 |
| `ctext` | str | 積分細項或備註，可空 |
| `url` | str | 原始報名／詳情連結（必填） |

### 去重與合併（`scripts/normalize.py`）

- 去重鍵：`(date, src, 去空白標題)`；同鍵時本次爬到的新資料覆蓋舊資料。
- **舊資料永不在 merge 階段刪除**：單一來源暫時掛掉不可清空它的歷史，過期淘汰交給時間窗。
- 時間窗：保留「今天 − keep_past_days」到「今天 ＋ window_days」；`ondemand` 不受限。
- 來源自 config 移除時，其活動於下次更新被淘汰（附警告）。

### 已知取捨（刻意接受並記錄）

1. 學會「主動撤下」的活動會殘留到過期為止（merge 不刪除的代價）。發生率低，可手動改 events.json 後 rebuild。
2. 活動改標題會產生新去重鍵，舊筆殘留到過期（同上處理）。
3. `ondemand` 活動因不受時間窗限制，需靠來源端消失＋手動清理退場。
4. 排序的中文 tie-break 用 Unicode 碼位非注音／筆畫 collation：只影響同日同來源多活動的顯示順序，不影響正確性。

## 4. 錯誤可見性設計（本模板的最高優先原則）

原則：**資料流斷裂必須有可見的錯誤狀態，禁止靜默通過。** 機制分四層：

1. **來源三態**（`data/status.json`）：`ok`（有資料通過驗證）／`empty`（成功但 0 筆：最危險的
   靜默失敗態，多半是網站改版讓選擇器失效卻沒丟例外，照樣警示）／`error`（下載或解析例外，
   **或抓到 >0 筆但整批無法通過欄位驗證**）。`last_success` 只在 ok 時刷新，讓「壞多久了」可追溯。

   健康判定用「通過 normalize 欄位驗證的存活筆數」而非 parser 原始抓取數
   （`scripts/status.py::finalize_outcomes`）。理由：若某來源改版讓 parser 抓到一堆
   格式壞掉的列，原始筆數會是非零、看似正常，但 normalize 會把它們全部丟棄——用存活數
   判定，這種「抓到卻整批無效」的靜默失敗會被顯性化成 error，不會蒙混成 ok 還刷新 last_success。

   **count 的分母**（避免對照兩檔時誤判）：`status.json` 的 `count` 是「通過欄位驗證的存活
   筆數」（時間窗過濾之前）；頁尾 chip 顯示的是「頁面實際呈現筆數」（時間窗過濾之後）。
   兩者可能不同（例如某來源 count=24 但頁面只顯示 16，差額是已過時間窗、暫不顯示的活動）。
   刻意用過濾前的數字做健康判斷，才不會把「活動單純過了時間窗」誤判成 parser 壞掉。
2. **頁面呈現**：overall 非 ok 時頁首出現橫幅（partial 黃／down 紅）；頁尾對每個非 ok 來源
   顯示警示徽章（原因＋最後成功日期或「從未成功」）；頁尾統計恆常列出所有來源筆數（含 0 筆）。
3. **CI 閘門**（`scripts/status.py --check`）：overall=down（全部來源 error，或完全沒有狀態）
   時 exit 1，讓 GitHub Actions 亮紅通知維護者。partial 不亮紅（靠頁面警示），避免警報疲乏。
4. **build 失敗必吵**：marker 缺漏、token 殘留一律 raise 非零退出，不發布半成品頁面。

### workflow 步驟順序是刻意設計（`.github/workflows/update.yml`）

```
① update.py       來源失敗恆常 exit 0（失敗進 status，不擋發布）
② diff-gated commit  有變更才 commit push → Pages 重建
③ status.py --check  唯一允許讓 job 亮紅的步驟
```

把 ③ 放在 ② 之後，保證「全滅」當週：警示頁照樣發布（使用者看得到紅色橫幅與過時提醒），
紅燈只拿來通知維護者，不會反過來把警示資訊擋在門外。
「來源失敗」與「系統失敗」被解耦：update.py 若因樣板等系統問題 crash，①就非零退出，同樣亮紅。

## 5. 通用化設計決策

- **`config/site.py` 用 Python dict 而非 YAML／JSON**：零額外依賴、可寫繁中註解、
  Claude Code 可直接讀懂並代改。全部純資料無邏輯，維護者只碰這一檔。
- **標籤單一定義**：Nurse_CNT 把來源／積分／類別標籤同時寫在 HTML 與 Python 兩處，改一處會漏另一處；
  本模板一律由 config 經 build 注入，HTML 內零手寫標籤。
- **樣板獨立成檔**：`templates/index.html.tpl` 用四個 marker 區塊（THEME／CONFIG／STATUS／EVENTS）
  ＋文字 token 注入。regex 置換用函式回呼，避免 payload 內反斜線被誤解析（有回歸測試）。
  JSON 內 `</` 轉義為 `<\/`，防止事件內容提前關閉 `<script>`（有測試）。前端渲染一律經 `esc()` 逃逸，
  爬回來的文字視為不可信輸入。
- **來源掛載介面**：每來源一檔，`fetch()`（連網）與 `parse()`（純函式）分離，fixture 即可離線測試。
  registry 逐來源 try/except 隔離，一家失敗不拖垮全部。`download()` 內建隨機延遲與表明身分的 UA。
- **demo 來源**：離線假資料產生器，涵蓋全部枚舉值組合。用途：模板展示、pipeline 冒煙測試、
  前端每個 pill 都有卡片可驗。上線前關閉並 `--reset` 清除。

## 6. 逐檔職責

| 檔案 | 職責 |
|---|---|
| `config/site.py` | 唯一設定檔：站名、配色、類別、積分別、地區、來源、爬蟲參數 |
| `scripts/sources/__init__.py` | registry：依 config 動態載入 parser、逐來源錯誤隔離、補 `src` 欄位 |
| `scripts/sources/base.py` | `download`（禮貌抓取，失敗必 raise）、`infer_region`／`infer_category`、`make_event` |
| `scripts/sources/demo.py` | 離線示範來源 |
| `scripts/sources/<code>.py` | 各學會 parser：`fetch()`＋純函式 `parse()` |
| `scripts/normalize.py` | schema 強制、去重合併、時間窗、排序（皆純函式） |
| `scripts/status.py` | 健康快照計算與存取、CI 閘門 `--check` |
| `scripts/build.py` | marker 注入樣板 → `index.html`；任何注入異常 raise |
| `scripts/update.py` | pipeline 入口與失敗語意的實作（來源失敗不退出、系統失敗必退出） |
| `scripts/scrape.py` | 除錯用 CLI：單獨跑某來源看結果，不動資料檔 |
| `templates/index.html.tpl` | 版面與前端互動（搜尋／篩選／排序／月份分組／行事曆連結／警示呈現） |
| `.github/workflows/update.yml` | 每週排程：update → diff-gated commit → status --check |

## 7. 沿用與捨棄的參考站行為

沿用：整體流水線形態、單檔自包含發布頁、全部前端功能、週更頻率、回連原始報名頁的資料姿態。
捨棄／改良：HTML 內嵌資料改為獨立 JSON、單檔爬蟲改模組化、標籤雙重定義改單一來源、
無警示改四層錯誤可見性、無測試改離線測試套件。

## 8. 給下一位維護者

- 換學會主題：只改 `config/site.py`＋新增 `scripts/sources/<code>.py`。README 有 SOP 與
  請 Claude Code 代寫 parser 的提示語範本。
- 來源網站改版時：Actions 亮紅或頁尾出現警示 → 重抓一份頁面存 fixture → 修 `parse()` → 測試綠 → push。
- 不要手改 `index.html`（會被下次 build 覆蓋）；版面改 `templates/index.html.tpl`。
