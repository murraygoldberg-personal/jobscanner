"""Per-recipient dedup state.

Each recipient has their own seen-file at seen/<key>.json, so a posting shown
to one person never suppresses it for another (they have different criteria and
may match different things). Committed back to the repo each run.
"""
from __future__ import annotations

import datetime as dt
import json
import os

STATE_DIR = os.path.join(os.path.dirname(__file__), "seen")
PRUNE_AFTER_DAYS = 60


def _path(key: str) -> str:
    return os.path.join(STATE_DIR, f"{key}.json")


def load(key: str) -> dict[str, str]:
    p = _path(key)
    if not os.path.exists(p):
        return {}
    with open(p, encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def save(key: str, seen: dict[str, str]) -> None:
    os.makedirs(STATE_DIR, exist_ok=True)
    cutoff = dt.date.today() - dt.timedelta(days=PRUNE_AFTER_DAYS)
    pruned = {jid: d for jid, d in seen.items() if _parse(d) >= cutoff}
    with open(_path(key), "w", encoding="utf-8") as f:
        json.dump(pruned, f, indent=0, sort_keys=True)


def mark_seen(seen: dict[str, str], job_ids) -> None:
    today = dt.date.today().isoformat()
    for jid in job_ids:
        seen.setdefault(jid, today)


def _parse(d: str) -> dt.date:
    try:
        return dt.date.fromisoformat(d)
    except ValueError:
        return dt.date.today()
