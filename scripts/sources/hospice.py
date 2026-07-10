"""Purpose: hospice（台灣安寧緩和護理學會）來源 parser —— 課程報名列表單頁解析（不需詳情頁）。
Input:  base.download(URL) 取得的 HTML（含 integrationProperty=1 查詢參數的伺服器渲染表格頁）。
Output: fetch() -> list[dict]；parse(html) 為純函式，供 tests/fixtures/hospice_list.html 離線測試使用。

feasibility 判定（2026-07-10 實測）：原始候選網址（不帶 integrationProperty）有 SPA 空殼疑慮；
Lin 提供她實際使用的確切網址（含 `?integrationProperty=1`）後改用該網址實測，回應為伺服器直接
渲染的 <table class="break-table">，非 JS 空殼，故判定可爬。robots.txt 404（不存在，依慣例視為
未限制）。URL 已寫回 config/site.py 的 hospice.url。

頁面結構（2026-07-10 實測該確切網址，5 筆，頁面內嵌 `var totalNum = 5;` 確認非分頁截斷，
totalNum 即為當前查詢條件下的全部筆數）：<table class="break-table"><tbody> 逐列 <tr>，每格
<td data-th="欄名"> 標出欄位語意，5 欄依序為 活動日期／活動名稱／學習性質／積分類別／積分數：
- 活動日期：民國日期，單一（"115/07/11"）或區間（"115/09/05 - 115/09/06"），用
  base.roc_date_to_iso() 取區間起始日（regex 天然只吃第一個出現的日期）。
- 活動名稱：<a href="/ehc-tahpn/s/w/edu/scheduleInfo1/schedule1/<hash>">，該 href 即詳情頁，
  當作事件 url（每筆活動各自的詳情連結，優於全部指回列表頁）。
- 學習性質：本批實測全為「實體」，未見「線上」樣本，解析仍依欄位文字通用判斷（非寫死實體），
  與標題一併餵給 _is_online()。
- 積分類別：如「學術研討」「必修課程」，非本站 CREDIT_TYPES 既有代碼，原文存入 ctext。
- 積分數：純數字（含小數），本會為護理人員繼續教育積分性質（非專科護理師 NP 特定積分），
  對映 CREDIT_TYPES 的 "pro"。

無地點欄位：列表頁與詳情頁（實測 scheduleInfo1/schedule1/<hash>，見開發紀錄）皆未提供活動地址／
場地欄位（詳情頁僅有課程簡介、繳費說明、課程明細時數，無地點），故本站不輸出 location，
交由 base.infer_region 落 tbd（誠實呈現未知，而非亂猜）。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bs4 import BeautifulSoup

from scripts.sources import base

URL = "https://www.hospicenurse.org.tw/ehc-tahpn/s/w/edu/schedule/schedule1?integrationProperty=1"

_SCORE_NUM_RE = re.compile(r"[\d.]+")
_ONLINE_RE = re.compile(r"線上|直播|視訊|遠距|webinar", re.IGNORECASE)


def _is_online(text: str) -> bool:
    """依學習性質＋標題文字關鍵字判斷是否為線上／視訊活動（純字面判斷，非語意理解）。"""
    return bool(_ONLINE_RE.search(text))


def parse(html: str) -> list[dict]:
    """解析課程報名列表表格；純函式、不連網。

    逐 <tr> 用 data-th 屬性取欄位（而非位置索引），對表頭 <tr>（只有 <th>、沒有
    data-th 的 <td>）天然得到空 cells dict 而被跳過，不需另外濾表頭列。
    """
    soup = BeautifulSoup(html, "html.parser")
    events: list[dict] = []
    for tr in soup.find_all("tr"):
        cells = {
            td.get("data-th", "").strip(): td
            for td in tr.find_all("td", attrs={"data-th": True})
        }
        if not cells:
            continue

        date_cell = cells.get("活動日期")
        title_cell = cells.get("活動名稱")
        if date_cell is None or title_cell is None:
            # 有 data-th 儲存格卻缺「活動日期／活動名稱」欄＝結構缺失，不可無聲
            print(
                f"[hospice] 資料列缺日期或名稱欄（data-th 欄位：{sorted(cells)[:4]}），已跳過",
                file=sys.stderr,
            )
            continue

        date_text = date_cell.get_text(strip=True)
        date_iso = base.roc_date_to_iso(date_text)

        a = title_cell.find("a", href=True)
        title = " ".join((a.get_text() if a is not None else title_cell.get_text()).split())

        if date_iso is None or not title:
            print(f"[hospice] 缺少可用日期或標題，已跳過：{(title or date_text)[:30]}", file=sys.stderr)
            continue

        url = urljoin(URL, a["href"]) if a is not None else URL

        nature_text = cells["學習性質"].get_text(strip=True) if "學習性質" in cells else ""
        category_text = cells["積分類別"].get_text(strip=True) if "積分類別" in cells else ""
        score_text = cells["積分數"].get_text(strip=True) if "積分數" in cells else ""

        credits: dict[str, float] = {}
        num_m = _SCORE_NUM_RE.search(score_text)
        if num_m and float(num_m.group()) > 0:
            credits = {"pro": float(num_m.group())}

        events.append(
            base.make_event(
                date=date_iso,
                title=title,
                url=url,
                credits=credits,
                online=_is_online(f"{nature_text} {title}"),
                ctext=category_text,
            )
        )
    return events


def fetch() -> list[dict]:
    # 用 download_curl 而非 download：本站憑證鏈的 TWCA 老式根憑證會被 requests 底下的
    # OpenSSL 嚴格驗證拒收，curl 用系統信任清單可通過且同樣完整驗證憑證（見 base.download_curl
    # docstring 的 2026-07-10 診斷）。刻意不用 verify=False。
    html = base.download_curl(URL)
    return parse(html)
