"""Purpose: twna 另存頁「零指令」自動匯入器 —— 掃描下載資料夾，發現另存的課程頁就自動走完
        匯入→更新→重建→通知，維護者只剩「瀏覽器另存新檔」一個動作。
Input:  --folder 指定掃描資料夾（預設 ~/Downloads）；單次掃描即結束（配合 launchd WatchPaths
        觸發，不常駐、不輪詢）。
Output: data/manual_twna.json 更新、網站重建（update.py --sources twna）、處理過的檔案移入
        <folder>/twna-imported/ 歸檔（避免重複處理）、macOS 桌面通知（盡力而為）。

合規背景（重要，勿刪）：act.e-twna.org.tw 的 robots.txt 全站 Disallow，本專案不對該站發出
任何自動化請求。本監看器全程零網路請求：它只認「維護者本人用瀏覽器另存到本機」的靜態檔案。
自動化的是存檔之後的粗工，不是抓取；「人開頁面、人存檔」這一步依守則必須保留為人類動作。

用法：
    手動單次掃描：  .venv/bin/python scripts/twna_watch.py
    配合 launchd：  安裝 scripts/launchd/com.lin.twna-watch.plist（見 README 方式三），
                    之後任何檔案落入 ~/Downloads 都會觸發一次快速掃描，非 twna 頁面立即結束。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import import_twna_page

PROJECT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT / "data" / "manual_twna.json"
ARCHIVE_DIRNAME = "twna-imported"
MAX_AGE_DAYS = 14      # 只看最近另存的檔，太舊的不猜
MAX_READ_BYTES = 400_000  # 判斷是否為 twna 頁只需讀開頭，不用整檔載入


def is_twna_page(html: str) -> bool:
    """判斷一段 HTML 是否為 twna 課程列表頁的另存檔；純函式，供測試。

    同時要求「GridView 容器 id」與「站台特徵字串」兩個訊號都在，避免把其他 ASP.NET
    網站的另存頁誤認進來（寧可漏認請使用者跑手動指令，不可誤匯入別站資料）。
    """
    return "ContentPlaceHolder1_GridView1" in html and ("ActSign" in html or "e-twna" in html)


def scan_folder(folder: Path, *, now: float | None = None) -> list[Path]:
    """找出資料夾內「最近 MAX_AGE_DAYS 天、內容像 twna 課程頁」的 .html/.htm 檔；純掃描不處理。"""
    now = now or time.time()
    hits: list[Path] = []
    for f in sorted(folder.iterdir()):
        if not f.is_file() or f.suffix.lower() not in (".html", ".htm"):
            continue
        if now - f.stat().st_mtime > MAX_AGE_DAYS * 86400:
            continue
        try:
            head = f.read_text(encoding="utf-8", errors="replace")[:MAX_READ_BYTES]
        except OSError as e:
            print(f"[twna-watch] 無法讀取 {f.name}：{e}", file=sys.stderr)
            continue
        if is_twna_page(head):
            hits.append(f)
    return hits


def _notify(message: str) -> None:
    """macOS 桌面通知；失敗就靜靜略過（通知只是體驗加分，不是資料流的一部分，可容忍失敗）。"""
    try:
        subprocess.run(
            ["osascript", "-e",
             f'display notification "{message}" with title "護理教育訓練網站"'],
            capture_output=True, timeout=10,
        )
    except Exception:
        pass


def process(f: Path) -> dict:
    """匯入單一另存頁 → 更新網站 → 歸檔原始檔。任何一步失敗都讓例外浮出（launchd log 可見）。"""
    stats = import_twna_page.run(f, DATA_PATH)
    if stats["added"] > 0:
        # 有新課程才值得重建網站；沒新增就省下這步（重建仍是本機動作，只是避免無謂 churn）
        subprocess.run(
            [sys.executable, str(PROJECT / "scripts" / "update.py"), "--sources", "twna"],
            check=True, cwd=PROJECT, capture_output=True,
        )
    archive = f.parent / ARCHIVE_DIRNAME
    archive.mkdir(exist_ok=True)
    target = archive / f.name
    if target.exists():
        target = archive / f"{int(time.time())}-{f.name}"
    f.rename(target)
    return stats


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="掃描下載資料夾，自動匯入 twna 另存課程頁")
    ap.add_argument("--folder", default=str(Path.home() / "Downloads"))
    args = ap.parse_args(argv)

    folder = Path(args.folder).expanduser()
    if not folder.is_dir():
        print(f"[twna-watch] 資料夾不存在：{folder}", file=sys.stderr)
        return 1

    hits = scan_folder(folder)
    if not hits:
        return 0  # launchd 每次下載都會觸發，非 twna 檔案安靜結束是正常路徑

    for f in hits:
        print(f"[twna-watch] 發現 twna 課程頁：{f.name}")
        stats = process(f)
        msg = f"台灣護理學會：新增 {stats['added']} 筆、重複 {stats['skipped_dupe']} 筆"
        print(f"[twna-watch] {msg}（原始檔已歸檔至 {ARCHIVE_DIRNAME}/）")
        _notify(msg if stats["added"] else "課程頁已處理，沒有新課程")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
