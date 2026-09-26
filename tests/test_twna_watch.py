"""twna_watch 監看器測試：頁面辨識、資料夾掃描與發布交接。全部離線、只碰 tmp_path。"""
from __future__ import annotations

import json
import subprocess

import pytest

from scripts import twna_watch

TWNA_HTML = "<html><div id='ctl00_ContentPlaceHolder1_GridView1'>x</div><a href='/ActSign/PUB/'>y</a></html>"


class TestIsTwnaPage:
    def test_real_markers_detected(self):
        assert twna_watch.is_twna_page(TWNA_HTML) is True

    def test_other_aspnet_site_rejected(self):
        # 只有 GridView 容器、沒有站台特徵：別站的 ASP.NET 另存頁不可誤認（寧漏勿誤）
        assert twna_watch.is_twna_page("<div id='ctl00_ContentPlaceHolder1_GridView1'></div>") is False

    def test_plain_page_rejected(self):
        assert twna_watch.is_twna_page("<html><body>一般網頁</body></html>") is False


class TestScanFolder:
    def test_finds_only_twna_html(self, tmp_path):
        (tmp_path / "course.html").write_text(TWNA_HTML, encoding="utf-8")
        (tmp_path / "other.html").write_text("<html>別的頁</html>", encoding="utf-8")
        (tmp_path / "note.txt").write_text(TWNA_HTML, encoding="utf-8")  # 副檔名不符
        hits = twna_watch.scan_folder(tmp_path)
        assert [f.name for f in hits] == ["course.html"]

    def test_stale_file_ignored(self, tmp_path):
        f = tmp_path / "old.html"
        f.write_text(TWNA_HTML, encoding="utf-8")
        # 用 now 參數模擬「檔案已超過 MAX_AGE_DAYS」，不真的改系統時間
        future = f.stat().st_mtime + (twna_watch.MAX_AGE_DAYS + 1) * 86400
        assert twna_watch.scan_folder(tmp_path, now=future) == []


def test_broken_candidate_rows_are_not_archived_or_recorded(monkeypatch, tmp_path):
    page = tmp_path / "broken.html"
    page.write_text(
        """<html><body><a href="/ActSign/PUB/">TWNA</a>
        <table id="ctl00_ContentPlaceHolder1_GridView1">
        <tr><th>辦理日期</th><th>活動名稱</th></tr>
        <tr><td data-th="辦理日期">壞日期</td><td data-th="活動名稱"></td></tr>
        </table></body></html>""",
        encoding="utf-8",
    )
    data = tmp_path / "manual_twna.json"
    original = {"manual_imported_at": "2026-07-10T00:00:00+08:00", "events": []}
    data.write_text(json.dumps(original), encoding="utf-8")
    monkeypatch.setattr(twna_watch, "DATA_PATH", data)

    with pytest.raises(ValueError, match="全部.*解析失敗"):
        twna_watch.process(page)

    assert page.exists()
    assert not (tmp_path / twna_watch.ARCHIVE_DIRNAME).exists()
    assert json.loads(data.read_text(encoding="utf-8")) == original


def test_process_only_imports_and_archives(monkeypatch, tmp_path):
    """process 只寫原始資料並歸檔；自己重建會留下未提交的衍生產物（2026-08-16 事故）。"""
    page = tmp_path / "course.html"
    page.write_text(TWNA_HTML, encoding="utf-8")
    monkeypatch.setattr(twna_watch.import_twna_page, "run", lambda f, data: {"added": 2, "skipped_dupe": 0})
    monkeypatch.setattr(
        twna_watch.subprocess, "run", lambda *a, **kw: pytest.fail("process 不可自己重建或呼叫外部指令")
    )

    stats = twna_watch.process(page)

    assert stats["added"] == 2
    assert not page.exists()
    assert (tmp_path / twna_watch.ARCHIVE_DIRNAME / "course.html").exists()


class TestMainHandsOffToLocalUpdate:
    def _patch(self, monkeypatch, tmp_path, exit_code=0):
        monkeypatch.setattr(twna_watch, "DOWNLOAD_DIR", tmp_path)
        calls = []
        monkeypatch.setattr(
            twna_watch.subprocess, "run",
            lambda cmd, **kw: calls.append(cmd) or subprocess.CompletedProcess(cmd, exit_code),
        )
        return calls

    def test_twna_page_triggers_local_update(self, monkeypatch, tmp_path):
        (tmp_path / "course.html").write_text(TWNA_HTML, encoding="utf-8")
        calls = self._patch(monkeypatch, tmp_path)

        assert twna_watch.main([]) == 0
        assert len(calls) == 1
        assert calls[0][-1].endswith("scripts/local_update.py")
        # 匯入與歸檔由 local_update 負責，監看器本身不動檔案
        assert (tmp_path / "course.html").exists()

    def test_local_update_failure_is_propagated(self, monkeypatch, tmp_path):
        (tmp_path / "course.html").write_text(TWNA_HTML, encoding="utf-8")
        self._patch(monkeypatch, tmp_path, exit_code=1)

        assert twna_watch.main([]) == 1

    def test_non_twna_file_does_nothing(self, monkeypatch, tmp_path):
        (tmp_path / "other.html").write_text("<html>別的頁</html>", encoding="utf-8")
        calls = self._patch(monkeypatch, tmp_path)

        assert twna_watch.main([]) == 0
        assert calls == []
