# AC：本機更新死結修復（P0 止血＋P1 根治）

> 日期：2026-09-27
> 背景：2026-08-16 twna-watch 匯入另存頁後只重建不 commit，留下未提交的衍生產物；
> 之後每天 local_update 在 `git pull --ff-only` 被拒（雲端每日改同一批檔），
> jct／tnpa／twna 停在 8/15 至 8/16，watchdog 連紅 40 天。

## 資料分類（本次設計核心）

| 類別 | 檔案 | 性質 | 同步前處理 |
|---|---|---|---|
| 原始資料 | `data/manual_twna.json` | 人工投入、只存在本機、雲端永不改寫 | 保留 |
| 衍生產物 | `data/events.json`、`data/status.json`、`index.html` | 可由原始資料＋爬取結果重建 | 還原成已提交版本，之後重建 |

## 驗收條件

1. **Observable**：在「衍生產物未提交＋雲端有新 commit」的狀態下，`local_update.sync_with_cloud()` 成功 fast-forward；`manual_twna.json` 的未提交修改原樣保留；衍生產物等於雲端版本。
2. **Measurable**：`pytest -q` 全綠。新增的整合測試用暫存 git repo 重現 8/16 狀態，且測試內含負對照：同一狀態下直接 `git pull --ff-only` 必須失敗（證明測試真的重現了死結）。
3. **Bounded**：只改 `scripts/local_update.py`、`scripts/twna_watch.py`、對應測試與 README／AUTOMATION 的相關段落。不動通知管道、log 路徑、psy、排程時間與架構（P2 至 P5 另案）。
4. **Testable**（P0 實跑）：修復版 local_update 實跑後，origin/main 的 `status.json` 中 jct 與 tnpa 的 `last_success` 為 2026-09-27；8/16 匯入的 3 筆 twna 課程出現在 `events.json`；本機 `git status` 乾淨且與 origin 同步。

## 不處理（明列）

- twna 的新鮮度：最近一次人工匯入是 8/16，watchdog 對 twna 仍會亮紅，需 Lin 另存課程頁或按「本週已確認」。不可用程式時間假裝人工檢查。
- 本機有「未推送的 commit」時 `pull --ff-only` 仍會失敗（例如推送因網路中斷）。此情況維持中止並通知，不自動 rebase 或 reset。

## 驗收結果（2026-09-27 00:52 實跑）

| 條件 | 結果 | 證據 |
|---|---|---|
| 1 Observable | 通過 | `TestSyncWithCloud::test_recovers_from_uncommitted_derived_artifacts` |
| 2 Measurable | 通過 | `pytest -q` 250 passed；負對照在 fixture 內直接 pull 確實失敗；變異驗證（拿掉還原步驟、拿掉 twna 重建）兩條新測試皆報紅 |
| 3 Bounded | 通過 | commit `eceb97c` 只含 local_update、twna_watch、兩支測試、README、AUTOMATION 與本檔 |
| 4 Testable | 通過，附一項修正 | origin 的 jct、tnpa `last_success` 為 2026-09-27；本機與 origin 同步、工作區乾淨；線上 Pages 已建置 `3dd625e` |

條件 4 的修正：8/16 匯入的 3 筆 twna 課程中，2026-09-04 與 2026-09-12 兩場已超過 `keep_past_days`（7 天），由時間窗依設計濾除；2026-10-17 那場已上站。原寫「3 筆都出現在 events.json」在 9/27 已不可能成立，以本表為準。

未解（屬預期）：`check_freshness.py` 對 twna 仍 exit 1（最近人工匯入 2026-08-16），需 Lin 另存課程頁或按「本週已確認」。
