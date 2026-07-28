"""Source registry — builds adapters from a per-recipient config dict.

The pipeline passes in one recipient's source config (the `rss:` and `indeed:`
lists from recipients.yml). This function turns that into adapter objects. The
code is generic and identical across all recipients; only the config differs.
"""
from __future__ import annotations

import sys

from sources.base import Adapter
from sources.rss import RSSAdapter
from sources.indeed import IndeedAdapter


def build_sources(cfg: dict) -> list[Adapter]:
    """cfg is one recipient's dict with optional 'rss' and 'indeed' lists."""
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

    print(f"[sources] built {len(adapters)} source(s)", file=sys.stderr)
    return adapters
