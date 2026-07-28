# Family Job Scanner

One deployment that scans jobs for multiple people, each with their own sources
and matching criteria, and emails everyone ONE combined digest with a section
per person. Runs itself daily on GitHub Actions.

## How it works

```
recipients.yml     ← master config: each person's sources + criteria + who gets the email
criteria/          ← one markdown criteria file per person (theory.md, immunology.md, ...)
config.py          global knobs (AI model, from-address) — same regardless of who's scanned
sources/           adapter code (RSS + Indeed), built per-recipient from recipients.yml
ai_filter.py       prefilter + Haiku judgment → strength + reason + 4-dimension scorecard
state.py           per-recipient dedup: seen/<key>.json
deliver.py         builds the combined tabbed email + per-recipient digest archives
pipeline.py        for each recipient: fetch → dedup → filter; then one email to all
```

Each run processes every recipient independently — their own sources, their own
`seen/<key>.json` (so a posting shown to one never suppresses it for another),
their own criteria. Then a single email with a section per person goes to
everyone in `all_recipients`. It's a family affair: everyone sees every section.

## Adding a person

Edit `recipients.yml`: add an entry under `recipients:` (name, key, criteria
file, and their `rss:`/`indeed:` sources), create their `criteria/<key>.md`,
and add their email to `all_recipients`. No code changes. Scales to any number.

## The email

Every person's section is fully visible, stacked with a clear header, so it
reads in any email client (Gmail strips interactive JS, so we don't rely on it).
Each match shows a strength badge, a four-dot scorecard
(🔬 field · 📍 location · 💼 job-type · 🎓 seniority), and a one-line reason.
A source problem for any person shows a red banner in their section and turns
the run red (GitHub emails you).

## Setup

Secrets (Settings → Secrets and variables → Actions):
- `ANTHROPIC_API_KEY` — for the AI filter.
- `RESEND_API_KEY` — from resend.com; `EMAIL_FROM` in config.py must be on a
  domain verified there.

Then edit `recipients.yml` (real email addresses + sources) and the `criteria/`
files. The workflow runs daily at 13:00 UTC (6am Vancouver); trigger manually
from the Actions tab to test.

## Breakage alerts

A source flagged `expect_nonzero: true` that returns zero, or any source that
errors, is reported in that person's email section and fails the run (red
Action → GitHub email). Feeds that can legitimately be empty use
`expect_nonzero: false`.
