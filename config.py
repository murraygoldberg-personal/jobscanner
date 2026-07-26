"""Tunable settings shared across the pipeline.

NOTE: source definitions (which boards, Indeed search terms) live in
sources.yml, NOT here — so this file and all code stay identical across
deploys. Candidate-specific matching lives in criteria.md. This file holds
only cross-cutting knobs.
"""

# --- AI filter --------------------------------------------------------------
# Haiku is the cheap workhorse. The prefilter kills obvious non-matches before
# anything reaches the model, so cost stays in the pennies-per-month range.
AI_MODEL = "claude-haiku-4-5-20251001"
AI_MAX_DESC_CHARS = 600         # how much of each description the model sees
AI_BATCH_SIZE = 20              # postings judged per API call

# Cheap deterministic prefilter. A posting must contain at least one INCLUDE
# term (in title+description) AND none of the EXCLUDE terms to reach the model.
# Leave PREFILTER_INCLUDE empty to send everything new to the AI. For a tightly
# scoped candidate you can add terms here to cut API cost, at the risk of
# missing broadly-worded postings — leave empty until you've seen real results.
PREFILTER_INCLUDE = [
    # "theory", "complexity", "postdoc", "research",
]
PREFILTER_EXCLUDE = [
    # "adjunct", "part-time", "graduate assistant",
]

# --- Delivery ---------------------------------------------------------------
# EMAIL_TO is overridden by the EMAIL_TO env var / GitHub secret if set.
EMAIL_TO = "you@example.com"
EMAIL_FROM = "jobscanner@example.com"   # a domain verified in Resend
EMAIL_SUBJECT_PREFIX = "[Job Scanner]"
