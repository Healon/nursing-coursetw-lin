"""normalize.py 純函式測試：欄位強制、去重合併、時間窗。全部離線。"""
from __future__ import annotations

import datetime as dt

from config import site as cfg
from scripts import normalize


def ev(**kw) -> dict:
    base = {
        "date": "2026-08-01",
        "title": "測試活動",
        "location": "台北市",
        "credits": {},
        "cat": "other",
        "src": "demo",
        "online": False,
        "ondemand": False,
        "region": "north",
        "ctext": "",
        "url": "https://example.org/1",
    }
    base.update(kw)
    return base


class TestNormalizeEvent:
    def test_valid_event_passes_through(self):
        assert normalize.normalize_event(ev()) == ev()

    def test_bad_date_dropped(self):
        assert normalize.normalize_event(ev(date="2026/08/01")) is None
        assert normalize.normalize_event(ev(date="")) is None

    def test_missing_title_or_url_dropped(self):
        assert normalize.normalize_event(ev(title="   ")) is None
        assert normalize.normalize_event(ev(url="")) is None

    def test_unknown_enums_fall_back_visibly(self):
        out = normalize.normalize_event(ev(cat="nope", region="mars"))
        assert out is not None
        assert out["cat"] == normalize.CAT_FALLBACK
        assert out["region"] == normalize.REGION_FALLBACK

    def test_credits_coercion(self):
        out = normalize.normalize_event(
            ev(credits={"pro": "2", "bogus": 3, "np": 0, "quality": 1.5})
        )
        assert out is not None
        assert out["credits"] == {"pro": 2, "quality": 1.5}

    def test_title_whitespace_collapsed(self):
        out = normalize.normalize_event(ev(title="  A   B\n C "))
        assert out is not None
        assert out["title"] == "A B C"


class TestMergeAndWindow:
    def test_fresh_wins_on_same_key(self):
        merged = normalize.merge([ev(ctext="舊")], [ev(ctext="新")])
        assert len(merged) == 1
        assert merged[0]["ctext"] == "新"

    def test_events_of_missing_source_survive(self):
        # 單一來源暫時掛掉時，它的舊活動不可以被清空
        merged = normalize.merge([ev(title="只存在於舊資料")], [ev(title="新活動")])
        assert {e["title"] for e in merged} == {"只存在於舊資料", "新活動"}

    def test_window_filter_bounds(self):
        today = dt.date(2026, 7, 10)
        keep_past = int(cfg.SCRAPE["keep_past_days"])
        horizon = int(cfg.SCRAPE["window_days"])
        inside_past = ev(date=(today - dt.timedelta(days=keep_past)).isoformat(), title="剛結束")
        too_old = ev(date=(today - dt.timedelta(days=keep_past + 1)).isoformat(), title="太舊")
        too_far = ev(date=(today + dt.timedelta(days=horizon + 1)).isoformat(), title="太遠")
        ondemand_far = ev(
            date=(today + dt.timedelta(days=horizon + 1)).isoformat(),
            title="隨選不受限",
            ondemand=True,
        )
        kept = normalize.window_filter([inside_past, too_old, too_far, ondemand_far], today)
        assert {e["title"] for e in kept} == {"剛結束", "隨選不受限"}

    def test_removed_source_events_dropped(self):
        kept = normalize.window_filter([ev(src="ghost")], dt.date(2026, 7, 10))
        assert kept == []

    def test_sort_by_date_then_title(self):
        events = [ev(date="2026-09-01", title="B"), ev(date="2026-08-01", title="C"), ev(date="2026-09-01", title="A")]
        ordered = normalize.sort_events(events)
        assert [(e["date"], e["title"]) for e in ordered] == [
            ("2026-08-01", "C"),
            ("2026-09-01", "A"),
            ("2026-09-01", "B"),
        ]
