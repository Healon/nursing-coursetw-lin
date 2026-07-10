"""Purpose: offline demo source — deterministic fake events so the whole pipeline runs with zero network.
Input:  config enums（保證每個類別、地區、積分別至少出現一次）。
Output: fetch() -> list[dict]。資料一望即知為假（標題含【示範】，連結指向 example.org）。
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from config import site as cfg
from scripts.sources.base import make_event

# 相對今天的日期偏移：涵蓋剛結束、今天、近期與較遠的未來
_OFFSETS = [-3, 0, 2, 5, 9, 14, 21, 30, 38, 45, 60, 75, 90, 120, 150, 180]

_VENUES = {
    "north": "台北市信義區 公務人力發展中心",
    "central": "台中市西屯區 學會教育訓練中心",
    "south": "高雄市三民區 醫學研討會館",
    "east": "花蓮市 醫療園區國際會議廳",
    "online": "線上直播（報名後提供連結）",
    "tbd": "地點另行公告",
}


def _credit_combos() -> list[dict]:
    """輪流產生積分組合：空（積分依公告）、單一積分別、雙積分別，涵蓋全部 CREDIT_TYPES。"""
    types = list(cfg.CREDIT_TYPES)
    combos: list[dict] = [{}]
    combos += [{t: 2} for t in types]
    combos += [{types[i]: 1.5, types[(i + 1) % len(types)]: 1} for i in range(len(types))]
    return combos


def fetch() -> list[dict]:
    today = dt.date.today()
    combos = _credit_combos()
    events: list[dict] = []
    i = 0
    # 類別 × 地區全組合，保證前端每個 pill 都有卡片可以驗證
    for cat in cfg.CATEGORIES:
        for region in cfg.REGIONS:
            date = today + dt.timedelta(days=_OFFSETS[i % len(_OFFSETS)] + i // len(_OFFSETS))
            online = region == "online"
            events.append(
                make_event(
                    date=date.isoformat(),
                    title=f"【示範】{cfg.CATEGORIES[cat]['label']}繼續教育課程 第 {i + 1} 期",
                    location=_VENUES.get(region, "地點另行公告"),
                    credits=dict(combos[i % len(combos)]),
                    cat=cat,
                    online=online,
                    ondemand=online and i % 5 == 0,
                    region=region,
                    ctext="" if i % 3 else "積分認證申請中，以主辦單位公告為準",
                    url=f"https://example.org/demo/{i + 1}",
                )
            )
            i += 1
    return events
