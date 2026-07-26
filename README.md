# Job Scanner

A near-zero-cost daily job scanner. A non-AI feed layer pulls postings from a
set of job boards, an AI filter keeps only the ones matching your criteria, and
matches are emailed to you each morning. Runs itself on GitHub Actions — no
server, no daily prompting.

## How it works

```
sources/           one adapter per board (RSS or scrape), all behind one interface
  base.py          the Adapter contract
  rss.py           generic RSS adapter (Chronicle, HigherEdJobs)
  indeed.py        JobSpy-backed Indeed adapter (the only scraper)
  __init__.py      the source registry — edit this to add/remove boards
config.py          Indeed search params, filter + delivery settings
criteria.md        your match rules, plain English — becomes the AI prompt
ai_filter.py       cheap keyword prefilter, then a Haiku judgment call
state.py           seen.json dedup store (committed each run)
deliver.py         emails matches (Resend) + writes a dated digest file
pipeline.py        ties it together: fetch → dedup → filter → deliver → persist
```

The pipeline never cares *how* a board produces jobs. Each adapter returns
normalized `Job` objects; RSS vs. scrape is an implementation detail.

## Cost

- **Scheduler:** GitHub Actions — free (a daily 2-min run is ~60 min/month;
  public repos are unlimited, private repos get 2,000 free min/month).
- **Email:** Resend free tier is 3,000 emails/month; you'll send ~30.
- **AI:** a keyword prefilter kills most postings before the model sees them,
  and only truncated descriptions are sent to Haiku. Realistically a few cents
  a month.

## Setup

1. Push this folder to a GitHub repo.
2. Add repository **Secrets** (Settings → Secrets and variables → Actions):
   - `ANTHROPIC_API_KEY` — for the AI filter.
   - `RESEND_API_KEY` — from resend.com (free). Verify a sending domain and
     set `EMAIL_FROM` in `config.py` to an address on it.
   - `EMAIL_TO` — where digests go.
3. Edit `criteria.md` to describe what you want. Edit `config.py` for the
   Indeed search terms/location.
4. (Optional) Run it once manually: **Actions → Daily job scan → Run workflow.**

That's it. It now runs every morning and emails you only what's new and
matching.

## Adding a board

Boards are configured in **sources.yml**, not in code. To add an RSS-backed
board, add an entry under `rss:`:

```yaml
  - name: someboard
    feed_url: "https://.../feed.xml"
    expect_nonzero: false   # true = alert if it ever returns zero jobs
```

Most boards that aren't Indeed/LinkedIn have a feed — check for an "RSS" link
on the board's results page, or try appending `/feed/`, `/rss`, or
`?format=rss`. WordPress sites are almost always `/feed/`.

Set `expect_nonzero: true` only for high-volume boards that should always have
jobs (so a zero means it broke). Leave it `false` for niche/low-volume feeds
that can legitimately be empty.

Indeed (scraped via JobSpy) is configured under `indeed:` with search terms
and location. Adding a *non-RSS, non-Indeed* board is the only case that needs
code: copy `sources/indeed.py` to a new adapter and register it in
`sources/__init__.py` — but this is rare.

## Running two deploys from one codebase

The code is identical across deploys. Everything person-specific is in two
files: **sources.yml** (which boards) and **criteria.md** (the candidate). To
run a second scanner, use a separate repo with its own `seen.json`, schedule,
and secrets, and change only those two files. Don't edit code per-deploy.

## Breakage alerts (automatic)

A scrape adapter that silently returns 0 looks identical to "no new jobs." So
the pipeline has a health check: any source listed in `EXPECT_NONZERO`
(`pipeline.py`) that returns zero on a run makes the pipeline exit non-zero,
which turns the GitHub Action red and triggers GitHub's automatic failed-run
email. You hear about a break the morning it happens — you don't have to watch
logs.

This is deliberately your *only* signal about JobSpy: it fires when Indeed
actually breaks (the case where you need a new version), and stays silent
through every routine JobSpy release you don't care about. There's no
auto-upgrade, by design — pulling unreviewed releases into an unattended job
trades a rare, visible, one-line fix for a rare, invisible auto-break.

**When you get the alert:** `pip install -U python-jobspy`, bump the pin in
`requirements.txt`, commit. If a *feed* source (Chronicle/HigherEdJobs) trips
it instead, the feed URL likely changed — check it in a browser.

Important: matches from the *healthy* sources are still delivered and their
state still saved on a broken-source run, so an Indeed break never costs you
Chronicle/HigherEdJobs jobs or re-alerts you for them the next day. The run
just also ends red to get your attention.

If a source can *legitimately* run dry (e.g. a narrow single-category feed),
leave it out of `EXPECT_NONZERO` so it doesn't cry wolf.

## Local test run

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python pipeline.py      # emails only if RESEND_API_KEY is also set
```

Without an email key it still fetches, filters, and writes `digests/<date>.md`.
