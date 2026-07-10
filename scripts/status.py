"""Purpose: source-health tracking — build data/status.json and provide the CI gate (--check).
Input:  本次爬取的逐來源 outcomes；既有 status.json（沿用 last_success）。
Output: data/status.json；--check 只在「全部來源皆 error」（overall=down）時 exit 1。

設計原則（錯誤可見性）：來源三態 ok／empty／error。empty（成功但 0 筆）是最危險的
靜默失敗態，通常代表網站改版讓選擇器失效卻沒丟例外，因此照樣警示。

count 語意：finalize_outcomes 之後，count 是「通過欄位驗證的存活筆數」（非 parser
原始抓取數，也非頁面實際顯示筆數）。頁面顯示筆數會再少一些，因為時間窗過濾發生在
更後面（見 normalize.window_filter）；用存活數而非顯示數做健康判斷，才不會把「活動
單純過了時間窗」誤判成 parser 壞掉。
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import site as cfg

ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "data" / "status.json"


def finalize_outcomes(outcomes: dict[str, dict], survived_by_src: dict[str, int]) -> dict[str, dict]:
    """用 normalize 後的存活筆數修正各來源 outcome（回傳新 dict，不改原物件）。

    抓取層（registry）只知道 parser 吐了幾筆；一批資料是否真的可用，要等 normalize
    驗證過欄位才知道。這裡把「抓到 N 筆但全部無法通過驗證」這種靜默失敗顯性化為 error，
    避免它被當成 ok——那會連帶把 last_success 刷新成今天，抹掉壞掉的起點。

    - status=error（抓取階段就丟例外）：原樣保留。
    - 有存活：status=ok，count=存活數；若存活 < 原始抓取數，於 message 記錄損耗筆數。
    - 抓到 >0 但存活 0：status=error（整批無效，通常是網站改版讓解析錯位）。
    - 本來就 0 筆：status=empty。
    """
    result: dict[str, dict] = {}
    for code, oc in outcomes.items():
        if oc.get("status") == "error":
            result[code] = dict(oc)
            continue
        raw = int(oc.get("count", 0))
        survived = int(survived_by_src.get(code, 0))
        if survived > 0:
            message = "" if survived == raw else f"抓取 {raw} 筆，{survived} 筆通過驗證（{raw - survived} 筆格式不符已丟棄）"
            result[code] = {"status": "ok", "count": survived, "message": message}
        elif raw > 0:
            result[code] = {
                "status": "error",
                "count": 0,
                "message": f"抓取 {raw} 筆但全部無法通過欄位驗證，可能網站已改版",
            }
        else:
            result[code] = {"status": "empty", "count": 0, "message": oc.get("message", "")}
    return result


def compute(outcomes: dict[str, dict], previous: dict | None, *, now: dt.datetime | None = None) -> dict:
    """把本次 outcomes 併進既有健康快照。

    - 本次有跑的來源：更新狀態；status=ok 才刷新 last_success。
    - 本次沒跑的來源（例如用 --sources 篩選）：沿用舊快照，不假裝有更新。
    - 已從 config 移除的來源：從快照剔除。
    - enabled=False 的來源：不納入快照與 overall 判定（監控範圍＝自動更新範圍＝enabled）。
      理由：停用是刻意狀態（如 twna 手動來源尚未填資料、robots 禁爬），不是故障；
      若讓它留在快照裡，「刻意尚未啟用」會被誤呈現成「壞掉」，黃橫幅常駐反而讓
      真正的來源故障失去信號價值。用 --sources 手動跑 disabled 來源做預覽時，
      資料照樣進 events.json，只是不列入健康監控。
    """
    now = now or dt.datetime.now().astimezone()
    today = now.date().isoformat()
    prev_sources = (previous or {}).get("sources", {})

    sources: dict[str, dict] = {}
    for code in cfg.SOURCES:
        if not cfg.SOURCES[code].get("enabled", False):
            continue
        prev = prev_sources.get(code)
        if code in outcomes:
            oc = outcomes[code]
            sources[code] = {
                "status": str(oc.get("status", "error")),
                "count": int(oc.get("count", 0)),
                "last_success": today if oc.get("status") == "ok" else (prev or {}).get("last_success", ""),
                "message": str(oc.get("message", "")),
            }
        elif prev:
            sources[code] = prev

    statuses = [s["status"] for s in sources.values()]
    if not statuses or all(s == "error" for s in statuses):
        overall = "down"  # 沒有任何來源狀態，同樣視為 down：空站不可以是綠燈
    elif any(s in ("error", "empty") for s in statuses):
        overall = "partial"
    else:
        overall = "ok"

    return {
        "generated": now.isoformat(timespec="seconds"),
        "overall": overall,
        "sources": sources,
    }


def check(status: dict) -> int:
    """CI 閘門：全滅（down）回 1，其餘回 0。partial 靠頁面警示與頁首橫幅呈現，不擋發布。"""
    return 1 if status.get("overall", "down") == "down" else 0


def load() -> dict:
    if STATUS_PATH.exists():
        return json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    return {}


def save(status: dict) -> None:
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Source health snapshot / CI gate")
    parser.add_argument("--check", action="store_true", help="overall=down 時 exit 1（供 GitHub Actions 亮紅用）")
    args = parser.parse_args()
    status = load()
    if args.check:
        if not status:
            print("[status] data/status.json 不存在，視為 down -> exit 1")
            return 1
        code = check(status)
        print(f"[status] overall={status.get('overall')} -> exit {code}")
        return code
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
