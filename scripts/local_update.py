"""Purpose: 本機一鍵更新 —— 收雲端結果、匯入 twna 另存頁、補爬雲端被擋的 jct/tnpa、推送上線。
Input:  預設零參數。--force 跳過「當日已成功」護欄；--no-push 只更新本機不推送（除錯用）。
Output: data/*.json 與 index.html 更新、git commit＋push、macOS 桌面通知、繁中執行摘要。

設計（Lin 2026-07-11 核准）：手動跑它＝一鍵指令；launchd 每週日 16:00 跑它＝自動化。
同一支程式、兩種觸發，沒有兩套邏輯。

為什麼需要本機跑（而不是全交給雲端）：
- jct（醫策會）與 tnpa（專科護理師學會）會擋 GitHub Actions 的機房 IP
  （見 ~/.claude/rules/LESSONS.md L-2026-07-10-008），只有台灣住宅 IP 爬得到。
- twna（台灣護理學會）robots 禁爬，靠維護者另存的頁面檔，而那些檔案只存在本機。

錯誤可見性：每一步失敗都要 stderr＋桌面通知，禁止靜默；git pull 失敗立即中止
（不在過期基底上工作，避免推送時打架）。排程時段刻意排在雲端週更（週日 15:00）之後，
pull 恰好先收到雲端最新結果。
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import twna_freshness, twna_watch

ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "data" / "status.json"
TWNA_DATA_PATH = ROOT / "data" / "manual_twna.json"
LOCAL_SOURCES = ("jct", "tnpa")

# 自動更新允許變動的檔案（資料產物）。工作區若有這清單以外的髒檔，代表 Lin 可能改到一半，
# 中止不碰，保護進行中的手動修改。
DATA_PATHS = ("data/events.json", "data/status.json", "data/manual_twna.json", "index.html")


def dirty_beyond_data(porcelain: str) -> list[str]:
    """從 `git status --porcelain` 輸出找出「資料產物以外」的髒檔；純函式，供測試。"""
    offending: list[str] = []
    for line in porcelain.splitlines():
        if not line.strip():
            continue
        path = line[3:].strip().strip('"')
        if path not in DATA_PATHS:
            offending.append(path)
    return offending


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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="本機一鍵更新（jct/tnpa 補爬＋twna 匯入＋推送）")
    ap.add_argument("--force", action="store_true", help="跳過「當日已成功」護欄，強制重爬 jct/tnpa")
    ap.add_argument("--no-push", action="store_true", help="只更新本機，不 commit/push（除錯用）")
    args = ap.parse_args(argv)

    print(f"[local-update] 開始（{dt.datetime.now().strftime('%Y-%m-%d %H:%M')}）", flush=True)

    # 1. 工作區保護：資料產物以外的髒檔 → 中止
    porcelain = _git("status", "--porcelain")
    if porcelain.returncode != 0:
        return _fail("git 檢查", porcelain.stderr.strip()[:120])
    offending = dirty_beyond_data(porcelain.stdout)
    if offending:
        return _fail("工作區檢查", f"有未提交的非資料檔改動：{', '.join(offending[:5])}（請先處理或收起來）")

    # 2. 先收雲端結果（週日 15:00 的雲端週更），避免之後推送打架
    pull = _git("pull", "--ff-only", "origin", "main")
    if pull.returncode != 0:
        return _fail("git pull", pull.stderr.strip()[:160])
    print("[local-update] ✔ 已同步雲端最新結果")

    # 3. 掃下載資料夾有無 twna 另存頁（重用監看器邏輯：辨識、匯入、去重、歸檔）
    downloads = Path.home() / "Downloads"
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

    # 4. 防狂打護欄：今天已成功抓過 jct/tnpa 就不重爬（--force 可強制）
    today_iso = dt.date.today().isoformat()
    snapshot = json.loads(STATUS_PATH.read_text(encoding="utf-8")) if STATUS_PATH.exists() else {}
    if not args.force and sources_fresh_today(snapshot, today_iso):
        print(f"[local-update] ✔ jct/tnpa 今天（{today_iso}）已成功抓過，跳過重爬（--force 可強制）")
    else:
        print("[local-update] 爬取 jct＋tnpa（台灣住宅 IP 專屬的兩家）…")
        upd = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "update.py"), "--sources", ",".join(LOCAL_SOURCES)],
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
