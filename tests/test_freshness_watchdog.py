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


# NOW＝2026-07-20（一）09:00 台北。天數窗語意（2026-07-26 隨日更導入）：
# jct/tnpa 允許 2 天（昨天更新是健康常態，容忍一次沒開機），twna 允許 8 天（人工週頻＋1 天寬限）。
FRESH_MANUAL = {"manual_checked_at": "2026-07-19T14:00:00+08:00"}


def test_yesterday_update_is_fresh():
    assert check_freshness.evaluate(snapshot("2026-07-19"), FRESH_MANUAL, NOW) == []


def test_all_sources_stale_beyond_windows_report_each():
    # jct/tnpa 距今 8 天（>2）；twna 距今 8 天又 17 小時（>8 天）
    failures = check_freshness.evaluate(
        snapshot("2026-07-12"),
        {"manual_checked_at": "2026-07-11T16:00:00+08:00"},
        NOW,
    )

    assert [failure.split(":", 1)[0] for failure in failures] == ["jct", "tnpa", "twna"]


def test_local_source_window_boundary_two_days_fresh_three_days_stale():
    assert check_freshness.evaluate(snapshot("2026-07-18"), FRESH_MANUAL, NOW) == []

    failures = check_freshness.evaluate(snapshot("2026-07-17"), FRESH_MANUAL, NOW)
    assert [failure.split(":", 1)[0] for failure in failures] == ["jct", "tnpa"]


def test_twna_window_boundary_eight_days_inclusive():
    # 恰好 8 天整（now - latest == 8d）：邊界當下仍新鮮（比照 twna_freshness.is_fresh 契約）
    exactly_8d = {"manual_checked_at": "2026-07-12T09:00:00+08:00"}
    assert check_freshness.evaluate(snapshot("2026-07-19"), exactly_8d, NOW) == []

    over_8d = {"manual_checked_at": "2026-07-12T08:59:59+08:00"}
    failures = check_freshness.evaluate(snapshot("2026-07-19"), over_8d, NOW)
    assert [failure.split(":", 1)[0] for failure in failures] == ["twna"]


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
