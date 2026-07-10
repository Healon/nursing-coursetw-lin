# AC — 積分制度依《醫事人員執業登記及繼續教育辦法》第 13 條四類建制

> 計畫：Lin 已核准（見任務派工訊息，2026-07-10）。
> 法規依據：law.moj.gov.tw L0020181 第13條（已查證）——護理人員六年 120 點；四類＝專業課程／
> 專業品質／專業倫理／專業相關法規；品質＋倫理＋法規合計至少 12 點（超過 24 以 24 計），
> 應含感染管制與性別議題課程。專科護理師（np）學分為另一套制度，不受本次變更影響。
> 追加範圍（同日併入，Lin 經協調 agent 追加）：醫策會（jct）數位課程／教學影片一律排除不收錄。

## AC-1 Observable（可觀察）
- [x] `config/site.py` CREDIT_TYPES 改為 pro/quality/ethics/law/np 五碼，label 對應 專業/品質/倫理/法規/專科護理師。
- [x] `nuna._parse_credit_cell` 回傳型態改為 `(credits: dict, ctext: str)`，可拆解「專業/品質/倫理/法規」四類與括號主題（性別／感染）。
- [x] 存量 `data/events.json` 全部 `credits` key 由 nurse 改 pro；nuna 來源事件重新以新版邏輯解析其積分細項。
- [x] jct 來源不再產生任何「數位課程／教學影片」事件；`_ONDEMAND_RE` 語意由「標記」改為「排除」（見 `_exclude_ondemand`）。

## AC-2 Measurable（可量測）
- [x] `.venv/bin/python -m pytest -q` 全綠（基準 156 -> 161，含 5 個新測試：nuna 3 個＋jct 2 個）。
- [x] `grep -c '"nurse"' data/events.json` 為 0。
- [x] `grep -c '"pro"' index.html` > 0（實測：34 次出現）。
- [x] 遷移統計輸出：nurse→pro 33 筆、nuna 重解析 16 筆（其中多類拆解 7 筆）、jct 排除數位課程 4 筆。

## AC-3 Bounded（有邊界）
- [x] 零網路請求：全程用既有 fixture 與存量 data/events.json 驗證，未對任何學會網站發請求。
- [x] 未修改 `scripts/normalize.py`、`scripts/status.py`、`scripts/update.py`、`templates/index.html.tpl`。
- [x] 未變動 `ahqroc.py`（quality）與 `tnpa.py`（np）既有對映。
- [x] 未 commit／未 push（git status 確認 training-course/ 仍為未追蹤目錄，無提交動作）。
- [x] 一次性遷移腳本落 scratchpad（`migrate_credit_types.py`），未進 repo。

## AC-4 Testable（可測試）
- [x] test_parsers.py 所有 `{"nurse": ...}` 斷言改 `{"pro": ...}`（critical/tnna/hospice 共 7 處；另 twna 測試樣本資料 4 處一併修正避免因 CREDIT_TYPES 改名而被 normalize 判為 bogus key）。
- [x] nuna 新增 3 測試：單一專業（真實 fixture 列）、加總不符退回防呆＋stderr 留痕（合成字串）、感染主題提示（合成字串）。
- [x] jct 新增 2 測試：數位課程候選被排除、不出現在結果＋排除留痕的 stderr 斷言；另補一個「無命中時靜默不留痕」的對照測試。
- [x] 遷移後：`data/events.json` 與 build 後 `index.html` 皆確認不存在任何 src=jct 且標題含「數位課程/教學影片」的事件；ondemand=true 事件數為 0，樣板「隨選數位課程」區因空清單自然不渲染（`if (ondemand.length)`，未改樣板）。
- [x] 抽查一筆「7.2」nuna 事件（2026-07-23 北區）：credits=={"pro":1.8,"law":5.4}，ctext=="含性別議題課程"，與規格完全相符。
