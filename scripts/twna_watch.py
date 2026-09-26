"""Purpose: twna 另存頁「零指令」自動發布的觸發器 —— 掃描專案的 download-twna/，發現另存的
        課程頁就交給 local_update 走完匯入→重建→commit→push→通知，維護者只剩「瀏覽器另存新檔」一個動作。
Input:  無參數；單次掃描即結束（配合 launchd WatchPaths 觸發，不常駐、不輪詢）。
Output: 由 local_update 產生：data/manual_twna.json 與網站更新並推送、處理過的檔案移入
        download-twna/twna-imported/ 歸檔（避免重複處理）、macOS 桌面通知。
        process() 供 local_update 呼叫，只寫原始資料與歸檔，不重建、不 commit。

合規背景（重要，勿刪）：act.e-twna.org.tw 的 robots.txt 全站 Disallow，本專案不對該站發出
任何自動化請求。本監看器全程零網路請求：它只認「維護者本人用瀏覽器另存到本機」的靜態檔案。
自動化的是存檔之後的粗工，不是抓取；「人開頁面、人存檔」這一步依守則必須保留為人類動作。

用法：
    手動單次掃描：  .venv/bin/python scripts/twna_watch.py
    配合 launchd：  安裝 scripts/launchd/com.lin.twna-watch.plist（見 README 方式三），
                    之後任何檔案落入 download-twna/ 都會觸發一次快速掃描，非 twna 頁面立即結束。
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
DOWNLOAD_DIR = PROJECT / "download-twna"
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


def process(f: Path) -> dict:
    """匯入單一另存頁到 manual_twna.json → 歸檔原始檔。任何一步失敗都讓例外浮出（launchd log 可見）。

    只寫原始資料、不重建網站：重建與 commit 由 local_update 一次做完。這裡若自己重建，
    會留下未提交的衍生產物（2026-08-16 事故，見 AC_local-update-deadlock.md）。
    """
    stats = import_twna_page.run(f, DATA_PATH)
    # 即使沒有新課程，run() 仍已更新 manual_* 時間戳；不要回復或略過這個本機資料變更，
    # local_update.py 會在後續 diff/commit 階段把「本週已人工檢查」的事實一併保存。
    archive = f.parent / ARCHIVE_DIRNAME
    archive.mkdir(exist_ok=True)
    target = archive / f.name
    if target.exists():
        target = archive / f"{int(time.time())}-{f.name}"
    f.rename(target)
    return stats


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="掃描下載資料夾，發現 twna 另存課程頁就交給 local_update 匯入並發布")
    ap.parse_args(argv)

    if not DOWNLOAD_DIR.is_dir():
        print(f"[twna-watch] 資料夾不存在：{DOWNLOAD_DIR}", file=sys.stderr)
        return 1

    hits = scan_folder(DOWNLOAD_DIR)
    if not hits:
        return 0  # launchd 每次資料夾變動都會觸發，非 twna 檔案安靜結束是正常路徑

    # 發布只走一條路：local_update 負責同步雲端、匯入、重建、commit、push、通知。
    # 它若正被 16:00 排程占用（單實例鎖），檔案留在收件匣，下一次執行會收走，不會遺失。
    print(f"[twna-watch] 發現 twna 課程頁：{', '.join(f.name for f in hits)}，交給 local_update 匯入並發布")
    return subprocess.run([sys.executable, str(PROJECT / "scripts" / "local_update.py")], cwd=PROJECT).returncode


if __name__ == "__main__":
    raise SystemExit(main())
