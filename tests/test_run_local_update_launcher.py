"""Static checks for the Finder/Dock launcher; never execute the live pipeline."""
from __future__ import annotations

import shlex
from pathlib import Path


LAUNCHER = Path(__file__).resolve().parents[1] / "scripts" / "run_local_update.command"


def test_missing_python_notification_passes_valid_applescript_argument():
    line = next(line.strip() for line in LAUNCHER.read_text().splitlines() if "osascript -e" in line)

    assert shlex.split(line) == [
        "osascript",
        "-e",
        'display notification "找不到專案 Python；請確認外接 SSD 已連接" '
        'with title "護理教育訓練網站"',
    ]
