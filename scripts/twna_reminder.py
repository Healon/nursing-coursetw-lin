"""提醒維護者人工核對 TWNA 課程；只讀本機狀態，不對 TWNA 發出請求。

TWNA 的 robots.txt 全站禁止自動抓取，因此本工具只在資料逾期且 download-twna/ 沒有待處理
另存頁時顯示 macOS 對話框。只有使用者明確按下「開啟課程頁」才會交由瀏覽器開頁；
程式不會自行開頁、下載或模擬瀏覽器操作。
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import twna_freshness, twna_watch
from scripts.sources import twna

PROJECT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT / "data" / "manual_twna.json"
DOWNLOADS = twna_watch.DOWNLOAD_DIR
SCRIPT = f'''button returned of (display dialog "台灣護理學會資料需要人工核對。請開啟課程頁，選擇「檔案 → 另存新檔 → 僅 HTML」，存到 {DOWNLOADS}。" with title "護理教育訓練網站" buttons {{"稍後提醒", "本週已確認", "開啟課程頁"}} default button "開啟課程頁")'''


def reminder_needed(data_path: Path, downloads: Path, now: dt.datetime) -> bool:
    """資料逾期且 download-twna/ 沒有待匯入 TWNA 另存頁時才需要提醒。"""
    raw = json.loads(data_path.read_text(encoding="utf-8"))
    if twna_freshness.has_activity_in_current_cycle(raw, now):
        return False
    return not bool(twna_watch.scan_folder(downloads, now=now.timestamp()))


def handle_choice(choice: str, data_path: Path, now: dt.datetime) -> int:
    """處理人工選擇；只有明確的開啟選項會呼叫系統瀏覽器。"""
    try:
        if choice == "稍後提醒":
            return 0
        if choice == "本週已確認":
            twna_freshness.mark_checked(data_path, now)
            return 0
        if choice == "開啟課程頁":
            subprocess.run(["open", twna.LIST_URL], check=True)
            return 0
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"[twna-reminder] 無法處理選擇：{exc}", file=sys.stderr)
        return 1

    print(f"[twna-reminder] 未知的對話框選擇：{choice!r}", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="提醒人工核對 TWNA 課程頁（零自動網路請求）")
    parser.add_argument("--data", type=Path, default=DATA_PATH)
    parser.add_argument("--downloads", type=Path, default=DOWNLOADS)
    args = parser.parse_args(argv)
    now = dt.datetime.now().astimezone()

    try:
        needed = reminder_needed(args.data, args.downloads, now)
    except (OSError, ValueError, TypeError) as exc:
        print(f"[twna-reminder] 無法讀取提醒狀態：{exc}", file=sys.stderr)
        return 1
    if not needed:
        return 0

    try:
        completed = subprocess.run(
            ["osascript", "-e", SCRIPT],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"[twna-reminder] 無法顯示提醒：{exc}", file=sys.stderr)
        return 1

    return handle_choice(completed.stdout.strip(), args.data, now)


if __name__ == "__main__":
    raise SystemExit(main())
