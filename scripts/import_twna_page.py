"""Purpose: CLI — 把維護者手動另存到本機的 twna 課程列表頁 HTML，匯入 data/manual_twna.json。
Input:  一個命令列參數：另存的 .html 檔案絕對或相對路徑（本機檔案，非 URL）。
Output: 覆寫 data/manual_twna.json（新解析事件與既有內容合併去重後寫回）；stdout 印出
        「新增 N 筆、略過重複 M 筆、解析失敗 K 筆」摘要。

合規背景（重要，勿刪）：act.e-twna.org.tw 的 robots.txt 全站 Disallow（見
scripts/sources/twna.py 檔頭），本專案對該站不發出任何自動化請求。本工具全程零網路請求：
輸入是「維護者本人用瀏覽器開課程頁、手動另存新檔到本機」之後的靜態 HTML 檔案，這裡只做
本機檔案的讀取與解析，把「開瀏覽器另存」這個人類動作之後的重複粗工（複製貼上、手動比對
去重）自動化，不涉及任何抓取行為。

用法：
    .venv/bin/python scripts/import_twna_page.py <另存的.html>

合併規則（不覆蓋人工修過的內容）：去重鍵為 (date, 去空白 title)。已存在於
data/manual_twna.json 的條目一律保留原樣——即使這次解析出同一筆活動，也不會用剛解析的版本
覆蓋掉 Lin 可能手動修過的欄位（例如手動核實過的 credits 或 region）；只有全新的鍵才會被
新增進去。
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bs4 import BeautifulSoup

from scripts import twna_freshness
from scripts.sources import twna

DEFAULT_COMMENT = (
    "台灣護理學會（twna）robots.txt 全站禁爬，手動維護；"
    "由 scripts/import_twna_page.py 另存頁匯入器建立與更新，見 README「手動維護來源」一節。"
)


def _dedupe_key(ev: dict) -> tuple[str, str]:
    """去重鍵：(日期, 去空白標題)。manual_twna.json 的條目本身不帶 src 欄位，故只用這兩者。"""
    return (str(ev.get("date", "")), "".join(str(ev.get("title", "")).split()))


def merge_events(existing: list[dict], parsed: list[dict]) -> tuple[list[dict], int, int]:
    """合併新解析事件與既有清單；既有條目保留、不被覆蓋。純函式，不觸碰任何檔案。

    回傳 (合併後清單, 新增筆數, 略過重複筆數)。既有清單的順序與內容原樣保留在前，
    新增的事件附加在後面，方便 diff 時一眼看出這次匯入新增了什麼。
    """
    keys = {_dedupe_key(ev) for ev in existing}
    merged = list(existing)
    added = 0
    skipped_dupe = 0
    for ev in parsed:
        key = _dedupe_key(ev)
        if key in keys:
            skipped_dupe += 1
            continue
        merged.append(ev)
        keys.add(key)
        added += 1
    return merged, added, skipped_dupe


def run(html_path: Path, data_path: Path, *, now: dt.datetime | None = None) -> dict:
    """核心邏輯（純函式化，供 CLI 與測試共用，I/O 範圍限定在傳入的兩個路徑，不碰任何全域路徑）。

    html_path 不存在 -> raise FileNotFoundError（呼叫端決定如何呈現；CLI 轉成 exit 1）。
    回傳統計 dict：{"added": 新增筆數, "skipped_dupe": 略過重複筆數, "failed": 解析失敗筆數}。
    """
    if not html_path.exists():
        raise FileNotFoundError(f"找不到另存的課程頁檔案：{html_path}")

    html = html_path.read_text(encoding="utf-8")
    if BeautifulSoup(html, "html.parser").find(
        "table", id="ctl00_ContentPlaceHolder1_GridView1"
    ) is None:
        raise ValueError("不是有效的 twna 課程列表另存頁：找不到課程表格")

    # parse_saved_page 對單列缺日期/標題的問題列印 stderr（見該函式 docstring），這裡暫時
    # 接住以便算出「解析失敗 K 筆」的摘要數字，接完仍原樣轉印到真正的 stderr——不吞掉診斷訊息。
    capture = io.StringIO()
    with contextlib.redirect_stderr(capture):
        parsed = twna.parse_saved_page(html)
    skip_log = capture.getvalue()
    if skip_log:
        sys.stderr.write(skip_log)
    failed = len([line for line in skip_log.splitlines() if line.strip()])

    if data_path.exists():
        raw = json.loads(data_path.read_text(encoding="utf-8"))
    else:
        raw = {"comment": DEFAULT_COMMENT, "events": []}
    existing = raw.get("events", [])

    merged, added, skipped_dupe = merge_events(existing, parsed)
    raw["events"] = merged
    twna_freshness.mark_imported(raw, now or dt.datetime.now().astimezone())

    twna_freshness.write_json_atomic(data_path, raw)

    return {"added": added, "skipped_dupe": skipped_dupe, "failed": failed}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="把另存到本機的 twna 課程列表頁 HTML 匯入 data/manual_twna.json（零網路請求）"
    )
    parser.add_argument("saved_html", help="維護者用瀏覽器另存新檔的課程列表頁 .html 路徑")
    args = parser.parse_args(argv)

    try:
        stats = run(Path(args.saved_html), twna.DATA_PATH)
    except (FileNotFoundError, ValueError) as exc:
        print(f"[import_twna_page] {exc}", file=sys.stderr)
        return 1

    print(
        f"[import_twna_page] 新增 {stats['added']} 筆、"
        f"略過重複 {stats['skipped_dupe']} 筆、"
        f"解析失敗 {stats['failed']} 筆"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
