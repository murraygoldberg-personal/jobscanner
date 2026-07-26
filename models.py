"""Shared job model + helpers. Every adapter returns a list[Job]."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field, asdict


def _clean(text: str | None) -> str:
    """Collapse whitespace and strip HTML tags from a snippet of text."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)          # drop HTML tags
    text = re.sub(r"\s+", " ", text)              # collapse whitespace
    return text.strip()


@dataclass
class Job:
    """One normalized posting. Adapters populate as many fields as they can."""
    source: str                       # which adapter produced it, e.g. "higheredjobs"
    title: str
    company: str = ""
    location: str = ""
    url: str = ""
    description: str = ""
    # Filled in automatically by __post_init__ — do not pass manually.
    id: str = field(default="", init=False)
    # Populated by the AI filter for matched jobs: a strength label
    # ("strong" / "medium" / "weak") and a one-line reason.
    match_strength: str = field(default="", init=False)
    match_reason: str = field(default="", init=False)

    def __post_init__(self) -> None:
        self.title = _clean(self.title)
        self.company = _clean(self.company)
        self.location = _clean(self.location)
        self.description = _clean(self.description)
        self.id = self._make_id()

    def _make_id(self) -> str:
        """Stable dedup key.

        We deliberately DO NOT trust the board's own job ID, because the same
        posting is often re-listed with a fresh ID. Hashing title+company+
        location makes a repost collapse to the same key. URL is left out on
        purpose: tracking params and reposts change it.
        """
        basis = f"{self.title}|{self.company}|{self.location}".lower()
        return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["id"] = self.id
        return d

    # A compact form for the AI filter — keeps token cost down by truncating
    # the description rather than sending the whole posting.
    def for_filter(self, max_desc_chars: int = 600) -> dict:
        return {
            "id": self.id,
            "source": self.source,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "description": self.description[:max_desc_chars],
        }
