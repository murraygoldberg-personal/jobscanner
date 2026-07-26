"""Delivery. Emails matches via Resend; always writes a dated markdown file.

The markdown file is committed by the Action, giving you a free searchable
archive even if email delivery ever fails. Email is the daily nudge.
"""
from __future__ import annotations

import datetime as dt
import os
import sys
import urllib.request
import json

import config
from models import Job

DIGEST_DIR = os.path.join(os.path.dirname(__file__), "digests")


def _strength_badge(s: str) -> str:
    return {
        "strong": "🟢 Strong",
        "medium": "🟡 Medium",
        "weak": "🟠 Weak",
    }.get(s, "⚪ Match")


def _render_match_entries(matches: list[Job]) -> str:
    """Just the match blocks — no date header. Used for both fresh writes and
    same-day appends."""
    lines: list[str] = []
    for j in matches:  # already sorted strongest-first by the filter
        loc = f" — {j.location}" if j.location else ""
        comp = f" · {j.company}" if j.company else ""
        lines.append(f"### {_strength_badge(j.match_strength)} — "
                     f"[{j.title}]({j.url})")
        lines.append(f"{j.source}{comp}{loc}")
        if j.match_reason:
            lines.append("")
            lines.append(f"> {j.match_reason}")
        lines.append("")
    return "\n".join(lines)


def _render_markdown(matches: list[Job]) -> str:
    today = dt.date.today().isoformat()
    if not matches:
        return f"# Job matches — {today}\n\n_No new matching jobs today._"
    return f"# Job matches — {today}\n\n" + _render_match_entries(matches)


def _render_html(matches: list[Job], problems: list[str] | None = None) -> str:
    problems = problems or []
    parts = []

    # Problems banner first — most important thing to see if a scrape broke.
    if problems:
        items = "".join(f"<li>{p}</li>" for p in problems)
        parts.append(
            '<div style="background:#fef2f2;border:1px solid #fecaca;'
            'border-radius:6px;padding:12px 16px;margin-bottom:16px">'
            '<strong style="color:#b91c1c">⚠️ Source problems this run</strong>'
            f'<ul style="margin:8px 0 0;color:#7f1d1d">{items}</ul>'
            '<div style="margin-top:8px;color:#7f1d1d;font-size:13px">'
            "A feed URL may have changed, or the Indeed scraper may need "
            "updating (pip install -U python-jobspy).</div></div>"
        )

    if not matches:
        parts.append('<h2 style="margin:0">No new matching jobs today</h2>')
        return "".join(parts)

    colors = {"strong": "#16a34a", "medium": "#ca8a04", "weak": "#ea580c"}
    rows = []
    for j in matches:
        meta = " · ".join(x for x in [j.source, j.company, j.location] if x)
        color = colors.get(j.match_strength, "#6b7280")
        badge = (
            f'<span style="color:{color};font-weight:600;text-transform:'
            f'capitalize">{j.match_strength or "match"}</span>'
        )
        reason = (
            f'<br><span style="color:#374151">{j.match_reason}</span>'
            if j.match_reason else ""
        )
        rows.append(
            f'<li style="margin-bottom:14px">'
            f'{badge} — <a href="{j.url}"><strong>{j.title}</strong></a>'
            f'<br><small style="color:#6b7280">{meta}</small>'
            f'{reason}</li>'
        )
    parts.append(
        f"<h2>{len(matches)} new matching "
        f"job{'s' if len(matches) != 1 else ''}</h2>"
        f'<ul style="list-style:none;padding:0">{"".join(rows)}</ul>'
    )
    return "".join(parts)


def _write_digest_file(matches: list[Job]) -> str:
    """Write today's digest. If a digest for today already exists (a second run
    on the same day), APPEND this run's matches under a timestamped separator
    rather than overwriting — so no run ever destroys another run's findings.
    """
    os.makedirs(DIGEST_DIR, exist_ok=True)
    path = os.path.join(DIGEST_DIR, f"{dt.date.today().isoformat()}.md")
    now = dt.datetime.now().strftime("%H:%M")

    if os.path.exists(path):
        # Append only the new match entries, under a separator noting the run.
        entries = _render_match_entries(matches)
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"\n---\n\n#### Additional matches (run at {now})\n\n")
            f.write(entries)
    else:
        # Fresh file for the day: full header + entries.
        with open(path, "w", encoding="utf-8") as f:
            f.write(_render_markdown(matches))
    return path


def _send_email(matches: list[Job], problems: list[str] | None = None) -> None:
    problems = problems or []
    api_key = os.environ.get("RESEND_API_KEY")
    to_addr = os.environ.get("EMAIL_TO", config.EMAIL_TO)
    if not api_key:
        print("[deliver] no RESEND_API_KEY set; skipping email", file=sys.stderr)
        return

    today = dt.date.today().isoformat()
    if matches:
        n = len(matches)
        subject = (f"{config.EMAIL_SUBJECT_PREFIX} {n} new "
                   f"job{'s' if n != 1 else ''} — {today}")
    else:
        subject = f"{config.EMAIL_SUBJECT_PREFIX} No new jobs — {today}"
    if problems:
        subject = f"⚠️ {subject} (source problem)"

    body = {
        "from": config.EMAIL_FROM,
        "to": [to_addr],
        "subject": subject,
        "html": _render_html(matches, problems),
    }
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print(f"[deliver] email sent ({r.status})", file=sys.stderr)
    except Exception as e:  # noqa: BLE001
        print(f"[deliver] email failed: {e}", file=sys.stderr)


def deliver(matches: list[Job], problems: list[str] | None = None) -> None:
    problems = problems or []

    # Digest file: written only when there are matches (an empty run never
    # overwrites a populated same-day digest). Appends if today's file exists.
    if matches:
        path = _write_digest_file(matches)
        print(f"[deliver] wrote {path}", file=sys.stderr)
    else:
        print("[deliver] no matches; leaving any existing digest intact",
              file=sys.stderr)

    # Email: ALWAYS sent — including on empty days (so you know it ran) and
    # whenever there are source problems (so a silent scrape break can't hide).
    _send_email(matches, problems)
