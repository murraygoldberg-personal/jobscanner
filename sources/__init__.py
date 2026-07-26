"""Source registry.

This is the ONE place you edit to add, remove, or reconfigure a board.
`get_sources()` returns the list of live adapters the pipeline will run.

Adding a board:
  - RSS feed available?  Add an RSSAdapter(...) line. No new file needed.
  - Needs scraping?      Copy sources/indeed.py to a new file, adapt it,
                         import it here, and add it to the list.
"""
from __future__ import annotations

import config
from sources.base import Adapter
from sources.rss import RSSAdapter
from sources.indeed import IndeedAdapter


def get_sources() -> list[Adapter]:
    return [
        # --- Chronicle of Higher Education (Madgex RSS) --------------------
        # Base feed is countrycode=US. You can narrow server-side by adding a
        # keyword, e.g. .../jobsrss/?countrycode=US&Keywords=dean — but it's
        # usually better to pull broad and let the AI filter decide.
        RSSAdapter(
            name="chronicle",
            feed_url="https://jobs.chronicle.com/jobsrss/?countrycode=US",
        ),

        # --- HigherEdJobs (per-category RSS) ------------------------------
        # catID=68 is the broad "Higher Education" category. Other useful IDs:
        #   34 = Executive/Admin, 141 = Deans, 30 = Faculty.
        # Add more lines to pull multiple categories.
        RSSAdapter(
            name="higheredjobs",
            feed_url="https://www.higheredjobs.com/rss/categoryFeed.cfm?catID=68",
        ),

        # --- Indeed (JobSpy scrape) ---------------------------------------
        IndeedAdapter(
            search_terms=config.INDEED_SEARCH_TERMS,
            location=config.INDEED_LOCATION,
            country=config.INDEED_COUNTRY,
            results_wanted=config.INDEED_RESULTS_WANTED,
            hours_old=config.INDEED_HOURS_OLD,
            is_remote=config.INDEED_IS_REMOTE,
        ),
    ]
