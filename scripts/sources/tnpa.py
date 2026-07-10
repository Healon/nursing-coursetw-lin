"""Purpose: tnpa（台灣專科護理師學會）來源 parser —— 「所有活動」列表單頁解析（不需詳情頁）。
Input:  base.download(URL) 取得的 HTML（events__list 卡片式列表，免登入伺服器渲染）。
Output: fetch() -> list[dict]；parse(html) 為純函式，供 tests/fixtures/tnpa_list.html 離線測試使用。

robots.txt 判定（2026-07-10 實測 https://www.tnpa.org.tw/robots.txt）：Cloudflare 代管區塊對
`User-agent: *` 給 `Content-Signal: search=yes,ai-train=no,use=reference` 並 `Allow: /`；
另有第二個 `user-agent: *` 區塊只 disallow 管理／會員／附件等後台路徑（/manage/、/member/、
/upload 等），/events/ 不在其中。本專案 UA（society-events-aggregator，見 config.SCRAPE）
不是被逐一點名 disallow 的具名 AI 爬蟲（GPTBot／ClaudeBot／CCBot／Bytespider 等），落在通用
`User-agent: *` 群組，故 /events/ 對本專案允許。

頁面結構（2026-07-10 實測 https://www.tnpa.org.tw/events/，「實體課程／所有活動」頁，
11 筆活動、無分頁標記）：每筆活動為 <li class="event__item">，內含
<span class="event__type">（活動形式，如「教育訓練課程」「線上直播-醫護專業」）／
<h3 class="event__title"><a class="event__link" href="content.php?id=NNN&...">標題</a></h3>／
<div class="event__date">YYYY/MM/DD (週幾) 起始時間 ~ 結束時間</div>（西元日期，非民國）／
<div class="event__place">活動地點：...</div>（"活動地點：" 為固定標籤前綴，解析時剝除）／
<div class="event__score"><strong>N.N</strong> 積點</div>。

積分對映（判斷依據見任務規格「積分對映：實際讀 event__score 內容決定」）：本站 event__score
只標「積點」，未像 critical/tnna 的詳情頁那樣區分「護理人員積分」與「專科護理師積分」兩種
label。本學會全稱即為「台灣專科護理師學會」（Taiwan Association of Nurse Practitioners），
其自辦與掛名協辦活動之積點性質對應本站 CREDIT_TYPES 的 "np"（專科護理師），故固定映射
{"np": 分數}；若 event__score 區塊有文字但抽不出正數（目前 11 筆實測皆有乾淨數字，此為防禦
分支），數字留空、原文放入 ctext，不臆測積分數字。

is_online 判斷除標題／地點關鍵字外，額外併入 event__type 文字（如「線上直播-醫護專業」本身
就含「線上」），三者合併判斷更穩定。
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

URL = "https://www.tnpa.org.tw/events/"

_DATE_RE = re.compile(r"(\d{4})/(\d{1,2})/(\d{1,2})")
_SCORE_NUM_RE = re.compile(r"[\d.]+")
_PLACE_LABEL_RE = re.compile(r"^活動地點[:：]\s*")
_ONLINE_RE = re.compile(r"線上|直播|視訊|遠距|webinar", re.IGNORECASE)


def _is_online(text: str) -> bool:
    """依活動形式＋標題＋地點文字關鍵字判斷是否為線上／視訊活動（純字面判斷，非語意理解）。"""
    return bool(_ONLINE_RE.search(text))


def parse(html: str) -> list[dict]:
    """解析「所有活動」列表頁；純函式、不連網。

    以 <li class="event__item"> 精準定位每筆活動（非全頁掃 <a>），故不需要像
    critical/psy/tnna 那樣用標題長度或關鍵字過濾導覽雜訊；仍以 href 做防禦性去重，
    避免版面重複渲染同一張卡片時重複計入（目前 fixture 未見此情況，純防禦）。
    """
    soup = BeautifulSoup(html, "html.parser")
    events: list[dict] = []
    seen: set[str] = set()
    for li in soup.find_all("li", class_="event__item"):
        a = li.select_one("h3.event__title a.event__link")
        if a is None:
            # event__item 是資料容器，缺標題連結＝結構缺失，不可無聲（多半是網站改版）
            print(f"[tnpa] event__item 缺標題連結，已跳過：{li.get_text(strip=True)[:30]}", file=sys.stderr)
            continue
        title = " ".join(a.get_text().split())
        href = a.get("href", "").strip()
        if not title or not href:
            print(f"[tnpa] 標題或連結為空，已跳過：{(title or href)[:40]}", file=sys.stderr)
            continue
        if href in seen:
            continue
        seen.add(href)
        url = urljoin(URL, href)

        date_div = li.select_one("div.event__date")
        date_text = date_div.get_text(" ", strip=True) if date_div else ""
        date_m = _DATE_RE.search(date_text)
        if not date_m:
            print(f"[tnpa] 找不到可用日期，已跳過：{title[:30]}", file=sys.stderr)
            continue
        y, mo, d = (int(x) for x in date_m.groups())
        try:
            date_iso = dt.date(y, mo, d).isoformat()
        except ValueError:
            print(f"[tnpa] 日期不合法 {date_m.group()}，已跳過：{title[:30]}", file=sys.stderr)
            continue

        place_div = li.select_one("div.event__place")
        location = _PLACE_LABEL_RE.sub("", place_div.get_text(" ", strip=True)) if place_div else ""

        type_span = li.select_one("span.event__type")
        event_type = type_span.get_text(strip=True) if type_span else ""

        credits: dict[str, float] = {}
        ctext = ""
        score_div = li.select_one("div.event__score")
        if score_div is not None:
            score_text = score_div.get_text(" ", strip=True)
            num_m = _SCORE_NUM_RE.search(score_text)
            if num_m and float(num_m.group()) > 0:
                credits = {"np": float(num_m.group())}
            elif score_text:
                ctext = score_text

        events.append(
            base.make_event(
                date=date_iso,
                title=title,
                url=url,
                location=location,
                credits=credits,
                online=_is_online(f"{event_type} {title} {location}"),
                ctext=ctext,
            )
        )
    return events


def fetch() -> list[dict]:
    html = base.download(URL)
    return parse(html)
