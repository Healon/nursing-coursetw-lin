"""Purpose: source registry — dynamically load parser modules and run them with per-source error isolation.
Input:  config.site.SOURCES；scripts/sources/<code>.py 模組（各自實作 fetch() -> list[dict]）。
Output: select_source_codes() 決定執行來源；run_all() -> (events, outcomes)。
每個被執行的來源都有明確 outcome，失敗不中斷其他來源。
"""
from __future__ import annotations

import importlib
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from config import site as cfg

VALID_EXECUTIONS = {"cloud", "local", "manual"}


def select_source_codes(
    only: list[str] | None = None,
    profile: str | None = None,
) -> list[str]:
    """Return source codes selected explicitly or by execution profile."""
    if only is not None and profile is not None:
        raise ValueError("only and profile are mutually exclusive")
    if profile is not None and profile not in VALID_EXECUTIONS:
        raise ValueError(f"unknown execution profile: {profile}")
    if only is not None:
        return list(only)
    return [
        code
        for code, src in cfg.SOURCES.items()
        if src.get("enabled", False)
        and (profile is None or src.get("execution", "cloud") == profile)
    ]


def run_all(
    only: list[str] | None = None,
    profile: str | None = None,
) -> tuple[list[dict], dict[str, dict]]:
    """Run source parsers.

    only/profile 只能擇一。兩者皆未指定時跑所有 enabled 來源；指定 only 時無視
    enabled 與 execution（方便單獨測一個來源）；指定 profile 時只跑該執行環境的 enabled 來源。
    單一來源的任何例外都被隔離成該來源的 error outcome，不影響其他來源繼續執行；
    例外訊息會進 status.json 與頁尾警示，絕不靜默吞掉。
    """
    events: list[dict] = []
    outcomes: dict[str, dict] = {}
    for code in select_source_codes(only=only, profile=profile):
        if code not in cfg.SOURCES:
            continue
        try:
            module = importlib.import_module(f"scripts.sources.{code}")
            fetched = module.fetch()
            for ev in fetched:
                ev["src"] = code
            events.extend(fetched)
            outcomes[code] = {
                "status": "ok" if fetched else "empty",
                "count": len(fetched),
                "message": "" if fetched else "抓取成功但 0 筆，可能網站改版或選擇器失效",
            }
        except Exception as exc:  # noqa: BLE001 — 逐來源隔離，錯誤透過 status 呈現
            outcomes[code] = {
                "status": "error",
                "count": 0,
                "message": f"{type(exc).__name__}: {exc}",
            }
            print(f"[scrape] {code} FAILED: {exc}", file=sys.stderr)
            traceback.print_exc()
    if only is not None:
        unknown = [code for code in only if code not in cfg.SOURCES]
        for code in unknown:
            outcomes[code] = {
                "status": "error",
                "count": 0,
                "message": "來源代碼不存在於 config/site.py 的 SOURCES",
            }
            print(f"[scrape] unknown source code: {code}", file=sys.stderr)
    return events, outcomes
