"""Purpose: single configuration file for adapting this template to any society or theme.
Input:  edited by the site maintainer (titles, labels, sources, theme colors).
Output: imported by scripts/* to drive scraping, normalization, and the page build.

換學會主題時，原則上只需要改這一個檔，加上在 scripts/sources/ 放對應的來源模組。
所有欄位都是純資料（dict／list），不含任何邏輯。
"""

SITE = {
    # 網站標題與副標（顯示在頁面 header 與瀏覽器分頁標題）
    "title": "護理教育訓練網站",
    "subtitle": "繼續教育課程與學術活動，一頁查詢",
    # 頁尾免責聲明：非官方彙整站的基本姿態，請保留同等意思的文字
    "disclaimer": "本站為個人維護的非官方彙整頁，活動資訊以各學會官方網站公告為準；活動內容著作權歸各主辦單位所有。",
    # 頁尾補充說明（可留空字串）
    "footer_note": "資料每週自動更新一次。",
}

THEME = {
    # 改這裡就能換整站配色（build 時輸出成 CSS 變數）
    # 目前套用：IBM Design Language / Carbon 的「靜謐青」（RX Ⅱ，2026-07-10 Lin 選定）。
    # 完整三帖配色參考見 docs/palette/palette-reference.png。
    "primary": "#007d79",       # 主色：header 漸層起點、按鈕、選中的 pill（Carbon teal 60）
    "primary_dark": "#004144",  # 主色深：header 漸層終點（Carbon teal 80）
    "accent": "#ba4e00",        # 強調色：積分徽章（Carbon orange 70，與主色對比讓積分跳出）
    "bg": "#f4f4f4",           # 頁面背景（Carbon gray 10）
    "card_bg": "#ffffff",       # 卡片背景
    "text": "#161616",          # 主文字（Carbon gray 100）
    "muted": "#525252",         # 次要文字（Carbon gray 70）
    "line": "#e0e0e0",         # 分隔線與卡片邊框（Carbon gray 20）
    "warn": "#da1e28",          # 警示（Carbon red 60；錯誤可見性用色，換帖不換）
    "warn_bg": "#fff1f1",       # 警示背景（Carbon red 10）
    # 三組篩選 pill 各一色（Lin 2026-07-10 訂，仿參考站分組配色）：未選＝白底彩框彩字，
    # 選中＝實心彩底白字。積分徽章的橙（accent）刻意不給任何 pill 組，保住它的辨識度。
    "pill_cat": "#007d79",      # 類別（Carbon teal 60，同主色）
    "pill_region": "#0f62fe",   # 地區（Carbon blue 60；原 green 60 與類別的 teal 太近，Lin 反饋後改）
    "pill_src": "#6929c4",      # 來源（Carbon purple 70）
}

# 活動類別：code -> {label, keywords}
# keywords 供爬蟲依標題自動歸類（infer_category）；比對不到就落入 other。
# 「順序即優先序」：由上往下比對、第一個命中就定案，所以特定性高的類別（如 teaching
# 的「教學／師資」）要放在泛用詞類別（如 clinical 的「護理／照護」幾乎每個標題都有）前面。
# 換主題時整組替換即可，但請保留 "other" 這個 fallback，勿刪除。
CATEGORIES = {
    "teaching": {"label": "教學", "keywords": ["教學", "師資", "教案", "臨床教師", "OSCE", "教育訓練師", "怎麼教"]},
    # tech 放 teaching 之後、clinical 之前：智慧科技詞彙特定性高於「照護／護理」泛用詞，
    # 讓「AI 在護理照護之應用」這類標題判 tech 而非 clinical；純教學類（含 AI 教案）仍歸 teaching。
    # 「智慧／數位／資訊」原屬 research 關鍵字，2026-07-18 隨本分類新增移入（Lin 指示加「智慧科技」
    # 分類收工研院 AI 課程；既有含這些字的課程會從研究學術改判智慧科技）。
    # 注意 infer_category 是子字串比對："AI" 理論上會誤中 TRAINING／PAIN 這類英文詞，
    # 2026-07-18 已逐筆掃過既有 events.json 標題確認無誤中；日後若出現，把 "AI" 移出關鍵字
    # 並靠其餘中文詞承接。
    "tech": {"label": "智慧科技", "keywords": ["AI", "人工智慧", "智慧", "智能", "數位", "資訊", "科技", "大數據", "機器學習", "深度學習", "生成式", "ChatGPT", "資安", "物聯網", "機器人", "虛擬實境", "元宇宙"]},
    "clinical": {"label": "臨床照護", "keywords": ["照護", "護理", "臨床", "急救", "重症", "傷口", "安寧", "緩和", "腎臟", "透析"]},
    "safety": {"label": "病人安全", "keywords": ["病人安全", "病安", "感染", "感控", "品質", "醫療品質", "異常事件"]},
    "admin": {"label": "行政管理", "keywords": ["管理", "行政", "領導", "溝通", "督導"]},
    "ethics": {"label": "倫理法規", "keywords": ["倫理", "法規", "法律", "性別"]},
    "research": {"label": "研究學術", "keywords": ["研究", "論文", "實證", "統計", "研討會", "年會", "學術"]},
    "other": {"label": "其他", "keywords": []},  # fallback，勿刪除
}

# 積分別：code -> label。
# 事件 credits 欄位的 key 必須存在於此（例：{"pro": 2, "law": 1.5}）。
# 定案（Lin 2026-07-10，依《醫事人員執業登記及繼續教育辦法》第13條，law.moj.gov.tw
# L0020181 已查證）：護理人員繼續教育六年 120 點，四類＝專業課程／專業品質／專業倫理／
# 專業相關法規（品質＋倫理＋法規合計至少 12 點，超過 24 以 24 計，應含感染管制與性別議題
# 課程）。未標明細類的護理積分預設歸「專業」(pro)。np 為專科護理師學分，屬另一套六年
# 更新制度，與此四類無關。
CREDIT_TYPES = {
    "pro": "專業",
    "quality": "品質",
    "ethics": "倫理",
    "law": "法規",
    "np": "專科護理師",
}

# 地區：code -> {label, keywords}。
# keywords 供 infer_region 依地點文字推斷；請保留 "online" 與 "tbd" 兩個特殊值，勿刪除。
REGIONS = {
    # 「北區／中區／南區／東區」是學會公告慣用的分區寫法（如「北區-三軍總醫院」），一併認得。
    # 名單順序即比對優先序：含城市名者（如「台北市東區」）會先命中 north，不會被「東區」誤導。
    "north": {"label": "北部", "keywords": ["台北", "臺北", "新北", "基隆", "桃園", "新竹", "宜蘭", "北區"]},
    "central": {"label": "中部", "keywords": ["台中", "臺中", "苗栗", "彰化", "南投", "雲林", "中區"]},
    "south": {"label": "南部", "keywords": ["嘉義", "台南", "臺南", "高雄", "屏東", "澎湖", "南區"]},
    "east": {"label": "東部", "keywords": ["花蓮", "台東", "臺東", "東區"]},
    "online": {"label": "線上", "keywords": ["線上", "視訊", "直播", "遠距", "webinar", "online"]},
    "tbd": {"label": "未定其他", "keywords": []},  # fallback，勿刪除
}

# 資料來源（學會）：code -> 設定。
#   label:   顯示名稱（pill 與頁尾統計用）
#   url:     活動列表頁（必須是公開、免登入的頁面）
#   enabled: 是否納入「無參數執行 update.py」的自動更新
#   execution: 執行位置（cloud＝GitHub Actions；local＝住宅 IP；manual＝只讀人工匯入資料）
#   note:    維護備註（例如「需會員登入，不爬，改人工維護」）
# 每個要爬的 code 必須在 scripts/sources/<code>.py 有對應模組（實作 fetch()）。
# 需要登入才看得到活動的網站：不要爬，enabled 設 False 並在 note 註明。
SOURCES = {
    "demo": {
        "label": "示範資料",
        "url": "",
        "enabled": False,
        "execution": "cloud",
        "note": "離線假資料產生器，讓模板不需網路即可完整跑通（pytest 與新手體驗仍會用到，勿刪模組）。"
        "已於 2026-07-10 轉正式資料後停用；要重新體驗示範模式改回 True 再 update.py --reset。",
    },
    "nuna": {
        "label": "護理師護士公會全聯會",
        "url": "https://www.nurse.org.tw/publicUI/D/D101.aspx",
        "enabled": True,
        "execution": "cloud",
        "note": "已驗證可抓（2026-07-10 實測研習活動報名表格，24 筆，ASP.NET GridView，免登入）。",
    },
    "critical": {
        "label": "中華民國急重症護理學會",
        "url": "https://www.taccn.org.tw/activity/list/2",
        "enabled": True,
        "execution": "cloud",
        "note": "已驗證可抓（2026-07-10 實測列表頁 10 筆，逐筆進入詳情頁取日期與積分，免登入）。官方全名依詳情頁頁尾核實。",
    },
    # ---- 以下為 2026-07-10 偵察後登錄、待逐波實作的來源（enabled=False 起步）----
    "psy": {
        "label": "中華民國精神衛生護理學會",
        "url": "https://www.psynurse.org.tw/news.aspx",
        "enabled": True,
        "execution": "cloud",
        "note": "已驗證可抓（2026-07-10 實測消息公告頁 10 則中 2 則為研習會，免登入，標題含民國日期用 base.roc_date_to_iso 換算；無積分欄）。",
    },
    "tnna": {
        "label": "臺灣腎臟護理學會",
        "url": "https://www.tnna.org.tw/home/study_list.asp",
        "enabled": True,
        "execution": "cloud",
        "note": "已驗證可抓（2026-07-10 實測列表 10 筆卡片式，含日期／地點；詳情頁 study_content.asp?WC_ID= 補積分，免登入）。勿與腎臟醫學會 tsn.org.tw 混淆。",
    },
    "tnma": {
        "label": "臺灣護理管理學會",
        "url": "https://www.tnma100.org.tw/training/training02.asp",
        "enabled": True,
        "execution": "cloud",
        "note": "已驗證可抓（2026-07-10 實測表格 50 列，標題＋西元日期＋地點，免登入）。詳情多為 PDF/XLS/DOCX 簡章，v1 不解析附件內容，只取第一個附件連結當 url；/training/ 目錄本身 403 不直接打。",
    },
    "ni": {
        "label": "台灣護理資訊學會",
        "url": "https://www.ni.org.tw/v2/newsm_cload3.aspx",
        "enabled": True,
        "execution": "cloud",
        "note": "已驗證可抓（2026-07-10 實測列表 10 筆/頁，免登入；詳情 ?pidm=ID 補地點）。分頁機制無法從靜態 HTML 確認為純 GET（無 __doPostBack 字串但也無 querystring 分頁證據），v1 只取第一頁。",
    },
    "ahqroc": {
        "label": "台灣醫療品質協會",
        "url": "https://www.ahqroc.org.tw/Class.aspx",
        "enabled": True,
        "execution": "cloud",
        "note": "已驗證可抓（2026-07-10 實測「課程清單」第 1 頁 8 筆，news_List 卡片式列表＋"
        "ClassDetail.aspx?sid= 詳情頁二段式，免登入伺服器渲染；robots.txt 404 視為未限制）。"
        "分頁為 ASP.NET postback，v1 只取第 1 頁。學分統一對映 quality（本會核心業務為醫品師"
        "／高階醫品師教育認證）。已排歧義（非醫策會、非中華民國品質學會）。",
    },
    "jct": {
        "label": "醫策會",
        "url": "https://attend.jct.org.tw/activity/event_news_calendar.php",
        "enabled": True,
        "execution": "local",
        # 標題含任一關鍵字即整筆不收錄（Lin 指示的排除規則；要加新規則往清單加詞即可，不用改程式）：
        # 數位課程/教學影片（2026-07-10，隨選非排定場次）、觀摩活動（2026-07-10，NHQA 現場觀摩非課程）
        "exclude_title_keywords": ["數位課程", "教學影片", "觀摩活動"],
        "note": "⚠️ 雲端更新不到：attend.jct.org.tw 對 GitHub Actions 機房 IP 連線逾時（LESSONS L-2026-07-10-008），由本機週排程 scripts/local_update.py 補抓。已驗證可抓（2026-07-10 v2 重工：Lin 發現首頁精選表只挑 5 筆漏課程，改抓活動"
        "月曆頁，免登入伺服器渲染；robots.txt 404 視為未限制）。月曆「下個月」是純 GET 連結"
        "（非 postback），本模組固定逐月串接抓 3 頁＝本月＋未來兩個月，涵蓋『三個月內』全部"
        "排定場次；2026 年 7 月單月實測即有數十筆真實場次，遠多於 v1 首頁的 5 筆。同一報名"
        "href 可能出現在不同天（多場次共用連結）甚至同一天出現多筆（同活動不同分組），去重鍵"
        "改用 (日期,href,標題) 三元組，不可只用 href。詳情頁地點標籤有「活動地點」（研討會類）"
        "與「課程地點」（實作課程/工作坊類）兩種，皆已支援。學分多為「申請中」等描述性文字，"
        "只有明確標示護理且有數字才計入 pro，否則存 ctext。數位課程／教學影片不收錄"
        "（Lin 2026-07-10 指示），僅收實體與直播排定場次。",
    },
    "hospice": {
        "label": "台灣安寧緩和護理學會",
        "url": "https://www.hospicenurse.org.tw/ehc-tahpn/s/w/edu/schedule/schedule1?integrationProperty=1",
        "enabled": True,
        "execution": "cloud",
        "note": "已驗證可抓（2026-07-10 實測 5 筆；URL 由 Lin 提供，?integrationProperty=1 為必要參數，"
        "帶參數為伺服器渲染表格非 JS 空殼；robots.txt 404 視為未限制）。下載層用 base.download_curl"
        "（系統信任清單驗證憑證）：此站憑證鏈的 TWCA 老式根憑證會被 requests/OpenSSL 嚴格驗證拒收，"
        "curl 驗證可過且同樣完整驗證，刻意不用 verify=False（診斷詳見 base.download_curl docstring）。",
    },
    "twna": {
        "label": "台灣護理學會",
        "url": "https://www.twna.org.tw/",
        "enabled": True,
        "execution": "manual",
        "note": "手動維護＋另存頁匯入器（robots 全站禁爬不自動抓，2026-07-10 實測"
        "act.e-twna.org.tw/robots.txt 為「User-agent: * / Disallow: /」）。初始資料"
        "2026-07-10 由偵察期快取頁匯入（42 筆）；日後更新：瀏覽器另存課程頁後跑"
        "scripts/import_twna_page.py，SOP 見 README。",
    },
    "tnpa": {
        "label": "台灣專科護理師學會",
        "url": "https://www.tnpa.org.tw/events/",
        "enabled": True,
        "execution": "local",
        "note": "⚠️ 雲端更新不到：tnpa.org.tw 對 GitHub Actions 機房 IP 回 403（LESSONS L-2026-07-10-008），由本機週排程 scripts/local_update.py 補抓。已驗證可抓（2026-07-10 實測「所有活動」列表 11 筆，event__item 卡片式，免登入伺服器渲染；"
        "robots.txt 對通用 UA 於 /events/ 允許，僅點名禁止具名 AI 爬蟲）。積點統一對映 np（本學會即專科護理師學會）。",
    },
    "itri": {
        "label": "工研院產業學院",
        # 「找課程」的「人工智慧」分類資料夾（Lin 2026-07-18 指定只收 AI 相關課程）；
        # FolderGUIDs 即該分類的固定識別碼，換分類範圍改這個參數。
        "url": "https://college.itri.org.tw/Lesson/LessonList?FolderGUIDs=41098C03-5148-4153-964A-2DE86697F68F",
        "enabled": True,
        "execution": "cloud",
        "note": "已驗證可抓（2026-07-18 實測人工智慧分類 83 筆課程，同頁 table#sample_1 含課名／"
        "開課日期／地點／時數，單一請求免詳情頁，免登入伺服器渲染；robots.txt 不存在（回自訂"
        "錯誤頁），依慣例視為未限制）。下載層用 base.download_curl：requests 對此站報 Missing"
        " Subject Key Identifier 憑證驗證失敗，與 hospice 同款老憑證問題（LESSONS"
        " L-2026-07-10-007），curl 系統信任清單驗證可過，禁止 verify=False。開課日期「進行中」"
        "的雲端教室自學課不收錄（比照 jct 2026-07-10 Lin 指示：僅收排定場次）；無護理積分"
        "（credits 留空），時數存 ctext；類別固定 tech（本來源即 AI 分類）。⚠️ 首次雲端排程"
        "跑完需核對是否被機房 IP 擋（LESSONS L-2026-07-10-008）；被擋要改三處（缺一即靜默停更）："
        "本欄 execution 改 local＋scripts/local_update.py 與 scripts/check_freshness.py 兩處的"
        " LOCAL_SOURCES 加 itri（皆為寫死清單，不吃 config）。",
    },
}

SCRAPE = {
    "window_days": 92,    # 只保留今天起算三個月內的活動（Lin 2026-07-10 訂；ondemand 隨選課程不受此限）
    "keep_past_days": 7,  # 已結束活動保留天數（方便回看上週）
    "delay_s": [1.0, 2.5],  # 對外請求之間的隨機延遲秒數範圍（爬蟲禮貌，勿調低於 1 秒）
    "timeout_s": 30,
    # contact 讓來源網站管理者需要時找得到人（用 repo URL，不放個人 email）
    "user_agent": "society-events-aggregator/1.0 (personal non-commercial aggregator; contact: https://github.com/Healon/nursing-coursetw-lin)",
}
