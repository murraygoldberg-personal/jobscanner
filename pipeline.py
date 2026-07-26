"""Entry point. Run: python pipeline.py

Flow:
  1. fetch   — run every adapter, collect postings + note any problems
  2. dedup   — drop anything already in seen.json (and dupes within this run)
  3. filter  — prefilter + AI judgment against criteria.md
  4. deliver — email (always) + write digest (only when there are matches)
  5. persist — mark everything seen so it won't reappear tomorrow

Note step 5 marks ALL new postings seen, not just matches. Otherwise a
posting the AI rejected today would be re-judged (and re-paid-for) every day
it stays live.

A "problem" is a source that errored, or a source flagged expect_nonzero in
sources.yml that returned zero. Problems are reported in the daily email AND
cause the run to exit non-zero (red Action → GitHub failure email).
"""
from __future__ import annotations

import sys

import state
from ai_filter import filter_jobs
from deliver import deliver
from sources import get_sources


def run() -> int:
    # 1. fetch — collect jobs and detect per-source problems
    all_jobs = []
    problems: list[str] = []
    for adapter in get_sources():
        jobs = adapter.fetch()
        all_jobs.extend(jobs)
        if adapter.last_error:
            problems.append(f"{adapter.name}: error — {adapter.last_error}")
        elif adapter.expect_nonzero and len(jobs) == 0:
            problems.append(f"{adapter.name}: expected jobs but got zero "
                            "(feed URL changed, or scraper needs updating)")
    print(f"[pipeline] total fetched: {len(all_jobs)}", file=sys.stderr)
    if problems:
        for p in problems:
            print(f"[pipeline] PROBLEM: {p}", file=sys.stderr)

    # 2. dedup — against history and within this run
    seen = state.load()
    new_jobs = []
    seen_this_run: set[str] = set()
    for j in all_jobs:
        if j.id in seen or j.id in seen_this_run:
            continue
        seen_this_run.add(j.id)
        new_jobs.append(j)
    print(f"[pipeline] new since last run: {len(new_jobs)}", file=sys.stderr)

    # 3. filter (only if there's anything new)
    matches = filter_jobs(new_jobs) if new_jobs else []

    # 4. deliver — email always sends (even on an empty day) and reports any
    #    source problems. Digest file is written only when there are matches.
    deliver(matches, problems)

    # 5. persist — mark ALL new postings seen, matched or not
    if new_jobs:
        state.mark_seen(seen, (j.id for j in new_jobs))
        state.save(seen)

    print(f"[pipeline] done. {len(matches)} match(es); "
          f"{len(problems)} problem(s).", file=sys.stderr)

    # Non-zero exit on any problem → red Action → GitHub failure email, on top
    # of the in-email report. Delivery and state-save happen first so an alert
    # never costs real matches.
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(run())
