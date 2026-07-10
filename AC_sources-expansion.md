# AC — 接入 Lin 指定的 11 學會教育訓練課程（第二階段）

> 計畫：~/.claude/plans/https-tlan1012-github-io-taiwan-neurolog-radiant-pretzel.md（2026-07-10 Lin 核准）
> 決策紀錄：抓不到的來源由 Lin 提供網址再實測；確認鎖登入者 enabled=False＋note 回報，絕不做登入爬取。

## AC-1 Observable（可觀察）
- [x] `update.py` 實跑後，status.json 中 11 家裡 ≥7 家 status=ok 且 count>0。（最終 11/11 ok：nuna 24／critical 10／psy 2／tnna 10／tnma 50／ni 10／ahqroc 8／jct 5／hospice 5／tnpa 11／twna 42。twna 為 robots 全站禁爬，依 Lin 決策走手動維護＋另存頁匯入器，零自動請求；2026-07-10 實跑）
- [x] 頁面來源 pill 與頁尾統計出現新學會，卡片可依新來源篩選。（瀏覽器實測：10 家 pill 齊、點「醫策會」篩出 5 筆、頁尾 chips 與各源筆數一致）

## AC-2 Measurable（可量測）
- [x] pytest 全綠，每個實作來源 ≥3 個 fixture 測試。（122 passed；psy 6／tnna 5／tnma 6／ni 4／tnpa／ahqroc／jct／hospice／twna 合計 38，全部 ≥3）
- [x] 每來源 config note 含驗證日期＋實測筆數。
- [x] dev 請求量每站 ≤20 GET，超過需誠實標記。（psy 7／tnna 15／tnma 3／ni 8／tnpa ~6／hospice ~8 皆在預算內；**ahqroc ~40、jct ~31 超標一倍，subagent 已誠實標記**：根因為驗收步驟重複實跑未用快取，延遲節流全程有效無爆打；教訓記入 LESSONS L-2026-07-10-006，README 禮貌守則補「實跑 2 次上限」條）

## AC-3 Bounded（有邊界）
- [x] 不登入爬取、不 POST、不用瀏覽器自動化爬資料。（twna robots 禁爬→手動維護；jctlearning 登入平台排除）
- [x] 不 commit／push／部署。（父層 git status：training-course/ 仍為未追蹤目錄）
- [x] 不解析 PDF（tnma v1 界線：url 連簡章附件、ctext 依有無附件條件註記）。

## AC-4 Testable（可測試）
- [x] 所有 parser 測試離線 fixture 驅動（不連網；download_curl 測試用 file:// URL）。
- [x] 民國日期轉西元有邊界測試（roc_date_to_iso 11 個：跨年、單位數月日、西元不誤吃、非日期回 None）。
- [x] 「抓到但整批無效」由既有 finalize_outcomes 回歸測試守護。

## 追加驗收（收尾階段補強，均有回歸測試或瀏覽器實測）
- [x] 停用來源不入健康快照與 overall（監控範圍＝enabled；twna／demo 不再造成黃橫幅常駐）。
- [x] 頁尾 chips 與來源 pill 只顯示「enabled 或有資料」的來源（示範資料 0 筆噪音已除）。
- [x] 隨選數位課程獨立成組（不混入月份分組、不誤標已結束、徽章顯示「隨時可上」）。
