"""Entry point for the family job scanner. Run: python pipeline.py

Reads recipients.yml. For EACH recipient: fetch their sources, dedup against
their own state, filter against their criteria, rate matches. Then send ONE
combined tabbed email (a section per recipient) to everyone in all_recipients.

Per-recipient isolation: each person has their own seen/<key>.json, so a
posting shown to one never suppresses it for another. A source problem for one
recipient is reported in their section and fails the run, without affecting
anyone else's results.
"""
from __future__ import annotations

import os
import sys

import yaml

import state
import ai_filter
import cost
from ai_filter import filter_jobs
from deliver import deliver_all
from sources import build_sources

RECIPIENTS_YML = os.path.join(os.path.dirname(__file__), "recipients.yml")


def _process_recipient(rec: dict) -> tuple[dict, bool]:
    """Run the pipeline for one recipient. Returns (result, had_problem)."""
    name = rec["name"]
    key = rec["key"]
    print(f"\n[pipeline] === {name} ({key}) ===", file=sys.stderr)

    # 1. fetch this recipient's sources
    adapters = build_sources(rec)
    all_jobs = []
    problems: list[str] = []
    for adapter in adapters:
        jobs = adapter.fetch()
        all_jobs.extend(jobs)
        if adapter.last_error:
            problems.append(f"{adapter.name}: error — {adapter.last_error}")
        elif adapter.expect_nonzero and len(jobs) == 0:
            problems.append(f"{adapter.name}: expected jobs but got zero")
    print(f"[pipeline] {key}: fetched {len(all_jobs)}", file=sys.stderr)

    # 2. dedup against THIS recipient's state
    seen = state.load(key)
    new_jobs, seen_this_run = [], set()
    for j in all_jobs:
        if j.id in seen or j.id in seen_this_run:
            continue
        seen_this_run.add(j.id)
        new_jobs.append(j)
    print(f"[pipeline] {key}: new since last run: {len(new_jobs)}", file=sys.stderr)

    # 3. filter against THIS recipient's criteria + dimension spec
    dimensions = rec.get("dimensions") or []
    matches = []
    if new_jobs:
        matches = filter_jobs(
            new_jobs,
            criteria_path=rec["criteria_file"],
            dimensions=dimensions,
            prefilter_include=rec.get("prefilter_include", []),
            prefilter_exclude=rec.get("prefilter_exclude", []),
        )

    # 4. persist state (all new postings, matched or not)
    if new_jobs:
        state.mark_seen(seen, (j.id for j in new_jobs))
        state.save(key, seen)

    result = {"name": name, "key": key, "matches": matches,
              "problems": problems, "dimensions": dimensions}
    return result, bool(problems)


def run() -> int:
    with open(RECIPIENTS_YML, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    recipients = cfg.get("recipients", []) or []
    all_recipients = cfg.get("all_recipients", []) or []
    if not recipients:
        print("[pipeline] no recipients configured", file=sys.stderr)
        return 0

    ai_filter.reset_usage()   # start counting tokens fresh for this run

    results = []
    any_problem = False
    for rec in recipients:
        result, had_problem = _process_recipient(rec)
        results.append(result)
        any_problem = any_problem or had_problem

    # Tally AI cost for this run and update the month-to-date total.
    cost_summary = cost.record_and_summarize(ai_filter.get_usage())
    print(f"[pipeline] AI cost today ~${cost_summary['today_cost']:.4f}; "
          f"month-to-date ~${cost_summary['month_cost']:.4f}", file=sys.stderr)

    # One combined email to everyone.
    deliver_all(results, all_recipients, cost_summary)

    total = sum(len(r["matches"]) for r in results)
    print(f"\n[pipeline] done. {total} total match(es) across "
          f"{len(results)} recipient(s); problems={any_problem}", file=sys.stderr)

    # Non-zero exit if any recipient had a source problem → red Action + email.
    return 1 if any_problem else 0


if __name__ == "__main__":
    sys.exit(run())
