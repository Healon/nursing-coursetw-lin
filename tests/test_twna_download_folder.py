"""TWNA 人工另存頁的固定收件匣契約；全部離線。"""
from __future__ import annotations

import plistlib
from pathlib import Path

from scripts import local_update, twna_reminder, twna_watch


ROOT = Path(__file__).resolve().parents[1]
EXPECTED = ROOT / "download-twna"
WATCH_PLIST = ROOT / "scripts" / "launchd" / "com.lin.twna-watch.plist"


def test_all_twna_ingress_paths_use_project_download_folder():
    assert twna_watch.DOWNLOAD_DIR == EXPECTED
    assert twna_reminder.DOWNLOADS == EXPECTED
    assert local_update.TWNA_DOWNLOAD_DIR == EXPECTED


def test_download_folder_exists_and_saved_pages_are_gitignored():
    assert EXPECTED.is_dir()
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "/download-twna/*" in ignore
    assert "!/download-twna/.gitkeep" in ignore


def test_optional_watch_agent_watches_project_download_folder():
    plist = plistlib.loads(WATCH_PLIST.read_bytes())
    assert plist["WatchPaths"] == [str(EXPECTED)]
