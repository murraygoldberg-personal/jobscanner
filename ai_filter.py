"""Two-stage filter: cheap prefilter, then a Haiku judgment call.

Stage 1 (free): keyword include/exclude on title+description. Kills the bulk
of non-matches so we never pay to have the model look at them.

Stage 2 (cheap): the survivors go to Haiku in batches, judged against your
plain-English rules in criteria.md. For each match the model returns a strength
rating ("strong"/"medium"/"weak") and a one-line reason, which get attached to
the Job and shown in the digest and email.
"""
from __future__ import annotations

import json
import os
import re
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


def _judge_batch(client, criteria: str, batch: list[Job]) -> dict[str, dict]:
    """Return {id: {"strength": ..., "reason": ...}} for matches in this batch."""
    payload = [j.for_filter(config.AI_MAX_DESC_CHARS) for j in batch]
    system = (
        "You are a job-matching filter for a specific candidate. Given the "
        "candidate criteria and a list of job postings as JSON, identify ONLY "
        "the postings that genuinely match. For each match, rate how strong the "
        "fit is and explain why in one sentence, grounded in the criteria "
        "(mention field fit and location).\n\n"
        "Respond with ONLY a JSON array — no prose, no markdown, no code "
        "fences. Each element is an object with exactly these keys:\n"
        '  "id": the posting id, as a double-quoted string\n'
        '  "strength": one of "strong", "medium", "weak"\n'
        '  "reason": one sentence explaining the match\n'
        'Example: [{"id":"9dad6b2335569b6a","strength":"strong",'
        '"reason":"Metacomplexity post-doc at UBC — top field and location fit."}]'
        "\nIf nothing matches, return []."
    )
    user = (
        f"# Candidate criteria\n{criteria}\n\n"
        f"# Postings\n{json.dumps(payload, ensure_ascii=False)}\n\n"
        "Return the JSON array of matches."
    )
    resp = client.messages.create(
        model=config.AI_MODEL,
        max_tokens=1500,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    text = text.replace("```json", "").replace("```", "").strip()

    batch_ids = {j.id for j in batch}
    verdicts: dict[str, dict] = {}

    # Preferred path: valid JSON array of verdict objects.
    try:
        parsed = json.loads(text)
        for item in parsed:
            jid = str(item.get("id", ""))
            if jid in batch_ids:
                verdicts[jid] = {
                    "strength": str(item.get("strength", "medium")).lower(),
                    "reason": str(item.get("reason", "")).strip(),
                }
        return verdicts
    except (json.JSONDecodeError, TypeError, AttributeError):
        pass

    # Fallback: if the JSON is malformed, recover at least the matched ids by
    # pattern (our ids are 16-char hex) so a formatting quirk never silently
    # drops matches. We lose the strength/reason for these, but not the match.
    # Intersecting with batch_ids prevents a stray hex token from inventing one.
    found = set(re.findall(r"\b[0-9a-f]{16}\b", text)) & batch_ids
    if found:
        print(f"[filter] recovered {len(found)} id(s) from non-JSON output "
              "(strength/reason unavailable for these)", file=sys.stderr)
        for jid in found:
            verdicts[jid] = {"strength": "unknown", "reason": ""}
        return verdicts

    print(f"[filter] could not parse model output: {text[:200]!r}",
          file=sys.stderr)
    return verdicts


def filter_jobs(jobs: list[Job]) -> list[Job]:
    """Return matching jobs, each annotated with match_strength and match_reason,
    sorted strongest first."""
    candidates = _prefilter(jobs)
    if not candidates:
        return []

    # Import lazily so runs that produce no candidates need no API key.
    from anthropic import Anthropic

    client = Anthropic()  # reads ANTHROPIC_API_KEY from env
    criteria = _load_criteria()

    verdicts: dict[str, dict] = {}
    for i in range(0, len(candidates), config.AI_BATCH_SIZE):
        batch = candidates[i : i + config.AI_BATCH_SIZE]
        verdicts.update(_judge_batch(client, criteria, batch))

    matches = []
    for j in candidates:
        v = verdicts.get(j.id)
        if not v:
            continue
        j.match_strength = v["strength"]
        j.match_reason = v["reason"]
        matches.append(j)

    # Sort strongest first so the best fits are at the top of the digest.
    order = {"strong": 0, "medium": 1, "weak": 2, "unknown": 3}
    matches.sort(key=lambda j: order.get(j.match_strength, 4))

    print(f"[filter] AI matched {len(matches)} / {len(candidates)}",
          file=sys.stderr)
    return matches
