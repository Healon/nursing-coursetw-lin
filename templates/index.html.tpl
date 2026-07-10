<!doctype html>
<!--
  樣板原始檔：templates/index.html.tpl（要改版面請改這裡）。
  根目錄 index.html 是 scripts/build.py 的產物，直接編輯會在下次 build 被覆蓋。
  資料注入點：THEME／CONFIG／STATUS／EVENTS 四個 marker 區塊，加上文字 token 替換（小老鼠符號×2 包住的大寫名稱）。
-->
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>@@SITE_TITLE@@</title>
<meta name="description" content="@@SITE_SUBTITLE@@">
<style>
/* THEME:START */
:root { /* build 時由 config/site.py 的 THEME 注入 CSS 變數 */ }
/* THEME:END */

* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0;
  font-family: system-ui, -apple-system, "PingFang TC", "Heiti TC", "Microsoft JhengHei", "Noto Sans TC", sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.55;
}
a { color: var(--primary); }

.wrap { max-width: 1080px; margin: 0 auto; padding: 0 16px; }

/* ── Header ─────────────────────────────────────────── */
.site-header {
  background: linear-gradient(135deg, var(--primary), var(--primary-dark));
  color: #fff;
  padding: 30px 0 26px;
}
.site-header h1 { margin: 0 0 6px; font-size: 1.7rem; letter-spacing: .02em; }
.site-header .subtitle { margin: 0; opacity: .92; font-size: 1rem; }
.site-header .updated { margin: 10px 0 0; font-size: .82rem; opacity: .78; }

/* 頁首狀態橫幅：來源異常時顯示（錯誤可見性，不點開也看得到） */
#status-banner { padding: 10px 16px; text-align: center; font-weight: 600; font-size: .92rem; }
#status-banner.partial { background: #fef3c7; color: #92400e; }
#status-banner.down { background: var(--warn-bg); color: var(--warn); }

/* ── Controls ───────────────────────────────────────── */
.controls {
  background: var(--card-bg);
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 14px 16px;
  margin: 18px 0 14px;
}
.controls .row { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
#q {
  flex: 1 1 240px;
  padding: 9px 12px;
  border: 1px solid var(--line);
  border-radius: 9px;
  font-size: .95rem;
  background: var(--bg);
}
#q:focus, #sort:focus { outline: 2px solid var(--primary); outline-offset: 1px; }
#sort {
  padding: 9px 10px;
  border: 1px solid var(--line);
  border-radius: 9px;
  font-size: .9rem;
  background: var(--bg);
}
#clear {
  padding: 9px 14px;
  border: 1px solid var(--line);
  border-radius: 9px;
  background: transparent;
  color: var(--muted);
  font-size: .9rem;
  cursor: pointer;
}
#clear:hover { color: var(--text); border-color: var(--muted); }

.pill-group { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-top: 10px; }
.group-label { font-size: .82rem; color: var(--muted); margin-right: 2px; min-width: 2.6em; }
.pill {
  border: 1px solid var(--pill-c, var(--line));
  background: var(--card-bg);
  border-radius: 999px;
  padding: 4px 12px;
  font-size: .85rem;
  color: var(--pill-c, var(--text));
  cursor: pointer;
}
.pill:hover { background: var(--bg); }
.pill[aria-pressed="true"] { background: var(--pill-c, var(--primary)); border-color: var(--pill-c, var(--primary)); color: #fff; }
/* 三組篩選各一色（config THEME 的 pill_cat/pill_region/pill_src 控制） */
#pills-cat { --pill-c: var(--pill-cat); }
#pills-region { --pill-c: var(--pill-region); }
#pills-src { --pill-c: var(--pill-src); }

.stats { margin: 12px 0 0; font-size: .85rem; color: var(--muted); }

/* ── Cards ──────────────────────────────────────────── */
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 14px;
  padding-bottom: 8px;
}
.month-divider {
  grid-column: 1 / -1;
  margin: 14px 0 0;
  padding-bottom: 6px;
  font-size: 1.02rem;
  color: var(--muted);
  font-weight: 700;
  border-bottom: 1px solid var(--line);
}
.card {
  background: var(--card-bg);
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.card.is-past { opacity: .62; }
.card-top { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }
.date-line { font-size: .95rem; font-weight: 700; color: var(--text); letter-spacing: .01em; }
.date-line.ondemand { color: var(--muted); font-weight: 600; }
.card-title { margin: 0; font-size: 1.02rem; line-height: 1.4; }
.card-title a { color: var(--text); text-decoration: none; }
.card-title a:hover { color: var(--primary); text-decoration: underline; }
.card-loc { margin: 0; font-size: .86rem; color: var(--muted); }
.card-tags, .card-credits { display: flex; flex-wrap: wrap; gap: 6px; }
.tag {
  font-size: .76rem;
  color: var(--muted);
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 2px 7px;
  background: var(--bg);
}
/* 卡片小標籤與上方篩選 pill 同色系（config THEME 的 pill_* 控制）：淡色底＋同色字 */
.tag-cat { color: var(--pill-cat); border-color: transparent; background: color-mix(in srgb, var(--pill-cat) 11%, #fff); }
.tag-region { color: var(--pill-region); border-color: transparent; background: color-mix(in srgb, var(--pill-region) 11%, #fff); }
.tag-src { color: var(--pill-src); border-color: transparent; background: color-mix(in srgb, var(--pill-src) 11%, #fff); }
.tag.online { color: var(--primary); border-color: var(--primary); background: transparent; }
.badge { font-size: .78rem; border-radius: 6px; padding: 2px 8px; white-space: nowrap; }
.badge.credit { background: var(--accent); color: #fff; }
.badge.nocredit { color: var(--muted); border: 1px dashed var(--line); }
.badge.soon { color: var(--primary); border: 1px solid var(--primary); font-weight: 600; }
.badge.today { background: #15803d; color: #fff; font-weight: 600; }
.badge.past { color: var(--muted); border: 1px solid var(--line); }
.card-note { margin: 0; font-size: .82rem; color: var(--muted); font-style: italic; }
.card-actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: auto; padding-top: 4px; }
.btn {
  display: inline-block;
  background: var(--primary);
  color: #fff;
  text-decoration: none;
  font-size: .86rem;
  padding: 7px 13px;
  border-radius: 9px;
}
.btn:hover { background: var(--primary-dark); }
.btn.ghost { background: transparent; color: var(--primary); border: 1px solid var(--primary); }
.btn.ghost:hover { background: var(--primary); color: #fff; }

.empty {
  text-align: center;
  color: var(--muted);
  padding: 40px 0;
  font-size: .95rem;
}

/* ── Footer ─────────────────────────────────────────── */
.site-footer {
  border-top: 1px solid var(--line);
  margin-top: 26px;
  padding: 20px 0 30px;
  font-size: .85rem;
  color: var(--muted);
}
#source-stats { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }
.chip {
  background: var(--card-bg);
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 3px 10px;
  font-size: .8rem;
}
.disclaimer, .footer-note, .credit-line { margin: 8px 0 0; }
.credit-line { font-size: .78rem; opacity: .8; }

@media (max-width: 560px) {
  .site-header h1 { font-size: 1.35rem; }
  #q { flex-basis: 100%; }
}
</style>
</head>
<body>

<header class="site-header">
  <div class="wrap">
    <h1>@@SITE_TITLE@@</h1>
    <p class="subtitle">@@SITE_SUBTITLE@@</p>
    <p class="updated">資料更新時間：@@UPDATED_AT@@</p>
  </div>
</header>

<div id="status-banner" hidden></div>

<main class="wrap">
  <section class="controls" aria-label="搜尋與篩選">
    <div class="row">
      <input id="q" type="search" placeholder="搜尋活動名稱或地點…" aria-label="關鍵字搜尋">
      <select id="sort" aria-label="排序方式">
        <option value="date-asc">日期：由近到遠</option>
        <option value="date-desc">日期：由遠到近</option>
        <option value="credits-desc">積分：由高到低</option>
      </select>
      <button id="clear" type="button">清除篩選</button>
    </div>
    <div class="pill-group" id="pills-cat"><span class="group-label">類別</span></div>
    <div class="pill-group" id="pills-region"><span class="group-label">地區</span></div>
    <div class="pill-group" id="pills-src"><span class="group-label">來源</span></div>
    <p class="stats" id="stats" role="status"></p>
  </section>

  <section id="cards" class="grid" aria-live="polite"></section>
  <p id="empty" class="empty" hidden>沒有符合條件的活動。試著清除部分篩選條件。</p>
</main>

<footer class="site-footer">
  <div class="wrap">
    <div id="source-stats"></div>
    <p class="disclaimer">@@DISCLAIMER@@</p>
    <p class="footer-note">@@FOOTER_NOTE@@</p>
    <p class="credit-line">本頁由開源靜態模板自動產生（GitHub Actions 排程爬蟲＋GitHub Pages）。</p>
  </div>
</footer>

<script>
"use strict";
/* CONFIG:START */
const CONFIG = null; /* build 時注入 */
/* CONFIG:END */
/* STATUS:START */
const SOURCE_STATUS = null; /* build 時注入 */
/* STATUS:END */
/* EVENTS:START */
const EVENTS = null; /* build 時注入 */
/* EVENTS:END */

/* 未經 build 直接開樣板時，顯示明確錯誤而非空白頁（錯誤可見性） */
if (!Array.isArray(EVENTS) || !CONFIG) {
  document.body.insertAdjacentHTML(
    "afterbegin",
    '<p style="background:#fee2e2;color:#991b1b;padding:12px;text-align:center;margin:0">' +
      '此檔為未經 build 的樣板：請執行 python3 scripts/update.py 產生 index.html。</p>'
  );
  throw new Error("template opened without build injection");
}

const $ = (sel) => document.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => (
  { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
));
const WEEKDAYS = ["日", "一", "二", "三", "四", "五", "六"];

const state = { q: "", sort: "date-asc", cat: new Set(), region: new Set(), src: new Set() };

function parseDate(s) {
  const [y, m, d] = s.split("-").map(Number);
  return new Date(y, m - 1, d);
}
function startOfToday() {
  const n = new Date();
  return new Date(n.getFullYear(), n.getMonth(), n.getDate());
}
function daysUntil(s) {
  return Math.round((parseDate(s) - startOfToday()) / 86400000);
}
function creditTotal(ev) {
  return Object.values(ev.credits || {}).reduce((a, b) => a + b, 0);
}
function safeUrl(u) {
  return /^https?:\/\//i.test(u || "") ? u : "";
}

/* 「加入 Google 行事曆」：純前端組 URL 參數，不呼叫任何 API（整日事件，隔日為結束日） */
function gcalUrl(ev) {
  const start = ev.date.replace(/-/g, "");
  const end = new Date(parseDate(ev.date).getTime() + 86400000);
  const pad = (n) => String(n).padStart(2, "0");
  const endStr = "" + end.getFullYear() + pad(end.getMonth() + 1) + pad(end.getDate());
  const params = new URLSearchParams({
    action: "TEMPLATE",
    text: ev.title,
    dates: start + "/" + endStr,
    details: (safeUrl(ev.url) || "") + (ev.ctext ? "\n" + ev.ctext : ""),
    location: ev.location || "",
  });
  return "https://calendar.google.com/calendar/render?" + params.toString();
}

function matches(ev) {
  if (state.q) {
    const q = state.q.toLowerCase();
    if (!(ev.title + " " + ev.location).toLowerCase().includes(q)) return false;
  }
  if (state.cat.size && !state.cat.has(ev.cat)) return false;
  if (state.region.size && !state.region.has(ev.region)) return false;
  if (state.src.size && !state.src.has(ev.src)) return false;
  return true;
}

function sortEvents(list) {
  if (state.sort === "date-desc") {
    list.sort((a, b) => b.date.localeCompare(a.date) || a.title.localeCompare(b.title));
  } else if (state.sort === "credits-desc") {
    list.sort((a, b) => creditTotal(b) - creditTotal(a) || a.date.localeCompare(b.date));
  } else {
    list.sort((a, b) => a.date.localeCompare(b.date) || a.title.localeCompare(b.title));
  }
}

function monthLabel(key) {
  const [y, m] = key.split("-");
  return y + " 年 " + Number(m) + " 月";
}

function countdownBadge(ev) {
  // 隨選課程沒有「場次日期」概念：不倒數、不標已結束（資料上的日期是公告／上架日）
  if (ev.ondemand) return '<span class="badge soon">隨時可上</span>';
  const n = daysUntil(ev.date);
  if (n < 0) return '<span class="badge past">已結束</span>';
  if (n === 0) return '<span class="badge today">今天</span>';
  return '<span class="badge soon">' + n + ' 天後</span>';
}

function cardHTML(ev) {
  const d = parseDate(ev.date);
  const url = safeUrl(ev.url);
  const credits = Object.entries(ev.credits || {})
    .map(([k, v]) => '<span class="badge credit">' + esc(CONFIG.creditTypes[k] || k) + ' ' + esc(v) + ' 點</span>')
    .join("");
  const tags = [
    '<span class="tag tag-cat">' + esc(CONFIG.categories[ev.cat] || ev.cat) + '</span>',
    '<span class="tag tag-region">' + esc(CONFIG.regions[ev.region] || ev.region) + '</span>',
    '<span class="tag tag-src">' + esc(CONFIG.sources[ev.src] || ev.src) + '</span>',
    // 「線上」有兩個資料載體：region=online（供地區篩選）與 online 旗標（供卡片標記）。
    // 純線上課兩者同時成立，若都畫會出現兩顆「線上」（2026-07-10 Lin 實測回報的重複標籤）。
    // 守門規則：地區標籤已是「線上」就不畫第二顆；只有混合型（實體地區＋可線上）才補線上標記。
    ev.online && ev.region !== "online" ? '<span class="tag online">線上</span>' : "",
    ev.ondemand ? '<span class="tag online">隨選</span>' : "",
  ].join("");
  const title = url
    ? '<a href="' + esc(url) + '" target="_blank" rel="noopener noreferrer">' + esc(ev.title) + '</a>'
    : esc(ev.title);
  const dateBlock = ev.ondemand
    ? '<span class="date-line ondemand">數位課程</span>'
    : '<span class="date-line">' + d.getFullYear() + '/' + (d.getMonth() + 1) + '/' + d.getDate() +
      '（' + WEEKDAYS[d.getDay()] + '）</span>';
  return (
    '<article class="card' + (!ev.ondemand && daysUntil(ev.date) < 0 ? " is-past" : "") + '">' +
      '<div class="card-top">' + dateBlock + countdownBadge(ev) +
      '</div>' +
      '<h3 class="card-title">' + title + '</h3>' +
      (ev.location ? '<p class="card-loc">' + esc(ev.location) + '</p>' : "") +
      '<div class="card-tags">' + tags + '</div>' +
      '<div class="card-credits">' + (credits || '<span class="badge nocredit">積分依主辦公告</span>') + '</div>' +
      (ev.ctext ? '<p class="card-note">' + esc(ev.ctext) + '</p>' : "") +
      '<div class="card-actions">' +
        (url ? '<a class="btn" href="' + esc(url) + '" target="_blank" rel="noopener noreferrer">報名資訊</a>' : "") +
        '<a class="btn ghost" href="' + esc(gcalUrl(ev)) + '" target="_blank" rel="noopener noreferrer">加入 Google 行事曆</a>' +
      '</div>' +
    '</article>'
  );
}

function render() {
  const filtered = EVENTS.filter(matches);
  // 隨選課程與有場次日期的活動分開呈現：隨選的「日期」只是公告日，混入月份分組
  // 會被誤標成過去的已結束活動（實例：醫策會數位課程掛 2024 公告日）
  const dated = filtered.filter((e) => !e.ondemand);
  const ondemand = filtered.filter((e) => e.ondemand);
  sortEvents(dated);
  ondemand.sort((a, b) => a.title.localeCompare(b.title));
  const grouping = state.sort.indexOf("date") === 0;
  const parts = [];
  let lastMonth = "";
  for (const ev of dated) {
    if (grouping) {
      const mk = ev.date.slice(0, 7);
      if (mk !== lastMonth) {
        lastMonth = mk;
        parts.push('<h2 class="month-divider">' + esc(monthLabel(mk)) + '</h2>');
      }
    }
    parts.push(cardHTML(ev));
  }
  if (ondemand.length) {
    parts.push('<h2 class="month-divider">隨選數位課程（不限日期，隨時可上）</h2>');
    for (const ev of ondemand) parts.push(cardHTML(ev));
  }
  $("#cards").innerHTML = parts.join("");
  $("#empty").hidden = filtered.length !== 0;
  $("#stats").textContent = "顯示 " + filtered.length + " 筆／共 " + EVENTS.length + " 筆";
}

/* pill 只列出資料中實際存在的值，避免一排永遠篩不到東西的死 pill */
function buildPills(groupEl, labels, stateSet, field) {
  const present = new Set(EVENTS.map((e) => e[field]));
  for (const code of Object.keys(labels)) {
    if (!present.has(code)) continue;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "pill";
    btn.textContent = labels[code];
    btn.setAttribute("aria-pressed", "false");
    btn.addEventListener("click", () => {
      if (stateSet.has(code)) {
        stateSet.delete(code);
        btn.setAttribute("aria-pressed", "false");
      } else {
        stateSet.add(code);
        btn.setAttribute("aria-pressed", "true");
      }
      render();
    });
    groupEl.appendChild(btn);
  }
}

/* 來源健康狀態（2026-07-10 Lin 指示改版）：公開頁不顯示個別來源的錯誤訊息——
   訪客不需要看原始技術錯誤；維護者的錯誤可見性走 data/status.json、GitHub Actions
   紅燈、本機更新的桌面通知三個管道，資訊沒有變少、只是換對象。
   公開頁保留：頁尾中性筆數 chips（含停更來源的「更新至」日期，誠實不驚悚）；
   以及唯一例外「全滅紅橫幅」——所有來源都失敗代表整頁可能過期，這是訪客權益，保留。 */
/* 來源能見度規則：列入健康快照（＝enabled）或實際有課程才顯示 chip 與篩選 pill；
   停用且無資料的來源（如已下線的示範資料、尚未填資料的手動來源）不佔版面當噪音 */
function srcVisible(code) {
  const st = (SOURCE_STATUS && SOURCE_STATUS.sources) || {};
  return Boolean(st[code]) || EVENTS.some((e) => e.src === code);
}

function renderStatus() {
  const st = (SOURCE_STATUS && SOURCE_STATUS.sources) || {};
  const counts = {};
  EVENTS.forEach((e) => { counts[e.src] = (counts[e.src] || 0) + 1; });

  $("#source-stats").innerHTML = Object.entries(CONFIG.sources)
    .filter(([code]) => srcVisible(code))
    .map(([code, label]) => {
      const s = st[code];
      const stale = s && s.status !== "ok" && s.last_success
        ? '（更新至 ' + esc(s.last_success) + '）' : '';
      return '<span class="chip">' + esc(label) + '：' + (counts[code] || 0) + ' 筆' + stale + '</span>';
    })
    .join("");

  const overall = SOURCE_STATUS && SOURCE_STATUS.overall;
  if (overall === "down") {
    const banner = $("#status-banner");
    banner.hidden = false;
    banner.classList.add("down");
    banner.textContent = "資料來源更新暫時中斷，本頁內容可能非最新，活動請以各學會官網公告為準。";
  }
}

buildPills($("#pills-cat"), CONFIG.categories, state.cat, "cat");
buildPills($("#pills-region"), CONFIG.regions, state.region, "region");
buildPills(
  $("#pills-src"),
  Object.fromEntries(Object.entries(CONFIG.sources).filter(([code]) => srcVisible(code))),
  state.src,
  "src"
);
$("#q").addEventListener("input", (e) => { state.q = e.target.value.trim(); render(); });
$("#sort").addEventListener("change", (e) => { state.sort = e.target.value; render(); });
$("#clear").addEventListener("click", () => {
  state.q = "";
  $("#q").value = "";
  state.cat.clear();
  state.region.clear();
  state.src.clear();
  document.querySelectorAll('.pill[aria-pressed="true"]').forEach((b) => b.setAttribute("aria-pressed", "false"));
  render();
});
renderStatus();
render();
</script>
</body>
</html>
