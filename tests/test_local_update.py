"""local_update 一鍵更新的離線測試：防狂打護欄、單實例鎖、TWNA 摘要、git 競爭處理與同步死結回歸。"""
from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys

import pytest

from scripts import local_update


def result(code=0, out="", err=""):
    return subprocess.CompletedProcess([], code, out, err)


class TestSingleInstanceLock:
    """flock 單實例鎖：同時只允許一份實例（儀表板背景觸發／launchd／手動可能撞期）。
    flock 綁 open file description，同一行程兩次 open 也會互斥，可在單測內驗證。"""

    def test_second_acquire_fails_until_first_released(self, monkeypatch, tmp_path):
        monkeypatch.setattr(local_update, "LOCK_PATH", tmp_path / "test.lock")

        first = local_update.acquire_single_instance_lock()
        assert first is not None
        assert local_update.acquire_single_instance_lock() is None  # 鎖被持有

        first.close()  # 釋放後可再取得
        second = local_update.acquire_single_instance_lock()
        assert second is not None
        second.close()


class TestDirtyBeyondData:
    def test_clean_tree_is_ok(self):
        assert local_update.dirty_beyond_data("") == []

    def test_data_artifacts_only_is_ok(self):
        porcelain = " M data/events.json\n M data/status.json\n M index.html\n M data/manual_twna.json\n"
        assert local_update.dirty_beyond_data(porcelain) == []

    def test_non_data_change_is_flagged(self):
        porcelain = " M data/events.json\n M scripts/sources/jct.py\n?? notes.txt\n"
        assert local_update.dirty_beyond_data(porcelain) == ["scripts/sources/jct.py", "notes.txt"]


class TestDirtyDerived:
    def test_only_derived_artifacts_are_restorable(self):
        porcelain = " M data/events.json\n M data/manual_twna.json\n M index.html\n M data/status.json\n"
        assert local_update.dirty_derived(porcelain) == ["data/events.json", "index.html", "data/status.json"]

    def test_source_data_is_never_restored(self):
        assert local_update.dirty_derived(" M data/manual_twna.json\n") == []

    def test_untracked_file_is_skipped(self):
        # checkout 還原不了未追蹤檔，列進去只會讓 git 報錯
        assert local_update.dirty_derived("?? index.html\n") == []


class TestSourcesToRebuild:
    def test_stale_local_sources_are_scraped(self):
        assert local_update.sources_to_rebuild(False, False) == ["jct", "tnpa"]

    def test_leftover_twna_data_is_rebuilt_even_when_scraped_today(self):
        assert local_update.sources_to_rebuild(True, True) == ["twna"]

    def test_nothing_to_do(self):
        assert local_update.sources_to_rebuild(True, False) == []


def _git_run(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _write_all(root, paths, text):
    for p in paths:
        (root / p).write_text(text, encoding="utf-8")


@pytest.fixture
def stuck_clone(tmp_path, monkeypatch):
    """重現 2026-08-16 的卡死狀態：本機資料產物未提交，雲端又推了改到同一批衍生產物的 commit。

    全程只用暫存 git repo；隔離使用者全域 git 設定，避免簽章或 hook 影響測試。
    """
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for key in ("GIT_AUTHOR_NAME", "GIT_COMMITTER_NAME"):
        monkeypatch.setenv(key, "test")
    for key in ("GIT_AUTHOR_EMAIL", "GIT_COMMITTER_EMAIL"):
        monkeypatch.setenv(key, "test@example.com")

    origin = tmp_path / "origin.git"
    _git_run(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    cloud = tmp_path / "cloud"
    _git_run(tmp_path, "init", "-q", "-b", "main", str(cloud))
    _git_run(cloud, "remote", "add", "origin", str(origin))
    (cloud / "data").mkdir()
    _write_all(cloud, local_update.DATA_PATHS, "v1\n")
    _git_run(cloud, "add", "-A")
    _git_run(cloud, "commit", "-q", "-m", "seed")
    _git_run(cloud, "push", "-q", "origin", "main")

    local = tmp_path / "local"
    _git_run(tmp_path, "clone", "-q", str(origin), str(local))

    # 雲端每日更新：只改衍生產物（雲端永不改寫 manual_twna.json）
    _write_all(cloud, local_update.DERIVED_PATHS, "cloud\n")
    _git_run(cloud, "commit", "-q", "-am", "chore: daily events update")
    _git_run(cloud, "push", "-q", "origin", "main")

    # 本機：twna 匯入改了原始資料，舊版監看器又重建了衍生產物，全部未提交
    _write_all(local, local_update.DATA_PATHS, "local\n")
    return local


class TestSyncWithCloud:
    def test_recovers_from_uncommitted_derived_artifacts(self, stuck_clone, monkeypatch):
        # 負對照：舊流程直接 pull 必定被擋，證明 fixture 真的重現了死結
        plain = subprocess.run(
            ["git", "pull", "--ff-only", "origin", "main"], cwd=stuck_clone, capture_output=True, text=True
        )
        assert plain.returncode != 0

        monkeypatch.setattr(local_update, "ROOT", stuck_clone)
        ok, detail = local_update.sync_with_cloud()

        assert ok, detail
        for p in local_update.DERIVED_PATHS:
            assert (stuck_clone / p).read_text(encoding="utf-8") == "cloud\n"
        assert (stuck_clone / "data/manual_twna.json").read_text(encoding="utf-8") == "local\n"
        head = subprocess.run(["git", "rev-parse", "HEAD", "origin/main"], cwd=stuck_clone,
                              capture_output=True, text=True).stdout.split()
        assert head[0] == head[1]

    def test_unpushed_local_commit_is_reported_not_rewritten(self, stuck_clone, monkeypatch):
        # 本機有未推送的 commit（例如上次推送因網路中斷）→ 回報失敗，不自動 rebase 或 reset
        _git_run(stuck_clone, "commit", "-q", "-am", "local data commit")
        before = subprocess.run(["git", "rev-parse", "HEAD"], cwd=stuck_clone,
                                capture_output=True, text=True).stdout.strip()

        monkeypatch.setattr(local_update, "ROOT", stuck_clone)
        ok, detail = local_update.sync_with_cloud()

        assert ok is False
        assert detail
        after = subprocess.run(["git", "rev-parse", "HEAD"], cwd=stuck_clone,
                               capture_output=True, text=True).stdout.strip()
        assert after == before


def test_leftover_twna_data_is_rebuilt_when_local_sources_are_fresh(monkeypatch, tmp_path):
    """8/16 遺留的 twna 匯入：jct/tnpa 今天已抓過也要重建 twna，否則還原衍生產物後課程會消失。"""
    today = dt.date.today().isoformat()
    status_path = tmp_path / "status.json"
    status_path.write_text(json.dumps(
        {"sources": {"jct": {"last_success": today}, "tnpa": {"last_success": today}}}
    ), encoding="utf-8")
    monkeypatch.setattr(local_update, "LOCK_PATH", tmp_path / "test.lock")
    monkeypatch.setattr(local_update, "STATUS_PATH", status_path)
    monkeypatch.setattr(local_update, "TWNA_DOWNLOAD_DIR", tmp_path / "no-inbox")
    monkeypatch.setattr(local_update, "TWNA_DATA_PATH", tmp_path / "missing.json")
    monkeypatch.setattr(local_update, "_notify", lambda message: None)

    def fake_git(*args):
        if args[:2] == ("status", "--porcelain") and "--" in args:
            return result(0, " M data/manual_twna.json\n")
        return result(0)

    runs = []
    monkeypatch.setattr(local_update, "_git", fake_git)
    monkeypatch.setattr(local_update.subprocess, "run", lambda cmd, **kw: runs.append(cmd) or result(0))

    assert local_update.main(["--no-push"]) == 0

    update_calls = [cmd for cmd in runs if str(cmd[1]).endswith("update.py")]
    assert update_calls == [
        [sys.executable, str(local_update.ROOT / "scripts" / "update.py"), "--sources", "twna"]
    ]


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
    downloads = tmp_path / "download-twna"
    downloads.mkdir()
    monkeypatch.setattr(local_update, "TWNA_DOWNLOAD_DIR", downloads)
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
