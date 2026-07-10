"""Purpose: pure data functions — validate/coerce raw events, dedupe/merge, time-window filter.
Input:  parser 產出的事件 dict 與既有的 events.json 內容。
Output: 乾淨、去重、依日期排序的事件清單（供 data/events.json 使用）。
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import site as cfg

CAT_FALLBACK = "other"
REGION_FALLBACK = "tbd"


def _warn(msg: str) -> None:
    print(f"[normalize] {msg}", file=sys.stderr)


def dedupe_key(ev: dict) -> tuple[str, str, str]:
    """去重鍵：(日期, 來源, 去空白標題)。同鍵視為同一活動，新資料覆蓋舊資料。"""
    return (
        str(ev.get("date", "")),
        str(ev.get("src", "")),
        "".join(str(ev.get("title", "")).split()),
    )


def normalize_event(ev: dict) -> dict | None:
    """把一筆事件強制轉成 schema；無法使用時回傳 None 並輸出可見警告（不靜默丟棄）。"""
    date = str(ev.get("date", "")).strip()
    try:
        dt.date.fromisoformat(date)
    except ValueError:
        _warn(f"drop event, bad date {date!r}: {str(ev.get('title', ''))[:50]}")
        return None

    title = " ".join(str(ev.get("title", "")).split())
    url = str(ev.get("url", "")).strip()
    if not title or not url:
        _warn(f"drop event on {date}: missing title or url")
        return None

    cat = str(ev.get("cat", ""))
    if cat not in cfg.CATEGORIES:
        if cat:
            _warn(f"unknown category {cat!r} -> {CAT_FALLBACK}: {title[:50]}")
        cat = CAT_FALLBACK

    region = str(ev.get("region", ""))
    if region not in cfg.REGIONS:
        if region:
            _warn(f"unknown region {region!r} -> {REGION_FALLBACK}: {title[:50]}")
        region = REGION_FALLBACK

    credits: dict = {}
    for key, val in (ev.get("credits") or {}).items():
        if key not in cfg.CREDIT_TYPES:
            _warn(f"unknown credit type {key!r} dropped: {title[:50]}")
            continue
        try:
            num = float(val)
        except (TypeError, ValueError):
            _warn(f"bad credit value {val!r} for {key!r} dropped: {title[:50]}")
            continue
        if num > 0:
            credits[key] = int(num) if num.is_integer() else num

    return {
        "date": date,
        "title": title,
        "location": " ".join(str(ev.get("location", "")).split()),
        "credits": credits,
        "cat": cat,
        "src": str(ev.get("src", "")),
        "online": bool(ev.get("online", False)),
        "ondemand": bool(ev.get("ondemand", False)),
        "region": region,
        "ctext": str(ev.get("ctext", "")).strip(),
        "url": url,
    }


def merge(previous: list[dict], fresh: list[dict]) -> list[dict]:
    """以去重鍵聯集合併；同鍵時新資料獲勝。

    舊資料在這裡永不刪除：單一來源暫時掛掉時不可清空它的歷史資料，
    過期淘汰交給 window_filter 處理。代價是「來源主動撤下的活動」會留到過期為止，
    此取捨已記錄於 docs/ARCHITECTURE.md。
    """
    merged = {dedupe_key(e): e for e in previous}
    for e in fresh:
        merged[dedupe_key(e)] = e
    return list(merged.values())


def window_filter(events: list[dict], today: dt.date) -> list[dict]:
    """保留設定時間窗內的活動；來源已從 config 移除的活動一併淘汰（附警告）。"""
    floor = today - dt.timedelta(days=int(cfg.SCRAPE["keep_past_days"]))
    horizon = today + dt.timedelta(days=int(cfg.SCRAPE["window_days"]))
    kept: list[dict] = []
    for e in events:
        if e.get("src") not in cfg.SOURCES:
            _warn(f"drop event of removed source {e.get('src')!r}: {str(e.get('title', ''))[:50]}")
            continue
        if e.get("ondemand"):
            kept.append(e)  # 線上隨選課程不受時間窗限制
            continue
        d = dt.date.fromisoformat(e["date"])
        if floor <= d <= horizon:
            kept.append(e)
    return kept


def sort_events(events: list[dict]) -> list[dict]:
    return sorted(events, key=lambda e: (e["date"], e["title"]))
