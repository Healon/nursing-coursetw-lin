"""twna_watch 監看器測試：頁面辨識與資料夾掃描。全部離線、只碰 tmp_path。"""
from __future__ import annotations

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
