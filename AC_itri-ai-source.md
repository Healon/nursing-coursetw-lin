# AC — 新增工研院產業學院 AI 課程來源（itri）＋「智慧科技」分類

> 需求（Lin 2026-07-18）：把 https://college.itri.org.tw/ 的 AI 相關課程依本專案規則加進彙整站，
> 分類多一個「智慧科技」。2026-07-18 完成並逐條驗收。
> 前提假設（照 §3 小任務先列假設繼續，已依此實作，請 Lin 確認）：
> 1. 只收「AI 相關」課程：取站方自己的「人工智慧」分類資料夾（LessonList?FolderGUIDs=41098C03-…），
>    不自行用關鍵字撈全站；要擴大範圍改 config 的 FolderGUIDs 參數即可。
> 2. 比照 jct 決策（2026-07-10 Lin 指示）：只收有排定日期的實體／直播場次，
>    開課日期「進行中」的雲端教室自學課不收錄（實測 83 筆中 8 筆屬此，已略過並留痕）。
> 3. 「智慧科技」＝新分類代碼 `tech`；research 既有的「智慧／數位／資訊」關鍵字移入 tech，
>    順序放 teaching 之後、clinical 之前（特定性高者優先）。既有課程含這些字者由
>    「研究學術／臨床照護／行政管理／病人安全」改判「智慧科技」。

## AC-1 Observable（可觀察）
- [x] `update.py --sources itri` 實跑後 status.json 的 itri status=ok 且 count>0。（2026-07-18 實跑：
      ok、75 筆；92 天時間窗過濾後 64 筆併入 data/events.json，日期 2026-07-22 至 2026-10-16）
- [x] 頁面出現「智慧科技」類別 pill 與「工研院產業學院」來源 pill，可篩出對應卡片。（瀏覽器實測
      127.0.0.1:8123：點智慧科技 pill 篩出 65 筆／共 159 筆＝64 itri＋1 twna，與 events.json 一致；
      卡片含類別徽章、地區、時數 ctext、來源徽章）
- [x] itri 事件的 cat 全部為 tech；卡片連結可點回 college.itri.org.tw 原課程頁。（events.json 逐筆
      驗證 cat 全 tech；url 全為 https://college.itri.org.tw/Lesson/LessonData/<GUID> 絕對網址）

## AC-2 Measurable（可量測）
- [x] pytest 全綠（230 passed，含新增 11 個 itri 測試＋5 個分類優先序測試，零回歸）。
- [x] 偵察＋開發總請求：對外共 5 次連線（偵察 3 GET：robots／首頁／列表頁；驗收段 1 次 TLS 交握
      失敗未成請求＋1 GET 成功），≤20 預算內；實跑 2 次（偵察 1＋最終驗收 1），中間迭代全部
      餵本地快取（scratchpad/itri-cache/）。誠實備註：驗收第一次實跑因 requests 憑證驗證失敗
      （見下）改 download_curl 後重跑一次，多消耗 1 次連線嘗試。
- [x] config note 含驗證日期＋實測筆數（2026-07-18、83 筆／收 75 筆排定場次）。
- [x] 既有 events.json 標題重跑 infer_category 逐筆檢視：13 筆改判 tech 全數合理（數位醫療病安、
      智慧醫療、AI 實戰、護理資訊、重症智慧化等）；「AI」子字串無 TRAINING／PAIN 型誤中
      （全大寫英文詞掃描：0 命中；含 AI 但無中文科技詞的 6 筆全是真 AI 課程，其中臨床教師
      系列 4 筆因 teaching 優先序正確留在教學類）。

## AC-3 Bounded（有邊界）
- [x] robots.txt 已查：不存在（回自訂錯誤頁），依專案慣例（ahqroc 前例）視為未限制。只抓公開
      免登入頁；不 POST、不用瀏覽器自動化。
- [x] 未改 scripts/sources/base.py（infer_category 行為不動，只動 config 資料；下載層沿用既有
      download_curl，未新增函式）。
- [x] 不動其他來源 parser；版面樣板不動（分類 pill 資料驅動自動出現）。
      例外（範圍內的資料修正）：data/manual_twna.json 42 筆中 40 筆機器推斷的 cat 依新規則
      就地重算（3 筆改判 tech），2 筆 stored 值與機器推斷不符（疑人工設定）保留不動並回報。

## AC-4 Testable（可測試）
- [x] itri 測試全部離線 fixture 驅動（tests/fixtures/itri_list.html＝真實頁面裁剪 8 筆代表列，
      含「進行中」排除案例；表格消失時 raise 不靜默的回歸測試）。
- [x] 分類移轉有測試（tests/test_base.py TestInferCategoryTechPriority）：智慧／數位／資訊標題
      判 tech；臨床教師＋AI 標題仍判 teaching；純研究、純臨床標題不受影響。
- [x] demo 來源 test_covers_every_enum_value 因資料驅動自動涵蓋 tech，維持綠燈。

## 交付後待辦（非本次範圍，需人工確認）
- [ ] 首次雲端排程（2026-07-19 週日 15:00）跑完核對 itri 是否被 GitHub 機房 IP 擋
      （LESSONS L-2026-07-10-008）。被擋的完整修法是三處，缺一 itri 會靜默停更：
      (1) config/site.py 該來源 execution 改 "local"；(2) scripts/local_update.py 的
      LOCAL_SOURCES 加 "itri"；(3) scripts/check_freshness.py 的 LOCAL_SOURCES 加 "itri"
      （後兩者為寫死清單，不讀 config 的 execution 欄）。
- [ ] 既有來源 10 筆含智慧科技關鍵字的課程（jct 1／tnpa 2／psy 1／ni 1／tnma 3／critical 2），
      將於 2026-07-19 各來源重抓時自動改判 tech，週日後可抽查。
