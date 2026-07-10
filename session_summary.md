# Session Summary — 2026-07-10

## 部署（已完成上線）

**網站上線**：https://healon.github.io/nursing-coursetw-lin/ （HTTP 200、137 筆課程、靜謐青主題）
- repo：`Healon/nursing-coursetw-lin`（public）；本機專案：`~/Projects/nursing-coursetw-lin`
  （＝外接 SSD `/Volumes/MAC SSD/dev/Projects/...`，Lin 確認在 SSD、暫不搬本機）。
- Pages：legacy branch 部署（main / root），status=built。
- **雲端每週自動更新已驗證可跑**：手動觸發首次 workflow → 結論 success，自動 commit
  `90ecbbb chore: weekly events update`（本機已 pull 同步）。cron 週日 07:00 UTC 之後自動執行。

**首次雲端跑暴露的來源問題（見 ~/.claude/rules/LESSONS.md L-2026-07-10-008）**：11 家中 9 家 ok，
但 **jct（醫策會）ConnectTimeout、tnpa（專科護理師）403**——本機（台灣家用 IP）都 ok，
GitHub Actions 機房 IP 被這兩站擋。設計正確運作：舊資料 merge 保留（jct 42／tnpa 8，總數
仍 137）、overall=partial 不擋站、頁面照發＋這兩家顯示黃色警示。
- **原本最擔心的 hospice 憑證在雲端過了**（curl 走系統信任清單，ubuntu 上 ok）。
- **後續選項（待 Lin 決定，非本次做）**：jct/tnpa 改「本機手動跑該來源＋push」半自動，
  或接受停在快照＋警示（三個月窗會逐漸把舊場次濾掉）。不建議掛 proxy 繞 IP 封鎖。

**待 Lin**：(1) jct/tnpa 雲端更新策略如上；(2) twna 自動監看 launchd 是否安裝
（plist 路徑已隨搬家更新為 ~/Projects/nursing-coursetw-lin）；(3) 是否搬本機（L-005 權限可克服，
搬家非必要，Lin 已知情選留 SSD）。

---

> 本檔含四段：客製第二三輪（前端細節／法規化積分／jct 月曆）、客製化（配色／地點規則／自動化）、
> 第二階段（接入 11 學會）、第一階段（模板骨架）。新內容在前。

---

## 客製第二、三輪（同日深夜，Lin 十項指示全數完成）

前端：日期改行內格式 2026/7/12（日）；類別（青）／地區（藍，原綠太近改）／來源（紫）三組
pill 各一色，卡片小標籤同色系；「線上」重複標籤修正（region=online 時不再畫第二顆，混合型保留）。

資料：新增「教學」類別（關鍵字置頂優先比對，8 筆自動歸類）；時間窗改 92 天（三個月）；
**積分依《醫事人員執業登記及繼續教育辦法》第 13 條四類建制**——CREDIT_TYPES＝專業(pro)／
品質(quality)／倫理(ethics)／法規(law)／專科護理師(np)，nuna 細項自動拆解（如 7.2 →
專業 1.8＋法規 5.4 兩徽章＋「含性別議題課程」提示，原始細項行刪除），存量遷移 33 筆改 key、
16 筆重解析，`grep '"nurse"' events.json`＝0。

jct 醫策會：v2 改抓活動月曆（純 GET 逐月串接三個月），5→42 筆；「禮貌上限外不丟課程」修正
（上限外以月曆資料收錄、詳情逐週補齊）；**數位課程／教學影片一律排除**（Lin 指示，含存量 4 筆
清除，「隨選」區隨之消失）。

驗證：pytest 161 passed；全站 137 筆；status ok；瀏覽器實測多類徽章／主題提示／三色標籤截圖。
自動化說明已答覆：週更跑 GitHub Actions 雲端（部署後啟用）、twna 監看為本機（待 Lin 同意安裝）。

---

## 客製化（同日晚間，Lin 三項指示）

1. **配色 RX Ⅱ 靜謐青**：THEME 換為 IBM Carbon teal 系（primary #007d79／dark #004144／accent 橙 #ba4e00；
   警示紅 #da1e28 為錯誤可見性用色不隨風格換）。三帖配色參考見 docs/palette/。瀏覽器實測漸層與徽章色值逐位正確。
2. **地點只留場館名**：新增 `base.simplify_location()`（一處生效全來源同步）。三種門牌形態安全去除
   （「地址：」尾段／括號含「號」／尾端縣市＋路街里村＋號），樓層如 (9F) 保留；顯示精簡但 region 推斷
   仍用原文（保住縣市線索）。存量 105 筆離線遷移 25 筆，全庫零殘留；9 個單元測試含澎湖鄉里式門牌實例。
3. **twna 自動化**：`scripts/twna_watch.py` 監看下載資料夾——Lin 只剩「瀏覽器另存」一個動作，之後
   辨識→匯入→去重→重建→桌面通知→歸檔全自動（合規不變：零對站請求）。launchd plist 備於
   scripts/launchd/（安裝指令見 README 方式三，尚未安裝、待 Lin 同意）。pytest 149 passed。

---

## 第二階段：接入 11 個學會教育訓練課程（同日下午）

### 結果總覽（`update.py --reset` 正式整合實跑，overall: ok，check exit 0）

| 學會 | 狀態 | 原始筆數 |
|---|---|---|
| 護理師護士公會全聯會（nuna） | ✅ 自動抓取 | 24 |
| 中華民國急重症護理學會（critical） | ✅ 自動抓取 | 10 |
| 中華民國精神衛生護理學會（psy） | ✅ 自動抓取 | 2 |
| 臺灣腎臟護理學會（tnna） | ✅ 自動抓取（詳情頁補積分） | 10 |
| 臺灣護理管理學會（tnma） | ✅ 自動抓取（簡章附件連結） | 50 |
| 台灣護理資訊學會（ni） | ✅ 自動抓取（v1 第一頁，截斷留痕） | 10 |
| 台灣醫療品質協會（ahqroc） | ✅ 自動抓取（二段式） | 8 |
| 醫策會（jct） | ✅ 自動抓取（首頁精選表；數位課程標 ondemand） | 5 |
| 台灣安寧緩和護理學會（hospice） | ✅ 自動抓取（Lin 提供帶參數 URL；download_curl 見下） | 5 |
| 台灣專科護理師學會（tnpa） | ✅ 自動抓取（Lin 提供 URL 證實免登入） | 11 |
| 台灣護理學會（twna） | ✅ 手動維護＋另存頁匯入器（robots 全站禁爬，零自動請求） | 42（快取頁匯入） |

頁面 105 筆（時間窗過濾後）。demo 已停用清空。pytest 135 passed。站名已依 Lin 指定改為
「護理教育訓練網站」（config SITE.title）。

**twna 日後更新方式**（README「方式二」，寫給非工程師）：瀏覽器開課程頁→另存新檔（僅 HTML）→
`scripts/import_twna_page.py <存檔路徑>` → `update.py --sources twna`。匯入器會去重、不覆蓋手改內容，
全程不對 twna 發網路請求。

### 重要決策紀錄
1. **twna robots.txt 全站 Disallow**：頁面公開但依守則不自動爬。Lin 決策改手動維護：
   `data/manual_twna.json`（scripts/sources/twna.py 只讀檔不連網），填入課程後 enabled 改 True。
2. **hospice TLS**：站方 TWCA 老式根憑證被 requests/OpenSSL 嚴格驗證拒收（診斷確認非資安
   事件）。裁決：新增 `base.download_curl()`（curl 走系統信任清單，完整驗證憑證），
   明文禁止 verify=False。
3. **tnpa robots 具名封鎖 AI 訓練爬蟲（含 ClaudeBot）但對一般 UA Allow**：本站以自有 UA
   做參考彙整（站方 Content-Signal 標 search=yes、use=reference），屬允許用途，已透明記錄。
4. **jct 深層列表有資料品質問題**（數位課程套裝把 1 筆報名炸成 10 列共用同一連結），
   改用首頁 5 列精選表；數位課程標 ondemand。

### 收尾階段修正（均有回歸測試或瀏覽器實測）
- 監控範圍＝enabled：停用來源不入健康快照與 overall（避免 twna/demo 造成黃橫幅常駐）。
- 頁尾 chips 與來源 pill 只顯示「enabled 或有資料」來源。
- 隨選數位課程獨立成組（不混月份分組、不誤標已結束、徽章「隨時可上」、日期塊顯示「數位課程」）。
- tnma ctext 條件化（有附件「詳見簡章附件」、無附件「請洽官方公告」）。

### 誠實記錄
- Wave 2 subagent 的 ahqroc（~40）與 jct（~31）開發請求超過 ≤20 預算一倍（驗收步驟重複
  實跑未用快取；延遲節流全程有效）。教訓記 LESSONS L-2026-07-10-006，README 補「實跑 2 次上限」。

### 待 Lin
1. **上線**：依 README 部署章節建 GitHub repo＋Pages＋每週自動更新（user_agent 記得填聯絡方式）。
2. （已解決）twna 課程：42 筆已由匯入器填入；站名已改「護理教育訓練網站」。

### 獨立審查（第二階段，已完成並修正）
判定「可交付、無阻斷項」＋3 功能缺失＋3 建議，全數修正（135 passed，含新增回歸測試）：
1. tnma 線上誤判：地點欄的「線上匯款」繳費備註把廈門實體論壇標成線上。修法：online 只看標題＋
   地點欄截掉「註：」後的備註（顯示也變乾淨）；順手把「北區/中區/南區/東區」加入 REGIONS 關鍵字
   （原本「北區-三軍總醫院」落未定其他）。
2. ni 地址截斷：右邊界用裸「活動」二字，遇「OO活動中心」場館名會切斷地址。修法：邊界改認具體
   欄位標籤。
3. 結構缺失靜默：六個新 parser 的「欄位整個不存在」分支無留痕（網站改版最常見的模式）。修法：
   逐檔補 stderr 留痕；tnna/jct 用防誤報設計（只對真異常示警，不對正常版面的按鈕連結/表頭刷噪音）。
4-6. 建議項：AC 檔 LESSONS 編號筆誤修正、ahqroc 死碼常數移除、README 提示語範本同步「實跑 2 次上限」。

---

## 第一階段：逆向拆解與模板骨架（同日上午）

## 本次做了什麼

逆向拆解 [Taiwan_Neurology](https://tlan1012.github.io/Taiwan_Neurology/) 學會活動彙整站，
建立一套「換一份設定檔就能套用到任何學會主題」的通用模板骨架，放在 `training-course/`。

### 逆向工程結論（證據見 docs/ARCHITECTURE.md）
- 參考站本質：零後端流水線 = GitHub Actions 週更 cron → Python 爬蟲爬公開活動頁 → 重產自包含
  單檔 index.html（資料內嵌）→ diff-gated commit → GitHub Pages 發布。無資料庫、無框架、無 API。
- 授權判斷：原站無 LICENSE（不複製其碼）；同作者 MIT 授權的 Taiwan_Nurse_CNT 架構更好，
  作為概念與結構參考，程式碼全部重新實作並通用化。

### 交付內容
- **config 驅動**：`config/site.py` 是唯一換主題開關（站名／配色／類別／積分別／地區／來源／爬蟲參數），
  純資料無邏輯，標籤只定義一處（修掉參考版標籤雙重定義問題）。
- **三層分離**：config（設定）／scripts（邏輯）／templates（版面）。HTML 樣板獨立，build 用 marker 注入。
- **前端功能**：搜尋、三組複選 pill 篩選、排序、月份分組、倒數天數、多積分別徽章、報名連結、
  加入 Google 行事曆（純前端組 URL）、頁尾來源統計。全部瀏覽器實測可操作。
- **錯誤可見性（四層）**：來源三態 ok／empty／error＋last_success；頁首橫幅＋頁尾警示徽章；
  CI 閘門 status.py --check 全滅時 exit 1；build 失敗必非零退出。三情境實測通過。
- **來源掛載**：demo（離線假資料）＋ nuna（護理師護士公會全聯會）＋ critical（急重症護理學會）
  三個來源，parser 拆 fetch()（連網）／parse()（純函式）兩層。
- **離線測試**：pytest 43 passed，全部 fixture 驅動不連網。
- **文件**：README（快速開始／GitHub Pages 部署／新增來源 SOP／Claude Code 提示語範本／
  爬蟲禮貌守則）＋ docs/ARCHITECTURE.md（完整拆解報告）＋ AC 檔。

### 驗證結果
- `pytest -q`：43 passed（離線）。
- `update.py --sources demo`：產出 events.json／status.json／index.html，瀏覽器實測搜尋／篩選／
  排序／月份分組／行事曆連結皆正常。
- 真實來源實跑（subagent 執行）：nuna ok 24 筆、critical ok 10 筆，overall ok，status --check exit 0。
- 錯誤可見性三情境：partial（頁首黃橫幅＋頁尾警示，check exit 0）、down（紅橫幅＋check exit 1，
  頁面照常發布）、正常（無橫幅，check exit 0）——全部符合設計。

## 未解問題／待 Lin 決定

1. **尚未部署**：本次刻意不建 GitHub repo、不 commit、不 push（計畫明確排除）。上線步驟已寫進
   README，待 Lin 執行。注意 `training-course/` 目前在父層 repo 中未追蹤。
2. **上線前要清 demo**：`config/site.py` 把 demo 的 enabled 改 False，跑 `update.py --reset`。
3. **主題仍是護理示範**：config 目前是護理主題示範。Lin 若要換其他學會，改 config 的 CATEGORIES／
   CREDIT_TYPES／SOURCES，並依 README SOP 新增對應 parser。
4. **status.count 與頁尾筆數語意不同**：status.json 記來源「抓取原始筆數」（nuna 24），頁尾 chip 顯示
   「進時間窗後筆數」（nuna 16）。審查判定與處理見下節。

## 下一步（建議順序）
1. 決定目標學會清單（護理沿用現狀，或換主題）。
2. 依 README「部署到 GitHub Pages」上線，手動觸發一次 workflow 確認綠燈。
3. 逐一新增想要的學會來源 parser（用 README 的 Claude Code 提示語範本）。

## 獨立審查結論（fresh-context subagent，已完成並修正）

判定「需修 3 項再交付」，其餘（XSS 逃逸、測試綠燈、AC 邊界、通用化宣稱）逐項查證無誤。三項全修：

1. **[阻斷] 靜默失敗漏洞**：來源健康狀態的 ok/empty 判定原本發生在資料驗證「之前」，只看 parser
   吐幾筆。若某學會改版、parser 抓到一堆格式壞掉的列，normalize 會默默全丟棄，頁面卻標該來源
   「正常」還把 last_success 刷新成今天——正是靜默失敗鐵則要擋的事。
   **修法**：新增 `status.finalize_outcomes()`，健康判定改用「通過欄位驗證的存活筆數」；抓到 >0
   但存活 0 → 顯性化為 error。加 6 個回歸測試＋端對端實測（error/count 0、last_success 保留
   2026-07-01、overall down）。改動：status.py、update.py、test_status.py。
2. **[功能缺失] critical 靜默丟棄**：詳情頁解析失敗與超過禮貌上限截斷都無留痕。補 stderr 警告
   （與 normalize 每次丟棄都 _warn 的一致性原則對齊）。改動：critical.py。
3. **[功能缺失／潛在 XSS] credits 值未逃逸**：樣板 credits 數值是唯一沒過 esc() 的欄位；活路徑
   因 float 轉型安全，但手改 events.json 後 rebuild 是文件允許的維運手段，故補防禦性逃逸。
   `esc()` 有 `String()` 包裹，對數字安全且輸出不變。改動：templates/index.html.tpl。

建議項處理：count 語意差異（status.json 記存活數 vs 頁尾 chip 記過窗後顯示數）已於
ARCHITECTURE.md 第4節與 status.py 檔頭文件化；AC 九項逐條驗證後補勾。問題7（demo enabled=False
≠移除）README／config 註解已涵蓋，判定不需程式面防呆。

**修正後最終驗證**：pytest 49 passed（含新回歸測試）、pipeline 重跑 overall ok、瀏覽器實測
credits 徽章正常（護理師 1.5 點／專科護理師 2 點）、真實護理活動正確渲染、status --check exit 0。
**結論：3 項全修，可交付。**
