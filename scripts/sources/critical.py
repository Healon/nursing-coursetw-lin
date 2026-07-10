"""Purpose: critical（台灣急重症護理學會 TACCN）來源 parser —— 活動列表頁＋詳情頁二段式。
Input:  base.download() 取得的列表頁與各詳情頁 HTML（皆公開免登入）。
Output: fetch() -> list[dict]；parse_list()／parse_detail() 為純函式，
        供 tests/fixtures/critical_list.html 與 critical_detail.html 離線測試使用。

頁面結構（2026-07-10 實測）：
- 列表頁 https://www.taccn.org.tw/activity/list/2：每筆活動為一個
  <a href="https://www.taccn.org.tw/activity/detail/<id>?category_id=2">標題</a>，
  但只列出「日期＋標題」，沒有積分，需進入詳情頁才有。
- 詳情頁 https://www.taccn.org.tw/activity/detail/<id>：頁首有結構化資訊區塊，
  依序為「時間 YYYY-MM-DD」「地點 ...」「費用 ...」「對象 ...」
  「護理人員積分 X.0」「專科護理師積分 Y.0」，日期已是西元 YYYY-MM-DD（非民國），
  故不需 ROC 轉換。標題採用列表頁的錨點文字（詳情頁標題會與課程簡介文字混在一起，
  不易乾淨切出），url 採用不含 query string 的正規化網址（實測可直接存取）。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bs4 import BeautifulSoup

from scripts.sources import base

LIST_URL = "https://www.taccn.org.tw/activity/list/2"
DETAIL_URL_TMPL = "https://www.taccn.org.tw/activity/detail/{id}"

# 詳情頁最多抓取頁數（禮貌上限，見任務規格）
MAX_DETAIL_PAGES = 12

_DETAIL_ID_RE = re.compile(r"/activity/detail/(\d+)")
_DATE_RE = re.compile(r"時間\s*(\d{4}-\d{2}-\d{2})")
_LOCATION_RE = re.compile(r"地點\s*(.+?)\s*費用")
_NURSE_CREDIT_RE = re.compile(r"護理人員積分\s*([\d.]+)")
_NP_CREDIT_RE = re.compile(r"專科護理師積分\s*([\d.]+)")
_ONLINE_RE = re.compile(r"線上|直播|視訊|遠距|webinar", re.IGNORECASE)


def _is_online(text: str) -> bool:
    """依標題＋地點文字關鍵字判斷是否為線上／視訊活動（純字面判斷，非語意理解）。"""
    return bool(_ONLINE_RE.search(text))


def parse_list(html: str) -> list[dict]:
    """從活動列表頁解析候選活動的 (id, title, url)；純函式、不連網。

    只認得含 /activity/detail/<id> 的連結；標題長度 < 6 的一律濾掉
    （濾掉導覽列／麵包屑等短詞連結，例如「更多」）。同一 id 若有多個連結
    （版面重複渲染同一張卡片），只保留第一次出現的標題。
    """
    soup = BeautifulSoup(html, "html.parser")
    seen: dict[str, dict] = {}
    for a in soup.find_all("a", href=True):
        m = _DETAIL_ID_RE.search(a["href"])
        if not m:
            continue
        aid = m.group(1)
        if aid in seen:
            continue
        title = " ".join(a.get_text().split())
        if len(title) < 6:
            continue
        seen[aid] = {"id": aid, "title": title, "url": DETAIL_URL_TMPL.format(id=aid)}
    return list(seen.values())


def parse_detail(html: str) -> dict | None:
    """從活動詳情頁解析 (date, location, credits)；純函式、不連網。

    找不到日期視為此頁無法使用（例如頁面結構改版或活動已下架），回傳 None，
    由呼叫端（fetch）決定如何處理，不在此拋例外中斷整體抓取。
    """
    soup = BeautifulSoup(html, "html.parser")
    body_text = " ".join(soup.get_text().split())

    date_m = _DATE_RE.search(body_text)
    if not date_m:
        return None

    loc_m = _LOCATION_RE.search(body_text)
    location = loc_m.group(1).strip() if loc_m else ""

    credits: dict[str, float] = {}
    nurse_m = _NURSE_CREDIT_RE.search(body_text)
    if nurse_m and float(nurse_m.group(1)) > 0:
        credits["pro"] = float(nurse_m.group(1))
    np_m = _NP_CREDIT_RE.search(body_text)
    if np_m and float(np_m.group(1)) > 0:
        credits["np"] = float(np_m.group(1))

    return {"date": date_m.group(1), "location": location, "credits": credits}


def fetch() -> list[dict]:
    list_html = base.download(LIST_URL)
    all_candidates = parse_list(list_html)
    candidates = all_candidates[:MAX_DETAIL_PAGES]
    if len(all_candidates) > MAX_DETAIL_PAGES:
        # 截斷不可無聲：超過禮貌上限的候選被捨棄時要留痕，避免維護者以為全抓了
        print(
            f"[critical] 列表 {len(all_candidates)} 筆，禮貌上限只取前 {MAX_DETAIL_PAGES} 筆詳情頁",
            file=sys.stderr,
        )

    events: list[dict] = []
    failed = 0
    for cand in candidates:
        detail_html = base.download(cand["url"])
        detail = parse_detail(detail_html)
        if detail is None:
            # 單筆詳情解析失敗不可無聲丟棄（與 normalize 每次丟棄都 _warn 的一致性原則相同）
            failed += 1
            print(f"[critical] id={cand['id']} 詳情頁無法解析，已跳過：{cand['url']}", file=sys.stderr)
            continue
        online = _is_online(f"{cand['title']} {detail['location']}")
        events.append(
            base.make_event(
                date=detail["date"],
                title=cand["title"],
                url=cand["url"],
                location=detail["location"],
                credits=detail["credits"],
                online=online,
            )
        )
    if failed:
        print(f"[critical] 共 {failed} 筆詳情頁解析失敗（列表 {len(candidates)} 筆）", file=sys.stderr)
    return events
