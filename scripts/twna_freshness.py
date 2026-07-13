"""TWNA 手動匯入資料的新鮮度中繼資料工具；只讀寫本機 JSON，不連網。"""
from __future__ import annotations

import datetime as dt
import json
import os
import tempfile
from pathlib import Path

FIELDS = ("manual_imported_at", "manual_checked_at")


def _require_aware(value: dt.datetime, label: str) -> dt.datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} 必須包含時區")
    return value


def latest_manual_activity(raw: dict) -> dt.datetime | None:
    """回傳兩個手動活動時間中較新者；空欄位表示從未執行。"""
    values: list[dt.datetime] = []
    for field in FIELDS:
        value = raw.get(field, "")
        if value:
            parsed = dt.datetime.fromisoformat(value)
            values.append(_require_aware(parsed, field))
    return max(values) if values else None


def is_fresh(raw: dict, now: dt.datetime, max_age_days: int) -> bool:
    """最新手動活動未超過指定天數時為新鮮；邊界當下仍算新鮮。"""
    _require_aware(now, "now")
    latest = latest_manual_activity(raw)
    return latest is not None and now - latest <= dt.timedelta(days=max_age_days)


def _timestamp(now: dt.datetime) -> str:
    return _require_aware(now, "now").astimezone().isoformat(timespec="seconds")


def mark_imported(raw: dict, now: dt.datetime) -> None:
    """在已成功解析、合併的資料上，同時記錄匯入與人工檢查時間。"""
    stamp = _timestamp(now)
    raw["manual_imported_at"] = stamp
    raw["manual_checked_at"] = stamp


def write_json_atomic(path: Path, raw: dict) -> None:
    """以同目錄暫存檔原子取代 JSON，避免中途中斷留下半份檔案。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump(raw, handle, ensure_ascii=False, indent=1)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def mark_checked(path: Path, now: dt.datetime) -> None:
    """保留既有資料，只更新成功人工檢查的時間，並原子寫回。"""
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["manual_checked_at"] = _timestamp(now)
    write_json_atomic(path, raw)
