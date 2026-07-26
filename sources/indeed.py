"""Indeed adapter, backed by JobSpy.

Indeed has no official feed, so this is the one source that scrapes. It is
deliberately isolated behind the same Adapter interface as everything else:
if JobSpy breaks after an Indeed re-skin, _safe() swallows the error and the
RSS sources still deliver. Watch the per-source counts in the run log — an
Indeed count that silently drops to 0 is the tell that this adapter needs a
JobSpy upgrade (`pip install -U python-jobspy`).

Config lives in config.py (search terms, location, results_wanted).
"""
from __future__ import annotations

from models import Job
from sources.base import Adapter


class IndeedAdapter(Adapter):
    name = "indeed"

    def __init__(
        self,
        search_terms: list[str],
        location: str = "",
        country: str = "usa",
        results_wanted: int = 25,
        hours_old: int = 48,
        is_remote: bool | None = None,
    ):
        self.search_terms = search_terms
        self.location = location
        self.country = country
        self.results_wanted = results_wanted
        self.hours_old = hours_old
        self.is_remote = is_remote

    def fetch(self) -> list[Job]:
        return self._safe(self._fetch)

    def _fetch(self) -> list[Job]:
        # Imported lazily so the RSS-only path doesn't pay JobSpy's import cost
        # and so a JobSpy install problem can't break module import.
        from jobspy import scrape_jobs

        jobs: list[Job] = []
        for term in self.search_terms:
            kwargs = dict(
                site_name=["indeed"],
                search_term=term,
                location=self.location,
                country_indeed=self.country,
                results_wanted=self.results_wanted,
                hours_old=self.hours_old,
            )
            if self.is_remote is not None:
                kwargs["is_remote"] = self.is_remote

            df = scrape_jobs(**kwargs)
            if df is None or df.empty:
                continue

            for _, row in df.iterrows():
                jobs.append(
                    Job(
                        source=self.name,
                        title=str(row.get("title", "")),
                        company=str(row.get("company", "")),
                        location=str(row.get("location", "")),
                        url=str(row.get("job_url", "")),
                        description=str(row.get("description", "") or ""),
                    )
                )
        return jobs
