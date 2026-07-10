# AC：學會活動彙整模板骨架（training-course-template）

- 日期：2026-07-10
- 任務性質：Implementation
- 計畫檔：`~/.claude/plans/https-tlan1012-github-io-taiwan-neurolog-radiant-pretzel.md`
- 目的：逆向拆解 https://tlan1012.github.io/Taiwan_Neurology/ 後，建立 config 驅動、本機可跑的通用「學會繼續教育活動彙整站」模板骨架。

## 驗收條件（四準則）

### AC-1 Observable（可觀察）
- [x] `python3 scripts/update.py --sources demo` 一條指令產出 `data/events.json`、`data/status.json`、`index.html` 三檔。
- [x] 瀏覽器開啟 index.html 後，關鍵字搜尋、三組 pill 複選篩選（類別／地區／來源）、排序切換、月份分組、「加入 Google 行事曆」按鈕皆可實際操作。（browser preview 實測，2026-07-10）

### AC-2 Measurable（可量測）
- [x] `pytest -q` 全綠，測試檔 ≥4 個（normalize／status／build／parsers）。（49 passed，含 finalize_outcomes 靜默失敗回歸測試）
- [x] demo 資料涵蓋 config 中全部類別、地區、積分別（每個枚舉值至少出現一次）。（test_parsers::test_covers_every_enum_value）
- [x] 刻意讓一個來源失敗重跑後：頁尾出現該來源警示徽章、`data/status.json` 記錄 error、`scripts/status.py --check` 在全滅情境 exit 1、非全滅情境 exit 0。（三情境實測，含「抓到但整批無效」）

### AC-3 Bounded（有邊界）
- [x] 只在 `training-course/` 內寫檔；不建 GitHub repo、不 commit、不 push、不動父層 repo 任何既有檔案。（父層 git status 顯示 training-course/ 為未追蹤）
- [x] 不引入資料庫、前端框架；執行期依賴僅 requests＋beautifulsoup4。

### AC-4 Testable（可測試）
- [x] 所有 pytest 測試不連網（fixture 驅動）。
- [x] 產出的 index.html 無殘留樣板 token（`@@...@@`）與注入占位字樣。（grep 驗證 0 命中）

## 驗證指令

```bash
cd "/Volumes/MAC SSD/claude code/project/training-course"
python3.13 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
python3 scripts/update.py --sources demo && ls -la data/ index.html
pytest -q
python3 scripts/status.py --check; echo "exit=$?"
```
