import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

from scripts import check_freshness

TZ = dt.timezone(dt.timedelta(hours=8))
NOW = dt.datetime(2026, 7, 20, 9, 0, tzinfo=TZ)
ROOT = Path(__file__).resolve().parents[1]


def snapshot(last_success="2026-07-12"):
    return {
        "sources": {
            "jct": {"last_success": last_success},
            "tnpa": {"last_success": last_success},
        }
    }


def test_current_sunday_is_fresh():
    manual = {"manual_checked_at": "2026-07-19T14:00:00+08:00"}
    assert check_freshness.evaluate(snapshot("2026-07-19"), manual, NOW) == []


def test_missed_sunday_makes_next_monday_fail_even_if_previous_sunday_succeeded():
    failures = check_freshness.evaluate(
        snapshot("2026-07-12"),
        {"manual_checked_at": "2026-07-12T16:00:00+08:00"},
        NOW,
    )

    assert [failure.split(":", 1)[0] for failure in failures] == ["jct", "tnpa", "twna"]


def test_older_cycle_reports_each_source():
    failures = check_freshness.evaluate(
        snapshot("2026-07-11"),
        {"manual_checked_at": "2026-07-11T08:59:59+08:00"},
        NOW,
    )
    assert any("jct" in failure for failure in failures)
    assert any("tnpa" in failure for failure in failures)
    assert any("twna" in failure for failure in failures)


def test_missing_or_invalid_state_fails_closed():
    failures = check_freshness.evaluate({}, {}, NOW)
    assert len(failures) == 3


def test_invalid_dates_fail_closed_with_source_names():
    failures = check_freshness.evaluate(
        snapshot("not-a-date"),
        {"manual_checked_at": "not-a-timestamp"},
        NOW,
    )
    assert [failure.split(":", 1)[0] for failure in failures] == ["jct", "tnpa", "twna"]


def test_future_dates_fail_closed():
    failures = check_freshness.evaluate(
        snapshot("2026-07-21"),
        {"manual_checked_at": "2026-07-20T09:00:01+08:00"},
        NOW,
    )
    assert len(failures) == 3


def test_cli_reads_injected_local_files_and_returns_zero(tmp_path, capsys):
    status_path = tmp_path / "status.json"
    manual_path = tmp_path / "manual_twna.json"
    status_path.write_text(json.dumps(snapshot("2026-07-19")), encoding="utf-8")
    manual_path.write_text(
        json.dumps({"manual_checked_at": "2026-07-19T14:00:00+08:00"}),
        encoding="utf-8",
    )

    exit_code = check_freshness.main(
        [],
        now=NOW,
        status_path=status_path,
        manual_path=manual_path,
    )

    assert exit_code == 0
    assert "fresh" in capsys.readouterr().out.lower()


def test_cli_returns_one_and_prints_one_line_per_failure(tmp_path, capsys):
    status_path = tmp_path / "missing-status.json"
    manual_path = tmp_path / "missing-manual.json"

    exit_code = check_freshness.main(
        [],
        now=NOW,
        status_path=status_path,
        manual_path=manual_path,
    )

    output_lines = capsys.readouterr().out.splitlines()
    assert exit_code == 1
    assert len(output_lines) == 3
    assert [line.split(":", 1)[0] for line in output_lines] == ["jct", "tnpa", "twna"]


def test_script_entrypoint_runs_from_repository_root():
    result = subprocess.run(
        [sys.executable, "scripts/check_freshness.py", "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
