# HANDOFF — 護理教育訓練網站（2026-07-10 收工交接）

> 給下一個 session 的 agent：先讀這份，再視需要讀 `session_summary.md`（完整開發歷程）。
> **下次對話請直接在本資料夾開**：`~/Projects/nursing-coursetw-lin`
> （此路徑是指向外接 SSD `/Volumes/MAC SSD/dev/Projects/nursing-coursetw-lin` 的捷徑，同一份資料；
> 捷徑勿刪，本機自動更新與 Lin 的其他專案都靠它。）

## 專案是什麼

Lin（護理長）的個人彙整站：把 11 個學會的護理繼續教育課程自動彙整成單頁靜態網站。
逆向自 Taiwan_Neurology、參考 MIT 授權之 Taiwan_Nurse_CNT 通用化重寫。

- **正式網站**：https://healon.github.io/nursing-coursetw-lin/
- **GitHub repo**：`Healon/nursing-coursetw-lin`（public，Pages＝main 分支 root）
- 現況：**已上線、已全自動化**。117 筆課程、pytest 170 passed、健康檢查 ok。

## 目前的自動化架構（已全部驗證可跑）

| 時間（台北） | 誰 | 做什麼 |
|---|---|---|
| 週日 15:00 | GitHub Actions（雲端） | 爬 9 家可雲端爬的學會 → 自動 commit push → Pages 更新 |
| 週日 16:00 | launchd `com.lin.nursing-local-update`（本機，已安裝） | 跑 `scripts/local_update.py`：pull 收雲端 → 掃 ~/Downloads 匯入 twna 另存頁 → 補爬 jct/tnpa（僅台灣住宅 IP 爬得到，見 LESSONS L-2026-07-10-008）→ commit push |
| 隨時手動 | 一鍵指令 | `.venv/bin/python scripts/local_update.py`（同一支程式；`--force` 跳過當日護欄） |

twna（台灣護理學會）robots 全站禁爬：Lin 用瀏覽器另存課程頁到「下載」資料夾即可，其餘全自動。
twna「即時」監看（com.lin.twna-watch.plist）**未安裝**（功能已被週排程涵蓋，Lin 要即時再裝）。

## 下次對話可能要處理的事

1. **真排程二次確認**（最重要）：下週日（2026-07-12）後檢查兩個排程是否真的自動跑了——
   `gh run list` 看雲端；`tail /tmp/nursing-local-update.log` 看本機；網站頁尾 jct/tnpa 筆數應刷新。
   特別注意 launchd 下的 git push 憑證（keychain）本輪未實測到（當時無變更），失敗會有桌面通知。
2. **舊空殼可刪**：`/Volumes/MAC SSD/claude code/project/training-course` 只剩 `.claude/launch.json`
   （上一 session 的預覽橋接），整個資料夾可刪。刪除類動作先跟 Lin 確認。
3. **選配（Lin 尚未決定）**：去函醫策會/專科護理師學會請求白名單（合規正道，可擬信稿）；
   twna 即時監看安裝；「離島」地區分類（金門/連江課程目前視訊場歸線上、實體會落未定其他）。

## 關鍵慣例（動手前必知）

- **唯一設定檔** `config/site.py`：站名/配色（RX Ⅱ 靜謐青）/類別/積分別/地區/來源/排除規則全在此。
- **積分四類**依《醫事人員執業登記及繼續教育辦法》第 13 條：pro 專業／quality 品質／ethics 倫理／
  law 法規＋np 專科護理師。nuna 細項自動拆解（含性別/感染主題提示）。
- **jct 排除規則兩層**：config `exclude_title_keywords`（數位課程/教學影片/觀摩活動，加詞免改程式）
  ＋程式內語意規則（標題含醫師/中醫→看詳情頁學分認可，無護理積分＝專屬排除）。
- **公開頁不顯示來源錯誤**（Lin 指示）：維護者錯誤可見性走 Actions 紅燈＋桌面通知＋status.json；
  頁面只有中性「更新至日期」註記與全滅紅橫幅。
- **爬蟲禮貌**（README 守則）：只 GET、守 robots、每站 dev ≤20 請求、**實跑 2 次上限**（偵察1＋驗收1，
  迭代餵快取）、禁 verify=False、禁 proxy 繞封鎖。
- 測試：`.venv/bin/python -m pytest -q`（全離線，fixture 驅動）。改動後必跑。
- RWD 已完成（375/768/1440 實測 1/2/3 欄）。
- 新增來源照 README「新增一個學會來源（SOP）」與內建提示語範本。

## 參考文件（不重複內容，按需讀取）

- `session_summary.md`——當日完整歷程（部署/客製三輪/審查修正）
- `README.md`——維運手冊（本機更新/部署/禮貌守則/twna 三種方式）
- `docs/ARCHITECTURE.md`——逆向拆解報告與設計決策
- `AC_*.md` 三份——各階段驗收清單
- `~/.claude/rules/LESSONS.md` L-2026-07-10-002/006/007/008——本專案沉澱的四條通用教訓
- 計畫檔（歷輪核准紀錄）：`~/.claude/plans/https-tlan1012-github-io-taiwan-neurolog-radiant-pretzel.md`

## Suggested skills（下一個 agent 視情境調用）

- `dual-machine-sync`——Lin 換 MacBook Air 工作時（MBA 端 `git clone` 到 ~/Projects 即可）
- `systematic-debugging`——任何來源突然 error/empty 時（多半是網站改版，照 README SOP 修 parser）
- `verification-before-completion`——宣稱完成前一律實跑驗證（本專案鐵則）
- `brainstorming`——若 Lin 要開新功能（如訂閱通知、行事曆匯出檔）

（維護註記：本檔為一次性交接快照，內容以 session_summary 與 README 為準；過時可直接刪除重寫。）
