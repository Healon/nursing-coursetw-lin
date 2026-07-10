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
