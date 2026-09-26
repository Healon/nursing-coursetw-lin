"""Purpose: 本機一鍵更新 —— 收雲端結果、匯入 twna 另存頁、補爬雲端被擋的 jct/tnpa、推送上線。
Input:  預設零參數。--force 跳過「當日已成功」護欄；--no-push 只更新本機不推送（除錯用）。
Output: data/*.json 與 index.html 更新、git commit＋push、macOS 桌面通知、繁中執行摘要。

設計（Lin 2026-07-11 核准；2026-07-26 改每日）：手動跑它＝一鍵指令；launchd 每天 16:00
跑它＝自動化；桌面儀表板捷徑背景跑它＝順手觸發。同一支程式、多種觸發，沒有兩套邏輯。
多重觸發靠兩道護欄不互撞：flock 單實例鎖（同時只跑一份）＋「當日已成功就跳過」。

為什麼需要本機跑（而不是全交給雲端）：
- jct（醫策會）與 tnpa（專科護理師學會）會擋 GitHub Actions 的機房 IP
  （見 ~/.claude/rules/LESSONS.md L-2026-07-10-008），只有台灣住宅 IP 爬得到。
- twna（台灣護理學會）robots 禁爬，靠維護者另存的頁面檔，而那些檔案只存在本機。

錯誤可見性：每一步失敗都要 stderr＋桌面通知，禁止靜默；git pull 失敗立即中止
（不在過期基底上工作，避免推送時打架）。排程時段刻意排在雲端每日更新（15:17）之後，
pull 恰好先收到雲端最新結果。
"""
from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import twna_freshness, twna_watch

ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "data" / "status.json"
TWNA_DATA_PATH = ROOT / "data" / "manual_twna.json"
TWNA_DOWNLOAD_DIR = twna_watch.DOWNLOAD_DIR
LOCAL_SOURCES = ("jct", "tnpa")
# 單實例鎖：儀表板背景觸發、launchd 16:00、手動一鍵可能同日多次或同時發生，
# 同時只允許一份實例跑（另一份立即安靜退出），避免並發 git commit／寫 data 檔互相打架。
LOCK_PATH = Path("/tmp/nursing-local-update.lock")

# 資料產物分兩類（2026-09-27）：
# - 原始資料：人工投入、只存在本機、雲端永不改寫（manual_twna.json）→ 同步時必須保留。
# - 衍生產物：由原始資料＋爬取結果重建（events/status/index）→ 未提交版本可丟棄、之後重建。
# 衍生產物若在 pull 前處於未提交狀態，雲端每日更新必定改到同一批檔，pull --ff-only 會拒絕
# 覆蓋而每天失敗（2026-08-16 至 09-26 本機更新停擺 42 天即此，見 AC_local-update-deadlock.md）。
SOURCE_DATA_PATHS = ("data/manual_twna.json",)
DERIVED_PATHS = ("data/events.json", "data/status.json", "index.html")
# 自動更新允許變動的檔案。工作區若有這清單以外的髒檔，代表 Lin 可能改到一半，
# 中止不碰，保護進行中的手動修改。
DATA_PATHS = DERIVED_PATHS + SOURCE_DATA_PATHS


def _porcelain_entries(porcelain: str) -> list[tuple[str, str]]:
    """把 `git status --porcelain` 輸出拆成 (狀態碼, 路徑)。"""
    entries: list[tuple[str, str]] = []
    for line in porcelain.splitlines():
        if not line.strip():
            continue
        entries.append((line[:2], line[3:].strip().strip('"')))
    return entries


def dirty_beyond_data(porcelain: str) -> list[str]:
    """從 `git status --porcelain` 輸出找出「資料產物以外」的髒檔；純函式，供測試。"""
    return [path for _, path in _porcelain_entries(porcelain) if path not in DATA_PATHS]


def dirty_derived(porcelain: str) -> list[str]:
    """找出已追蹤、但有未提交修改的衍生產物；純函式，供測試。未追蹤（??）的不算，checkout 還原不了。"""
    return [path for code, path in _porcelain_entries(porcelain) if path in DERIVED_PATHS and code != "??"]


def sources_to_rebuild(local_fresh_today: bool, twna_changed: bool) -> list[str]:
    """決定本次要跑 update.py 的來源；純函式，供測試。

    jct/tnpa 今天已成功就不重爬（爬蟲禮貌）；twna 只要原始資料有未提交變動就重建
    （零網路請求，且衍生產物在同步時已還原，不重建就會漏掉這批課程）。
    """
    codes = [] if local_fresh_today else list(LOCAL_SOURCES)
    if twna_changed:
        codes.append("twna")
    return codes


def sources_fresh_today(status_snapshot: dict, today_iso: str, codes=LOCAL_SOURCES) -> bool:
    """jct 與 tnpa 是否「今天都已成功抓過」；是則不必重爬（爬蟲禮貌護欄）。純函式，供測試。"""
    sources = status_snapshot.get("sources", {})
    return all(sources.get(c, {}).get("last_success", "") == today_iso for c in codes)


def _notify(message: str) -> None:
    try:
        subprocess.run(
            ["osascript", "-e", f'display notification "{message}" with title "護理教育訓練網站"'],
            capture_output=True, timeout=10,
        )
    except Exception:
        pass


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def sync_with_cloud() -> tuple[bool, str]:
    """先把未提交的衍生產物還原，再 fast-forward 到雲端最新；原始資料原樣保留。

    衍生產物稍後一律重建，丟掉本機未提交版本不會失去資訊；原始資料雲端永不改寫，
    留在工作區也不會擋住 fast-forward。本機若有未推送的 commit 仍會失敗並回報，
    不自動 rebase 或 reset（那需要人判斷）。
    """
    porcelain = _git("status", "--porcelain")
    if porcelain.returncode != 0:
        return False, porcelain.stderr.strip()
    derived = dirty_derived(porcelain.stdout)
    if derived:
        restore = _git("checkout", "--", *derived)
        if restore.returncode != 0:
            return False, (restore.stderr or restore.stdout).strip()
        print(f"[local-update] 已還原 {len(derived)} 個未提交的衍生產物，稍後依原始資料重建", flush=True)
    pull = _git("pull", "--ff-only", "origin", "main")
    if pull.returncode != 0:
        return False, (pull.stderr or pull.stdout).strip()
    return True, ""


def push_with_one_rebase_retry() -> tuple[bool, str]:
    """Push once, recovering from one ordinary non-fast-forward race only."""
    first = _git("push", "origin", "main")
    if first.returncode == 0:
        return True, ""
    detail = (first.stderr or first.stdout).strip()
    if "non-fast-forward" not in detail and "fetch first" not in detail.lower():
        return False, detail

    rebase = _git("pull", "--rebase", "origin", "main")
    if rebase.returncode != 0:
        conflict = (rebase.stderr or rebase.stdout).strip()
        _git("rebase", "--abort")
        return False, conflict

    second = _git("push", "origin", "main")
    return second.returncode == 0, (second.stderr or second.stdout).strip()


def twna_summary(hits_count: int, added: int, raw: dict, now: dt.datetime) -> str:
    """Describe whether TWNA was imported, recently confirmed, or left stale."""
    if hits_count:
        return f"匯入 {hits_count} 檔、新增 {added} 筆"
    if twna_freshness.has_activity_in_current_cycle(raw, now):
        return "本週已確認，無新匯入檔"
    return "尚未核對，本次沿用上次資料"


def _fail(step: str, detail: str) -> int:
    print(f"[local-update] ❌ {step}失敗：{detail}", file=sys.stderr)
    _notify(f"本機更新失敗（{step}），詳見終端機或 /tmp/nursing-local-update.log")
    return 1


def acquire_single_instance_lock():
    """搶單實例鎖；成功回傳鎖檔 handle（呼叫端保留引用到結束），搶不到回 None。

    flock 隨行程結束（含 crash）由核心自動釋放，不會留殘鎖；LOCK_NB 讓後到者立即
    知道有人在跑，安靜退出即可（exit 0——這是預期協調，不是錯誤）。
    """
    handle = LOCK_PATH.open("w")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return None
    return handle


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="本機一鍵更新（jct/tnpa 補爬＋twna 匯入＋推送）")
    ap.add_argument("--force", action="store_true", help="跳過「當日已成功」護欄，強制重爬 jct/tnpa")
    ap.add_argument("--no-push", action="store_true", help="只更新本機，不 commit/push（除錯用）")
    args = ap.parse_args(argv)

    lock = acquire_single_instance_lock()
    if lock is None:
        print("[local-update] 另一個更新實例正在執行，本次直接退出（單實例鎖）", flush=True)
        return 0

    print(f"[local-update] 開始（{dt.datetime.now().strftime('%Y-%m-%d %H:%M')}）", flush=True)

    # 1. 工作區保護：資料產物以外的髒檔 → 中止
    porcelain = _git("status", "--porcelain")
    if porcelain.returncode != 0:
        return _fail("git 檢查", porcelain.stderr.strip()[:120])
    offending = dirty_beyond_data(porcelain.stdout)
    if offending:
        return _fail("工作區檢查", f"有未提交的非資料檔改動：{', '.join(offending[:5])}（請先處理或收起來）")

    # 2. 先收雲端結果，避免之後推送打架；未提交的衍生產物先還原，否則 pull 會被擋
    synced, detail = sync_with_cloud()
    if not synced:
        return _fail("git pull", detail[:160])
    print("[local-update] ✔ 已同步雲端最新結果")

    # 3. 掃下載資料夾有無 twna 另存頁（重用監看器邏輯：辨識、匯入、去重、歸檔）
    downloads = TWNA_DOWNLOAD_DIR
    twna_hits = 0
    twna_added = 0
    try:
        if downloads.is_dir():
            hits = twna_watch.scan_folder(downloads)
            if hits:
                twna_hits = len(hits)
                for f in hits:
                    stats = twna_watch.process(f)
                    twna_added += stats["added"]
        twna_raw = (
            json.loads(TWNA_DATA_PATH.read_text(encoding="utf-8"))
            if TWNA_DATA_PATH.exists()
            else {}
        )
        twna_note = twna_summary(
            twna_hits,
            twna_added,
            twna_raw,
            dt.datetime.now().astimezone(),
        )
    except Exception as exc:  # noqa: BLE001 - operational boundary must notify instead of traceback
        return _fail("twna import", f"{type(exc).__name__}: {exc}"[:160])
    print(f"[local-update] ✔ twna 另存頁：{twna_note}")

    # 4. 決定要重建哪些來源：jct/tnpa 今天已成功就不重爬（--force 可強制）；
    #    twna 原始資料有未提交變動（本次匯入或先前遺留）就重建，把課程併進衍生產物
    today_iso = dt.date.today().isoformat()
    snapshot = json.loads(STATUS_PATH.read_text(encoding="utf-8")) if STATUS_PATH.exists() else {}
    local_fresh = not args.force and sources_fresh_today(snapshot, today_iso)
    if local_fresh:
        print(f"[local-update] ✔ jct/tnpa 今天（{today_iso}）已成功抓過，跳過重爬（--force 可強制）")
    twna_status = _git("status", "--porcelain", "--", *SOURCE_DATA_PATHS)
    if twna_status.returncode != 0:
        return _fail("git 檢查", twna_status.stderr.strip()[:120])
    codes = sources_to_rebuild(local_fresh, bool(twna_status.stdout.strip()))
    if codes:
        print(f"[local-update] 更新來源：{'、'.join(codes)}（jct/tnpa 走台灣住宅 IP，twna 只讀本機資料）…")
        upd = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "update.py"), "--sources", ",".join(codes)],
            cwd=ROOT,
        )
        if upd.returncode != 0:
            return _fail("update pipeline", f"exit {upd.returncode}")

    # 5. 健康檢查結果（顯示用；partial 不擋，與雲端同語意）
    chk = subprocess.run([sys.executable, str(ROOT / "scripts" / "status.py"), "--check"], cwd=ROOT)
    print(f"[local-update] 健康檢查 exit={chk.returncode}（0＝正常或部分警示，1＝全滅）")

    # 6. 有變更才 commit＋push
    porcelain = _git("status", "--porcelain")
    if not porcelain.stdout.strip():
        print("[local-update] 今天沒有新資料，不需要推送。")
        _notify("本機更新完成：今天沒有新資料")
        return 0
    if args.no_push:
        print("[local-update] --no-push：變更留在本機，未提交。")
        return 0

    for step, cmd in [
        ("git add", ["add", *DATA_PATHS]),
        ("git commit", ["commit", "-m", "chore: local sources update (jct/tnpa/twna)"]),
    ]:
        r = _git(*cmd)
        if r.returncode != 0:
            return _fail(step, (r.stderr or r.stdout).strip()[:160])

    pushed, detail = push_with_one_rebase_retry()
    if not pushed:
        return _fail("git push", detail[:160])

    print("[local-update] ✔ 已推送，GitHub Pages 一至兩分鐘後更新")
    _notify(f"本機更新完成並已推送（twna：{twna_note}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
