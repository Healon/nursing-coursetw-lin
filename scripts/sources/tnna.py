"""Purpose: tnna（臺灣腎臟護理學會）來源 parser —— 活動列表頁＋詳情頁二段式（仿 critical.py）。
Input:  base.download() 取得的列表頁與各詳情頁 HTML（study_content.asp?WC_ID=，皆公開免登入）。
Output: fetch() -> list[dict]；parse_list()／parse_detail() 為純函式，
        供 tests/fixtures/tnna_list.html 與 tnna_detail.html 離線測試使用。

頁面結構（2026-07-10 實測）：
- 列表頁 https://www.tnna.org.tw/home/study_list.asp：每筆活動為一張卡片
  <a href="study_content.asp?WC_ID=<id>" class="block p-6"><h3>標題</h3>...
  <span>舉辦日期：YYYY/M/D</span>...<span class="truncate">地點</span>...</a>。
  與 critical.py 不同的是，列表頁本身已含日期（西元，非民國）與地點，不必等詳情頁才知道；
  只有「積分」需要進詳情頁才拿得到，因此本 parser 的日期／地點一律採用列表頁資料，詳情頁
  只用來補積分，這點與 critical.py（date/location 皆來自詳情頁）刻意不同，請勿誤改一致。
- 詳情頁 study_content.asp?WC_ID=<id>：右側「積分資訊」區塊固定用 <div class="p-3 ..."> 包
  每一種積分，實測含兩類：「衛生署繼續教育課程積分」（如「專業課程 3 積分」-> credits={"pro":3}）
  與「公務人員終身學習時數」（如「3 小時」，非本站 CREDIT_TYPES 涵蓋的單位，原文存入 ctext）。
  兩類彼此獨立存在，任一缺席都合理（並非每場都申請兩種認證），找不到不視為解析失敗。

詳情抓取上限 12 頁（MAX_DETAIL_PAGES 慣例，仿 critical.py）；列表超過上限時 stderr 留痕
「已截斷」。為省請求，候選日期已超過「今天 7 天前」的一律跳過詳情頁抓取（積分留空，但事件本身
仍輸出——日期/地點/標題早已從列表頁拿到，跳過詳情頁只影響積分完整度，不影響事件本身可用性，
時間窗淘汰交給 normalize.window_filter 處理，這裡只是單純的請求節流）。
"""
from __future__ import annotations

import datetime as dt
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bs4 import BeautifulSoup

from scripts.sources import base

LIST_URL = "https://www.tnna.org.tw/home/study_list.asp"

MAX_DETAIL_PAGES = 12
STALE_DAYS = 7

_WC_ID_RE = re.compile(r"WC_ID=(\d+)")
_LIST_DATE_RE = re.compile(r"舉辦日期[：:]\s*(\d{4})/(\d{1,2})/(\d{1,2})")
_CREDIT_POINT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*積分")
_LIFELONG_HOUR_RE = re.compile(r"(\d+(?:\.\d+)?)\s*小時")
_ONLINE_RE = re.compile(r"線上|直播|視訊|遠距|webinar", re.IGNORECASE)


def _is_online(text: str) -> bool:
    """依標題＋地點文字關鍵字判斷是否為線上／視訊活動（純字面判斷，非語意理解）。"""
    return bool(_ONLINE_RE.search(text))


def parse_list(html: str) -> list[dict]:
    """從活動列表頁解析候選活動的 (id, title, date, location, url)；純函式、不連網。

    只認得 href 含 study_content.asp?WC_ID=<id> 的卡片錨點；卡片內找不到 <h3> 標題或
    「舉辦日期」的一律跳過（結構不符預期，非本站要處理的資料列）。同一 id 只留第一次出現。
    """
    soup = BeautifulSoup(html, "html.parser")
    seen: set[str] = set()
    no_h3: set[str] = set()  # 出現過「無 h3 的 WC_ID 連結」的 id（可能只是卡片旁的按鈕連結）
    candidates: list[dict] = []
    for a in soup.find_all("a", href=True):
        m = _WC_ID_RE.search(a["href"])
        if not m:
            continue
        wc_id = m.group(1)
        if wc_id in seen:
            continue
        h3 = a.find("h3")
        if h3 is None:
            no_h3.add(wc_id)
            continue
        card_text = " ".join(a.get_text(separator=" ").split())
        date_m = _LIST_DATE_RE.search(card_text)
        if not date_m:
            print(f"[tnna] WC_ID={wc_id} 卡片找不到舉辦日期，已跳過整筆：{h3.get_text()[:30]}", file=sys.stderr)
            continue
        seen.add(wc_id)
        y, mo, d = (int(x) for x in date_m.groups())
        loc_span = a.select_one("span.truncate")
        candidates.append(
            {
                "id": wc_id,
                "title": " ".join(h3.get_text().split()),
                "date": dt.date(y, mo, d).isoformat(),
                "location": " ".join(loc_span.get_text().split()) if loc_span else "",
                "url": urljoin(LIST_URL, a["href"]),
            }
        )
    # 結構缺失不可無聲，但要避免誤報：只有「從頭到尾都沒出現正常卡片」的 WC_ID 才示警
    # （卡片旁的純文字按鈕連結也會指向同一 WC_ID，那是正常版面，不叫）
    ghost = no_h3 - seen
    if ghost:
        print(
            f"[tnna] {len(ghost)} 個 WC_ID 只有連結、找不到對應的 h3 標題卡片，疑網站改版：{sorted(ghost)[:5]}",
            file=sys.stderr,
        )
    return candidates


def parse_detail(html: str) -> dict:
    """從活動詳情頁解析 (credits, ctext)；純函式、不連網。

    「積分資訊」區塊固定用 <div class="p-3 ..."> 逐項列出（與報名費區塊的 <li class="p-3 ...">
    標籤不同，find_all("div", class_="p-3") 天然只會取到積分項目）。找不到任何積分項目時回傳
    空 credits／ctext，這是合理狀態（該場次未申請對應認證），不是解析失敗。
    """
    soup = BeautifulSoup(html, "html.parser")
    credits: dict[str, float] = {}
    ctext_parts: list[str] = []
    for div in soup.find_all("div", class_="p-3"):
        text = " ".join(div.get_text().split())
        if "終身學習" in text:
            m = _LIFELONG_HOUR_RE.search(text)
            if m and float(m.group(1)) > 0:
                ctext_parts.append(f"公務人員終身學習時數 {m.group(1)} 小時")
        elif "積分" in text:
            m = _CREDIT_POINT_RE.search(text)
            if m and float(m.group(1)) > 0:
                credits["pro"] = float(m.group(1))
    return {"credits": credits, "ctext": "；".join(ctext_parts)}


def fetch() -> list[dict]:
    list_html = base.download(LIST_URL)
    all_candidates = parse_list(list_html)
    candidates = all_candidates[:MAX_DETAIL_PAGES]
    if len(all_candidates) > MAX_DETAIL_PAGES:
        print(
            f"[tnna] 列表 {len(all_candidates)} 筆，禮貌上限只取前 {MAX_DETAIL_PAGES} 筆候選（已截斷）",
            file=sys.stderr,
        )

    stale_floor = dt.date.today() - dt.timedelta(days=STALE_DAYS)

    events: list[dict] = []
    skipped_stale = 0
    for cand in candidates:
        credits: dict[str, float] = {}
        ctext = ""
        if dt.date.fromisoformat(cand["date"]) < stale_floor:
            skipped_stale += 1
        else:
            detail_html = base.download(cand["url"])
            detail = parse_detail(detail_html)
            credits, ctext = detail["credits"], detail["ctext"]
        events.append(
            base.make_event(
                date=cand["date"],
                title=cand["title"],
                url=cand["url"],
                location=cand["location"],
                credits=credits,
                online=_is_online(f"{cand['title']} {cand['location']}"),
                ctext=ctext,
            )
        )
    if skipped_stale:
        print(
            f"[tnna] {skipped_stale} 筆候選日期已超過 {STALE_DAYS} 天，為省請求跳過詳情頁（積分留空）",
            file=sys.stderr,
        )
    return events
