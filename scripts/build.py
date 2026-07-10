"""Purpose: render templates/index.html.tpl + config + data into the final self-contained index.html.
Input:  config/site.py、data/events.json、data/status.json、templates/index.html.tpl。
Output: 專案根目錄 index.html（產生的檔案，勿手改）。

樣板注入採 marker 區塊置換：THEME（CSS 變數）、CONFIG／STATUS／EVENTS（JS 常數），
加上 @@TOKEN@@ 純文字替換。任何 marker 缺漏或 token 殘留都會 raise：
壞掉的 build 必須大聲失敗，不可以靜默發布半成品頁面。
"""
from __future__ import annotations

import json
import re
import sys
from html import escape as html_escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import site as cfg

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = ROOT / "templates" / "index.html.tpl"
OUTPUT_PATH = ROOT / "index.html"
EVENTS_PATH = ROOT / "data" / "events.json"
STATUS_PATH = ROOT / "data" / "status.json"

MARKERS = ("THEME", "CONFIG", "STATUS", "EVENTS")


class BuildError(RuntimeError):
    """Template problems must crash loudly — never publish a half-rendered page silently."""


def js_json(value: object) -> str:
    """serialize for embedding inside a <script> block（把 </ 轉義，避免 </script> 提前關閉標籤）。"""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def theme_css(theme: dict) -> str:
    lines = [f"  --{key.replace('_', '-')}: {value};" for key, value in theme.items()]
    return ":root {\n" + "\n".join(lines) + "\n}"


def replace_marker(html: str, name: str, payload: str) -> str:
    pattern = re.compile(rf"(/\* {name}:START \*/).*?(/\* {name}:END \*/)", re.DOTALL)
    # 用函式替換：payload 內的反斜線（如 <\/）不可被當成 regex 反向參照解析
    html, count = pattern.subn(lambda m: f"{m.group(1)}\n{payload}\n{m.group(2)}", html)
    if count != 1:
        raise BuildError(f"marker {name} matched {count} times in template (expected exactly 1)")
    return html


def make_config_blob() -> dict:
    """前端只需要 label 對照表，keywords 等爬蟲設定不進頁面。"""
    return {
        "site": dict(cfg.SITE),
        "categories": {code: item["label"] for code, item in cfg.CATEGORIES.items()},
        "creditTypes": dict(cfg.CREDIT_TYPES),
        "regions": {code: item["label"] for code, item in cfg.REGIONS.items()},
        "sources": {code: item["label"] for code, item in cfg.SOURCES.items()},
    }


def render(
    template: str,
    *,
    config_blob: dict,
    events: list[dict],
    status: dict,
    tokens: dict[str, str],
) -> str:
    out = template
    out = replace_marker(out, "THEME", theme_css(cfg.THEME))
    out = replace_marker(out, "CONFIG", f"const CONFIG = {js_json(config_blob)};")
    out = replace_marker(out, "STATUS", f"const SOURCE_STATUS = {js_json(status)};")
    out = replace_marker(out, "EVENTS", f"const EVENTS = {js_json(events)};")
    for token, value in tokens.items():
        out = out.replace(f"@@{token}@@", html_escape(str(value)))
    leftovers = sorted(set(re.findall(r"@@[A-Z_]+@@", out)))
    if leftovers:
        raise BuildError(f"unreplaced tokens in output: {leftovers}")
    return out


def main() -> None:
    if not TEMPLATE_PATH.exists():
        raise BuildError(f"template not found: {TEMPLATE_PATH}")
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    data = json.loads(EVENTS_PATH.read_text(encoding="utf-8")) if EVENTS_PATH.exists() else {"meta": {}, "events": []}
    status = json.loads(STATUS_PATH.read_text(encoding="utf-8")) if STATUS_PATH.exists() else {}

    tokens = {
        "SITE_TITLE": cfg.SITE["title"],
        "SITE_SUBTITLE": cfg.SITE["subtitle"],
        "DISCLAIMER": cfg.SITE["disclaimer"],
        "FOOTER_NOTE": cfg.SITE["footer_note"],
        "UPDATED_AT": data.get("meta", {}).get("generated", "") or "（尚未更新）",
    }
    html = render(
        template,
        config_blob=make_config_blob(),
        events=data.get("events", []),
        status=status,
        tokens=tokens,
    )
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print(f"[build] wrote {OUTPUT_PATH.name} ({len(html):,} bytes, {len(data.get('events', []))} events)")


if __name__ == "__main__":
    main()
