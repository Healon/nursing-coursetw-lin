"""status.py 測試：三態健康快照、overall 判斷、last_success 沿用、CI 閘門。全部離線。

compute() 只納入 enabled 來源（監控範圍＝自動更新範圍），因此 TestCompute 不依賴
config 的即時 enabled 狀態，一律用 monkeypatch 把測試用到的來源固定為 enabled，
避免日後有人在 config 開關來源時（如 demo 轉正式後停用）測試莫名紅掉。
"""
from __future__ import annotations

import datetime as dt

import pytest

from config import site as cfg
from scripts import status

NOW = dt.datetime(2026, 7, 10, 15, 0, 0).astimezone()


def oc(state: str, count: int = 0, msg: str = "") -> dict:
    return {"status": state, "count": count, "message": msg}


class TestCompute:
    @pytest.fixture(autouse=True)
    def _enable_test_sources(self, monkeypatch):
        # 測試情境固定：demo 與 nuna 視為 enabled，不受 config 即時開關影響
        monkeypatch.setitem(cfg.SOURCES, "demo", dict(cfg.SOURCES["demo"], enabled=True))
        monkeypatch.setitem(cfg.SOURCES, "nuna", dict(cfg.SOURCES["nuna"], enabled=True))

    def test_ok_refreshes_last_success(self):
        snap = status.compute({"demo": oc("ok", 5)}, {}, now=NOW)
        assert snap["sources"]["demo"]["last_success"] == "2026-07-10"
        assert snap["overall"] == "ok"

    def test_error_keeps_previous_last_success(self):
        prev = {"sources": {"demo": {"status": "ok", "count": 5, "last_success": "2026-07-01", "message": ""}}}
        snap = status.compute({"demo": oc("error", 0, "boom")}, prev, now=NOW)
        assert snap["sources"]["demo"]["last_success"] == "2026-07-01"
        assert snap["overall"] == "down"  # 唯一有狀態的來源 error → down

    def test_empty_counts_as_partial_never_ok(self):
        # empty＝成功但 0 筆，是最危險的靜默失敗態，不可以是綠燈
        snap = status.compute({"demo": oc("ok", 3), "nuna": oc("empty", 0)}, {}, now=NOW)
        assert snap["overall"] == "partial"

    def test_source_not_run_this_time_carries_previous_state(self):
        prev = {"sources": {"nuna": {"status": "error", "count": 0, "last_success": "", "message": "x"}}}
        snap = status.compute({"demo": oc("ok", 3)}, prev, now=NOW)
        assert snap["sources"]["nuna"]["status"] == "error"
        assert snap["overall"] == "partial"

    def test_source_removed_from_config_is_pruned(self):
        prev = {"sources": {"ghost": {"status": "ok", "count": 1, "last_success": "2026-01-01", "message": ""}}}
        snap = status.compute({"demo": oc("ok", 1)}, prev, now=NOW)
        assert "ghost" not in snap["sources"]

    def test_disabled_source_excluded_from_snapshot_and_overall(self, monkeypatch):
        # 監控範圍＝enabled：停用來源（如 twna 手動來源尚未填資料）是刻意狀態非故障，
        # 不可讓它的 empty/error 舊態常駐快照、把 overall 拖成 partial（黃橫幅常駐）
        monkeypatch.setitem(cfg.SOURCES, "twna", dict(cfg.SOURCES["twna"], enabled=False))
        prev = {"sources": {"twna": {"status": "empty", "count": 0, "last_success": "", "message": ""}}}
        snap = status.compute({"demo": oc("ok", 3)}, prev, now=NOW)
        assert "twna" not in snap["sources"]
        assert snap["overall"] == "ok"
        # 即使本次被 --sources 強制跑了，disabled 來源也不進健康快照
        snap2 = status.compute({"demo": oc("ok", 3), "twna": oc("empty", 0)}, prev, now=NOW)
        assert "twna" not in snap2["sources"]
        assert snap2["overall"] == "ok"

    def test_no_source_states_is_down(self):
        # 完全沒有來源狀態＝空站，不可以是綠燈
        snap = status.compute({}, {}, now=NOW)
        assert snap["overall"] == "down"


class TestFinalizeOutcomes:
    """存活數修正：抓到卻整批壞掉必須顯性化成 error，不可被原始筆數蒙混成 ok。"""

    def test_error_outcome_preserved(self):
        out = status.finalize_outcomes({"x": oc("error", 0, "boom")}, {})
        assert out["x"]["status"] == "error"

    def test_all_survive_stays_ok_no_message(self):
        out = status.finalize_outcomes({"x": oc("ok", 24)}, {"x": 24})
        assert out["x"] == {"status": "ok", "count": 24, "message": ""}

    def test_partial_survive_ok_with_loss_message(self):
        out = status.finalize_outcomes({"x": oc("ok", 24)}, {"x": 20})
        assert out["x"]["status"] == "ok"
        assert out["x"]["count"] == 20
        assert "4" in out["x"]["message"]  # 損耗 4 筆要留痕

    def test_fetched_but_all_invalid_becomes_error(self):
        # 問題 1 核心：抓到 5 筆但 normalize 全丟棄 → 不可以是 ok，必須 error
        out = status.finalize_outcomes({"x": oc("ok", 5)}, {"x": 0})
        assert out["x"]["status"] == "error"
        assert out["x"]["count"] == 0
        assert "改版" in out["x"]["message"]

    def test_genuinely_empty_stays_empty(self):
        out = status.finalize_outcomes({"x": oc("empty", 0)}, {})
        assert out["x"]["status"] == "empty"

    def test_finalize_then_compute_does_not_refresh_last_success_on_mass_failure(self):
        # 端對端：整批壞掉經 finalize 變 error，compute 就不會把 last_success 刷成今天
        # （用 config 內真實來源 nuna，因為 compute 會剪掉未登記於 SOURCES 的來源）
        prev = {"sources": {"nuna": {"status": "ok", "count": 5, "last_success": "2026-07-01", "message": ""}}}
        finalized = status.finalize_outcomes({"nuna": oc("ok", 5)}, {"nuna": 0})
        snap = status.compute(finalized, prev, now=NOW)
        assert snap["sources"]["nuna"]["status"] == "error"
        assert snap["sources"]["nuna"]["last_success"] == "2026-07-01"
        assert snap["overall"] == "down"


class TestCheckGate:
    def test_down_exits_1(self):
        assert status.check({"overall": "down"}) == 1

    def test_partial_and_ok_exit_0(self):
        assert status.check({"overall": "partial"}) == 0
        assert status.check({"overall": "ok"}) == 0

    def test_missing_overall_treated_as_down(self):
        assert status.check({}) == 1
