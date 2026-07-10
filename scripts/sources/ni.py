"""Purpose: ni（台灣護理資訊學會）來源 parser —— 消息列表頁＋詳情頁二段式（詳情僅補地點／積分）。
Input:  base.download() 取得的列表頁與各詳情頁 HTML（?pidm=ID 為同一支頁面依 querystring
        顯示的詳情，皆公開免登入）。
Output: fetch() -> list[dict]；parse_list()／parse_detail() 為純函式，
        供 tests/fixtures/ni_list.html 與 ni_detail.html 離線測試使用。

頁面結構（2026-07-10 實測 https://www.ni.org.tw/v2/newsm_cload3.aspx）：
- 列表頁：<table class="footable"> 逐列為「活動日期」（YYYY/MM/DD，已零填）＋
  <a href="newsm_cload3.aspx?pidm=ID" class="accordion-toggle"><span class="atitlestyle...">
  標題</span></a>，固定 10 筆/頁，只有日期與標題，無地點、無積分。
- 詳情頁 ?pidm=ID：同一支 .aspx 依 querystring 顯示卡片內容，含「活動地點」「活動地址」等
  結構化欄位（<span class='spanblackstyle12'> 前一格是欄位名稱，後一格是值），取「活動地址」
  優先、缺席才退回「活動地點」。積分多半只是一段呼籲文字（如「本課程申請護理人員繼續教育
  積分…」），沒有統一的數字格式；只在明確抓到「數字＋積分／點」時才寫入 credits，抓不到就把
  呼籲文字整段放進 ctext，不臆測數字。

分頁機制實測：頁面有 <select id='select_page'> 下拉選單（value 格式如 "2,10"，疑似頁碼＋
每頁筆數），但整頁找不到任何純 querystring 分頁連結（如 ?page=2 之類），也找不到內嵌的
__doPostBack(...) 呼叫字串——最可能是透過外部編譯後的 unobtrusive script（ScriptResource.axd）
綁定 change 事件觸發 ASP.NET postback，無法從靜態 HTML 100% 肉眼確認。但沒有任何證據支持
「純 GET 可翻頁」，依任務規格的保守分支處理：v1 只取第一頁（10 筆），不臆測 querystring 打
第二頁（避免打一個猜測、可能根本不存在的網址）。

禮貌上限：詳情頁抓取比照 tnna 慣例，上限 12 頁（MAX_DETAIL_PAGES）；為省請求，日期已超過
「今天 7 天前」的候選直接跳過詳情頁（地點／積分留空，不影響已從列表頁取得的日期／標題），
此節流做法是把任務規格明文要求 tnna 做的「先跳過明顯過期候選」，依相同理由類推套用到 ni——
ni 詳情頁也是二段式且列表頁同樣先給了日期，跳過理由與 tnna 完全一致。
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

LIST_URL = "https://www.ni.org.tw/v2/newsm_cload3.aspx"

MAX_DETAIL_PAGES = 12
STALE_DAYS = 7

_PIDM_RE = re.compile(r"pidm=(\d+)")
_LIST_DATE_RE = re.compile(r"(\d{4})/(\d{2})/(\d{2})")
_CREDIT_NUM_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:積分|點)")
_CREDIT_NOTE_RE = re.compile(r"(本課程[^。]*?繼續教育積分[^。]*。)")
# 值的右邊界只認「具體的下一個欄位標籤」，不可用裸「活動」二字當邊界：
# 地址值本身常含「OO活動中心」這類場館名，裸詞會把地址提前截斷（審查發現的邊界案例，
# 例：「…長泰街25號三重區民活動中心3樓」會被切成「…三重區民」）
_NEXT_LABEL = r"(?=活動(?:日期|時間|地址|地點|場次|對象|網址|名稱)[：:]|報名|消息說明|$)"
_ADDRESS_RE = re.compile(r"活動地址[：:]\s*([^\s].*?)" + _NEXT_LABEL)
_VENUE_RE = re.compile(r"活動地點[：:]\s*([^\s].*?)" + _NEXT_LABEL)
_ONLINE_RE = re.compile(r"線上|直播|視訊|遠距|webinar", re.IGNORECASE)


def _is_online(text: str) -> bool:
    """依標題＋地點文字關鍵字判斷是否為線上／視訊活動（純字面判斷，非語意理解）。"""
    return bool(_ONLINE_RE.search(text))


def parse_list(html: str) -> list[dict]:
    """從消息列表頁解析候選活動的 (id, title, date, url)；純函式、不連網。

    只認 table.footable 內、每列第 2 欄含 pidm= 連結的資料列；同一 id 只留第一次出現。
    """
    soup = BeautifulSoup(html, "html.parser")
    seen: set[str] = set()
    candidates: list[dict] = []
    for tr in soup.select("table.footable tr"):
        tds = tr.find_all("td")
        if len(tds) < 2:
            continue  # 表頭列（th）或版面分隔列，非資料列
        a = tds[1].find("a", href=True)
        if a is None:
            # 結構缺失不可無聲：資料列沒有標題連結，多半是網站改版讓選擇器失效
            print(f"[ni] 資料列缺標題連結，已跳過：{tds[0].get_text(strip=True)[:20]}", file=sys.stderr)
            continue
        m = _PIDM_RE.search(a["href"])
        if not m:
            print(f"[ni] 標題連結無 pidm 參數，已跳過：{a.get('href', '')[:60]}", file=sys.stderr)
            continue
        pidm = m.group(1)
        if pidm in seen:
            continue
        date_m = _LIST_DATE_RE.search(tds[0].get_text())
        if not date_m:
            print(f"[ni] pidm={pidm} 找不到可用日期，已跳過：{tds[0].get_text(strip=True)[:20]}", file=sys.stderr)
            continue
        seen.add(pidm)
        candidates.append(
            {
                "id": pidm,
                "title": " ".join(a.get_text().split()),
                "date": f"{date_m.group(1)}-{date_m.group(2)}-{date_m.group(3)}",
                "url": urljoin(LIST_URL, a["href"]),
            }
        )
    return candidates


def parse_detail(html: str) -> dict:
    """從詳情頁解析 (location, credits, ctext)；純函式、不連網。找不到就回傳空值，非失敗。

    地點優先採「活動地址」（含街道門牌，資訊較完整），該欄缺席才退回「活動地點」（僅機構
    名稱）；兩個 regex 分開比對且明確按此優先序 if/elif，不可合併成一個 pattern 用 search()
    找「第一個出現的」，因為「活動地點」欄在真實頁面永遠排在「活動地址」欄前面，合併搜尋會
    誤把資訊較少的地點名稱取代掉地址（此為實作過程中發現並修正的一個真實 bug）。
    """
    soup = BeautifulSoup(html, "html.parser")
    body_text = " ".join(soup.get_text().split())

    addr_m = _ADDRESS_RE.search(body_text)
    if addr_m:
        location = addr_m.group(1).strip()
    else:
        venue_m = _VENUE_RE.search(body_text)
        location = venue_m.group(1).strip() if venue_m else ""

    credits: dict[str, float] = {}
    ctext = ""
    credit_m = _CREDIT_NUM_RE.search(body_text)
    if credit_m:
        credits["pro"] = float(credit_m.group(1))
    else:
        note_m = _CREDIT_NOTE_RE.search(body_text)
        if note_m:
            ctext = note_m.group(1)

    return {"location": location, "credits": credits, "ctext": ctext}


def fetch() -> list[dict]:
    list_html = base.download(LIST_URL)
    all_candidates = parse_list(list_html)
    candidates = all_candidates[:MAX_DETAIL_PAGES]
    if len(all_candidates) > MAX_DETAIL_PAGES:
        print(
            f"[ni] 列表 {len(all_candidates)} 筆，禮貌上限只取前 {MAX_DETAIL_PAGES} 筆候選（已截斷）",
            file=sys.stderr,
        )
    print("[ni] 分頁機制無法從靜態 HTML 確認為純 GET，疑似 postback，v1 只取第一頁", file=sys.stderr)

    stale_floor = dt.date.today() - dt.timedelta(days=STALE_DAYS)

    events: list[dict] = []
    skipped_stale = 0
    for cand in candidates:
        location, credits, ctext = "", {}, ""
        if dt.date.fromisoformat(cand["date"]) < stale_floor:
            skipped_stale += 1
        else:
            detail_html = base.download(cand["url"])
            detail = parse_detail(detail_html)
            location, credits, ctext = detail["location"], detail["credits"], detail["ctext"]
        events.append(
            base.make_event(
                date=cand["date"],
                title=cand["title"],
                url=cand["url"],
                location=location,
                credits=credits,
                online=_is_online(f"{cand['title']} {location}"),
                ctext=ctext,
            )
        )
    if skipped_stale:
        print(
            f"[ni] {skipped_stale} 筆候選日期已超過 {STALE_DAYS} 天，為省請求跳過詳情頁（地點／積分留空）",
            file=sys.stderr,
        )
    return events
