"""Purpose: shared helpers for source parsers — polite download, region/category inference,
           ROC-date conversion, event factory.
Input:  config/site.py settings.
Output: functions used by scripts/sources/<code>.py parser modules.
"""
from __future__ import annotations

import datetime as dt
import random
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from config import site as cfg

_last_request_ts = 0.0


def polite_delay() -> None:
    """對外請求之間的隨機延遲（爬蟲禮貌：不對來源網站造成壓力）。"""
    global _last_request_ts
    lo, hi = cfg.SCRAPE["delay_s"]
    wait = random.uniform(float(lo), float(hi)) - (time.time() - _last_request_ts)
    if wait > 0:
        time.sleep(wait)
    _last_request_ts = time.time()


def download(url: str) -> str:
    """抓取公開頁面。任何網路或 HTTP 錯誤一律 raise，禁止吞例外。

    例外由 registry（scripts/sources/__init__.py）統一接住並記進 status，
    parser 模組內不要自行 try/except 網路錯誤。
    """
    import requests  # 延遲載入：離線的 demo 來源與測試不需要安裝 requests

    polite_delay()
    resp = requests.get(
        url,
        timeout=int(cfg.SCRAPE["timeout_s"]),
        headers={"User-Agent": cfg.SCRAPE["user_agent"]},
    )
    resp.raise_for_status()
    if resp.encoding is None or resp.encoding.lower() == "iso-8859-1":
        # 部分老站不回 charset，requests 會誤設 iso-8859-1 造成中文亂碼
        resp.encoding = resp.apparent_encoding
    return resp.text


def download_curl(url: str) -> str:
    """用系統 curl 抓取公開頁面（憑證驗證交給作業系統信任清單），錯誤一律 raise。

    用途限定：極少數網站的憑證鏈含老式根憑證（無 X.509v3 擴充欄位），requests 底下的
    OpenSSL 嚴格驗證會拒收（實例：hospicenurse.org.tw 的 TWCA Global Root CA，
    2026-07-10 診斷），但 curl 用系統信任清單驗證可通過（macOS 本機與 GitHub Actions
    ubuntu 的 curl 皆內建）。curl 一樣做完整憑證驗證，這不是關閉驗證的後門；
    **禁止**為了省事把 verify=False 引進本專案（放棄傳輸層防護）。
    其餘來源一律用 download()；本函式與 download() 共用同一個禮貌延遲節流。
    """
    import subprocess

    polite_delay()
    proc = subprocess.run(
        [
            "curl", "-sS", "-L", "--fail",
            "--max-time", str(int(cfg.SCRAPE["timeout_s"])),
            "-A", cfg.SCRAPE["user_agent"],
            url,
        ],
        capture_output=True,
        timeout=int(cfg.SCRAPE["timeout_s"]) + 10,
    )
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", "replace").strip()[:200]
        raise RuntimeError(f"curl failed (exit {proc.returncode}) for {url}: {err}")
    return proc.stdout.decode("utf-8", "replace")


_ROC_DATE_RE = re.compile(
    r"(?<!\d)(?P<y>\d{2,3})[年/\-.](?P<m>\d{1,2})[月/\-.](?P<d>\d{1,2})日?(?!\d)"
)


def roc_date_to_iso(text: str) -> str | None:
    r"""從文字中抽出第一個民國日期並轉西元 ISO（YYYY-MM-DD）；辨認不出或日期不合法回傳 None。

    支援分隔樣式："115年9月4日"、"115/09/04"、"115-9-4"、"115.9.4"（月／日可一位或兩位數）。
    民國年 -> 西元年：year + 1911。

    年份前後以 (?<!\d)／(?!\d) 卡住邊界，避免把西元四位數年份（如 "2026/09/04"）的其中
    三碼誤吃成民國年；代價是呼叫端仍須確保傳入文字本身就是民國日期語境（例如已知來源固定用
    民國紀年的公告標題），本函式不負責判斷「這段文字是不是民國年」，只負責格式辨識與換算。
    """
    if not text:
        return None
    m = _ROC_DATE_RE.search(text)
    if not m:
        return None
    try:
        year = int(m.group("y")) + 1911
        month = int(m.group("m"))
        day = int(m.group("d"))
        return dt.date(year, month, day).isoformat()
    except ValueError:
        return None


def infer_region(text: str, *, online: bool = False) -> str:
    """依地點文字推斷地區代碼；線上活動歸 online；比對不到給 tbd（寧標未定，不亂猜）。"""
    lowered = text.lower()
    for code, region in cfg.REGIONS.items():
        if code in ("online", "tbd"):
            continue
        if any(kw and kw.lower() in lowered for kw in region.get("keywords", [])):
            return code
    online_kws = cfg.REGIONS.get("online", {}).get("keywords", [])
    if online or any(kw and kw.lower() in lowered for kw in online_kws):
        return "online"
    return "tbd"


def infer_category(title: str) -> str:
    """依標題關鍵字推斷類別代碼；比對不到落入 other。"""
    for code, category in cfg.CATEGORIES.items():
        if any(kw and kw in title for kw in category.get("keywords", [])):
            return code
    return "other"


_ADDR_LABEL_RE = re.compile(r"\s*地址\s*[:：].*$")
_PAREN_ADDR_RE = re.compile(r"\s*[（(][^（()）]*號[^（()）]*[)）]")
_TRAIL_ADDR_RE = re.compile(r"\s+\S*?[縣市區]\S*?[路街道段巷弄里村鄰]\S*?號\S*$")


def simplify_location(text: str) -> str:
    """只保留場館／機構／地區名稱，移除詳細門牌住址（卡片顯示規則，2026-07-10 Lin 訂）。

    使用者要的是「在哪個單位辦」，門牌屬冗餘細節，去掉讓卡片乾淨。只移除三種可安全辨識
    的門牌形態，其餘一律不動（寧可保留也不亂砍）：
      1. 「地址：…」引導的尾段整段去除。
      2. 括號內含「號」的門牌去除；如「(9F)」「(北棟)」不含號屬樓層／棟別，保留。
      3. 尾端「〔縣市區〕…〔路街道段巷弄〕…號」的完整門牌去除。
    砍完若為空（整段就是純門牌）則退回原文，不製造空地點。
    注意：本函式只管「顯示用」精簡；地區推斷仍用未精簡的原文（見 make_event），
    以免門牌被砍掉後連帶失去唯一的縣市線索。
    """
    if not text:
        return text
    out = _ADDR_LABEL_RE.sub("", text)
    out = _PAREN_ADDR_RE.sub("", out)
    out = _TRAIL_ADDR_RE.sub("", out)
    out = out.strip().rstrip(",，、").strip()
    return out or text.strip()


def make_event(
    *,
    date: str,
    title: str,
    url: str,
    location: str = "",
    credits: dict | None = None,
    cat: str = "",
    online: bool = False,
    ondemand: bool = False,
    region: str = "",
    ctext: str = "",
) -> dict:
    """事件工廠：補預設值；cat／region 留空時自動推斷。src 欄位由 registry 統一補上。

    location 顯示值經 simplify_location 去除門牌住址（只留場館／機構名）；但 region 推斷
    刻意用「未精簡的原文」，以免門牌被砍後失去唯一的縣市線索（如「亞東醫院…地址:新北市…」
    精簡成「亞東醫院…」後就判不出北部，改用原文即可保留該線索）。
    """
    title = " ".join(title.split())
    raw_location = " ".join(location.split())
    display_location = simplify_location(raw_location)
    return {
        "date": date,
        "title": title,
        "location": display_location,
        "credits": credits or {},
        "cat": cat or infer_category(title),
        "online": online,
        "ondemand": ondemand,
        "region": region or infer_region(f"{raw_location} {title}", online=online),
        "ctext": ctext.strip(),
        "url": url,
    }
