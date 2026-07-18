"""Purpose: itri（工研院產業學院）來源 parser —— 「找課程／人工智慧」分類的單頁表格式列表。
Input:  base.download_curl() 取得的 LessonList 列表頁 HTML（公開免登入，伺服器渲染）。
Output: fetch() -> list[dict]；parse() 為純函式，供 tests/fixtures/itri_list.html 離線測試使用。

下載層用 download_curl 而非 download：2026-07-18 實測 requests 對 college.itri.org.tw 報
「Missing Subject Key Identifier」憑證驗證失敗，與 hospice 同款（老式根憑證無 X.509v3 擴充
欄位被嚴格 OpenSSL 拒收，LESSONS L-2026-07-10-007）；curl 走系統信任清單可過且同樣完整驗證，
禁止改成 verify=False。

範圍界定（Lin 2026-07-18 指示）：只收「有關 AI 的課程」，取站方自己的「人工智慧」分類資料夾
（LessonList?FolderGUIDs=41098C03-…），不自行用關鍵字撈全站；分類範圍要擴大時改 config 的
FolderGUIDs 參數即可，不用改本模組。

頁面結構（2026-07-18 實測，83 筆）：列表頁同時渲染 isotope 卡片檢視與 <table id="sample_1">
清單檢視；表格才是完整資料（卡片僅部分且無日期），四欄固定為「課程名稱（含 LessonData 詳情
連結）／開課日期／地點/型態／時數」，一頁包含全部課程，無伺服器端分頁（dataTable 分頁為前端
行為）。日期為西元 YYYY/MM/DD（非民國，不用 roc_date_to_iso）；開課日期欄為「進行中」者是
雲端教室隨選自學課，比照 jct 決策（2026-07-10 Lin 指示：僅收排定場次）整筆不收錄，但會在
stderr 留下略過筆數。地點值實測為城市名（台北／新竹／台南／嘉義／高雄／台中）或「數位直播」
／「雲端教室」；「數位直播」為排定時間的直播場次，收錄且標 online。

積分與類別：工研院課程無護理繼續教育積分，credits 一律留空 dict；時數欄轉存 ctext
（「30 hrs」→「時數 30 小時」）供卡片參考。類別固定 cat="tech"（本來源整批就是站方 AI 分類，
不需標題推斷；智慧科技分類即為收納本來源而於 2026-07-18 新增）。

去重：同名課程不同梯次各有獨立 LessonData GUID 與日期，屬不同事件；防禦性以 (date, url)
去重（防站方同列重複渲染），不可只用 url。
"""
from __future__ import annotations

import datetime as dt
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bs4 import BeautifulSoup

from config import site as cfg
from scripts.sources import base

URL = cfg.SOURCES["itri"]["url"]

_WEST_DATE_RE = re.compile(r"(?<!\d)(\d{4})/(\d{1,2})/(\d{1,2})(?!\d)")
_ONLINE_RE = re.compile(r"直播|線上|遠距|視訊|webinar", re.IGNORECASE)


def _west_date_to_iso(text: str) -> str | None:
    """西元 YYYY/M/D → ISO；辨認不出或日期不合法回傳 None（「進行中」等文字即落此）。"""
    m = _WEST_DATE_RE.search(text)
    if not m:
        return None
    try:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
    except ValueError:
        return None


def parse(html: str) -> list[dict]:
    """從列表頁的清單檢視表格解析課程；純函式、不連網。

    只認 table#sample_1 的四欄列；表格不存在（改版）時 raise 讓 registry 記 error，
    不可靜默回空（0 筆會被誤判為「來源正常剛好沒課」）。缺日期的「進行中」自學課
    屬預期略過（計數留痕）；四欄不齊或缺標題連結的列屬結構異常，逐列留痕後跳過。
    """
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table#sample_1")
    if table is None:
        raise ValueError("找不到 table#sample_1 課程清單表格，網站可能改版")

    seen: set[tuple[str, str]] = set()
    events: list[dict] = []
    ondemand_skipped = 0
    for tr in table.find_all("tr"):
        tds = tr.find_all("td")
        if not tds:
            continue  # 表頭列
        if len(tds) != 4:
            print(f"[itri] 列欄數異常（{len(tds)} 欄），已跳過", file=sys.stderr)
            continue
        link = tds[0].find("a", href=True)
        if link is None:
            print("[itri] 列缺課程連結，已跳過", file=sys.stderr)
            continue
        title = " ".join(link.get_text().split())
        date_iso = _west_date_to_iso(tds[1].get_text(strip=True))
        if date_iso is None:
            # 「進行中」＝雲端教室隨選自學課，依決策不收錄（非結構異常）
            ondemand_skipped += 1
            continue
        location = tds[2].get_text(strip=True)
        hours = tds[3].get_text(strip=True)

        url = urljoin(URL, link["href"])
        key = (date_iso, url)
        if key in seen or not title:
            continue
        seen.add(key)
        events.append(
            base.make_event(
                date=date_iso,
                title=title,
                url=url,
                location=location,
                cat="tech",
                online=bool(_ONLINE_RE.search(f"{location} {title}")),
                ctext=f"時數 {hours.replace('hrs', '小時').strip()}" if hours else "",
            )
        )
    if ondemand_skipped:
        print(f"[itri] 略過 {ondemand_skipped} 筆「進行中」雲端自學課（依規則不收隨選課程）", file=sys.stderr)
    return events


def fetch() -> list[dict]:
    return parse(base.download_curl(URL))
