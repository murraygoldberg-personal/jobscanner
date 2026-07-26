"""Tunable settings. Edit this file (and criteria.md) rather than the code."""

# --- Indeed (JobSpy) search parameters --------------------------------------
# One scrape runs per term. Keep the list short; each term is a separate
# request and Indeed will rate-limit if you get greedy.
INDEED_SEARCH_TERMS = [
    "higher education administration",
    "university dean",
]
INDEED_LOCATION = "Remote"      # city/state, or "Remote"
INDEED_COUNTRY = "usa"          # JobSpy's country_indeed value
INDEED_RESULTS_WANTED = 25      # per term, per run
INDEED_HOURS_OLD = 48           # only postings newer than this
INDEED_IS_REMOTE = None         # True / False / None (no filter)

# --- AI filter --------------------------------------------------------------
# Haiku is the cheap workhorse. The prefilter kills obvious non-matches before
# anything reaches the model, so cost stays in the pennies-per-month range.
AI_MODEL = "claude-haiku-4-5-20251001"
AI_MAX_DESC_CHARS = 600         # how much of each description the model sees
AI_BATCH_SIZE = 20              # postings judged per API call

# Cheap deterministic prefilter. A posting must contain at least one INCLUDE
# term (in title+description) AND none of the EXCLUDE terms to reach the model.
# Leave PREFILTER_INCLUDE empty to send everything new to the AI.
PREFILTER_INCLUDE = [
    # "dean", "provost", "director", "vice president",
]
PREFILTER_EXCLUDE = [
    # "adjunct", "part-time", "graduate assistant",
]

# --- Delivery ---------------------------------------------------------------
EMAIL_TO = "you@example.com"        # overridden by env var EMAIL_TO if set
EMAIL_FROM = "jobscanner@example.com"  # a domain verified in Resend
EMAIL_SUBJECT_PREFIX = "[Job Scanner]"
SEND_EMPTY_DIGEST = False           # don't email when nothing new matched
