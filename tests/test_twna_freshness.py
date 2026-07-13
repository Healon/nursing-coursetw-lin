import datetime as dt
import json

from scripts import twna_freshness

TZ = dt.timezone(dt.timedelta(hours=8))
NOW = dt.datetime(2026, 7, 19, 14, 0, tzinfo=TZ)


def test_latest_activity_uses_newer_checked_timestamp():
    raw = {
        "manual_imported_at": "2026-07-10T00:00:00+08:00",
        "manual_checked_at": "2026-07-18T14:00:00+08:00",
    }
    assert twna_freshness.latest_manual_activity(raw) == dt.datetime(2026, 7, 18, 14, 0, tzinfo=TZ)


def test_freshness_boundary_is_inclusive():
    raw = {"manual_checked_at": "2026-07-12T14:00:00+08:00"}
    assert twna_freshness.is_fresh(raw, NOW, 7) is True
    assert twna_freshness.is_fresh(raw, NOW + dt.timedelta(seconds=1), 7) is False


def test_mark_checked_preserves_events(tmp_path):
    path = tmp_path / "manual_twna.json"
    path.write_text(json.dumps({"events": [{"title": "x"}]}), encoding="utf-8")
    twna_freshness.mark_checked(path, NOW)
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["events"] == [{"title": "x"}]
    assert raw["manual_checked_at"] == "2026-07-19T14:00:00+08:00"
