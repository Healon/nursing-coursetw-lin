"""TWNA 人工核對提醒測試；所有 macOS 互動都以 monkeypatch 攔截。"""
from __future__ import annotations

import datetime as dt
import json
import subprocess

from scripts import twna_reminder
from scripts.sources import twna

TZ = dt.timezone(dt.timedelta(hours=8))
NOW = dt.datetime(2026, 7, 19, 14, 0, tzinfo=TZ)
TWNA_HTML = "<div id='ContentPlaceHolder1_GridView1'><a href='/ActSign/'>課程</a></div>"


def test_pending_saved_page_suppresses_reminder(tmp_path):
    data = tmp_path / "manual.json"
    data.write_text('{"events": []}', encoding="utf-8")
    page = tmp_path / "twna.html"
    page.write_text(TWNA_HTML, encoding="utf-8")

    assert twna_reminder.reminder_needed(data, tmp_path, NOW) is False


def test_recent_manual_activity_suppresses_reminder(tmp_path):
    data = tmp_path / "manual.json"
    data.write_text(
        json.dumps({"events": [], "manual_checked_at": NOW.isoformat()}),
        encoding="utf-8",
    )

    assert twna_reminder.reminder_needed(data, tmp_path, NOW) is False


def test_stale_state_without_saved_page_needs_reminder(tmp_path):
    data = tmp_path / "manual.json"
    data.write_text(
        json.dumps(
            {
                "events": [],
                "manual_checked_at": (NOW - dt.timedelta(days=8)).isoformat(),
            }
        ),
        encoding="utf-8",
    )

    assert twna_reminder.reminder_needed(data, tmp_path, NOW) is True


def test_explicit_open_choice_is_only_path_that_opens_browser(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(twna_reminder.subprocess, "run", lambda args, **kw: calls.append(args))

    assert twna_reminder.handle_choice("稍後提醒", tmp_path / "x.json", NOW) == 0
    assert calls == []
    assert twna_reminder.handle_choice("開啟課程頁", tmp_path / "x.json", NOW) == 0
    assert calls == [["open", twna.LIST_URL]]


def test_confirmed_choice_records_check_without_opening(monkeypatch, tmp_path):
    data = tmp_path / "manual.json"
    data.write_text('{"events": []}', encoding="utf-8")
    calls = []
    monkeypatch.setattr(twna_reminder.subprocess, "run", lambda args, **kw: calls.append(args))

    assert twna_reminder.handle_choice("本週已確認", data, NOW) == 0
    assert calls == []
    assert "manual_checked_at" in data.read_text(encoding="utf-8")


def test_cli_suppressed_path_never_runs_osascript(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(twna_reminder, "reminder_needed", lambda *args: False)
    monkeypatch.setattr(twna_reminder.subprocess, "run", lambda *args, **kwargs: calls.append(args))

    assert twna_reminder.main(["--data", str(tmp_path / "manual.json"), "--downloads", str(tmp_path)]) == 0
    assert calls == []


def test_cli_returns_one_for_unreadable_state(tmp_path):
    assert twna_reminder.main(
        ["--data", str(tmp_path / "missing.json"), "--downloads", str(tmp_path)]
    ) == 1


def test_cli_returns_one_when_osascript_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(twna_reminder, "reminder_needed", lambda *args: True)

    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(1, args[0])

    monkeypatch.setattr(twna_reminder.subprocess, "run", fail)

    assert twna_reminder.main(["--data", str(tmp_path / "x.json"), "--downloads", str(tmp_path)]) == 1
