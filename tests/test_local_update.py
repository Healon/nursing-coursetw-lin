"""local_update 一鍵更新的離線測試：工作區保護與防狂打護欄兩個純函式。不連網、不碰真 git。"""
from __future__ import annotations

from scripts import local_update


class TestDirtyBeyondData:
    def test_clean_tree_is_ok(self):
        assert local_update.dirty_beyond_data("") == []

    def test_data_artifacts_only_is_ok(self):
        porcelain = " M data/events.json\n M data/status.json\n M index.html\n M data/manual_twna.json\n"
        assert local_update.dirty_beyond_data(porcelain) == []

    def test_non_data_change_is_flagged(self):
        porcelain = " M data/events.json\n M scripts/sources/jct.py\n?? notes.txt\n"
        assert local_update.dirty_beyond_data(porcelain) == ["scripts/sources/jct.py", "notes.txt"]


class TestSourcesFreshToday:
    def test_both_fresh_today_skips_scrape(self):
        snap = {"sources": {"jct": {"last_success": "2026-07-10"}, "tnpa": {"last_success": "2026-07-10"}}}
        assert local_update.sources_fresh_today(snap, "2026-07-10") is True

    def test_one_stale_requires_scrape(self):
        snap = {"sources": {"jct": {"last_success": "2026-07-10"}, "tnpa": {"last_success": "2026-07-03"}}}
        assert local_update.sources_fresh_today(snap, "2026-07-10") is False

    def test_missing_source_requires_scrape(self):
        # status.json 還沒有該來源（例如剛部署、從未成功）→ 必須爬，不可誤判成「今天抓過」
        assert local_update.sources_fresh_today({"sources": {}}, "2026-07-10") is False

    def test_empty_snapshot_requires_scrape(self):
        assert local_update.sources_fresh_today({}, "2026-07-10") is False
