"""Purpose: psy（社團法人中華民國精神衛生護理學會）來源 parser —— 消息公告列表單頁解析（無詳情二段式）。
Input:  base.download(URL) 取得的 HTML（消息公告表格頁，免登入）。
Output: fetch() -> list[dict]；parse(html) 為純函式，供 tests/fixtures/psy_list.html 離線測試使用。

頁面結構（2026-07-10 實測 https://www.psynurse.org.tw/news.aspx，實際會 302 重導向到
news.aspx?pages=1，requests 會自動跟隨）：
消息公告表格逐列為 <a href="news1.aspx?entry=NNN" title="...">連結文字</a>，「發佈日期」欄
（表格第一欄）是公告本身的發布時間（西元），不是研習會實際辦理日期；真正的辦理日期藏在
「主題」欄錨點文字裡的民國日期（如「115年8月6日」），須用 base.roc_date_to_iso() 抽取。

本頁混雜大量非研習公告（會員信函、抗議聲明、政府公告、會員代表名單、考試複查、專書購書
說明等），因此只保留同時滿足下列兩條件的錨點：①標題含「研習」關鍵字 ②標題可抽出民國日期；
兩者缺一即跳過——非研習公告本來就沒有辦理日期可抽，天然被濾掉，不需要額外的公告類型判斷。
實測頁面 10 筆公告中僅 2 筆同時滿足兩條件（entry=1229、entry=1226）；另有一筆陷阱案例
（entry=999，標題含「(111.7.11調整)」可被 roc_date_to_iso 解析成日期，但不含「研習」關鍵字），
用來驗證關鍵字條件不可省略。

解析策略（關鍵字掃描＋從連結文字正則抽民國日期）參考 Taiwan_Nurse_CNT（MIT 授權，
https://github.com/TLAN1012/Taiwan_Nurse_CNT）scrape_psy 的邏輯，程式碼依本專案慣例重寫。

無積分欄（credits={} 恆空）；url 優先採用 news1.aspx?entry=NNN 的絕對網址（同一 entry 的
「發佈日期」欄與「主題」欄各自成一個錨點，內容重複，只取第一次出現），href 缺失或明顯不可用
（如 javascript: 偽連結）時退回列表頁本身。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bs4 import BeautifulSoup

from scripts.sources import base

URL = "https://www.psynurse.org.tw/news.aspx"

_KEYWORD_RE = re.compile(r"研習")
_ONLINE_RE = re.compile(r"線上|直播|視訊|遠距|webinar", re.IGNORECASE)


def _is_online(text: str) -> bool:
    """依標題文字關鍵字判斷是否為線上／視訊活動（純字面判斷，非語意理解）。"""
    return bool(_ONLINE_RE.search(text))


def parse(html: str) -> list[dict]:
    """解析消息公告列表頁，只保留含「研習」關鍵字且能抽出民國辦理日期的公告；純函式、不連網。

    同一 entry 在表格中會出現兩次（日期欄＋主題欄各一個錨點，文字相同），用 href+title 當
    去重鍵只取第一次出現。
    """
    soup = BeautifulSoup(html, "html.parser")
    seen: set[str] = set()
    events: list[dict] = []
    for a in soup.find_all("a", href=True):
        title = " ".join(a.get_text().split())
        if not title or not _KEYWORD_RE.search(title):
            continue
        date_iso = base.roc_date_to_iso(title)
        if date_iso is None:
            continue
        href = a["href"].strip()
        key = f"{href}|{title}"
        if key in seen:
            continue
        seen.add(key)
        url = URL if not href or href.lower().startswith("javascript:") else urljoin(URL, href)
        events.append(
            base.make_event(
                date=date_iso,
                title=title,
                url=url,
                credits={},
                online=_is_online(title),
            )
        )
    return events


def fetch() -> list[dict]:
    html = base.download(URL)
    return parse(html)
