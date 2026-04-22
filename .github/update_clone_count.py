#!/usr/bin/env python3
"""Merge the latest 14-day clones API response into a running total.

Writes two files:
- state_path: {total_clones, total_uniques, days} — internal, source of truth
- badge_path: shields.io endpoint format (schemaVersion, label, message, color)
  which rejects unknown properties, so state must live elsewhere.
"""
import json
import sys
from pathlib import Path

new_data = json.loads(Path(sys.argv[1]).read_text())
state_path = Path(sys.argv[2])
badge_path = Path(sys.argv[3])

if state_path.exists():
    state = json.loads(state_path.read_text())
    days = state["days"]
    total = state["total_clones"]
    uniques = state["total_uniques"]
else:
    days, total, uniques = {}, 0, 0

for day in new_data["clones"]:
    ts = day["timestamp"]
    if ts in days:
        prev = days[ts]
    else:
        prev = {"count": 0, "uniques": 0}
    total += day["count"] - prev["count"]
    uniques += day["uniques"] - prev["uniques"]
    days[ts] = {"count": day["count"], "uniques": day["uniques"]}

state_out = {"total_clones": total, "total_uniques": uniques, "days": days}
state_path.write_text(json.dumps(state_out, indent=2) + "\n")

badge_out = {
    "schemaVersion": 1,
    "label": "clones",
    "message": str(total),
    "color": "blue",
}
badge_path.write_text(json.dumps(badge_out, indent=2) + "\n")
