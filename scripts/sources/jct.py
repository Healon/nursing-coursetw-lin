"""Purpose: jct（財團法人醫院評鑑暨醫療品質策進會，醫策會）來源 parser —— 活動月曆頁＋詳情頁
           二段式（仿 critical.py/tnna.py）。
Input:  base.download() 取得的月曆頁與各詳情頁 HTML（attend.jct.org.tw 子網域，皆公開免登入）。
Output: fetch() -> list[dict]；parse_calendar()／parse_detail() 為純函式，供 tests/fixtures/
        jct_calendar.html、jct_detail.html、jct_detail_bundle.html 離線測試使用。

robots.txt 404（不存在，依慣例視為未限制）。日期格式：月曆頁天數為純數字（如「20」），實際
日期＝月曆頁標題「YYYY年MM月」＋格內數字組成；詳情頁欄位日期仍為西元 YYYY/MM/DD（沿用
2026-07-10 首版訂正，不需 base.roc_date_to_iso()）。

**v2 改用月曆頁（2026-07-10 重工）**：v1 原用首頁精選表（5 列），但 Lin 實測發現首頁漏列
大量真實排定課程（首頁只挑 5 筆展示，非全部）。改抓 activity/event_news_calendar.php，
逐月列出當月「每一天」的全部場次，同月份可有數十筆，三個月（本月＋未來兩個月）涵蓋更完整。

月份切換機制（2026-07-10 實測確認）：月曆頁有「上個月／YYYY年MM月／下個月」列
（`<div class="calendar2">`），「下個月」是純 `<a href="event_news_calendar.php?arg=<加密
token>">`，**純 GET、非 postback**，可逐月往前串接抓取（本模組固定抓 3 頁：本月＋未來兩個
月）；同頁另有一個 `method="post"` 的年月下拉選單表單（`frm_search`），那是另一種跳月方式，
本模組不使用（避免 POST，維持全站 GET-only 慣例），純 GET 換月連結已足夠。

**v1 曾放棄月曆頁的理由已不成立**：v1 docstring 原記錄「月曆需逐月翻頁且日期要反推，解析
更脆弱」；v2 實測後發現日期反推很直接（頁面標題月份＋格內數字），逐月翻頁也是單純 GET 串接
不是問題，故重新採用。v1 曾考慮過的另一深層清單 event_news_list.php（分頁清單，數位課程
套裝洗版問題）與此無關，仍不採用。

**資料形態**：月曆每一天格子可有 0～多筆課程連結；**同一個 href 出現在不同天是正常資料**
（同一報名活動的不同場次各自佔一個日期格，如「說明會 (第1場)」在 20 日、「(第2場)」在 22
日，共用同一個 event_news_detail.php?arg= 報名頁），**同一天也可能有多筆連結共用同一 href**
（如同場論壇的不同分組場次，2026-07-10 實測「抗生素管理與感染管制高峰論壇」兩組同天共用一個
href），故候選去重鍵用 (日期, href, 標題) 三者合一，只用 (日期, href) 仍可能誤刪同天不同標題
的場次；只用 href 更會把跨月/跨日全部場次砍到剩一筆（這正是 v1 放棄 event_news_list.php 的
原因，月曆頁看似有同樣風險，故特別做這三元鍵防禦）。

**數位課程／教學影片一律排除，不收錄上站**（Lin 2026-07-10 指示）。v1／v2 首版曾把這類項目
標題關鍵字判斷後標記 ondemand=True（跳過視窗過濾但仍收錄），本版起改為在 fetch() 內部直接
過濾掉，不產出事件；`_ONDEMAND_RE` 保留，但用途由「標記」改為「排除」（見 `_exclude_ondemand`）。
過濾點刻意放在去重後、選詳情前（最省請求：命中的候選連詳情頁都不必抓），排除筆數以彙總
形式 stderr 留痕，不可無聲丟棄。ondemand 基礎設施本身（normalize 的視窗過濾豁免、樣板的
隨選課程分組）未受影響、原樣保留供其他來源未來使用，只是 jct 不再產生任何 ondemand=True
的事件。

**詳情頁地點標籤有兩種**（2026-07-10 v2 實測發現，v1 只見過「活動地點」）：一般排定活動
（如研討會）用「活動地點：」，實作課程／工作坊類用「課程地點：」，兩者語意相同，_PLACE_LINE_RE
與掃描迴圈已同時比對兩種前綴；學分認可單位欄位解析邏輯不變（結構化 span.title5 標籤照舊）。

積分：「學分認可單位」為描述性文字（列出認可此課程積分的單位／制度，如「醫策會上課時數
證明、公務人力時數、護理人員繼續教育訓練積分」），多數情況無明確數字（積分「申請中」是
本站常態），只有文字提到「護理」且能抽出數字時才對映 pro，否則原文整段存入 ctext，
不臆測積分數字。
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

CALENDAR_URL = "https://attend.jct.org.tw/activity/event_news_calendar.php"

# 月曆逐月串接抓取頁數：本月＋未來兩個月（Lin 2026-07-10 指定涵蓋「三個月內」）。
MONTHS_TO_FETCH = 3

# 詳情頁最多抓取頁數（禮貌上限，仿 critical.py／tnna.py；月曆頁筆數遠多於舊首頁 5 筆，
# 上限不變，時間窗內超過此數只取最近的，stderr 留痕，見 fetch()）。
MAX_DETAIL_PAGES = 12

_MONTH_HEADER_RE = re.compile(r"(\d{4})年\s*(\d{1,2})月")
_BULLET_RE = re.compile(r"^＊\s*")
_ONDEMAND_RE = re.compile(r"數位課程|教學影片")
_ONLINE_RE = re.compile(r"線上|直播|視訊|遠距|webinar", re.IGNORECASE)
_CREDIT_NUM_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:積分|學分)")
_PLACE_LINE_RE = re.compile(r"^(?:活動|課程)地點[:：]\s*")


def _is_online(text: str) -> bool:
    """依標題＋活動地點文字關鍵字判斷是否為線上／視訊活動（純字面判斷，非語意理解）。"""
    return bool(_ONLINE_RE.search(text))


def parse_calendar(html: str, base_url: str) -> tuple[list[dict], str | None]:
    """從單月月曆頁解析候選活動與「下個月」連結；純函式、不連網。

    回傳 (candidates, next_month_url)：
    - candidates：月曆格線上每一次出現＝一筆候選 {title, date, url}，同一活動在不同天
      出現（或同天不同分組場次共用同一連結）皆各自成立一筆，不在此函式去重（去重鍵需要
      跨月合併後才能正確判斷，交給 fetch() 用 (日期,href,標題) 處理，見檔頭資料形態說明）。
    - next_month_url：「下個月」連結的絕對網址；找不到（改版或已無下一頁）回傳 None。

    月份標題與換月連結從 `<div class="calendar2">`（「上個月／YYYY年MM月／下個月」）讀取；
    月曆格線用 `table.table2.table-bordered` 定位。找不到任一結構代表改版，回傳空清單／None
    並留 stderr 痕跡，不假裝有資料。空白格（跨月溢出或月初/月底留白）本站原生就是空 `<td>`，
    無數字可比對，天然被跳過，不需另外判斷是否為相鄰月份的溢出格。
    """
    soup = BeautifulSoup(html, "html.parser")

    nav = soup.select_one("div.calendar2")
    month_m = _MONTH_HEADER_RE.search(nav.get_text()) if nav else None
    if month_m is None:
        print("[jct] 月曆頁找不到「YYYY年MM月」標題（可能改版），已跳過此頁", file=sys.stderr)
        return [], None
    year, month = int(month_m.group(1)), int(month_m.group(2))

    next_url = None
    for a in nav.select("a.btn5"):
        if a.get_text(strip=True) == "下個月" and a.get("href"):
            next_url = urljoin(base_url, a["href"].strip())
            break

    table = soup.select_one("table.table2.table-bordered")
    if table is None:
        print(f"[jct] {year}年{month}月月曆頁找不到月曆格線 table（可能改版）", file=sys.stderr)
        return [], next_url

    candidates: list[dict] = []
    week_rows = table.select(":scope > tbody > tr")[1:]  # 第一列是星期標題列，跳過
    for tr in week_rows:
        for cell in tr.find_all("td", recursive=False):
            day_strong = cell.select_one("td.text4 strong")
            day_text = day_strong.get_text(strip=True) if day_strong else ""
            if not day_text.isdigit():
                continue  # 空白格：跨月溢出或月初/月底留白，本站原生如此，非資料缺失
            try:
                date_iso = dt.date(year, month, int(day_text)).isoformat()
            except ValueError:
                print(f"[jct] {year}年{month}月 {day_text} 日不合法，已跳過", file=sys.stderr)
                continue

            for a in cell.select("a[href*='event_news_detail']"):
                href = (a.get("href") or "").strip()
                if not href:
                    continue
                title = _BULLET_RE.sub("", a.get_text(strip=True))
                title = " ".join(title.split())
                if not title:
                    print(f"[jct] {date_iso} 有課程連結但標題為空，已跳過：{href[:60]}", file=sys.stderr)
                    continue
                candidates.append(
                    {"title": title, "date": date_iso, "url": urljoin(base_url, href)}
                )
    return candidates, next_url


def parse_detail(html: str) -> dict:
    """從活動詳情頁解析 (location, credits, ctext)；純函式、不連網。

    地點標籤有「活動地點」（一般排定活動，如研討會）與「課程地點」（實作課程／工作坊）兩種
    前綴，2026-07-10 v2 實測皆會出現，一併比對。「訓練課程」模組總表型的詳情頁（見
    jct_detail_bundle.html）沒有地點與學分認可單位，優雅回傳空值，不是解析失敗。
    """
    soup = BeautifulSoup(html, "html.parser")

    location = ""
    for line in soup.get_text("\n").split("\n"):
        line = line.strip()
        if line.startswith("活動地點") or line.startswith("課程地點"):
            location = _PLACE_LINE_RE.sub("", line).strip()
            break

    credits: dict[str, float] = {}
    ctext = ""
    credit_label = soup.find("span", class_="title5", string=re.compile("學分認可單位"))
    if credit_label is not None and credit_label.parent is not None:
        full_text = " ".join(credit_label.parent.get_text().split())
        value_text = full_text.split("：", 1)[-1].strip() if "：" in full_text else ""
        if value_text:
            num_m = _CREDIT_NUM_RE.search(value_text)
            if num_m and "護理" in value_text and float(num_m.group(1)) > 0:
                credits = {"pro": float(num_m.group(1))}
            else:
                ctext = value_text

    return {"location": location, "credits": credits, "ctext": ctext}


def _dedupe_candidates(candidates: list[dict]) -> list[dict]:
    """依 (日期, href, 標題) 三元鍵去重，保留首次出現的順序；純函式、不連網。

    三元鍵理由見檔頭「資料形態」：同一 href 在不同天出現（多場次共用報名連結）或同一天
    出現在多筆不同標題（同場論壇的不同分組）皆是合法的個別事件，只有三者完全相同才視為
    真重複（如同一天同一格內因版面問題重複輸出同一連結）。
    """
    seen: set[tuple[str, str, str]] = set()
    out: list[dict] = []
    for cand in candidates:
        key = (cand["date"], cand["url"], cand["title"])
        if key in seen:
            continue
        seen.add(key)
        out.append(cand)
    return out


def _exclude_ondemand(candidates: list[dict]) -> list[dict]:
    """把標題命中數位課程／教學影片關鍵字的候選整批排除；純函式、不連網。

    Lin 2026-07-10 指示：醫策會的數位課程／教學影片一律不收錄上站（本站定位為排定場次的
    課程／研討會彙整）。放在去重後、選詳情前這個位置過濾，是最省請求的做法——命中的候選
    連詳情頁都不必抓。排除筆數以彙總形式 stderr 留痕，不可無聲丟棄（呼應本專案「靜默失敗
    必須可見」的一貫原則）。
    """
    kept = [c for c in candidates if not _ONDEMAND_RE.search(c["title"])]
    excluded = len(candidates) - len(kept)
    if excluded:
        print(
            f"[jct] 排除數位課程/教學影片 {excluded} 筆（Lin 2026-07-10 指示不收錄）",
            file=sys.stderr,
        )
    return kept


def _select_for_detail(candidates: list[dict], today: dt.date) -> tuple[list[dict], list[dict]]:
    """依時間窗篩選，切成（要抓詳情的近期候選, 只用月曆資料收錄的其餘窗內候選）；純函式、不連網。

    today 由呼叫端傳入（而非在此呼叫 dt.date.today()），使本函式可離線測試不依賴系統時鐘。
    時間窗與 normalize.window_filter 用同一組 cfg.SCRAPE 設定，先在這裡濾掉窗外候選可省下
    詳情頁請求（超窗的事件本來就會被 normalize 過濾掉，抓詳情也是白抓）。

    窗內超過 MAX_DETAIL_PAGES 時**不丟棄任何課程**（v2 首版曾整筆截掉，會重演 Lin 回報的
    「醫策會沒抓全」）：日期最近的前 N 筆抓詳情頁補地點／積分，其餘照樣收錄（標題／日期／
    報名連結月曆頁本來就有，零額外請求），地點積分留空待每週更新輪到它們變近期時自動補齊
    （merge 保留既有資料，資料會逐週變完整）。
    """
    floor = today - dt.timedelta(days=int(cfg.SCRAPE["keep_past_days"]))
    horizon = today + dt.timedelta(days=int(cfg.SCRAPE["window_days"]))

    windowed = [c for c in candidates if floor <= dt.date.fromisoformat(c["date"]) <= horizon]
    if len(windowed) < len(candidates):
        print(
            f"[jct] 月曆候選 {len(candidates)} 筆，時間窗（{floor}~{horizon}）外先濾掉 "
            f"{len(candidates) - len(windowed)} 筆省請求，剩 {len(windowed)} 筆",
            file=sys.stderr,
        )
    windowed.sort(key=lambda c: (c["date"], c["title"]))

    with_detail = windowed[:MAX_DETAIL_PAGES]
    without_detail = windowed[MAX_DETAIL_PAGES:]
    if without_detail:
        print(
            f"[jct] 時間窗內 {len(windowed)} 筆，禮貌上限只對日期最近的 {MAX_DETAIL_PAGES} 筆"
            f"抓詳情頁；其餘 {len(without_detail)} 筆以月曆資料收錄（地點／積分待後續週期補齊）",
            file=sys.stderr,
        )
    return with_detail, without_detail


def fetch() -> list[dict]:
    all_candidates: list[dict] = []
    url: str | None = CALENDAR_URL
    for _ in range(MONTHS_TO_FETCH):
        if url is None:
            print(
                "[jct] 月曆換月連結未找到（可能改版或退化成 postback），"
                f"僅涵蓋已抓到的 {len(all_candidates)} 筆候選所在月份，涵蓋範圍可能不足三個月",
                file=sys.stderr,
            )
            break
        html = base.download(url)
        month_candidates, next_url = parse_calendar(html, url)
        all_candidates.extend(month_candidates)
        url = next_url

    candidates = _exclude_ondemand(_dedupe_candidates(all_candidates))
    with_detail, without_detail = _select_for_detail(candidates, dt.date.today())

    events: list[dict] = []
    for cand in with_detail:
        detail_html = base.download(cand["url"])
        detail = parse_detail(detail_html)
        title = cand["title"]
        events.append(
            base.make_event(
                date=cand["date"],
                title=title,
                url=cand["url"],
                location=detail["location"],
                credits=detail["credits"],
                online=_is_online(f"{title} {detail['location']}"),
                ctext=detail["ctext"],
            )
        )
    # 禮貌上限外的窗內課程照樣收錄：月曆頁已給標題／日期／報名連結，零額外請求；
    # 地點／積分留空，待每週更新輪到它們成為「日期最近的前 N 筆」時自動補齊
    for cand in without_detail:
        title = cand["title"]
        events.append(
            base.make_event(
                date=cand["date"],
                title=title,
                url=cand["url"],
                online=_is_online(title),
            )
        )
    return events
