"""Generic RSS adapter.

Most job boards that aren't Indeed/LinkedIn expose an RSS feed, and RSS items
map almost 1:1 onto our Job model. This one class covers both Chronicle and
HigherEdJobs — you configure it with a feed URL rather than writing new code.

Add another RSS-backed board by instantiating RSSAdapter(...) in
sources/__init__.py; you rarely need a new file at all.
"""
from __future__ import annotations

import feedparser

from models import Job
from sources.base import Adapter

# Some boards (HigherEdJobs among them) return 403 to the default feedparser
# User-Agent. Presenting a browser-like UA avoids that.
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


class RSSAdapter(Adapter):
    def __init__(self, name: str, feed_url: str, default_company: str = ""):
        self.name = name
        self.feed_url = feed_url
        self.default_company = default_company

    def fetch(self) -> list[Job]:
        return self._safe(self._fetch)

    def _fetch(self) -> list[Job]:
        parsed = feedparser.parse(self.feed_url, agent=_UA)

        # Distinguish "feed genuinely empty" from "feed broke / blocked us".
        # A non-200 HTTP status or a parse error on an empty feed is a failure
        # we want surfaced in the logs, not silently reported as zero jobs.
        status = parsed.get("status")
        if status and status >= 400:
            raise RuntimeError(f"feed returned HTTP {status} for {self.feed_url}")
        if not parsed.entries and parsed.get("bozo"):
            raise RuntimeError(
                f"feed parse failed: {parsed.get('bozo_exception')!r}"
            )
        jobs: list[Job] = []
        for entry in parsed.entries:
            title = entry.get("title", "")
            # Feeds vary: some put employer in author, some in a custom field,
            # many embed it in the title as "Job Title - Employer".
            company = (
                entry.get("author")
                or entry.get("dc_creator")
                or self.default_company
            )
            # description/summary is the human-readable blurb; content is richer
            # when present.
            desc = entry.get("summary", "")
            if entry.get("content"):
                desc = entry["content"][0].get("value", desc)

            jobs.append(
                Job(
                    source=self.name,
                    title=title,
                    company=company,
                    location=entry.get("location", ""),  # rarely present in RSS
                    url=entry.get("link", ""),
                    description=desc,
                )
            )
        return jobs
