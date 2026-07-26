"""The adapter contract.

Every source is a subclass of Adapter that implements fetch() and returns a
list[Job]. The pipeline never needs to know HOW a source produces jobs (RSS,
JSON endpoint, scrape) — only that fetch() gives back normalized Job objects.

To add a new board: copy an existing file in this folder, adjust it, and add
the class to sources/__init__.py. That is the whole process.
"""
from __future__ import annotations

import sys

from models import Job


class Adapter:
    # Short, stable identifier used in logs, state, and Job.source.
    name: str = "base"
    # If True, this source returning zero jobs on a run is treated as a
    # failure (the run fails loudly so you get an alert). Set per-source in
    # sources.yml. Feeds that can legitimately be empty should leave this False.
    expect_nonzero: bool = False
    # Set by _safe() when a fetch raises — lets the pipeline distinguish "this
    # source errored" from "this source genuinely had no jobs". An error is
    # always alert-worthy regardless of expect_nonzero.
    last_error: str = ""

    def fetch(self) -> list[Job]:
        raise NotImplementedError

    # Adapters should call this instead of raising, so one broken source never
    # takes down the whole run. Returns [] and logs to stderr.
    def _safe(self, fn) -> list[Job]:
        self.last_error = ""
        try:
            jobs = fn()
            print(f"[{self.name}] fetched {len(jobs)} jobs", file=sys.stderr)
            return jobs
        except Exception as e:  # noqa: BLE001 — intentional catch-all per source
            self.last_error = str(e)
            print(f"[{self.name}] ERROR: {e}", file=sys.stderr)
            return []
