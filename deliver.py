"""Delivery. Emails matches via Resend; always writes a dated markdown file.

The markdown file is committed by the Action, giving you a free searchable
archive even if email delivery ever fails. Email is the daily nudge.
"""
from __future__ import annotations

import datetime as dt
import os
import sys
import urllib.request
import urllib.error
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


# Default dimension spec (used if a recipient doesn't define one). Each dim:
# {key, label, emoji, desc}. Recipients override this in recipients.yml.
_DEFAULT_DIMENSIONS = [
    {"key": "field", "label": "field", "emoji": "🔬", "desc": "field fit"},
    {"key": "location", "label": "location", "emoji": "📍", "desc": "location fit"},
    {"key": "job_type", "label": "job-type", "emoji": "💼", "desc": "role type"},
    {"key": "seniority", "label": "seniority", "emoji": "🎓", "desc": "seniority"},
]


def _dot(rating: str) -> str:
    return {"strong": "🟢", "medium": "🟡", "weak": "🔴"}.get(rating, "⚪")


def _scorecard_text(dims: dict, dim_spec: list[dict]) -> str:
    """Compact scorecard from a per-recipient dimension spec. Empty if no dims."""
    if not dims or not dim_spec:
        return ""
    return "  ".join(f"{d.get('emoji','')}{_dot(dims.get(d['key'], ''))}"
                     for d in dim_spec)


def _legend(dim_spec: list[dict]) -> str:
    return "  ".join(f"{d.get('emoji','')} {d.get('label', d['key'])}"
                     for d in dim_spec)


def _render_match_entries(matches: list[Job], dim_spec: list[dict]) -> str:
    """Just the match blocks — no date header. Used for both fresh writes and
    same-day appends."""
    lines: list[str] = []
    for j in matches:  # already sorted strongest-first by the filter
        loc = f" — {j.location}" if j.location else ""
        comp = f" · {j.company}" if j.company else ""
        lines.append(f"### {_strength_badge(j.match_strength)} — "
                     f"[{j.title}]({j.url})")
        lines.append(f"{j.source}{comp}{loc}")
        sc = _scorecard_text(j.match_dimensions, dim_spec)
        if sc:
            lines.append("")
            lines.append(f"{sc}  ·  {_legend(dim_spec)}")
        if j.match_reason:
            lines.append("")
            lines.append(f"> {j.match_reason}")
        lines.append("")
    return "\n".join(lines)


def _render_markdown(matches: list[Job], dim_spec: list[dict]) -> str:
    today = dt.date.today().isoformat()
    if not matches:
        return f"# Job matches — {today}\n\n_No new matching jobs today._"
    return f"# Job matches — {today}\n\n" + _render_match_entries(matches, dim_spec)


def _render_html(matches: list[Job], problems: list[str] | None = None,
                 dim_spec: list[dict] | None = None) -> str:
    problems = problems or []
    dim_spec = dim_spec or _DEFAULT_DIMENSIONS
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

    legend_html = " &nbsp; ".join(
        f'{d.get("emoji","")} {d.get("label", d["key"])}' for d in dim_spec
    )
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
        scorecard = ""
        if j.match_dimensions:
            cells = "".join(
                f'<span style="margin-right:12px">{d.get("emoji","")}&nbsp;'
                f'{_dot(j.match_dimensions.get(d["key"], ""))}</span>'
                for d in dim_spec
            )
            scorecard = (
                f'<br><span style="font-size:13px;color:#6b7280">{cells}</span>'
                f'<br><span style="font-size:11px;color:#9ca3af">{legend_html}'
                '</span>'
            )
        rows.append(
            f'<li style="margin-bottom:16px">'
            f'{badge} — <a href="{j.url}"><strong>{j.title}</strong></a>'
            f'<br><small style="color:#6b7280">{meta}</small>'
            f'{scorecard}{reason}</li>'
        )
    parts.append(
        f"<h2>{len(matches)} new matching "
        f"job{'s' if len(matches) != 1 else ''}</h2>"
        f'<ul style="list-style:none;padding:0">{"".join(rows)}</ul>'
    )
    return "".join(parts)


# ---------------------------------------------------------------------------
# Multi-recipient tabbed email
# ---------------------------------------------------------------------------
# Each recipient is a dict: {"name","key","matches":[Job],"problems":[str]}.
# We build ONE email with a section per recipient and send it to everyone.
# Every section is fully visible (stacked, clear header) so it reads in any
# email client — no reliance on JS, which Gmail strips.

def _tab_summary(r: dict) -> str:
    n = len(r["matches"])
    flag = " ⚠️" if r["problems"] else ""
    return f"{r['name']} ({n}){flag}"


def _render_tabbed_email(recipients_results: list[dict]) -> str:
    today = dt.date.today().isoformat()
    header = (
        f'<div style="margin-bottom:16px;font-family:-apple-system,Segoe UI,'
        f'Roboto,Helvetica,Arial,sans-serif">'
        f'<h1 style="margin:0 0 4px;font-size:20px">Family job matches — {today}</h1>'
        f'<div style="color:#6b7280;font-size:13px">'
        f'{" · ".join(_tab_summary(r) for r in recipients_results)}</div></div>'
    )
    panels = []
    for r in recipients_results:
        dim_spec = r.get("dimensions") or _DEFAULT_DIMENSIONS
        inner = _render_html(r["matches"], r["problems"], dim_spec)
        panels.append(
            f'<div style="margin-bottom:28px;font-family:-apple-system,Segoe UI,'
            f'Roboto,Helvetica,Arial,sans-serif">'
            f'<h3 style="font-size:16px;margin:0 0 10px;padding:6px 10px;'
            f'background:#f3f4f6;border-radius:6px">📁 {r["name"]}</h3>'
            f'{inner}</div>'
        )
    return (
        f'<div style="max-width:680px;margin:0 auto;color:#111827">{header}'
        f'{"".join(panels)}'
        f'<div style="color:#9ca3af;font-size:11px;margin-top:24px">'
        f'Sent to the whole family — every section is visible to everyone.</div>'
        f'</div>'
    )


def _post_to_resend(to_addrs: list[str], subject: str, html: str) -> None:
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        print("[deliver] no RESEND_API_KEY set; skipping email", file=sys.stderr)
        return
    body = {"from": config.EMAIL_FROM, "to": to_addrs,
            "subject": subject, "html": html}
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "jobscanner/1.0",   # avoids Resend 403 error 1010
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            print(f"[deliver] email sent ({resp.status}) to {len(to_addrs)} "
                  "recipient(s)", file=sys.stderr)
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            detail = "(could not read response body)"
        print(f"[deliver] email failed: HTTP {e.code} to={to_addrs!r} — "
              f"Resend said: {detail}", file=sys.stderr)
    except Exception as e:  # noqa: BLE001
        print(f"[deliver] email failed: {e}", file=sys.stderr)


def _write_digest_file_keyed(key: str, matches: list[Job],
                             dim_spec: list[dict]) -> str:
    """Per-recipient digest at digests/<key>/<date>.md, append-on-same-day."""
    d = os.path.join(DIGEST_DIR, key)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"{dt.date.today().isoformat()}.md")
    now = dt.datetime.now().strftime("%H:%M")
    if os.path.exists(path):
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"\n---\n\n#### Additional matches (run at {now})\n\n")
            f.write(_render_match_entries(matches, dim_spec))
    else:
        with open(path, "w", encoding="utf-8") as f:
            f.write(_render_markdown(matches, dim_spec))
    return path


def deliver_all(recipients_results: list[dict], all_recipients: list[str]) -> None:
    """Write per-recipient digests and send ONE combined email to everyone."""
    total = sum(len(r["matches"]) for r in recipients_results)
    any_problem = any(r["problems"] for r in recipients_results)

    for r in recipients_results:
        if r["matches"]:
            dim_spec = r.get("dimensions") or _DEFAULT_DIMENSIONS
            path = _write_digest_file_keyed(r["key"], r["matches"], dim_spec)
            print(f"[deliver] wrote {path}", file=sys.stderr)

    today = dt.date.today().isoformat()
    subject = f"{config.EMAIL_SUBJECT_PREFIX} Family digest — {total} new — {today}"
    if any_problem:
        subject = f"⚠️ {subject} (source problem)"
    _post_to_resend(all_recipients, subject, _render_tabbed_email(recipients_results))
