"""Purpose: pipeline entry point — scrape sources, normalize/merge/filter, write data files, rebuild the page.
Input:  --sources code1,code2（只跑指定來源）或 --profile cloud/local/manual（擇一）；
--reset（忽略既有資料，從空開始）。
Output: data/events.json、data/status.json、index.html。

失敗語意（刻意設計，勿改動順序）：
- 「來源」失敗不會讓本程式失敗：逐來源隔離，結果進 status.json 與頁尾警示。
- 「系統」失敗（樣板壞掉、寫檔失敗）直接 raise、非零退出：真正的建置問題必須大聲失敗。
CI 亮紅與否由 scripts/status.py --check 在 commit 之後判斷（見 .github/workflows/update.yml）。
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import site as cfg
from scripts import build, normalize, status
from scripts.sources import VALID_EXECUTIONS, run_all

ROOT = Path(__file__).resolve().parents[1]
EVENTS_PATH = ROOT / "data" / "events.json"


def load_previous_events() -> list[dict]:
    if EVENTS_PATH.exists():
        return json.loads(EVENTS_PATH.read_text(encoding="utf-8")).get("events", [])
    return []


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape sources and rebuild the site")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--sources", help="逗號分隔的來源代碼，只跑這些（預設：所有 enabled 來源）")
    selection.add_argument(
        "--profile",
        choices=sorted(VALID_EXECUTIONS),
        help="只跑指定執行環境的 enabled 來源",
    )
    parser.add_argument("--reset", action="store_true", help="忽略既有 events.json，從空資料開始（例如清除示範資料）")
    args = parser.parse_args()
    only = [s.strip() for s in args.sources.split(",") if s.strip()] if args.sources else None

    today = dt.date.today()
    previous = [] if args.reset else load_previous_events()

    fresh_raw, outcomes = run_all(only=only, profile=args.profile)
    fresh: list[dict] = []
    survived_by_src: dict[str, int] = {}
    for ev in fresh_raw:
        n = normalize.normalize_event(ev)
        if n is not None:
            fresh.append(n)
            survived_by_src[n["src"]] = survived_by_src.get(n["src"], 0) + 1
    # 用「通過驗證的存活筆數」重新判定各來源健康狀態：抓到卻整批壞掉會顯性化成 error，
    # 不會被抓取層的原始筆數蒙混成 ok（見 status.finalize_outcomes）。
    outcomes = status.finalize_outcomes(outcomes, survived_by_src)

    events = normalize.sort_events(
        normalize.window_filter(normalize.merge(previous, fresh), today)
    )

    EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "meta": {
            "generated": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "disclaimer": cfg.SITE["disclaimer"],
        },
        "events": events,
    }
    EVENTS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    snapshot = status.compute(outcomes, status.load())
    status.save(snapshot)

    build.main()

    print(f"[update] sources run: {len(outcomes)}, events total: {len(events)}, overall: {snapshot['overall']}")
    for code, oc in outcomes.items():
        mark = {"ok": "OK ", "empty": "警告", "error": "失敗"}.get(oc["status"], "？")
        print(f"  [{mark}] {code}: {oc['status']}, {oc['count']} 筆 {oc['message']}".rstrip())


if __name__ == "__main__":
    main()
