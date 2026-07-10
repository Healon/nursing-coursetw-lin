"""Purpose: nuna（護理師護士公會全聯會）來源 parser ——「研習活動報名」公開表格。
Input:  base.download(URL) 取得的 HTML（ASP.NET GridView 表格頁，免登入免會員）。
Output: fetch() -> list[dict]；parse(html) 為純函式，供 tests/fixtures/nuna_list.html 離線測試使用。

頁面結構（2026-07-10 實測 https://www.nurse.org.tw/publicUI/D/D101.aspx）：
表格欄位（依序）：舉辦日期／研習會活動名稱／活動地點／開放報名期間／課程積分／
會員報名餘額／非會員報名餘額／線上報名／報名結果。
「線上報名」欄位是指『可否線上報名繳費』，與活動本身是否線上／視訊授課無關，
因此活動是否線上，改以標題＋地點文字關鍵字判斷（見 _is_online）。
此頁為 ASP.NET GridView，逐列連結是 javascript:__doPostBack(...)，沒有可用的
單列詳情頁 URL，因此每筆事件的 url 一律指向列表頁本身（與參考實作一致）。

課程積分欄位拆解（Lin 2026-07-10 依《醫事人員執業登記及繼續教育辦法》第13條訂定，
見 _parse_credit_cell）：原始格式含衛福部四大類別逐項列點（如「專業: 1.8, 法規: 3.6,
法規(性別): 1.8,」），本 parser 直接拆進 config.CREDIT_TYPES 的 pro／quality／ethics／law
四碼，括號主題（性別／感染）轉成 ctext 提示語，不再把細項原文整段塞進 ctext。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bs4 import BeautifulSoup

from scripts.sources import base

URL = "https://www.nurse.org.tw/publicUI/D/D101.aspx"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ONLINE_RE = re.compile(r"線上|直播|視訊|遠距|webinar", re.IGNORECASE)
_CREDIT_NUM_RE = re.compile(r"[\d.]+")
# 逐項「類別(括號主題)?: 點數」；標籤與括號皆不含空白/逗號/冒號，天然在下一個分隔符處收尾。
_CREDIT_PAIR_RE = re.compile(r"([^\s,，:：()（）]+)(?:[（(]([^)）]*)[)）])?\s*[:：]\s*([\d.]+)")

# 衛福部四大類別文字 -> CREDIT_TYPES key（Lin 2026-07-10 依《醫事人員執業登記及繼續教育
# 辦法》第13條訂定，見 config/site.py CREDIT_TYPES 註解）。
_CAT_MAP = {"專業": "pro", "品質": "quality", "倫理": "ethics", "法規": "law"}

# 括號主題標記 -> ctext 提示語（只用來偵測、不影響歸類；供人工核對細節用）。
_THEME_NOTES = [("性別", "含性別議題課程"), ("感染", "含感染管制課程")]

# 細項加總與開頭總點數的容許誤差（浮點運算與四捨五入留的緩衝）。
_MISMATCH_TOLERANCE = 0.05


def _is_online(text: str) -> bool:
    """依標題＋地點文字關鍵字判斷是否為線上／視訊活動（純字面判斷，非語意理解）。"""
    return bool(_ONLINE_RE.search(text))


def _parse_credit_cell(cell: str) -> tuple[dict[str, float], str]:
    """把課程積分欄位拆成 (credits 依四大類拆解, ctext 主題提示字串)。

    原始格式例：「7.2 專業: 1.8, 法規: 3.6, 法規(性別): 1.8,」—— 第一個數字為總點數，
    其後為衛福部四大類別逐項列點，類別後可能帶括號主題（如「法規(性別)」）。

    對映：專業->pro／品質->quality／倫理->ethics／法規->law（同類別，含括號變體，加總）。
    括號內文字只用來偵測主題提示，不影響歸類：出現「性別」提示「含性別議題課程」，出現
    「感染」提示「含感染管制課程」，兩者皆無則 ctext 為空字串；原始細項全文不再塞進 ctext
    （Lin 2026-07-10 指示）。

    防呆：細項加總與開頭總點數不符（差 > 0.05，可能是本函式漏認某個類別詞或網站格式
    變動）時，不信任細項拆解，整筆退回粗分 {"pro": 總點數}、ctext 清空，並在 stderr
    留痕——寧粗分不錯分。無冒號（無細項、只有總數）時同樣只回傳 {"pro": 總點數}。
    空欄回傳 ({}, "")。
    """
    cell = cell.replace("\xa0", " ").strip().rstrip(",，").strip()
    if not cell:
        return {}, ""

    total_m = _CREDIT_NUM_RE.search(cell)
    total = float(total_m.group()) if total_m else 0.0

    if ":" not in cell and "：" not in cell:
        return ({"pro": total} if total > 0 else {}), ""

    credits: dict[str, float] = {}
    themes: list[str] = []
    for m in _CREDIT_PAIR_RE.finditer(cell):
        label = m.group(1).strip()
        paren = m.group(2)
        value = float(m.group(3))
        cat_key = _CAT_MAP.get(label)
        if cat_key:
            credits[cat_key] = round(credits.get(cat_key, 0.0) + value, 2)
        if paren:
            for kw, note in _THEME_NOTES:
                if kw in paren and note not in themes:
                    themes.append(note)

    breakdown_sum = round(sum(credits.values()), 2)
    if abs(breakdown_sum - total) > _MISMATCH_TOLERANCE:
        print(
            f"[nuna] 積分細項加總 {breakdown_sum} 與開頭總點數 {total} 不符"
            f"（差 {abs(breakdown_sum - total):.2f}），整筆退回 pro={total}：{cell[:60]}",
            file=sys.stderr,
        )
        return ({"pro": total} if total > 0 else {}), ""

    return credits, "、".join(themes)


def parse(html: str) -> list[dict]:
    """解析研習活動報名表格；純函式、不連網，供 fixture 驅動測試使用。

    每列以 <td> 的非空白文字為準（濾掉空字串儲存格），索引依序為：
    [0]=舉辦日期 [1]=活動名稱 [2]=活動地點 [4]=課程積分（若該列有）。
    只保留第一格為 YYYY-MM-DD 的資料列，藉此天然跳過表頭與非資料雜訊列。
    """
    soup = BeautifulSoup(html, "html.parser")
    events: list[dict] = []
    for tr in soup.find_all("tr"):
        cells = [" ".join(td.get_text().split()) for td in tr.find_all("td")]
        cells = [c for c in cells if c]
        if len(cells) < 3 or not _DATE_RE.match(cells[0]):
            continue
        date_s = cells[0]
        title = cells[1]
        location = cells[2]
        credit_cell = cells[4] if len(cells) > 4 else ""
        credits, ctext = _parse_credit_cell(credit_cell)
        online = _is_online(f"{title} {location}")
        events.append(
            base.make_event(
                date=date_s,
                title=title,
                url=URL,
                location=location,
                credits=credits,
                online=online,
                ctext=ctext,
            )
        )
    return events


def fetch() -> list[dict]:
    html = base.download(URL)
    return parse(html)
