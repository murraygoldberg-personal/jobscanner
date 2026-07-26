"""Dedup state: which job IDs we've already seen.

Stored as a JSON map of id -> ISO date first seen, committed back to the repo
by the GitHub Action each run. "New since last time" is just: id not in here.

Old entries are pruned so the file doesn't grow forever. Pruning is safe
because a posting older than the window is no longer live on the boards, so it
won't reappear to be re-flagged as new.
"""
from __future__ import annotations

import datetime as dt
import json
import os

STATE_PATH = os.path.join(os.path.dirname(__file__), "seen.json")
PRUNE_AFTER_DAYS = 60


def load() -> dict[str, str]:
    if not os.path.exists(STATE_PATH):
        return {}
    with open(STATE_PATH, encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def save(seen: dict[str, str]) -> None:
    cutoff = dt.date.today() - dt.timedelta(days=PRUNE_AFTER_DAYS)
    pruned = {
        jid: d for jid, d in seen.items()
        if _parse(d) >= cutoff
    }
    with open(STATE_PATH, "w", encoding="utf-8") as f:
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
