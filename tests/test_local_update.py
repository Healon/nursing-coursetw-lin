"""local_update 一鍵更新的離線測試：防狂打護欄、TWNA 摘要與 git 競爭處理。"""
from __future__ import annotations

import datetime as dt
import subprocess

from scripts import local_update


def result(code=0, out="", err=""):
    return subprocess.CompletedProcess([], code, out, err)


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

    def test_both_succeeded_yesterday_requires_scrape(self):
        snap = {"sources": {"jct": {"last_success": "2026-07-10"}, "tnpa": {"last_success": "2026-07-10"}}}
        assert local_update.sources_fresh_today(snap, "2026-07-11") is False

    def test_missing_source_requires_scrape(self):
        # status.json 還沒有該來源（例如剛部署、從未成功）→ 必須爬，不可誤判成「今天抓過」
        assert local_update.sources_fresh_today({"sources": {}}, "2026-07-10") is False

    def test_empty_snapshot_requires_scrape(self):
        assert local_update.sources_fresh_today({}, "2026-07-10") is False


class TestPushWithOneRebaseRetry:
    def test_push_retries_once_after_non_fast_forward(self, monkeypatch):
        responses = iter(
            [
                result(1, err="non-fast-forward"),
                result(0),
                result(0),
            ]
        )
        calls = []
        monkeypatch.setattr(local_update, "_git", lambda *args: calls.append(args) or next(responses))

        ok, detail = local_update.push_with_one_rebase_retry()

        assert ok is True
        assert detail == ""
        assert calls == [
            ("push", "origin", "main"),
            ("pull", "--rebase", "origin", "main"),
            ("push", "origin", "main"),
        ]

    def test_push_conflict_aborts_rebase_and_does_not_retry_again(self, monkeypatch):
        responses = iter(
            [
                result(1, err="non-fast-forward"),
                result(1, err="CONFLICT"),
                result(0),
            ]
        )
        calls = []
        monkeypatch.setattr(local_update, "_git", lambda *args: calls.append(args) or next(responses))

        ok, detail = local_update.push_with_one_rebase_retry()

        assert ok is False
        assert "CONFLICT" in detail
        assert calls == [
            ("push", "origin", "main"),
            ("pull", "--rebase", "origin", "main"),
            ("rebase", "--abort"),
        ]


class TestTwnaSummary:
    NOW = dt.datetime(2026, 7, 19, 16, 0, tzinfo=dt.timezone(dt.timedelta(hours=8)))

    def test_import_summary_takes_precedence(self):
        assert local_update.twna_summary(2, 3, {}, self.NOW) == "匯入 2 檔、新增 3 筆"

    def test_recent_confirmation_without_file_is_explicit(self):
        raw = {"manual_checked_at": "2026-07-19T14:00:00+08:00"}
        assert local_update.twna_summary(0, 0, raw, self.NOW) == "本週已確認，無新匯入檔"

    def test_stale_or_unconfirmed_data_is_explicit(self):
        raw = {"manual_imported_at": "2026-07-10T14:00:00+08:00"}
        assert local_update.twna_summary(0, 0, raw, self.NOW) == "尚未核對，本次沿用上次資料"


def test_twna_scan_error_uses_failure_notification_path(monkeypatch, tmp_path):
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    monkeypatch.setattr(local_update.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(local_update, "_git", lambda *args: result(0))
    monkeypatch.setattr(
        local_update.twna_watch,
        "scan_folder",
        lambda folder: (_ for _ in ()).throw(ValueError("broken saved page")),
    )
    notifications = []
    monkeypatch.setattr(local_update, "_notify", notifications.append)

    exit_code = local_update.main(["--no-push"])

    assert exit_code == 1
    assert notifications == [
        "本機更新失敗（twna import），詳見終端機或 /tmp/nursing-local-update.log"
    ]
