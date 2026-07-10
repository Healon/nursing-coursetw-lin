"""Purpose: thin CLI over the source registry — run parsers and inspect results without touching data files.
Input:  --sources code1,code2（預設：所有 enabled 來源）；--dump 印出完整事件 JSON。
Output: stdout 摘要。單獨除錯某來源時用這支；正式流程請用 scripts/update.py。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.sources import run_all


def main() -> None:
    parser = argparse.ArgumentParser(description="Run source parsers (debug helper)")
    parser.add_argument("--sources", help="逗號分隔的來源代碼，只跑這些")
    parser.add_argument("--dump", action="store_true", help="印出完整事件 JSON")
    args = parser.parse_args()
    only = [s.strip() for s in args.sources.split(",") if s.strip()] if args.sources else None

    events, outcomes = run_all(only)
    for code, oc in outcomes.items():
        print(f"{code}: {oc['status']} ({oc['count']} 筆) {oc['message']}")
    if args.dump:
        print(json.dumps(events, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
