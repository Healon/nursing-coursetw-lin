"""Purpose: ahqroc（臺灣醫療品質協會）來源 parser —— 課程清單列表＋詳情頁二段式（仿 critical.py/tnna.py）。
Input:  base.download() 取得的列表頁與各詳情頁 HTML（Class.aspx／ClassDetail.aspx?sid=，皆公開免登入）。
Output: fetch() -> list[dict]；parse_list()／parse_detail() 為純函式，供 tests/fixtures/
        ahqroc_list.html、ahqroc_detail.html、ahqroc_detail_online.html 離線測試使用。

歧義排除：本站為「臺灣醫療品質協會」（Taiwan Healthcare Quality Association，ahqroc.org.tw），
非「醫策會」（jct，見 scripts/sources/jct.py）、非「中華民國品質學會」，三者常被混淆，已於
2026-07-10 偵察階段排除。robots.txt 404（不存在，依慣例視為未限制）。

頁面結構（2026-07-10 實測 https://www.ahqroc.org.tw/Class.aspx，「課程活動／課程清單」預設
「全部」頁籤第 1 頁，8 筆）：每筆課程為 <a class="news_List" href="ClassDetail.aspx?sid=<sid>">
包 <div class="news_Date">民國日期 YYY-MM-DD</div> 與 <div class="news_Title">標題</div>；標題
保留原站「※」項目符號前綴（原文如此，未做清理）。分頁用 ASP.NET __doPostBack，無可用的純 GET
分頁網址（與 ni.py 的既有限制相同），v1 只取第 1 頁；列表頁本身即含日期與標題，詳情頁只用來
補地點與學分。

詳情頁 ClassDetail.aspx?sid=<sid>：<div class="class_Main"><ul><li> 逐項用
<div class="th_title">欄名</div><div class="tr_text">值</div> 配對呈現，本 parser 只取
「上課地點」與「學分」兩欄；「課程日期」欄與列表頁日期重複（本 parser 信任列表頁日期，
不重複解析，同 tnna.py 的既有設計）。「上課地點」對視訊課程的實測值是平台名稱（如
"webex"）而非地址，故 online 判斷不依賴這欄位本身，改用標題＋地點合併關鍵字掃描
（此站視訊課程標題實測皆有「(視訊課程)」／「(全英視訊課程)」字樣，穩定可判）。詳情頁解析
不到地點或學分是合理狀態（非解析失敗，同 tnna.py 的既有設計），不影響事件是否輸出——
日期／標題／url 早已從列表頁取得。

積分對映：本會核心業務為醫療品質／病人安全教育認證（醫品師／高階醫品師甄審），「學分」欄位
對映 CREDIT_TYPES 的 "quality"（品質病安），不分課程主題細節（如「護理人的改善故事館」雖含
護理字樣，其學分仍是本會品質類認證學分，非另立的護理師積分）。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bs4 import BeautifulSoup

from scripts.sources import base

URL = "https://www.ahqroc.org.tw/Class.aspx"
# 詳情頁網址結構為 ClassDetail.aspx?sid=<sid>，但實際 URL 一律由列表頁 href 經 urljoin 產生，
# 不用模板拼字串（審查建議：原本定義了未使用的 DETAIL_URL_TMPL 常數，屬死碼已移除）

# 詳情頁最多抓取頁數（禮貌上限，仿 critical.py／tnna.py；本站第 1 頁實測僅 8 筆，遠低於此）
MAX_DETAIL_PAGES = 12

_SID_RE = re.compile(r"sid=([\w-]+)")
_CREDIT_NUM_RE = re.compile(r"[\d.]+")
_ONLINE_RE = re.compile(r"線上|直播|視訊|遠距|webinar", re.IGNORECASE)


def _is_online(text: str) -> bool:
    """依標題＋上課地點文字關鍵字判斷是否為線上／視訊活動（純字面判斷，非語意理解）。"""
    return bool(_ONLINE_RE.search(text))


def parse_list(html: str) -> list[dict]:
    """從課程清單頁解析候選課程的 (sid, title, date, url)；純函式、不連網。

    只認得 class="news_List" 的錨點；缺日期或標題（結構跑掉）的一律跳過並留痕。
    同一 sid 只留第一次出現（防禦；本站同一場次的不同報名身分會用不同 sid，如
    A-20260829／A-20260829-1，兩者視為獨立事件，不算重複）。
    """
    soup = BeautifulSoup(html, "html.parser")
    seen: set[str] = set()
    candidates: list[dict] = []
    for a in soup.find_all("a", class_="news_List", href=True):
        m = _SID_RE.search(a["href"])
        if not m:
            continue
        sid = m.group(1)
        if sid in seen:
            continue

        date_div = a.select_one("div.news_Date")
        title_div = a.select_one("div.news_Title")
        if date_div is None or title_div is None:
            # news_List 是課程卡片容器，缺日期／標題區塊＝結構缺失，不可無聲
            print(f"[ahqroc] sid={sid} 卡片缺 news_Date/news_Title 區塊，已跳過", file=sys.stderr)
            continue

        date_iso = base.roc_date_to_iso(date_div.get_text(strip=True))
        title = " ".join(title_div.get_text().split())
        if date_iso is None or not title:
            print(f"[ahqroc] sid={sid} 缺少可用日期或標題，已跳過", file=sys.stderr)
            continue

        seen.add(sid)
        candidates.append(
            {
                "sid": sid,
                "title": title,
                "date": date_iso,
                "url": urljoin(URL, a["href"]),
            }
        )
    return candidates


def parse_detail(html: str) -> dict:
    """從課程詳情頁解析 (location, credits)；純函式、不連網。

    逐 <li> 取 th_title/tr_text 配對成 dict；「上課地點」或「學分」缺席／解析不到數字
    時該欄留空，這是合理狀態（同 tnna.py 的既有設計），不視為解析失敗。
    """
    soup = BeautifulSoup(html, "html.parser")
    fields: dict[str, str] = {}
    for li in soup.select("div.class_Main ul > li"):
        label = li.select_one("div.th_title")
        value = li.select_one("div.tr_text")
        if label is None or value is None:
            continue
        fields[label.get_text(strip=True)] = " ".join(value.get_text().split())

    location = fields.get("上課地點", "")
    credits: dict[str, float] = {}
    num_m = _CREDIT_NUM_RE.search(fields.get("學分", ""))
    if num_m and float(num_m.group()) > 0:
        credits = {"quality": float(num_m.group())}

    return {"location": location, "credits": credits}


def fetch() -> list[dict]:
    list_html = base.download(URL)
    all_candidates = parse_list(list_html)
    candidates = all_candidates[:MAX_DETAIL_PAGES]
    if len(all_candidates) > MAX_DETAIL_PAGES:
        print(
            f"[ahqroc] 列表 {len(all_candidates)} 筆，禮貌上限只取前 {MAX_DETAIL_PAGES} 筆詳情頁（已截斷）",
            file=sys.stderr,
        )

    events: list[dict] = []
    for cand in candidates:
        detail_html = base.download(cand["url"])
        detail = parse_detail(detail_html)
        events.append(
            base.make_event(
                date=cand["date"],
                title=cand["title"],
                url=cand["url"],
                location=detail["location"],
                credits=detail["credits"],
                online=_is_online(f"{cand['title']} {detail['location']}"),
            )
        )
    return events
