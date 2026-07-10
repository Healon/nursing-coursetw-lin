"""Purpose: twna（台灣護理學會）來源 —— 手動維護清單，不連網、不自動爬取。
Input:  data/manual_twna.json（維護者手動編輯的事件清單，由 scripts/import_twna_page.py
        半自動匯入器或手動編輯填入）。
Output: fetch() -> list[dict]；每筆事件經 base.make_event() 補齊 schema 預設值。
        parse_saved_page(html) -> list[dict]：純函式，解析「維護者本人另存到本機的課程列表
        HTML」，供 import_twna_page.py 與離線測試使用，同樣不發出任何網路請求。

robots.txt 背景與決策（2026-07-10 實測 https://act.e-twna.org.tw/robots.txt）：
```
User-agent: *
Disallow: /
```
全站對所有 UA 禁止，課程頁面本身雖公開（免登入即可瀏覽），但依本專案「新增來源前先看
robots.txt，被明確禁止就不要爬」守則（見 README 爬蟲禮貌守則），本模組與其匯入器**絕不**
對 twna 網站發出任何自動化請求。Lin 已決策的半自動工作流：

1. 維護者本人用瀏覽器開啟課程列表頁，手動「另存新檔」HTML 到本機（人類操作，非程式爬取）。
2. `scripts/import_twna_page.py <另存的.html>` 讀取這份本機檔案，呼叫本模組的
   parse_saved_page() 解析，與既有 data/manual_twna.json 合併去重後寫回。
3. fetch() 一如既往只讀 data/manual_twna.json，完全不知道、也不需要知道資料是怎麼填進去的。

錯誤語意（刻意設計，呼應 registry 的「錯誤可見」原則）：
- data/manual_twna.json 不存在 -> raise FileNotFoundError，registry 記為該來源 status=error。
- JSON 語法壞掉 -> json.loads 原生 raise，同樣被 registry 接住記為 error。
- events 欄位缺失 -> raise KeyError（視為結構壞掉，同上）。
- 單筆事件缺必要欄位（date/title/url）-> raise ValueError，訊息含是第幾筆，方便 Lin 手動
  編輯 JSON 時定位錯誤（比裸露的 TypeError 更好讀）。
- events 為空清單是合法狀態（尚未填入資料），回傳空 list；registry 會標為 status=empty，
  誠實呈現「這來源目前沒有資料」而非假裝抓取失敗。
- parse_saved_page() 單列缺日期或缺標題 -> 該列跳過並印 stderr 留痕（不 raise、不靜默），
  因為列表頁本身就會出現「規劃中、日期只標到月份」的合法但不完整資料列（實測 2 筆）。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bs4 import BeautifulSoup

from scripts.sources import base

ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = ROOT / "data" / "manual_twna.json"

# 課程列表頁（維護者另存 HTML 的來源頁面）；GridView 逐列無可用 GET 詳情連結（標題是
# javascript:__doPostBack(...) postback），故每筆事件的 url 一律指回這個公開列表頁。
LIST_URL = "https://www.act.e-twna.org.tw/ActSign/PUB/ActClass_List.aspx"

_GRID_ID = "ctl00_ContentPlaceHolder1_GridView1"
_ONLINE_RE = re.compile(r"線上|直播|視訊|遠距|webinar", re.IGNORECASE)
_NO_CREDIT_CTEXT = "積分請洽學會官網"


def _is_online(text: str) -> bool:
    """依標題＋地點文字關鍵字判斷是否為線上／視訊活動（純字面判斷，非語意理解）。"""
    return bool(_ONLINE_RE.search(text))


def parse_saved_page(html: str) -> list[dict]:
    """解析維護者手動另存的課程列表頁 HTML（GridView 表格），純函式、不連網。

    頁面結構（2026-07-10 偵察期單次快取實測，見模組檔頭合規背景；本函式的輸入永遠是本機
    檔案內容，不代表本函式本身會發出任何請求）：GridView id="ctl00_ContentPlaceHolder1_
    GridView1"，表頭依序為 辦理日期／活動名稱／活動場地／費用／開放可報名額／報名日期／
    報名／名單。以 <td data-th="..."> 屬性定位儲存格（比用欄位索引更不受版面微調影響）；
    儲存格內另有語意 id（如 ..._A_act_OpenDate、..._A_act_cName）可供人工核對，但不作為
    本函式的定位依據。

    日期為民國格式＋星期文字（如 "115/7/2(四)"），交給 base.roc_date_to_iso 換算——星期
    文字在括號內、緊接數字日期之後為非數字字元，落在該函式邊界規則內可直接解析，不需要
    先自行剝除 "(四)"。

    列表頁本身沒有積分欄位：credits 一律空字典，ctext 固定填「積分請洽學會官網」。標題
    儲存格的連結是 javascript:__doPostBack(...) postback，沒有可用的 GET 詳情頁，因此每筆
    事件的 url 一律填模組層級常數 LIST_URL（公開列表頁本身）。

    單列缺日期或缺標題視為壞資料，該列跳過並於 stderr 留痕（不靜默）。實測頁面即有 2 筆
    「規劃中」活動日期只標到月份（"115/9"，無日），會被此規則自然跳過。
    """
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id=_GRID_ID)
    events: list[dict] = []
    if table is None:
        return events

    data_rows = [tr for tr in table.find_all("tr") if tr.find("th") is None]
    for i, tr in enumerate(data_rows, start=1):
        date_cell = tr.find("td", attrs={"data-th": "辦理日期"})
        title_cell = tr.find("td", attrs={"data-th": "活動名稱"})
        place_cell = tr.find("td", attrs={"data-th": "活動場地"})

        date_text = date_cell.get_text(" ", strip=True) if date_cell else ""
        date_iso = base.roc_date_to_iso(date_text)

        title_text = ""
        if title_cell is not None:
            title_node = title_cell.find("a") or title_cell
            title_text = " ".join(title_node.get_text(" ", strip=True).split())

        if not date_iso or not title_text:
            print(
                f"[twna] 另存頁第 {i} 列缺日期或標題，已跳過：date={date_text!r} title={title_text!r}",
                file=sys.stderr,
            )
            continue

        location = ""
        if place_cell is not None:
            location = " ".join(place_cell.get_text(" ", strip=True).split())

        events.append(
            base.make_event(
                date=date_iso,
                title=title_text,
                url=LIST_URL,
                location=location,
                credits={},
                online=_is_online(f"{title_text} {location}"),
                ctext=_NO_CREDIT_CTEXT,
            )
        )
    return events


def fetch() -> list[dict]:
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"手動維護清單不存在，請先建立：{DATA_PATH}")

    raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    items = raw["events"]  # 缺 events 欄位視為 JSON 結構壞掉，直接 raise KeyError

    events: list[dict] = []
    for i, item in enumerate(items):
        try:
            events.append(base.make_event(**item))
        except TypeError as exc:
            raise ValueError(f"{DATA_PATH.name} 第 {i + 1} 筆事件格式錯誤：{exc}") from exc
    return events
