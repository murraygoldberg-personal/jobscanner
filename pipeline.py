"""Entry point. Run: python pipeline.py

Flow:
  1. fetch   — run every adapter, collect all postings
  2. dedup   — drop anything already in seen.json (and dupes within this run)
  3. filter  — prefilter + AI judgment against criteria.md
  4. deliver — email matches + write dated digest
  5. persist — mark everything seen so it won't reappear tomorrow

Note step 5 marks ALL new postings seen, not just matches. Otherwise a
posting the AI rejected today would be re-judged (and re-paid-for) every day
it stays live.
"""
from __future__ import annotations

import sys

import state
from ai_filter import filter_jobs
from deliver import deliver
from sources import get_sources

# Sources that should always return at least some postings on a healthy run.
# If one of these returns zero, that's almost certainly a break (a scrape
# adapter out of date, or a feed URL that changed) — not a genuinely empty
# board. We exit non-zero so the GitHub Action goes red and emails you.
#
# This is the early-warning for JobSpy/Indeed breakage: you get told the
# morning it happens, and the fix is `pip install -U python-jobspy` + bump
# the pin in requirements.txt.
#
# Leave a source OUT of this set if it legitimately runs dry sometimes (e.g. a
# narrow single-category feed that can genuinely have no current postings).
EXPECT_NONZERO = {"chronicle", "higheredjobs", "indeed"}


def _health_check(counts: dict[str, int]) -> list[str]:
    """Return the names of expected-nonzero sources that returned nothing."""
    return sorted(s for s in EXPECT_NONZERO if counts.get(s, 0) == 0)


def run() -> int:
    # 1. fetch — track per-source counts for the health check
    all_jobs = []
    counts: dict[str, int] = {}
    for adapter in get_sources():
        jobs = adapter.fetch()
        counts[adapter.name] = len(jobs)
        all_jobs.extend(jobs)
    print(f"[pipeline] total fetched: {len(all_jobs)}", file=sys.stderr)

    # Health check runs on EVERY path, before the "nothing new" early return —
    # a source can break on a day that also has no new jobs, and we still want
    # to hear about it. We finish delivery first (below) so a broken Indeed
    # doesn't suppress genuine matches from the healthy feeds, then report the
    # failure at the very end.
    broken = _health_check(counts)
    if broken:
        print(f"[pipeline] WARNING: expected jobs but got zero from: {broken}",
              file=sys.stderr)

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

    if not new_jobs:
        deliver([])
        # Even with nothing new, surface a broken source as a failed run.
        return 1 if broken else 0

    # 3. filter
    matches = filter_jobs(new_jobs)

    # 4. deliver
    deliver(matches)

    # 5. persist — mark ALL new postings seen, matched or not
    state.mark_seen(seen, (j.id for j in new_jobs))
    state.save(seen)
    print(f"[pipeline] done. {len(matches)} match(es) delivered.",
          file=sys.stderr)

    # Report a broken source last, after matches are safely delivered and
    # state is saved — so the alert never costs you real jobs or re-processing.
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(run())
