"""Two-stage filter: cheap prefilter, then a Haiku judgment call.

Stage 1 (free): keyword include/exclude on title+description. Kills the bulk
of non-matches so we never pay to have the model look at them.

Stage 2 (cheap): the survivors go to Haiku in batches, judged against your
plain-English rules in criteria.md. The model returns only the IDs that match.
"""
from __future__ import annotations

import json
import os
import sys

import config
from models import Job

CRITERIA_PATH = os.path.join(os.path.dirname(__file__), "criteria.md")


def _prefilter(jobs: list[Job]) -> list[Job]:
    inc = [t.lower() for t in config.PREFILTER_INCLUDE]
    exc = [t.lower() for t in config.PREFILTER_EXCLUDE]
    out = []
    for j in jobs:
        hay = f"{j.title} {j.description}".lower()
        if inc and not any(t in hay for t in inc):
            continue
        if exc and any(t in hay for t in exc):
            continue
        out.append(j)
    print(f"[filter] prefilter: {len(jobs)} -> {len(out)}", file=sys.stderr)
    return out


def _load_criteria() -> str:
    with open(CRITERIA_PATH, encoding="utf-8") as f:
        return f.read()


def _judge_batch(client, criteria: str, batch: list[Job]) -> set[str]:
    payload = [j.for_filter(config.AI_MAX_DESC_CHARS) for j in batch]
    system = (
        "You are a job-matching filter. Given a user's criteria and a list of "
        "job postings as JSON, return ONLY the postings that genuinely match "
        "the criteria. Respond with a JSON array of the matching `id` strings "
        "and nothing else — no prose, no markdown, no code fences. If none "
        "match, return []."
    )
    user = (
        f"# User criteria\n{criteria}\n\n"
        f"# Postings\n{json.dumps(payload, ensure_ascii=False)}\n\n"
        "Return the JSON array of matching ids."
    )
    resp = client.messages.create(
        model=config.AI_MODEL,
        max_tokens=1000,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    text = text.replace("```json", "").replace("```", "").strip()
    try:
        ids = json.loads(text)
        return {str(i) for i in ids}
    except (json.JSONDecodeError, TypeError):
        print(f"[filter] could not parse model output: {text[:200]!r}",
              file=sys.stderr)
        return set()


def filter_jobs(jobs: list[Job]) -> list[Job]:
    """Return the subset of `jobs` that match the user's criteria."""
    candidates = _prefilter(jobs)
    if not candidates:
        return []

    # Import lazily so runs that produce no candidates need no API key.
    from anthropic import Anthropic

    client = Anthropic()  # reads ANTHROPIC_API_KEY from env
    criteria = _load_criteria()

    matched_ids: set[str] = set()
    for i in range(0, len(candidates), config.AI_BATCH_SIZE):
        batch = candidates[i : i + config.AI_BATCH_SIZE]
        matched_ids |= _judge_batch(client, criteria, batch)

    matches = [j for j in candidates if j.id in matched_ids]
    print(f"[filter] AI matched {len(matches)} / {len(candidates)}",
          file=sys.stderr)
    return matches
