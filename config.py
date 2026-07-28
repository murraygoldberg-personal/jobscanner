"""Cross-cutting settings shared across all recipients.

Per-recipient config (sources, criteria, prefilter, email address) lives in
recipients.yml and the criteria/ files — NOT here. This file holds only
global knobs, so it's identical regardless of who's being scanned.
"""

# --- AI filter --------------------------------------------------------------
AI_MODEL = "claude-haiku-4-5-20251001"
AI_MAX_DESC_CHARS = 600         # how much of each description the model sees
AI_BATCH_SIZE = 20              # postings judged per API call

# --- Delivery ---------------------------------------------------------------
# The combined email is sent to the addresses in recipients.yml -> all_recipients.
# EMAIL_FROM must be on a domain verified in Resend.
EMAIL_FROM = "jobscanner@jobs.murraygoldberg.com"
EMAIL_SUBJECT_PREFIX = "[Job Scanner]"
