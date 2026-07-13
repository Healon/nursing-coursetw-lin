"""來源 parser 測試：demo 離線來源、registry 錯誤隔離、nuna／critical／psy／tnna／tnma／ni／tnpa／
hospice／ahqroc／jct／twna 的 fixture 驅動測試；另含 import_twna_page.py 另存頁匯入器的
合併邏輯測試。

真實來源的 parse() 測試以 tests/fixtures/ 的頁面快照驅動，同樣不連網；fixture 為實際頁面
裁剪後的真實結構（見各檔開頭註解的來源與抓取日期）。twna 為手動維護來源（不連網），測試改用
monkeypatch 換掉 DATA_PATH 指向 tmp_path，不動真實 data/manual_twna.json；
parse_saved_page()／import_twna_page.run() 兩者皆為純函式化設計（路徑與內容都由參數傳入），
測試直接傳 tmp_path，不需要 monkeypatch 也不會碰到真實 data/manual_twna.json。
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from config import site as cfg
from scripts import import_twna_page, normalize
from scripts.sources import (
    ahqroc,
    base,
    critical,
    demo,
    hospice,
    jct,
    ni,
    nuna,
    psy,
    run_all,
    select_source_codes,
    tnma,
    tnna,
    tnpa,
    twna,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class TestDemoSource:
    def test_every_event_normalizes_clean(self):
        events = demo.fetch()
        assert events
        for ev in events:
            ev = dict(ev, src="demo")
            assert normalize.normalize_event(ev) is not None

    def test_covers_every_enum_value(self):
        events = demo.fetch()
        assert {e["cat"] for e in events} == set(cfg.CATEGORIES)
        assert {e["region"] for e in events} == set(cfg.REGIONS)
        used_credit_types = {key for e in events for key in e["credits"]}
        assert used_credit_types == set(cfg.CREDIT_TYPES)

    def test_urls_are_clearly_fake(self):
        assert all(e["url"].startswith("https://example.org/") for e in demo.fetch())


class TestRegistry:
    def test_run_demo_only(self):
        events, outcomes = run_all(["demo"])
        assert outcomes["demo"]["status"] == "ok"
        assert outcomes["demo"]["count"] == len(events)
        assert all(e["src"] == "demo" for e in events)

    def test_unknown_source_code_reports_error_not_crash(self):
        events, outcomes = run_all(["no-such-source"])
        assert events == []
        assert outcomes["no-such-source"]["status"] == "error"


class TestSourceSelection:
    def test_profile_selects_only_enabled_matching_sources(self, monkeypatch):
        monkeypatch.setattr(cfg, "SOURCES", {
            "a": {"enabled": True, "execution": "cloud"},
            "b": {"enabled": True, "execution": "local"},
            "c": {"enabled": False, "execution": "cloud"},
        })
        assert select_source_codes(profile="cloud") == ["a"]
        assert select_source_codes(profile="local") == ["b"]

    def test_explicit_sources_override_enabled_and_execution(self, monkeypatch):
        monkeypatch.setattr(cfg, "SOURCES", {
            "a": {"enabled": False, "execution": "manual"},
        })
        assert select_source_codes(only=["a"]) == ["a"]

    def test_profile_and_only_are_mutually_exclusive(self):
        with pytest.raises(ValueError, match="only and profile"):
            select_source_codes(only=["a"], profile="cloud")


class TestNunaSource:
    """nuna.parse() 對 tests/fixtures/nuna_list.html（真實表格裁剪 7 列）的離線測試。"""

    def test_parse_extracts_all_fixture_rows(self):
        events = nuna.parse(_fixture("nuna_list.html"))
        assert len(events) == 7

    def test_events_normalize_clean(self):
        events = nuna.parse(_fixture("nuna_list.html"))
        assert events
        for ev in events:
            assert normalize.normalize_event(dict(ev, src="nuna")) is not None

    def test_dates_are_iso_format(self):
        events = nuna.parse(_fixture("nuna_list.html"))
        for ev in events:
            dt.date.fromisoformat(ev["date"])  # 格式不對會直接 raise ValueError

    def test_urls_are_absolute(self):
        events = nuna.parse(_fixture("nuna_list.html"))
        assert all(ev["url"].startswith("https://") for ev in events)

    def test_credit_total_and_breakdown_detail(self):
        events = nuna.parse(_fixture("nuna_list.html"))
        # 固定表格第 3 列（彰化中區場）為三細項積分：7.2 專業:1.8, 法規:3.6, 法規(性別):1.8
        # -> 依《醫事人員執業登記及繼續教育辦法》第13條四類拆解：pro=1.8、law=3.6+1.8=5.4，
        # 括號主題「性別」轉成 ctext 提示語（Lin 2026-07-10 訂，見 nuna._parse_credit_cell）。
        multi = next(e for e in events if "中區" in e["title"])
        assert multi["credits"] == {"pro": 1.8, "law": 5.4}
        assert multi["ctext"] == "含性別議題課程"

    def test_single_category_professional_credit(self):
        # 固定表格第 1 列（南部場，2026-09-09）為單一總數、無括號主題：3 專業: 3,
        events = nuna.parse(_fixture("nuna_list.html"))
        single = next(e for e in events if e["date"] == "2026-09-09")
        assert single["credits"] == {"pro": 3}
        assert single["ctext"] == ""

    def test_mismatch_breakdown_falls_back_to_pro_total_with_stderr(self, capsys):
        # 細項加總（3+3=6）與開頭總點數（10）不符：防呆整筆退回粗分 {"pro": 10}，不可無聲
        # （真實 fixture 無此案例，直接餵 _parse_credit_cell 字串驗證）
        credits, ctext = nuna._parse_credit_cell("10 專業: 3, 法規: 3,")
        assert credits == {"pro": 10.0}
        assert ctext == ""
        captured = capsys.readouterr()
        assert "積分細項加總" in captured.err and "不符" in captured.err

    def test_theme_tag_infection_control_detected(self):
        # 括號主題含「感染」應提示「含感染管制課程」（真實 fixture 只見性別主題案例，
        # 感染主題直接餵 _parse_credit_cell 字串驗證）
        credits, ctext = nuna._parse_credit_cell("5 品質: 3, 品質(感染): 2,")
        assert credits == {"quality": 5.0}
        assert ctext == "含感染管制課程"

    def test_online_keyword_detected_for_webex_row(self):
        events = nuna.parse(_fixture("nuna_list.html"))
        webex = next(e for e in events if "webex" in e["location"].lower())
        assert webex["online"] is True

    def test_physical_region_inferred_from_location(self):
        events = nuna.parse(_fixture("nuna_list.html"))
        south = next(e for e in events if "高雄" in e["location"])
        assert south["region"] == "south"


class TestCriticalSource:
    """critical 的二段式 parser 對 tests/fixtures/critical_list.html／critical_detail.html 的離線測試。

    critical_detail.html 是 critical_list.html 中活動編號 415（115年度急重症CKRT照護研習會北區）
    的真實詳情頁裁剪，兩個 fixture 可組合驗證 fetch() 實際會做的「候選＋詳情」合併流程。
    """

    def test_parse_list_extracts_multiple_candidates(self):
        candidates = critical.parse_list(_fixture("critical_list.html"))
        assert len(candidates) >= 5
        for cand in candidates:
            assert cand["id"].isdigit()
            assert cand["title"]
            assert cand["url"] == f"https://www.taccn.org.tw/activity/detail/{cand['id']}"

    def test_parse_detail_extracts_date_location_credits(self):
        detail = critical.parse_detail(_fixture("critical_detail.html"))
        assert detail is not None
        assert detail["date"] == "2026-09-10"
        assert "土城" in detail["location"]
        assert detail["credits"] == {"pro": 6.0, "np": 6.0}

    def test_parse_detail_returns_none_when_no_date_found(self):
        assert critical.parse_detail("<html><body>沒有任何活動資訊</body></html>") is None

    def test_combined_event_normalizes_clean(self):
        candidates = {c["id"]: c for c in critical.parse_list(_fixture("critical_list.html"))}
        detail = critical.parse_detail(_fixture("critical_detail.html"))
        cand = candidates["415"]

        online = critical._is_online(f"{cand['title']} {detail['location']}")
        ev = base.make_event(
            date=detail["date"],
            title=cand["title"],
            url=cand["url"],
            location=detail["location"],
            credits=detail["credits"],
            online=online,
        )
        normalized = normalize.normalize_event(dict(ev, src="critical"))
        assert normalized is not None
        assert normalized["date"] == "2026-09-10"
        assert normalized["url"].startswith("https://")
        assert normalized["credits"] == {"pro": 6.0, "np": 6.0}


class TestPsySource:
    """psy 的單頁列表 parser 對 tests/fixtures/psy_list.html（真實頁面 10 列未刪減）的離線測試。

    10 列中只有 2 列（entry=1229、entry=1226）同時滿足「標題含研習關鍵字」與「可抽出民國
    辦理日期」兩條件；entry=999 是刻意保留的陷阱案例（標題含可解析日期但無研習關鍵字）。
    """

    def test_parse_filters_to_seminar_rows_with_roc_date(self):
        events = psy.parse(_fixture("psy_list.html"))
        assert len(events) == 2

    def test_events_normalize_clean(self):
        events = psy.parse(_fixture("psy_list.html"))
        assert events
        for ev in events:
            assert normalize.normalize_event(dict(ev, src="psy")) is not None

    def test_dates_are_iso_format(self):
        events = psy.parse(_fixture("psy_list.html"))
        for ev in events:
            dt.date.fromisoformat(ev["date"])  # 格式不對會直接 raise ValueError

    def test_roc_date_correctly_converted(self):
        # entry=1229 標題含「115年8月6日」，民國 115 年 -> 西元 2026 年
        events = psy.parse(_fixture("psy_list.html"))
        ai_event = next(e for e in events if "AI數位照護" in e["title"])
        assert ai_event["date"] == "2026-08-06"
        assert ai_event["url"] == "https://www.psynurse.org.tw/news1.aspx?entry=1229"

    def test_non_seminar_trap_with_parseable_date_excluded(self):
        # entry=999 標題含「(111.7.11調整)」可被 roc_date_to_iso 解析，但不含「研習」關鍵字
        events = psy.parse(_fixture("psy_list.html"))
        assert all("開課單位繼續教育積分申請相關說明" not in e["title"] for e in events)

    def test_credits_always_empty(self):
        events = psy.parse(_fixture("psy_list.html"))
        assert all(e["credits"] == {} for e in events)


class TestTnnaSource:
    """tnna 的二段式 parser 對 tests/fixtures/tnna_list.html／tnna_detail.html 的離線測試。

    tnna_detail.html 是 tnna_list.html 中 WC_ID=1918（115年_研3 (北區) 高齡透析研習會）
    的真實詳情頁裁剪，兩個 fixture 組合驗證 fetch() 實際會做的「列表給日期地點＋詳情補積分」
    流程（與 critical.py 的日期/地點皆來自詳情頁不同，這是 tnna 的刻意設計）。
    """

    def test_parse_list_extracts_all_fixture_candidates(self):
        candidates = tnna.parse_list(_fixture("tnna_list.html"))
        assert len(candidates) == 4
        for cand in candidates:
            assert cand["id"].isdigit()
            assert cand["title"]
            assert cand["url"] == f"https://www.tnna.org.tw/home/study_content.asp?WC_ID={cand['id']}"

    def test_parse_list_date_from_gregorian_slash(self):
        candidates = {c["id"]: c for c in tnna.parse_list(_fixture("tnna_list.html"))}
        assert candidates["1918"]["date"] == "2026-07-12"
        assert "亞東醫院" in candidates["1918"]["location"]

    def test_parse_detail_extracts_credit_point_and_lifelong_hour(self):
        detail = tnna.parse_detail(_fixture("tnna_detail.html"))
        assert detail["credits"] == {"pro": 3.0}
        assert "終身學習" in detail["ctext"] and "3 小時" in detail["ctext"]

    def test_parse_detail_empty_when_no_credit_blocks_found(self):
        assert tnna.parse_detail("<html><body>沒有積分資訊區塊</body></html>") == {"credits": {}, "ctext": ""}

    def test_combined_event_normalizes_clean(self):
        candidates = {c["id"]: c for c in tnna.parse_list(_fixture("tnna_list.html"))}
        detail = tnna.parse_detail(_fixture("tnna_detail.html"))
        cand = candidates["1918"]

        ev = base.make_event(
            date=cand["date"],
            title=cand["title"],
            url=cand["url"],
            location=cand["location"],
            credits=detail["credits"],
            ctext=detail["ctext"],
        )
        normalized = normalize.normalize_event(dict(ev, src="tnna"))
        assert normalized is not None
        assert normalized["date"] == "2026-07-12"
        assert normalized["credits"] == {"pro": 3.0}


class TestTnmaSource:
    """tnma 的單頁表格 parser 對 tests/fixtures/tnma_list.html（真實頁面裁剪 6 列，含未閉合
    <td> 缺陷結構）的離線測試。
    """

    def test_parse_extracts_all_fixture_rows(self):
        events = tnma.parse(_fixture("tnma_list.html"))
        assert len(events) == 6

    def test_events_normalize_clean(self):
        events = tnma.parse(_fixture("tnma_list.html"))
        assert events
        for ev in events:
            assert normalize.normalize_event(dict(ev, src="tnma")) is not None

    def test_dates_are_iso_format_and_range_takes_start_date(self):
        events = tnma.parse(_fixture("tnma_list.html"))
        for ev in events:
            dt.date.fromisoformat(ev["date"])  # 格式不對會直接 raise ValueError
        # T2607425 辦理日期欄為區間「2026/9/2～2026/9/9」，應取起始日
        webex = next(e for e in events if "9月視訊" in e["title"])
        assert webex["date"] == "2026-09-02"

    def test_credits_always_empty_with_conditional_ctext_note(self):
        # v1 不解析附件內容 → credits 恆空；ctext 依有無附件用不同措辭：
        # 有附件叫使用者看簡章附件，無附件（url 退回列表頁）不可宣稱有簡章可看
        events = tnma.parse(_fixture("tnma_list.html"))
        assert all(e["credits"] == {} for e in events)
        for e in events:
            if e["url"] == "https://www.tnma100.org.tw/training/training02.asp":
                assert e["ctext"] == "積分與細節請洽官方公告"
            else:
                assert e["ctext"] == "積分與細節詳見簡章附件"
        # fixture 中兩種情況都要有，避免條件分支只測到一半
        assert {e["ctext"] for e in events} == {"積分與細節請洽官方公告", "積分與細節詳見簡章附件"}

    def test_attachment_url_used_when_present_else_list_url(self):
        events = tnma.parse(_fixture("tnma_list.html"))
        webex = next(e for e in events if "9月視訊" in e["title"])
        assert webex["url"] == "https://www.tnma100.org.tw/training/training02.asp"
        pdf_row = next(e for e in events if "中區" in e["title"])
        assert pdf_row["url"] == "https://www.tnma100.org.tw/manager/upload/2607021315231.pdf"
        # T2403389 課程表欄有 3 個附件（.xls/.pdf/.pdf），應取第一個
        multi = next(e for e in events if "海峽護理高峰論壇" in e["title"])
        assert multi["url"] == "https://www.tnma100.org.tw/manager/upload/2404230925203.xls"

    def test_online_keyword_detected_for_webex_row(self):
        events = tnma.parse(_fixture("tnma_list.html"))
        webex = next(e for e in events if "9月視訊" in e["title"])
        assert webex["online"] is True

    def test_payment_remark_does_not_poison_online_or_region(self):
        # 審查發現的誤判回歸測試：廈門實體論壇的地點欄拖著「註：…（線上）匯款…」繳費備註，
        # 不可因此標成線上活動或線上地區；「註：」之後的備註也不應出現在顯示用地點
        events = tnma.parse(_fixture("tnma_list.html"))
        xiamen = next(e for e in events if "海峽護理高峰論壇" in e["title"])
        assert xiamen["online"] is False
        assert xiamen["region"] == "tbd"  # 境外城市，誠實落未定，不亂猜
        assert "註" not in xiamen["location"] and "人民幣" not in xiamen["location"]
        assert xiamen["location"].startswith("廈門")

    def test_region_prefix_convention_recognized(self):
        # 「北區-三軍總醫院」這類學會慣用分區前綴應歸 north（REGIONS 關鍵字已含北/中/南/東區）
        events = tnma.parse(_fixture("tnma_list.html"))
        north = next(e for e in events if e["location"].startswith("北區"))
        assert north["region"] == "north"


class TestNiSource:
    """ni 的二段式 parser 對 tests/fixtures/ni_list.html／ni_detail.html 的離線測試。

    ni_detail.html 是 ni_list.html 中 pidm=3538 那一列的真實詳情頁裁剪；該頁沒有明確數字
    積分（只有呼籲文字），用來驗證 parse_detail() 在抓不到乾淨數字時把原文放進 ctext、
    不臆測 credits 數字。
    """

    def test_parse_list_extracts_all_fixture_candidates(self):
        candidates = ni.parse_list(_fixture("ni_list.html"))
        assert len(candidates) == 10
        for cand in candidates:
            assert cand["id"].isdigit()
            assert cand["title"]
            assert cand["url"] == f"https://www.ni.org.tw/v2/newsm_cload3.aspx?pidm={cand['id']}"

    def test_parse_list_dates_are_iso_format(self):
        candidates = ni.parse_list(_fixture("ni_list.html"))
        for cand in candidates:
            dt.date.fromisoformat(cand["date"])  # 格式不對會直接 raise ValueError

    def test_parse_detail_prefers_address_over_venue_name(self):
        detail = ni.parse_detail(_fixture("ni_detail.html"))
        assert detail["location"] == "天主教永和耕莘醫院門診大樓8F視訊教學會議室(234新北市永和區國光路123號)"
        assert detail["credits"] == {}
        assert "繼續教育積分" in detail["ctext"]

    def test_parse_detail_address_containing_venue_word_not_truncated(self):
        # 審查發現的邊界回歸測試：地址值本身含「活動中心」時，右邊界不可被裸「活動」
        # 二字提前截斷（現以「具體下一個欄位標籤」為界）
        html = (
            "<html><body><span>活動地點：三重區民活動中心</span>"
            "<span>活動地址：新北市三重區長泰街25號三重區民活動中心3樓</span>"
            "<span>報名截止：2026/08/01</span></body></html>"
        )
        detail = ni.parse_detail(html)
        assert detail["location"] == "新北市三重區長泰街25號三重區民活動中心3樓"

    def test_combined_event_normalizes_clean(self):
        candidates = {c["id"]: c for c in ni.parse_list(_fixture("ni_list.html"))}
        detail = ni.parse_detail(_fixture("ni_detail.html"))
        cand = candidates["3538"]

        ev = base.make_event(
            date=cand["date"],
            title=cand["title"],
            url=cand["url"],
            location=detail["location"],
            credits=detail["credits"],
            ctext=detail["ctext"],
        )
        normalized = normalize.normalize_event(dict(ev, src="ni"))
        assert normalized is not None
        assert normalized["date"] == "2026-08-07"
        assert normalized["location"].startswith("天主教永和耕莘醫院")


class TestTnpaSource:
    """tnpa 的單頁列表 parser 對 tests/fixtures/tnpa_list.html（真實頁面 11 筆未刪減）的離線測試。

    頁面本身無分頁標記，11 筆即為全部候選；涵蓋線上直播、已額滿、報名尚未開放、
    以及同一日期兩筆不同標題（id=6254/6255，同場次的「實際操作學員」與「觀摩學員」報名處）。
    """

    def test_parse_extracts_all_fixture_events(self):
        events = tnpa.parse(_fixture("tnpa_list.html"))
        assert len(events) == 11

    def test_events_normalize_clean(self):
        events = tnpa.parse(_fixture("tnpa_list.html"))
        assert events
        for ev in events:
            assert normalize.normalize_event(dict(ev, src="tnpa")) is not None

    def test_dates_are_iso_format(self):
        events = tnpa.parse(_fixture("tnpa_list.html"))
        for ev in events:
            dt.date.fromisoformat(ev["date"])  # 格式不對會直接 raise ValueError

    def test_urls_are_absolute_and_joined_from_relative_href(self):
        events = tnpa.parse(_fixture("tnpa_list.html"))
        assert all(ev["url"].startswith("https://www.tnpa.org.tw/events/content.php?id=") for ev in events)

    def test_credit_score_mapped_to_np(self):
        # id=6232：8/1Part1+8/15Part2 工作坊，event__score 為 16.2 積點
        events = tnpa.parse(_fixture("tnpa_list.html"))
        workshop = next(e for e in events if "AI 實戰升級" in e["title"])
        assert workshop["credits"] == {"np": 16.2}

    def test_place_label_prefix_stripped(self):
        events = tnpa.parse(_fixture("tnpa_list.html"))
        assert all(not e["location"].startswith("活動地點") for e in events)
        webex = next(e for e in events if "血脂管理" in e["title"])
        assert webex["location"] == "Google Meet 線上直播課程"

    def test_online_detected_from_event_type_and_location(self):
        events = tnpa.parse(_fixture("tnpa_list.html"))
        livestream = next(e for e in events if "血脂管理" in e["title"])
        assert livestream["online"] is True
        onsite = next(e for e in events if "成大醫院場" in e["title"])
        assert onsite["online"] is False

    def test_same_date_different_titles_both_kept(self):
        # id=6254（實際操作學員報名處）與 id=6255（觀摩學員報名處）同為 2026-12-12，標題不同
        events = tnpa.parse(_fixture("tnpa_list.html"))
        dec12 = [e for e in events if e["date"] == "2026-12-12"]
        assert len(dec12) == 2
        assert {e["title"] for e in dec12} == {
            "實際操作學員報名處-【實體】專科護理師場【從腫脹到線條：淋巴繃帶加壓治療工作坊】",
            "觀摩學員報名處-【實體】專科護理師場【從腫脹到線條：淋巴繃帶加壓治療工作坊】",
        }


class TestHospiceSource:
    """hospice 的單頁表格 parser 對 tests/fixtures/hospice_list.html（真實頁面 5 筆未刪減，
    頁面內嵌 totalNum=5 確認非分頁截斷）的離線測試。
    """

    def test_parse_extracts_all_fixture_rows(self):
        events = hospice.parse(_fixture("hospice_list.html"))
        assert len(events) == 5

    def test_events_normalize_clean(self):
        events = hospice.parse(_fixture("hospice_list.html"))
        assert events
        for ev in events:
            assert normalize.normalize_event(dict(ev, src="hospice")) is not None

    def test_dates_are_iso_format(self):
        events = hospice.parse(_fixture("hospice_list.html"))
        for ev in events:
            dt.date.fromisoformat(ev["date"])  # 格式不對會直接 raise ValueError

    def test_roc_single_date_converted(self):
        # 115/07/11 -> 民國 115 年 -> 西元 2026 年
        events = hospice.parse(_fixture("hospice_list.html"))
        first = next(e for e in events if "當生命不以斷食作答" in e["title"] and "延期" not in e["title"])
        assert first["date"] == "2026-07-11"

    def test_roc_date_range_takes_start_date(self):
        # 115/09/30 - 115/11/15 -> 取起始日 2026-09-30
        events = hospice.parse(_fixture("hospice_list.html"))
        advanced = next(e for e in events if "進階" in e["title"])
        assert advanced["date"] == "2026-09-30"

    def test_credit_score_mapped_to_pro_with_category_in_ctext(self):
        events = hospice.parse(_fixture("hospice_list.html"))
        basic = next(e for e in events if "基礎" in e["title"])
        assert basic["credits"] == {"pro": 13.0}
        assert basic["ctext"] == "必修課程"
        seminar = next(e for e in events if "回到內在的寧靜" in e["title"])
        assert seminar["credits"] == {"pro": 2.5}
        assert seminar["ctext"] == "學術研討"

    def test_urls_point_to_per_event_detail_page(self):
        events = hospice.parse(_fixture("hospice_list.html"))
        basic = next(e for e in events if "基礎" in e["title"])
        assert basic["url"] == (
            "https://www.hospicenurse.org.tw/ehc-tahpn/s/w/edu/scheduleInfo1/schedule1/"
            "b5487a4af37a4bb880a1e2d8c55fb19c"
        )

    def test_location_absent_but_region_still_inferred_from_title(self):
        # 列表頁與詳情頁皆無地點欄位，location 應為空字串；region 仍可能從標題文字推斷
        # （make_event 用 f"{location} {title}" 推斷），推斷不到的才落 tbd（不亂猜）。
        events = hospice.parse(_fixture("hospice_list.html"))
        assert all(e["location"] == "" for e in events)
        # 標題含「臺中榮民總醫院」，即使沒有獨立 location 欄位仍應推斷出 central
        basic = next(e for e in events if "基礎" in e["title"])
        assert basic["region"] == "central"
        # 標題帶「南區」：學會公告慣用分區寫法已加入 REGIONS 關鍵字（2026-07-10 審查後強化），
        # 應正確歸 south（先前推斷不到落 tbd，此斷言即該行為改善的回歸見證）
        seminar = next(e for e in events if "回到內在的寧靜" in e["title"])
        assert seminar["region"] == "south"


class TestAhqrocSource:
    """ahqroc 的二段式 parser 對 tests/fixtures/ahqroc_list.html／ahqroc_detail.html／
    ahqroc_detail_online.html（第 1 頁真實 8 筆未刪減＋兩份真實詳情頁）的離線測試。

    ahqroc_detail.html 是 sid=A-20260908「護理人的改善故事館」（實體課程）的詳情頁；
    ahqroc_detail_online.html 是 sid=A-20260731「危機風險應變與設施設備安全管理(視訊課程)」
    （視訊課程）的詳情頁，其「上課地點」實測值為平台名稱「webex」而非地址，用來驗證 online
    判斷不依賴這個欄位、改靠標題關鍵字。
    """

    def test_parse_list_extracts_all_fixture_candidates(self):
        candidates = ahqroc.parse_list(_fixture("ahqroc_list.html"))
        assert len(candidates) == 8
        for cand in candidates:
            assert cand["title"]
            assert cand["url"] == f"https://www.ahqroc.org.tw/ClassDetail.aspx?sid={cand['sid']}"

    def test_parse_list_dates_are_iso_format(self):
        candidates = ahqroc.parse_list(_fixture("ahqroc_list.html"))
        for cand in candidates:
            dt.date.fromisoformat(cand["date"])  # 格式不對會直接 raise ValueError

    def test_parse_list_same_date_different_sid_both_kept(self):
        # A-20260829／A-20260829-1：同日期、不同 sid（同場次不同報名身分），視為兩筆獨立事件
        candidates = ahqroc.parse_list(_fixture("ahqroc_list.html"))
        aug29 = [c for c in candidates if c["date"] == "2026-08-29"]
        assert len(aug29) == 2
        assert {c["sid"] for c in aug29} == {"A-20260829", "A-20260829-1"}

    def test_parse_detail_physical_course_extracts_location_and_quality_credits(self):
        detail = ahqroc.parse_detail(_fixture("ahqroc_detail.html"))
        assert detail["location"] == "高雄榮民總醫院門診大樓第二會議室"
        assert detail["credits"] == {"quality": 3.0}

    def test_parse_detail_online_course_location_is_platform_name(self):
        detail = ahqroc.parse_detail(_fixture("ahqroc_detail_online.html"))
        assert detail["location"] == "webex"
        assert detail["credits"] == {"quality": 5.0}

    def test_parse_detail_missing_section_returns_empty_not_raise(self):
        assert ahqroc.parse_detail("<html><body>沒有任何課程資訊</body></html>") == {
            "location": "",
            "credits": {},
        }

    def test_combined_physical_event_normalizes_clean(self):
        candidates = {c["sid"]: c for c in ahqroc.parse_list(_fixture("ahqroc_list.html"))}
        detail = ahqroc.parse_detail(_fixture("ahqroc_detail.html"))
        cand = candidates["A-20260908"]

        ev = base.make_event(
            date=cand["date"],
            title=cand["title"],
            url=cand["url"],
            location=detail["location"],
            credits=detail["credits"],
            online=ahqroc._is_online(f"{cand['title']} {detail['location']}"),
        )
        normalized = normalize.normalize_event(dict(ev, src="ahqroc"))
        assert normalized is not None
        assert normalized["date"] == "2026-09-08"
        assert normalized["credits"] == {"quality": 3.0}
        assert normalized["online"] is False

    def test_combined_online_event_detected_via_title_not_location(self):
        candidates = {c["sid"]: c for c in ahqroc.parse_list(_fixture("ahqroc_list.html"))}
        detail = ahqroc.parse_detail(_fixture("ahqroc_detail_online.html"))
        cand = candidates["A-20260731"]

        ev = base.make_event(
            date=cand["date"],
            title=cand["title"],
            url=cand["url"],
            location=detail["location"],
            credits=detail["credits"],
            online=ahqroc._is_online(f"{cand['title']} {detail['location']}"),
        )
        normalized = normalize.normalize_event(dict(ev, src="ahqroc"))
        assert normalized is not None
        assert normalized["online"] is True
        assert normalized["region"] == "online"


class TestJctSource:
    """jct 的二段式 parser 對 tests/fixtures/jct_calendar.html（2026 年 07 月活動月曆真實頁，
    裁到週標題列＋3 個真實週列）／jct_detail.html（真實排定活動 TCPI 研討會，「活動地點」
    標籤）／jct_detail_course_place.html（真實實作課程/工作坊，「課程地點」標籤，2026-07-10
    v2 重工實測發現的第二種地點標籤）／jct_detail_bundle.html（數位課程模組總表）的離線測試。

    2026-07-10 重工背景：首頁精選表只挑 5 筆、漏掉大量真實排定課程，改抓月曆頁涵蓋整月每一天
    的全部場次；同一報名連結可能出現在不同天（多場次共用 href）甚至同一天出現多次（同場活動
    不同分組），故去重鍵由單純 href 改為 (日期,href,標題) 三元組，_dedupe_candidates／
    _select_for_detail 為此新增的可離線測試純函式（細節見 jct.py 檔頭「資料形態」說明）。
    """

    def test_parse_calendar_extracts_all_fixture_candidates(self):
        # fixture 保留週標題列＋3 週（7/1 那週、7/19-25、7/26-31），真實資料共 16 筆課程連結
        candidates, _ = jct.parse_calendar(_fixture("jct_calendar.html"), jct.CALENDAR_URL)
        assert len(candidates) == 16
        for cand in candidates:
            assert cand["title"]
            assert cand["url"].startswith("https://attend.jct.org.tw/activity/event_news_detail.php")
            dt.date.fromisoformat(cand["date"])  # 格式不對會直接 raise ValueError
        # 前導空白格（7/1 那週的週日／週一／週二屬上月）與月底空白格皆無對應日期候選
        assert not any(c["date"] == "2026-07-01" for c in candidates)
        assert not any(c["date"] == "2026-08-01" for c in candidates)

    def test_parse_calendar_dates_combine_header_month_with_cell_day(self):
        candidates, _ = jct.parse_calendar(_fixture("jct_calendar.html"), jct.CALENDAR_URL)
        tcpi = next(c for c in candidates if "TCPI" in c["title"])
        assert tcpi["date"] == "2026-07-20"

    def test_parse_calendar_finds_next_month_link(self):
        _, next_url = jct.parse_calendar(_fixture("jct_calendar.html"), jct.CALENDAR_URL)
        assert next_url == (
            "https://attend.jct.org.tw/activity/event_news_calendar.php"
            "?arg=%2FJ2sYsBfspKDoW2rW3YwJ1tndYJMxkxv9nzm5KaYuQ"
        )

    def test_parse_detail_real_event_extracts_location(self):
        # 「活動地點」標籤（一般排定活動，如研討會）
        detail = jct.parse_detail(_fixture("jct_detail.html"))
        assert detail["location"] == "視訊課程（課程連結待報名截止，將以email方式通知）"

    def test_parse_detail_course_place_label_extracts_location(self):
        # 「課程地點」標籤（實作課程/工作坊），2026-07-10 v2 重工實測發現的第二種前綴
        detail = jct.parse_detail(_fixture("jct_detail_course_place.html"))
        assert detail["location"] == "醫策會901會議室（新北市板橋區三民路2段37號9樓之3）"

    def test_parse_detail_credit_pending_text_goes_to_ctext_not_guessed_number(self):
        # 學分認可單位是描述性文字（積分申請中，無明確數字），不可臆測成數字
        detail = jct.parse_detail(_fixture("jct_detail.html"))
        assert detail["credits"] == {}
        assert detail["ctext"] == "醫策會上課時數證明、公務人力時數、護理人員繼續教育訓練積分"

    def test_parse_detail_bundle_shape_returns_empty_gracefully(self):
        # 數位課程模組總表型的詳情頁沒有活動地點／學分認可單位，不應拋例外
        detail = jct.parse_detail(_fixture("jct_detail_bundle.html"))
        assert detail == {"location": "", "credits": {}, "ctext": ""}

    def test_exclude_keywords_read_from_config(self):
        # 排除規則已 config 化（SOURCES['jct']['exclude_title_keywords']），維護者加詞免改程式；
        # 三個既定規則（Lin 2026-07-10）必須在清單裡
        kws = jct._exclude_keywords()
        assert "數位課程" in kws and "教學影片" in kws and "觀摩活動" in kws

    def test_exclude_by_title_rules_filters_and_reports_per_keyword(self, capsys):
        # Lin 指示的排除規則：命中候選整批濾掉、連詳情頁都不抓；
        # 排除以「關鍵字：筆數」彙總 stderr 留痕（不可無聲丟棄）
        candidates = [
            {"title": "醫療品質學院數位課程-TRM系列套裝課程", "date": "2026-07-01", "url": "https://x/1"},
            {"title": "醫療品質學院【TRM醫療團隊資源管理工具書】教學影片", "date": "2026-07-02", "url": "https://x/2"},
            {"title": "2026年第27屆NHQA國家醫療品質獎智慧醫療類現場發表暨觀摩活動", "date": "2026-07-15", "url": "https://x/4"},
            {"title": "115年台灣臨床成效指標(TCPI)精神照護指標標竿暨交流會", "date": "2026-07-20", "url": "https://x/3"},
        ]
        kept = jct._exclude_by_title_rules(candidates)
        assert [c["title"] for c in kept] == ["115年台灣臨床成效指標(TCPI)精神照護指標標竿暨交流會"]
        captured = capsys.readouterr()
        assert "數位課程 1 筆" in captured.err
        assert "教學影片 1 筆" in captured.err
        assert "觀摩活動 1 筆" in captured.err

    def test_exclude_by_title_rules_noop_and_silent_when_nothing_matches(self, capsys):
        candidates = [{"title": "115年台灣臨床成效指標(TCPI)精神照護指標標竿暨交流會", "date": "2026-07-20", "url": "https://x/3"}]
        kept = jct._exclude_by_title_rules(candidates)
        assert kept == candidates
        captured = capsys.readouterr()
        assert captured.err == ""

    def test_nursing_signal_from_credits_or_ctext(self):
        # 醫師/中醫專屬判定（Lin 2026-07-10）：詳情頁學分欄有護理訊號＝跨職類保留
        assert jct._has_nursing_signal({"credits": {"pro": 6.0}, "ctext": ""}) is True
        assert jct._has_nursing_signal({"credits": {}, "ctext": "醫策會上課時數證明、護理人員繼續教育積分申請中"}) is True
        assert jct._has_nursing_signal({"credits": {}, "ctext": "醫師繼續教育積分、中醫師學分"}) is False
        assert jct._has_nursing_signal({"credits": {}, "ctext": ""}) is False

    def test_doctor_trigger_candidates_prioritized_into_detail_queue(self):
        # 醫師/中醫觸發字的候選必須搶到詳情額度（沒有詳情就無法判定專屬與否）：
        # 即使日期排在禮貌上限之外，也要被排進 with_detail
        today = dt.date(2026, 7, 10)
        candidates = [
            {"title": f"一般課程 {i}", "date": (today + dt.timedelta(days=i)).isoformat(), "url": f"https://x/{i}"}
            for i in range(jct.MAX_DETAIL_PAGES + 2)
        ]
        candidates.append({"title": "115年度醫師畢業後一般醫學訓練計畫－導師研習營",
                           "date": (today + dt.timedelta(days=60)).isoformat(), "url": "https://x/doc"})
        with_detail, without_detail = jct._select_for_detail(candidates, today)
        assert any("醫師" in c["title"] for c in with_detail)
        assert not any("醫師" in c["title"] for c in without_detail)

    def test_dedupe_keeps_same_href_across_different_days_and_same_day(self):
        # 真實情境（見 jct_calendar.html 20/21/22 日、23/30 日）：同一 href 出現在不同天，
        # 是不同場次，不可被 href 單獨去重砍成一筆
        candidates, _ = jct.parse_calendar(_fixture("jct_calendar.html"), jct.CALENDAR_URL)
        deduped = jct._dedupe_candidates(candidates)
        assert len(deduped) == len(candidates) == 16  # fixture 內無真重複，全數保留

        by_href: dict[str, set[str]] = {}
        for c in deduped:
            by_href.setdefault(c["url"], set()).add(c["date"])
        multi_day_hrefs = [href for href, days in by_href.items() if len(days) > 1]
        assert multi_day_hrefs, "fixture 應至少有一個 href 橫跨多天（20/21/22 或 23/30 日）"

        # 7/30 同一天內，抗生素論壇兩組共用同一 href 但標題不同，兩筆都要保留
        day30_same_href_titles = {
            c["title"] for c in deduped
            if c["date"] == "2026-07-30" and "抗生素管理與感染管制高峰論壇" in c["title"]
        }
        assert len(day30_same_href_titles) == 2

    def test_dedupe_collapses_true_duplicate(self):
        # (日期,href,標題) 三者皆同才視為真重複
        cand = {"title": "重複測試場次", "date": "2026-07-20", "url": "https://x/event?arg=1"}
        deduped = jct._dedupe_candidates([cand, dict(cand)])
        assert len(deduped) == 1

    def test_cross_month_candidates_merge_without_dropping(self):
        # 模擬 fetch() 逐月串接：同一 fixture 換月份標題代表「下個月」頁，驗證跨月合併不會
        # 互相蓋掉或漏掉（兩個月日期不重疊，理論上聯集筆數＝兩邊各自筆數相加）
        july_html = _fixture("jct_calendar.html")
        august_html = july_html.replace("2026年07月", "2026年08月")
        july_candidates, _ = jct.parse_calendar(july_html, jct.CALENDAR_URL)
        august_candidates, _ = jct.parse_calendar(august_html, jct.CALENDAR_URL)

        merged = jct._dedupe_candidates(july_candidates + august_candidates)
        assert len(merged) == len(july_candidates) + len(august_candidates)
        assert any(c["date"].startswith("2026-07") for c in merged)
        assert any(c["date"].startswith("2026-08") for c in merged)

    def test_combined_calendar_event_normalizes_clean_and_online(self):
        candidates = {c["title"]: c for c in jct.parse_calendar(_fixture("jct_calendar.html"), jct.CALENDAR_URL)[0]}
        detail = jct.parse_detail(_fixture("jct_detail.html"))
        cand = next(c for t, c in candidates.items() if "TCPI" in t)

        ev = base.make_event(
            date=cand["date"],
            title=cand["title"],
            url=cand["url"],
            location=detail["location"],
            credits=detail["credits"],
            online=jct._is_online(f"{cand['title']} {detail['location']}"),
            ctext=detail["ctext"],
        )
        normalized = normalize.normalize_event(dict(ev, src="jct"))
        assert normalized is not None
        assert normalized["date"] == "2026-07-20"
        assert normalized["online"] is True
        assert normalized["ondemand"] is False
        assert normalized["credits"] == {}
        assert "護理人員繼續教育訓練積分" in normalized["ctext"]

    def test_combined_calendar_event_course_place_normalizes_clean(self):
        # 「課程地點」標籤路徑也要能完整走過 normalize（不只 parse_detail 單元測試）
        candidates, _ = jct.parse_calendar(_fixture("jct_calendar.html"), jct.CALENDAR_URL)
        cand = next(c for c in candidates if "FMEA工作坊" in c["title"] or "團隊資源管理TRM工作坊" in c["title"])
        detail = jct.parse_detail(_fixture("jct_detail_course_place.html"))

        ev = base.make_event(
            date=cand["date"],
            title=cand["title"],
            url=cand["url"],
            location=detail["location"],
            credits=detail["credits"],
            online=jct._is_online(f"{cand['title']} {detail['location']}"),
            ctext=detail["ctext"],
        )
        normalized = normalize.normalize_event(dict(ev, src="jct"))
        assert normalized is not None
        assert normalized["location"] == "醫策會901會議室"  # simplify_location 去除門牌
        assert normalized["online"] is False

    def test_select_for_detail_drops_out_of_window_candidates(self):
        today = dt.date(2026, 7, 10)
        candidates = [
            {"title": "太久以前", "date": "2026-01-01", "url": "https://x/1"},
            {"title": "太遙遠的未來", "date": "2027-06-01", "url": "https://x/2"},
            {"title": "窗內", "date": "2026-07-15", "url": "https://x/3"},
        ]
        with_detail, without_detail = jct._select_for_detail(candidates, today)
        assert [c["title"] for c in with_detail] == ["窗內"]
        assert without_detail == []  # 窗外是「丟棄」（normalize 反正會濾），與上限外的「保留」不同

    def test_select_for_detail_over_cap_kept_without_detail_not_dropped(self, capsys):
        # 禮貌上限不可變成漏課程：窗內超過 MAX_DETAIL_PAGES 的部分要以月曆資料收錄，
        # 不是整筆截掉（v2 首版曾截掉，會重演 Lin 回報的「醫策會沒抓全」）
        today = dt.date(2026, 7, 10)
        candidates = [
            {"title": f"event {i}", "date": (today + dt.timedelta(days=i)).isoformat(), "url": f"https://x/{i}"}
            for i in range(jct.MAX_DETAIL_PAGES + 3)
        ]
        with_detail, without_detail = jct._select_for_detail(candidates, today)
        assert len(with_detail) == jct.MAX_DETAIL_PAGES
        assert [c["title"] for c in with_detail] == [f"event {i}" for i in range(jct.MAX_DETAIL_PAGES)]
        assert [c["title"] for c in without_detail] == [f"event {i}" for i in range(jct.MAX_DETAIL_PAGES, jct.MAX_DETAIL_PAGES + 3)]
        captured = capsys.readouterr()
        assert "以月曆資料收錄" in captured.err  # 截斷必留痕，且語意是「收錄無詳情」非「丟棄」


class TestTwnaSource:
    """twna 手動維護來源（不連網）：讀 data/manual_twna.json 轉成事件清單。

    robots.txt 全站禁爬（見 scripts/sources/twna.py 檔頭），本專案不自動爬取，改由 Lin
    手動編輯 JSON 或跑 scripts/import_twna_page.py 另存頁匯入器填入。這裡大多數測試用
    monkeypatch 把 twna.DATA_PATH 換成 tmp_path 下的臨時檔，不觸碰真實的
    data/manual_twna.json（2026-07-10 起已由另存頁匯入器填入初始資料，見
    test_real_manual_data_fetch_returns_populated_events）。
    """

    def test_empty_events_list_returns_empty(self, tmp_path, monkeypatch):
        # events 為空清單是合法狀態（不是解析失敗），registry 會標為 status=empty 誠實呈現。
        # 用 tmp_path 而非真實 DATA_PATH：真實檔案 2026-07-10 起已由匯入器填入資料，不再是空的。
        data_path = tmp_path / "manual_twna.json"
        data_path.write_text(json.dumps({"comment": "empty", "events": []}, ensure_ascii=False), encoding="utf-8")
        monkeypatch.setattr(twna, "DATA_PATH", data_path)

        assert twna.fetch() == []

    def test_real_manual_data_fetch_returns_populated_events(self):
        # 專案現況（2026-07-10 起）：真實 data/manual_twna.json 已由另存頁匯入器填入初始資料。
        # 驗證真實檔案格式正確、fetch() 讀得動、且每筆都能通過 normalize（非另存頁 fixture 測試，
        # 這裡刻意直接讀真實檔案，確保「已交付進 repo 的資料」本身是健康的）。
        events = twna.fetch()
        assert len(events) > 0
        for ev in events:
            assert normalize.normalize_event(dict(ev, src="twna")) is not None

    def test_normal_entry_normalizes_clean(self, tmp_path, monkeypatch):
        sample = {
            "comment": "test fixture",
            "events": [
                {
                    "date": "2026-09-01",
                    "title": "測試課程：手動維護格式範例",
                    "url": "https://www.twna.org.tw/example-course",
                    "location": "台北市中正區",
                    "credits": {"pro": 2},
                }
            ],
        }
        data_path = tmp_path / "manual_twna.json"
        data_path.write_text(json.dumps(sample, ensure_ascii=False), encoding="utf-8")
        monkeypatch.setattr(twna, "DATA_PATH", data_path)

        events = twna.fetch()
        assert len(events) == 1
        normalized = normalize.normalize_event(dict(events[0], src="twna"))
        assert normalized is not None
        assert normalized["title"] == "測試課程：手動維護格式範例"
        assert normalized["credits"] == {"pro": 2}
        assert normalized["region"] == "north"  # 從「台北市」地點文字推斷

    def test_missing_file_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr(twna, "DATA_PATH", tmp_path / "does_not_exist.json")
        with pytest.raises(FileNotFoundError):
            twna.fetch()

    def test_malformed_json_raises(self, tmp_path, monkeypatch):
        data_path = tmp_path / "manual_twna.json"
        data_path.write_text("{not valid json", encoding="utf-8")
        monkeypatch.setattr(twna, "DATA_PATH", data_path)

        with pytest.raises(json.JSONDecodeError):
            twna.fetch()

    def test_missing_events_key_raises_key_error(self, tmp_path, monkeypatch):
        data_path = tmp_path / "manual_twna.json"
        data_path.write_text(json.dumps({"comment": "缺 events 欄位"}), encoding="utf-8")
        monkeypatch.setattr(twna, "DATA_PATH", data_path)

        with pytest.raises(KeyError):
            twna.fetch()

    def test_event_missing_required_field_raises_value_error_with_index(self, tmp_path, monkeypatch):
        sample = {"events": [{"title": "缺日期與網址的壞資料"}]}
        data_path = tmp_path / "manual_twna.json"
        data_path.write_text(json.dumps(sample, ensure_ascii=False), encoding="utf-8")
        monkeypatch.setattr(twna, "DATA_PATH", data_path)

        with pytest.raises(ValueError, match="第 1 筆"):
            twna.fetch()

    # ---- parse_saved_page()：另存頁匯入器的解析核心，純函式、不連網（見模組檔頭合規背景）。
    # fixture tests/fixtures/twna_saved_page.html 是 2026-07-10 偵察期快取頁裁剪出的 6 筆
    # 代表列，其中 1 筆（ctl44「規劃中」）刻意保留日期只標到月份、無日的真實不完整列，
    # 用來驗證「缺日期跳過」邏輯不是憑空想像的分支。----

    def test_parse_saved_page_count(self):
        events = twna.parse_saved_page(_fixture("twna_saved_page.html"))
        # 6 筆資料列，1 筆（規劃中，日期缺日）會被跳過，應剩 5 筆。
        assert len(events) == 5

    def test_parse_saved_page_all_normalize_clean(self):
        events = twna.parse_saved_page(_fixture("twna_saved_page.html"))
        assert events
        for ev in events:
            normalized = normalize.normalize_event(dict(ev, src="twna"))
            assert normalized is not None

    def test_parse_saved_page_roc_date_converted_to_iso(self):
        events = twna.parse_saved_page(_fixture("twna_saved_page.html"))
        by_title = {e["title"]: e for e in events}
        title = next(t for t in by_title if "人工智慧" in t)
        # 原始儲存格文字為民國「115/7/2(四)」，115 + 1911 = 2026 年。
        assert by_title[title]["date"] == "2026-07-02"

    def test_parse_saved_page_credits_empty_and_ctext_fixed(self):
        events = twna.parse_saved_page(_fixture("twna_saved_page.html"))
        assert events
        for ev in events:
            # 列表頁沒有積分欄，credits 一律空字典，ctext 固定提示改洽學會官網。
            assert ev["credits"] == {}
            assert ev["ctext"] == "積分請洽學會官網"

    def test_parse_saved_page_url_points_to_public_list_page(self):
        events = twna.parse_saved_page(_fixture("twna_saved_page.html"))
        assert events
        for ev in events:
            # 逐列標題連結是 __doPostBack，沒有可用詳情頁，url 一律指回公開列表頁。
            assert ev["url"] == twna.LIST_URL

    def test_parse_saved_page_skips_row_missing_date(self, capsys):
        events = twna.parse_saved_page(_fixture("twna_saved_page.html"))
        titles = [e["title"] for e in events]
        assert "「實證健康照護」審查委員共識會(南區)" not in titles
        captured = capsys.readouterr()
        assert "缺日期或標題" in captured.err
        assert "已跳過" in captured.err


class TestImportTwnaPage:
    """scripts/import_twna_page.py 的合併邏輯測試：一律用 tmp_path，不觸碰真實
    data/manual_twna.json；run() 的路徑皆由參數傳入，不需要 monkeypatch。
    """

    def test_run_adds_new_and_dedupes_existing(self, tmp_path):
        html_path = FIXTURES / "twna_saved_page.html"
        data_path = tmp_path / "manual_twna.json"

        # 既有清單放一筆會與 fixture 解析結果撞鍵（同 date ＋ 同去空白 title）、且欄位已被
        # 「人工修過」的條目，用來驗證合併時保留既有版本、不被剛解析出的版本覆蓋；
        # 再放一筆完全不相關的既有條目，驗證合併不會遺失既有資料。
        existing_dupe = base.make_event(
            date="2026-07-02",
            title="人工智慧在護理研究與智慧照護中的應用(線上視訊)",
            url="https://www.twna.org.tw/manually-fixed-url",
            credits={"pro": 99},
            ctext="Lin 手動核實過的積分",
        )
        unrelated = base.make_event(
            date="2099-01-01",
            title="既有不相關活動，應保留",
            url="https://example.com/keep-me",
        )
        data_path.write_text(
            json.dumps({"comment": "test", "events": [existing_dupe, unrelated]}, ensure_ascii=False),
            encoding="utf-8",
        )

        now = dt.datetime(2026, 7, 19, 14, 0, tzinfo=dt.timezone(dt.timedelta(hours=8)))
        stats = import_twna_page.run(html_path, data_path, now=now)

        assert stats == {"added": 4, "skipped_dupe": 1, "failed": 1}

        saved = json.loads(data_path.read_text(encoding="utf-8"))
        assert saved["manual_imported_at"] == "2026-07-19T14:00:00+08:00"
        assert saved["manual_checked_at"] == "2026-07-19T14:00:00+08:00"
        events = saved["events"]
        assert len(events) == 2 + 4  # 既有 2 筆 + 新增 4 筆（5 筆解析成功 - 1 筆撞鍵）

        by_key = {(e["date"], "".join(e["title"].split())): e for e in events}
        kept = by_key[("2026-07-02", "人工智慧在護理研究與智慧照護中的應用(線上視訊)")]
        # 既有（人工修過）版本必須原封不動保留，不被剛解析出的版本蓋掉。
        assert kept["url"] == "https://www.twna.org.tw/manually-fixed-url"
        assert kept["credits"] == {"pro": 99}
        assert ("2099-01-01", "既有不相關活動，應保留") in by_key

    def test_run_updates_both_timestamps_when_no_event_is_added(self, tmp_path):
        html_path = FIXTURES / "twna_saved_page.html"
        parsed = twna.parse_saved_page(html_path.read_text(encoding="utf-8"))
        data_path = tmp_path / "manual_twna.json"
        data_path.write_text(
            json.dumps(
                {
                    "manual_imported_at": "2026-07-10T00:00:00+08:00",
                    "manual_checked_at": "",
                    "events": parsed,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        now = dt.datetime(2026, 7, 19, 14, 0, tzinfo=dt.timezone(dt.timedelta(hours=8)))

        stats = import_twna_page.run(html_path, data_path, now=now)

        assert stats["added"] == 0
        saved = json.loads(data_path.read_text(encoding="utf-8"))
        assert saved["manual_imported_at"] == "2026-07-19T14:00:00+08:00"
        assert saved["manual_checked_at"] == "2026-07-19T14:00:00+08:00"

    def test_run_invalid_html_leaves_timestamps_unchanged(self, tmp_path):
        html_path = tmp_path / "not_twna.html"
        html_path.write_text("<html><body>not a saved TWNA page</body></html>", encoding="utf-8")
        data_path = tmp_path / "manual_twna.json"
        original = {
            "manual_imported_at": "2026-07-10T00:00:00+08:00",
            "manual_checked_at": "",
            "events": [],
        }
        data_path.write_text(json.dumps(original), encoding="utf-8")

        with pytest.raises(ValueError, match="twna"):
            import_twna_page.run(html_path, data_path)

        assert json.loads(data_path.read_text(encoding="utf-8")) == original

    def test_run_missing_html_raises_file_not_found(self, tmp_path):
        data_path = tmp_path / "manual_twna.json"
        original = {
            "manual_imported_at": "2026-07-10T00:00:00+08:00",
            "manual_checked_at": "",
            "events": [],
        }
        data_path.write_text(json.dumps(original), encoding="utf-8")

        with pytest.raises(FileNotFoundError):
            import_twna_page.run(tmp_path / "does_not_exist.html", data_path)

        assert json.loads(data_path.read_text(encoding="utf-8")) == original

    def test_main_missing_html_returns_exit_code_1(self, tmp_path, capsys):
        # html 不存在時 run() 在碰到 data_path 之前就 raise，main() 才會用到真實
        # twna.DATA_PATH 當預設值，此路徑保證不觸碰、不寫入該檔案。
        code = import_twna_page.main([str(tmp_path / "does_not_exist.html")])
        assert code == 1
        captured = capsys.readouterr()
        assert "找不到" in captured.err
