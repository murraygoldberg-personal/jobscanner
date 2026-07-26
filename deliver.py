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


def _render_markdown(matches: list[Job]) -> str:
    today = dt.date.today().isoformat()
    lines = [f"# Job matches — {today}", ""]
    if not matches:
        lines.append("_No new matching jobs today._")
        return "\n".join(lines)
    by_source: dict[str, list[Job]] = {}
    for j in matches:
        by_source.setdefault(j.source, []).append(j)
    for source, jobs in sorted(by_source.items()):
        lines.append(f"## {source} ({len(jobs)})")
        lines.append("")
        for j in jobs:
            loc = f" — {j.location}" if j.location else ""
            comp = f" · {j.company}" if j.company else ""
            lines.append(f"- **[{j.title}]({j.url})**{comp}{loc}")
        lines.append("")
    return "\n".join(lines)


def _render_html(matches: list[Job]) -> str:
    rows = []
    for j in matches:
        meta = " · ".join(x for x in [j.company, j.location] if x)
        rows.append(
            f'<li><a href="{j.url}"><strong>{j.title}</strong></a>'
            f'<br><small>{j.source} · {meta}</small></li>'
        )
    return f"<h2>{len(matches)} new matching jobs</h2><ul>{''.join(rows)}</ul>"


def _write_digest_file(md: str) -> str:
    os.makedirs(DIGEST_DIR, exist_ok=True)
    path = os.path.join(DIGEST_DIR, f"{dt.date.today().isoformat()}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(md)
    return path


def _send_email(matches: list[Job]) -> None:
    api_key = os.environ.get("RESEND_API_KEY")
    to_addr = os.environ.get("EMAIL_TO", config.EMAIL_TO)
    if not api_key:
        print("[deliver] no RESEND_API_KEY set; skipping email", file=sys.stderr)
        return
    subject = f"{config.EMAIL_SUBJECT_PREFIX} {len(matches)} new " \
              f"job{'s' if len(matches) != 1 else ''} — {dt.date.today().isoformat()}"
    body = {
        "from": config.EMAIL_FROM,
        "to": [to_addr],
        "subject": subject,
        "html": _render_html(matches),
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


def deliver(matches: list[Job]) -> None:
    md = _render_markdown(matches)
    path = _write_digest_file(md)
    print(f"[deliver] wrote {path}", file=sys.stderr)
    if not matches and not config.SEND_EMPTY_DIGEST:
        print("[deliver] nothing new; no email", file=sys.stderr)
        return
    _send_email(matches)
