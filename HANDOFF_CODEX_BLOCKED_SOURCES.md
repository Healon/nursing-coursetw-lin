# HANDOFF — 三個「無法雲端自動抓取」的來源(交給 Codex)

> 建立時間:2026-07-13。用途:把 twna / jct / tnpa 這三個來源的處理現況與可改善方向交給 Codex。
> 讀這份的你沒有先前對話脈絡。專案整體架構請先讀 `README.md` 與 `docs/ARCHITECTURE.md`,本文件不重複。
> **先看「守則禁區」一節再動手**——這三家的難點正是最容易誘使人違規繞過的地方。

---

## TL;DR:這三家「已經有完整解法在跑」,不是待解 bug

| 來源 | 為何無法雲端自動抓 | 現行解法(已上線) |
|---|---|---|
| 台灣護理學會 twna(act.e-twna.org.tw) | robots.txt 全站 `Disallow: /` | 零請求。維護者瀏覽器另存頁 → `scripts/import_twna_page.py` 匯入 → `data/manual_twna.json`。另有 `scripts/twna_watch.py` 資料夾監看(launchd)。**無自動抓取路徑,且不該有。** |
| 醫策會 jct | GitHub Actions 機房 IP 連線逾時(僅雲端被擋,台灣住宅 IP 可抓) | 雲端照跑會失敗標黃;真資料由 `scripts/local_update.py`(住宅 IP)補抓後 push。 |
| 專科護理師學會 tnpa | GitHub Actions 機房 IP 回 403(同上) | 同 jct,`local_update.py` 補抓。 |

判定依據見 `~/.claude/rules/LESSONS.md` L-2026-07-10-008(雲端機房 IP 被台灣機構站擋)。

**所以 Codex 的工作不是「讓它們在雲端爬起來」——那條路守則明文禁止(見下)。** 這份 handoff 的目的是
(1) 讓你完整理解現狀、不要重造現成輪子或誤刪,(2) 若 Lin 要「減少對本機補抓的依賴」,指出唯一合規的架構槓桿。

---

## 守則禁區(硬性,違反即為錯誤產出,先讀)

以下全部**禁止**,不因「只是想讓它動起來」而放寬:

1. ❌ **掛 proxy / 住宅代理 / 輪替 IP** 去繞 jct、tnpa 的機房 IP 封鎖。
2. ❌ **偽裝 User-Agent / 竄改 header / 重放 cookie** 去騙過 403 或封鎖。本專案 UA 一律表明身分(含 repo URL)。
3. ❌ **對 act.e-twna.org.tw(twna)發出任何自動化請求**。它 robots 全站禁爬,`scripts/sources/twna.py` 檔頭與 `import_twna_page.py` 檔頭都寫明合規背景,零網路請求是刻意設計,不可「順手加個 fetch」。
4. ❌ **`verify=False`**。憑證問題用 `scripts/sources/base.py` 的 `download_curl()`(系統信任清單,完整驗證),不是關閉驗證。
5. ❌ **開發期反覆連網實跑**。爬蟲禮貌預算:每個 parser 對外實跑上限 2 次(偵察 1 + 驗收 1),中間餵本地快取;排程每週最多一次,測試勿狂打。

以上不是建議,是這個專案的身分姿態(守 robots、標明身分、不遊走灰色地帶)。Codex 若判斷「繞過就能解決」,正確反應是**停下並回報**,不是動手。

---

## 現行機制的關鍵檔案(改動前務必先讀,別重造)

- `scripts/local_update.py` — 本機一鍵/launchd 週日 16:00。流程:工作區保護 → `git pull --ff-only`(先收雲端週更)→ 掃 `~/Downloads` 匯入 twna 另存頁 → 補抓 jct+tnpa(住宅 IP,含「當日已成功則跳過」護欄,`--force` 強制)→ 健康檢查 → diff-gated commit+push → 桌面通知。`LOCAL_SOURCES = ("jct", "tnpa")`。
- `scripts/import_twna_page.py` — twna 另存頁 → `data/manual_twna.json`,零網路請求。合併規則:去重鍵 `(date, 去空白 title)`,**不覆蓋**維護者手動修過的既有條目。
- `scripts/twna_watch.py` — 資料夾監看(方式三,launchd `com.lin.twna-watch.plist`),另存後即時匯入。
- `scripts/sources/twna.py` — twna 的「來源模組」,但只讀 `data/manual_twna.json`,不連網(檔頭有合規說明)。
- `.github/workflows/update.yml` — 雲端週日 07:00 UTC(台北 15:00),跑**所有 enabled 來源**(含 jct/tnpa,失敗標黃不擋發布)。
- `scripts/launchd/` — `com.lin.nursing-local-update.plist`、`com.lin.twna-watch.plist`。
- `config/site.py` — 各來源 `enabled` 與 `note`(jct/tnpa/twna 的 note 已寫明被擋原因與解法)。
- README.md:78-88(手動維護來源)、142-174(twna 匯入方式二/三)、202-225(本機週更 local_update)。

---

## 可做的事(合規範圍內,依 Lin 指定範圍再動手)

> 這三家「抓得更用力」不會有進展。以下是真正能改善的方向,**動手前先跟 Lin 確認要做哪一項**。

### 選項 A(唯一能消除本機補抓依賴的架構槓桿):jct/tnpa 改用 self-hosted runner
在 Lin 的 Mac(住宅 IP)架一台 GitHub Actions self-hosted runner,讓 jct/tnpa 的更新在「住宅 IP 的 runner」上跑,名正言順走 CI、免掉 `local_update.py` 手動/launchd 補抓那半套。
- 做法輪廓:新增一個只在 self-hosted runner 上跑的 workflow(`runs-on: self-hosted`),`--sources jct,tnpa`;現有雲端 workflow 可改為排除這兩家(或維持嘗試、標黃)。
- 權衡(必須在提案裡誠實列出):Mac 要開機在線;self-hosted runner 的安全性(不要對 public repo 開放 fork PR 觸發);與現有 launchd 方案功能重疊,要決定「取代」還是「並存」,不要兩套都跑造成重複 commit。
- **這是提案+討論題,不是直接動手題**:先寫一頁權衡給 Lin 決定,再實作。

### 選項 B:本機排程的「失聯偵測」
`local_update.py` 靠 launchd 週日 16:00;若 Mac 那天沒開機就整週沒更新,目前不會有人知道。可加「距上次成功 local_update 超過 N 天就桌面通知/在頁尾標記」的 staleness 偵測。純加值,不碰抓取邏輯。

### 選項 C:twna 匯入流程的人因改善
twna 只能手動另存(robots),但「另存→匯入」這段可更省事(例如匯入器對常見另存變體更寬容、錯誤訊息更明確)。**範圍僅限本機檔案解析,絕不加任何對 twna 的網路請求。**

---

## 驗收與驗證(不論做哪一項)

```bash
cd "/Volumes/MAC SSD/dev/Projects/nursing-coursetw-lin"
.venv/bin/python -m pytest -q                         # 全離線測試須全綠
.venv/bin/python scripts/update.py --sources jct,tnpa # 本機(住宅 IP)驗 jct/tnpa 可抓
.venv/bin/python scripts/local_update.py --no-push    # 演練本機更新不推送
grep -rn "verify=False" scripts/                       # 應零命中(只在 base.py 註解出現)
```
- 任何「抓取健康」宣稱都要有實際輸出佐證(status.py 的三態、頁尾徽章),不接受形容詞。
- 若改動 workflow / launchd,要說明「取代或並存」,並確認不會產生重複 commit 或雙重抓取。

## 明確不在範圍(Out of scope)

- 讓 twna 自動抓取(robots 禁,永遠手動)。
- 用任何技術手段繞 jct/tnpa 的機房 IP 封鎖(proxy、偽裝、輪替 IP)。
- 為了「省事」引入 verify=False 或關閉任何憑證/robots 檢查。

## Suggested skills(給接手的 agent)

- `systematic-debugging`:若 jct/tnpa 本機也抓不到了(非雲端封鎖,是網站改版),先 4-phase 根因再改 parser。
- `verification-before-completion`:宣稱「改好了」前,跑上面的驗證指令取實證。
- `brainstorming`:選項 A(self-hosted runner)屬架構決策,先釐清需求與權衡再實作,別直接開工。

## 環境備忘

- 專案:`/Volumes/MAC SSD/dev/Projects/nursing-coursetw-lin`
- 全域守則:`~/.claude/CLAUDE.md`、`~/.claude/rules/LESSONS.md`(尤其 L-2026-07-10-008 雲端 IP 封鎖、L-2026-07-10-007 TWCA 憑證)。
- Codex 專用記憶已有 `AGENTS.md`? 本專案根目錄目前無 AGENTS.md;若 Codex 需要,可比照 course-scraper 的做法從 CLAUDE.md 鏡像一份(此為選配,非本任務必需)。
