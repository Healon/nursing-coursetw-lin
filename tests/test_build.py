"""build.py 測試：marker 注入、token 替換、逃逸與失敗必吵。全部離線。"""
from __future__ import annotations

import json

import pytest

from scripts import build

MINI_TPL = """<html><style>
/* THEME:START */ placeholder /* THEME:END */
</style><body><h1>@@SITE_TITLE@@</h1><p>@@SITE_SUBTITLE@@ @@DISCLAIMER@@ @@FOOTER_NOTE@@ @@UPDATED_AT@@</p>
<script>
/* CONFIG:START */ const CONFIG = null; /* CONFIG:END */
/* STATUS:START */ const SOURCE_STATUS = null; /* STATUS:END */
/* EVENTS:START */ const EVENTS = null; /* EVENTS:END */
</script></body></html>"""


def tokens(**kw) -> dict:
    base = {
        "SITE_TITLE": "T",
        "SITE_SUBTITLE": "S",
        "DISCLAIMER": "D",
        "FOOTER_NOTE": "F",
        "UPDATED_AT": "U",
    }
    base.update(kw)
    return base


class TestRender:
    def test_markers_replaced(self):
        out = build.render(MINI_TPL, config_blob={"a": 1}, events=[{"t": 1}], status={"s": 2}, tokens=tokens())
        assert 'const CONFIG = {"a":1};' in out
        assert 'const EVENTS = [{"t":1}];' in out
        assert 'const SOURCE_STATUS = {"s":2};' in out
        assert "@@" not in out
        assert "placeholder" not in out

    def test_script_close_tag_escaped_but_roundtrips(self):
        evil = [{"title": "</script><script>alert(1)</script>"}]
        out = build.render(MINI_TPL, config_blob={}, events=evil, status={}, tokens=tokens())
        blob = out.split("/* EVENTS:START */")[1].split("/* EVENTS:END */")[0].strip()
        assert "</script>" not in blob  # 不可讓事件內容提前關閉 <script>
        payload = blob.removeprefix("const EVENTS = ").removesuffix(";")
        assert json.loads(payload)[0]["title"] == "</script><script>alert(1)</script>"

    def test_token_values_are_html_escaped(self):
        out = build.render(MINI_TPL, config_blob={}, events=[], status={}, tokens=tokens(SITE_TITLE='<b>"x"</b>'))
        assert "<b>" not in out.split("<h1>")[1].split("</h1>")[0]
        assert "&lt;b&gt;" in out

    def test_missing_marker_raises(self):
        with pytest.raises(build.BuildError):
            build.render("<html>no markers</html>", config_blob={}, events=[], status={}, tokens=tokens())

    def test_leftover_token_raises(self):
        with pytest.raises(build.BuildError):
            build.render(MINI_TPL + "@@UNKNOWN_TOKEN@@", config_blob={}, events=[], status={}, tokens=tokens())

    def test_backslash_in_payload_survives(self):
        # regex 替換若誤用字串 repl，payload 內的反斜線會被吃掉，此測試防回歸
        out = build.render(MINI_TPL, config_blob={}, events=[{"t": "a\\b</x"}], status={}, tokens=tokens())
        blob = out.split("/* EVENTS:START */")[1].split("/* EVENTS:END */")[0].strip()
        payload = blob.removeprefix("const EVENTS = ").removesuffix(";")
        assert json.loads(payload)[0]["t"] == "a\\b</x"


class TestManualSourceDates:
    """manual_source_dates()：手動來源顯示「人工匯入／確認日」而非 pipeline 執行日；
    缺檔／壞檔回空 dict 不擋 build（頁面顯示「尚無人工紀錄」）。"""

    def test_returns_newer_of_two_timestamps_as_taipei_date(self, monkeypatch, tmp_path):
        path = tmp_path / "manual_twna.json"
        path.write_text(json.dumps({
            "manual_imported_at": "2026-07-20T16:00:00+08:00",
            "manual_checked_at": "2026-07-24T09:30:00+08:00",
        }), encoding="utf-8")
        monkeypatch.setattr(build, "MANUAL_TWNA_PATH", path)
        assert build.manual_source_dates() == {"twna": "2026-07-24"}

    def test_missing_file_returns_empty(self, monkeypatch, tmp_path):
        monkeypatch.setattr(build, "MANUAL_TWNA_PATH", tmp_path / "nope.json")
        assert build.manual_source_dates() == {}

    def test_broken_json_returns_empty(self, monkeypatch, tmp_path):
        path = tmp_path / "manual_twna.json"
        path.write_text("{broken", encoding="utf-8")
        monkeypatch.setattr(build, "MANUAL_TWNA_PATH", path)
        assert build.manual_source_dates() == {}

    def test_no_manual_activity_returns_empty(self, monkeypatch, tmp_path):
        path = tmp_path / "manual_twna.json"
        path.write_text(json.dumps({"manual_imported_at": "", "events": []}), encoding="utf-8")
        monkeypatch.setattr(build, "MANUAL_TWNA_PATH", path)
        assert build.manual_source_dates() == {}

    def test_config_blob_carries_manual_dates_and_executions(self):
        blob = build.make_config_blob()
        assert "manualUpdatedAt" in blob  # 模板 manual 分支消費這個鍵
        assert set(blob["sourceExecutions"]) == set(blob["sources"])
        assert blob["sourceExecutions"]["twna"] == "manual"


class TestRealTemplate:
    def test_real_template_renders_clean(self):
        template = build.TEMPLATE_PATH.read_text(encoding="utf-8")
        out = build.render(
            template,
            config_blob=build.make_config_blob(),
            events=[],
            status={"overall": "ok", "sources": {}},
            tokens=tokens(),
        )
        assert "@@" not in out
        assert "build 時注入" not in out  # 三個 script marker 的占位字樣必須全數被換掉
        assert "--primary:" in out  # THEME 變數已注入
