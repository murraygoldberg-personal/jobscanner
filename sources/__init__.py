"""Source registry — builds adapters from sources.yml.

The code here is deliberately generic and identical across deploys. All
per-deploy configuration (which boards, which search terms) lives in
sources.yml at the repo root. To retarget the scanner, edit sources.yml and
criteria.md — never this file.
"""
from __future__ import annotations

import os
import sys

import yaml

from sources.base import Adapter
from sources.rss import RSSAdapter
from sources.indeed import IndeedAdapter

SOURCES_YML = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sources.yml")


def get_sources() -> list[Adapter]:
    if not os.path.exists(SOURCES_YML):
        print(f"[sources] no sources.yml found at {SOURCES_YML}", file=sys.stderr)
        return []

    with open(SOURCES_YML, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    adapters: list[Adapter] = []

    for entry in cfg.get("rss", []) or []:
        a = RSSAdapter(
            name=entry["name"],
            feed_url=entry["feed_url"],
            default_company=entry.get("default_company", ""),
        )
        a.expect_nonzero = bool(entry.get("expect_nonzero", False))
        adapters.append(a)

    for entry in cfg.get("indeed", []) or []:
        a = IndeedAdapter(
            search_terms=entry.get("search_terms", []),
            location=entry.get("location", ""),
            country=entry.get("country", "usa"),
            results_wanted=int(entry.get("results_wanted", 25)),
            hours_old=int(entry.get("hours_old", 48)),
            is_remote=entry.get("is_remote", None),
        )
        a.name = entry.get("name", "indeed")
        a.expect_nonzero = bool(entry.get("expect_nonzero", False))
        adapters.append(a)

    print(f"[sources] loaded {len(adapters)} source(s) from sources.yml",
          file=sys.stderr)
    return adapters
