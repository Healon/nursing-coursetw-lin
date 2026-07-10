"""Purpose: tnma（臺灣護理管理學會）來源 parser —— 研習會活動報名表格單頁解析（不解析 PDF 內容）。
Input:  base.download(URL) 取得的 HTML（傳統 ASP 表格頁，免登入）。
Output: fetch() -> list[dict]；parse(html) 為純函式，供 tests/fixtures/tnma_list.html 離線測試使用。

頁面結構（2026-07-10 實測 https://www.tnma100.org.tw/training/training02.asp）：
表格逐列 8 個邏輯欄位：編號／活動名稱／辦理日期／活動地點／報名截止日／課程表／報名狀態／
可報名人數。這是老式 ASP 產生的表格，「課程表」欄的 <td> 沒有正確閉合（缺 </td>），導致其後
「報名狀態」「可報名人數」兩欄被解析器容錯地巢狀掛在課程表欄底下，而非同一 <tr> 的直接子節點；
因此逐列必須用 tr.find_all("td", recursive=False)（只取直接子節點）取得穩定的 6 個直接子欄位
（[0]編號 [1]活動名稱 [2]辦理日期 [3]活動地點 [4]報名截止日 [5]課程表，[5] 內巢狀含報名狀態／
可報名人數，本站不需要這兩欄的資料），實測全部 50 列皆穩定得到這個直接子欄位數；若改回預設的
recursive=True 遞迴搜尋，會把巢狀報名連結誤判成同一列的內容重複計入，實測筆數從 50 暴增到 99。

辦理日期欄可能是單一日期「2026/9/23」或區間「2026/9/2～2026/9/9」，一律取區間起始日；
欄位常在日期後方以 <br> 接續上課時段文字（如「11:50-13:10」），一併併入純文字後靠正則只挑
YYYY/M/D 樣式即可自然略過時間字串，不需特別切割。

課程表欄底下常見一或多個 manager/upload/ 路徑下的附件連結，實測格式不限 PDF（也有 .xls／
.docx 案例），一律視為「簡章附件」不分格式，取第一個出現的附件連結當 url；完全無附件的列
（如純視訊課程）則 url 退回列表頁本身。任務範圍明確排除本 parser 解析附件內容（PDF/XLS/DOCX
一律不開），故 credits 恆為空字典。ctext 依有無附件用不同措辭（審查判斷 2026-07-10）：
有附件寫「積分與細節詳見簡章附件」（不寫死 PDF，因為附件格式不一），無附件寫「積分與細節
請洽官方公告」──避免 url 指向列表頁時卻叫使用者去看不存在的簡章連結。
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

URL = "https://www.tnma100.org.tw/training/training02.asp"

_CODE_RE = re.compile(r"^T\d+$")
_DATE_RE = re.compile(r"(\d{4})/(\d{1,2})/(\d{1,2})")
_ONLINE_RE = re.compile(r"線上|直播|視訊|遠距|webinar", re.IGNORECASE)
_CTEXT_WITH_ATTACHMENT = "積分與細節詳見簡章附件"
_CTEXT_NO_ATTACHMENT = "積分與細節請洽官方公告"


def _is_online(text: str) -> bool:
    """依標題＋地點文字關鍵字判斷是否為線上／視訊活動（純字面判斷，非語意理解）。"""
    return bool(_ONLINE_RE.search(text))


def _first_date_iso(cell_text: str) -> str | None:
    """從辦理日期欄純文字取第一組 YYYY/M/D 轉 ISO；區間日期取起始日，找不到或不合法回 None。"""
    m = _DATE_RE.search(cell_text)
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    try:
        return dt.date(y, mo, d).isoformat()
    except ValueError:
        return None


def parse(html: str) -> list[dict]:
    """解析研習會活動報名表格；純函式、不連網。

    見檔頭註解：td 只取直接子節點（recursive=False）是應對「課程表」欄未閉合 <td> 的必要
    作法，勿改回預設遞迴搜尋。只保留第一欄符合「T 開頭＋數字」編號樣式的資料列，同編號重複
    出現只留第一次（此頁實測沒有重複編號，此處僅為防禦）。
    """
    soup = BeautifulSoup(html, "html.parser")
    events: list[dict] = []
    seen: set[str] = set()
    for tr in soup.find_all("tr"):
        tds = tr.find_all("td", recursive=False)
        if not tds:
            continue
        code = " ".join(tds[0].get_text().split())
        if not _CODE_RE.match(code) or code in seen:
            continue

        title = " ".join(tds[1].get_text().split()) if len(tds) > 1 else ""
        date_cell = " ".join(tds[2].get_text(separator=" ").split()) if len(tds) > 2 else ""
        location = " ".join(tds[3].get_text().split()) if len(tds) > 3 else ""
        # 地點欄常拖一段「註：…」自由文字備註（繳費方式等），截掉：卡片顯示乾淨，
        # 也避免備註裡的「線上（匯款）」等字樣污染地區推斷（審查發現的誤判來源）
        location = re.split(r"\s*註[：:]", location, maxsplit=1)[0].strip()

        date_iso = _first_date_iso(date_cell)
        if date_iso is None or not title:
            print(
                f"[tnma] 編號={code} 缺少可用日期或標題，已跳過：{(title or date_cell)[:30]}",
                file=sys.stderr,
            )
            continue
        seen.add(code)

        url = URL
        if len(tds) > 5:
            attach_href = next(
                (a["href"] for a in tds[5].find_all("a", href=True) if "/manager/upload/" in a["href"]),
                None,
            )
            if attach_href:
                url = urljoin(URL, attach_href)

        events.append(
            base.make_event(
                date=date_iso,
                title=title,
                url=url,
                location=location,
                credits={},
                # online 只看標題：本站地點欄常混入自由文字備註（實測有「線下/線上匯款」
                # 付款說明），整欄餵關鍵字會把實體活動誤判成線上（審查發現：廈門實體
                # 論壇因備註含「線上」被誤標）。實測本站真正的視訊課程標題必含「視訊」。
                online=_is_online(title),
                ctext=_CTEXT_WITH_ATTACHMENT if url != URL else _CTEXT_NO_ATTACHMENT,
            )
        )
    return events


def fetch() -> list[dict]:
    html = base.download(URL)
    return parse(html)
