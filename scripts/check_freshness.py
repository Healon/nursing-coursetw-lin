"""Offline watchdog for the sources that GitHub Actions cannot fetch directly.

The checker reads repository JSON only.  It never imports a source scraper and
never issues a network request.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import twna_freshness

STATUS_PATH = ROOT / "data" / "status.json"
MANUAL_TWNA_PATH = ROOT / "data" / "manual_twna.json"
TAIPEI = ZoneInfo("Asia/Taipei")
LOCAL_SOURCES = ("jct", "tnpa")


def _aware_now(now: dt.datetime) -> dt.datetime:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now 必須包含時區")
    return now.astimezone(TAIPEI)


def _local_source_failure(
    status_snapshot: dict,
    code: str,
    today: dt.date,
    max_age_days: int,
) -> str | None:
    try:
        value = status_snapshot["sources"][code]["last_success"]
        last_success = dt.date.fromisoformat(value)
    except (KeyError, TypeError, ValueError):
        return f"{code}: 缺少或無效的 last_success"

    age = (today - last_success).days
    if age < 0:
        return f"{code}: last_success 位於未來（{last_success.isoformat()}）"
    if age > max_age_days:
        return f"{code}: 已 {age} 天未成功（最近 {last_success.isoformat()}）"
    return None


def _twna_failure(manual_twna: dict, now: dt.datetime, max_age_days: int) -> str | None:
    try:
        latest = twna_freshness.latest_manual_activity(manual_twna)
    except (AttributeError, TypeError, ValueError):
        return "twna: 缺少或無效的手動檢查時間"

    if latest is None:
        return "twna: 缺少或無效的手動檢查時間"
    if latest > now:
        return f"twna: 手動檢查時間位於未來（{latest.isoformat()}）"

    age = now - latest
    if age > dt.timedelta(days=max_age_days):
        return f"twna: 已超過 {max_age_days} 天未手動檢查（最近 {latest.isoformat()}）"
    return None


def evaluate(
    status_snapshot: dict,
    manual_twna: dict,
    now: dt.datetime,
    max_age_days: int = 8,
) -> list[str]:
    """Return one failure per missing, invalid, future, or stale required source."""
    if max_age_days < 0:
        raise ValueError("max_age_days 不可為負數")
    local_now = _aware_now(now)

    failures: list[str] = []
    for code in LOCAL_SOURCES:
        failure = _local_source_failure(
            status_snapshot,
            code,
            local_now.date(),
            max_age_days,
        )
        if failure:
            failures.append(failure)

    twna_failure = _twna_failure(manual_twna, local_now, max_age_days)
    if twna_failure:
        failures.append(twna_failure)
    return failures


def _load_dict(path: Path) -> dict:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def main(
    argv: list[str] | None = None,
    *,
    now: dt.datetime | None = None,
    status_path: Path | None = None,
    manual_path: Path | None = None,
) -> int:
    parser = argparse.ArgumentParser(description="檢查本機／手動來源資料是否過期（完全離線）")
    parser.add_argument("--max-age-days", type=int, default=8, help="允許的最長天數（預設 8）")
    args = parser.parse_args(argv)
    if args.max_age_days < 0:
        parser.error("--max-age-days 不可為負數")

    failures = evaluate(
        _load_dict(status_path or STATUS_PATH),
        _load_dict(manual_path or MANUAL_TWNA_PATH),
        now or dt.datetime.now(TAIPEI),
        args.max_age_days,
    )
    if failures:
        for failure in failures:
            print(failure)
        return 1

    print(f"fresh: jct、tnpa、twna 均在 {args.max_age_days} 天期限內")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
