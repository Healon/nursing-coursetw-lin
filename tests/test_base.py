"""scripts.sources.base 共用工具測試：roc_date_to_iso 民國轉西元邊界情境、
download_curl 的成功／失敗契約（用 file:// URL，不連網）、infer_category 的
智慧科技分類優先序（2026-07-18 新增 tech 分類時訂下的比對順序契約）。
"""
from __future__ import annotations

import pytest

from scripts.sources import base


class TestInferCategoryTechPriority:
    """tech（智慧科技）分類 2026-07-18 新增時的順序契約：teaching 之後、clinical 之前；
    「智慧／數位／資訊」自 research 移入 tech。標題皆取自或仿自真實課程。"""

    def test_ai_in_care_title_prefers_tech_over_clinical(self):
        # 含「照護」也含 AI／智慧 → tech 先於 clinical 命中
        assert base.infer_category("AI數位照護在精神科護理的運用研習會") == "tech"
        assert base.infer_category("重症照護3.0 - 智慧化、整合化、流程再進化研習會") == "tech"

    def test_informatics_title_moved_from_research_to_tech(self):
        # 「資訊／數位」原屬 research 關鍵字，移入 tech 後改判智慧科技
        assert base.infer_category("護理資訊進階系列課程") == "tech"
        assert base.infer_category("手術室數位轉型與管理新紀元工作坊") == "tech"

    def test_teaching_keywords_still_win_over_tech(self):
        # 教學類特定詞在 tech 之前：AI 教學課程仍歸教學
        assert base.infer_category("臨床教師的留任藝術 CBME實務、AI創新與帶領新生代護理人的關鍵策略") == "teaching"

    def test_plain_research_title_still_research(self):
        assert base.infer_category("年度學術研討會論文發表") == "research"

    def test_plain_clinical_title_unaffected(self):
        assert base.infer_category("疼痛照護實務研習") == "clinical"


class TestSimplifyLocation:
    """地點顯示規則（2026-07-10 Lin 訂）：只留場館／機構名，去門牌住址。全部用真實資料形態。"""

    def test_address_label_tail_removed(self):
        # tnna 實料形態：「地址:」引導的尾段
        assert base.simplify_location("亞東醫院 14 樓國際會議廳 地址:新北市板橋區南雅南路二段 21 號") == "亞東醫院 14 樓國際會議廳"

    def test_paren_address_removed(self):
        # ni 實料形態：括號包住的門牌（含郵遞區號變體）
        assert base.simplify_location("高雄長庚紀念醫院質子中心二樓多功能教室 (高雄市鳥松區大埤路123號)") == "高雄長庚紀念醫院質子中心二樓多功能教室"
        assert base.simplify_location("天主教永和耕莘醫院門診大樓8F視訊教學會議室(234新北市永和區國光路123號)") == "天主教永和耕莘醫院門診大樓8F視訊教學會議室"

    def test_trailing_address_removed(self):
        # nuna 實料形態：空格後直接接完整門牌
        assert base.simplify_location("台中慈濟醫院大愛講堂 台中市潭子區豐興路一段88號") == "台中慈濟醫院大愛講堂"

    def test_rural_style_address_removed(self):
        # nuna 實料（澎湖）：鄉村門牌用「里／村」而非路街（首輪遷移抓漏的真實案例）
        assert base.simplify_location("三軍總醫院澎湖分院EMT教室(舊院區二樓訓練教室） 澎湖縣馬公市前寮里90號") == "三軍總醫院澎湖分院EMT教室(舊院區二樓訓練教室）"

    def test_floor_paren_kept(self):
        # twna 實料：括號是樓層不是門牌（不含「號」），必須保留
        assert base.simplify_location("台灣護理學會 國際會議廳(9F)") == "台灣護理學會 國際會議廳(9F)"

    def test_plain_venue_untouched(self):
        assert base.simplify_location("東元綜合醫院") == "東元綜合醫院"
        assert base.simplify_location("Google meet視訊直播") == "Google meet視訊直播"

    def test_pure_address_falls_back_to_original(self):
        # 整段就是門牌時退回原文，不製造空地點
        assert base.simplify_location("台北市中正區徐州路5號") == "台北市中正區徐州路5號"

    def test_empty_stays_empty(self):
        assert base.simplify_location("") == ""

    def test_make_event_display_simplified_but_region_from_raw(self):
        # 顯示精簡、地區推斷用原文：門牌被砍後仍要能從原文判出北部
        ev = base.make_event(date="2026-08-01", title="研習會", url="https://x.example/1",
                             location="亞東醫院 14 樓國際會議廳 地址:新北市板橋區南雅南路二段 21 號")
        assert ev["location"] == "亞東醫院 14 樓國際會議廳"
        assert ev["region"] == "north"  # 縣市線索只在被砍掉的門牌裡，仍須判對


class TestDownloadCurl:
    """download_curl 用 file:// URL 離線驗證契約；polite_delay 換成 no-op 免等待。"""

    @pytest.fixture(autouse=True)
    def _no_delay(self, monkeypatch):
        monkeypatch.setattr(base, "polite_delay", lambda: None)

    def test_returns_file_content(self, tmp_path):
        f = tmp_path / "page.html"
        f.write_text("<html>中文內容 OK</html>", encoding="utf-8")
        assert base.download_curl(f.as_uri()) == "<html>中文內容 OK</html>"

    def test_raises_on_failure_not_silent(self, tmp_path):
        # 錯誤必 raise（由 registry 記進 status），禁止吞例外回空字串
        with pytest.raises(RuntimeError, match="curl failed"):
            base.download_curl((tmp_path / "no-such-file.html").as_uri())


class TestRocDateToIso:
    def test_basic_full_width_labels(self):
        assert base.roc_date_to_iso("115年9月4日") == "2026-09-04"

    def test_slash_separator_zero_padded(self):
        assert base.roc_date_to_iso("115/09/04") == "2026-09-04"

    def test_single_digit_month_and_day(self):
        # 單位數月日（無補零）：常見於列表頁的口語化日期寫法
        assert base.roc_date_to_iso("115/9/4") == "2026-09-04"
        assert base.roc_date_to_iso("100年1月1日") == "2011-01-01"

    def test_dash_and_dot_separators(self):
        assert base.roc_date_to_iso("115-9-4") == "2026-09-04"
        assert base.roc_date_to_iso("115.9.4") == "2026-09-04"

    def test_year_boundary_crossing(self):
        # 跨年：112 年 12 月 31 日 -> 西元 2023 年底（非 2024）
        assert base.roc_date_to_iso("112年12月31日") == "2023-12-31"

    def test_embedded_in_longer_sentence(self):
        # 日期前後夾雜其他文字（實際公告標題常見情境）
        assert base.roc_date_to_iso("【本會研習會訊息】115年8月6日【AI數位照護】研習會（南區）") == "2026-08-06"

    def test_plain_gregorian_year_not_misread_as_roc(self):
        # 西元四位數年份不可誤吃成民國年（三碼子字串）
        assert base.roc_date_to_iso("2026/09/04") is None

    def test_non_date_text_returns_none(self):
        assert base.roc_date_to_iso("這是一段沒有日期的公告文字") is None

    def test_empty_string_returns_none(self):
        assert base.roc_date_to_iso("") is None

    def test_invalid_calendar_date_returns_none(self):
        # 月份 13、日期 40 皆非合法曆日
        assert base.roc_date_to_iso("115年13月4日") is None
        assert base.roc_date_to_iso("115年9月40日") is None

    def test_no_match_when_no_separator(self):
        # 純數字堆疊、沒有年月日分隔符號，不應誤判
        assert base.roc_date_to_iso("1159904") is None
