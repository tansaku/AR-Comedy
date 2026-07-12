#!/usr/bin/env python3
"""Build complete industry outreach emails without Thunderbird templates."""

from __future__ import annotations

import html as html_lib
from pathlib import Path

from campaigns import Campaign
from industry_contacts import IndustryContact
from template import FROM_EMAIL, INSTAGRAM_URL, build_compose_arg

DEFAULT_SUBJECT = "Edinburgh Fringe — culture-clash solo comedy"


def _paragraphs_to_html(text: str) -> str:
    parts = [p.strip() for p in text.replace("\r\n", "\n").split("\n\n") if p.strip()]
    if not parts:
        parts = [line.strip() for line in text.split("\n") if line.strip()]
    return "".join(f"<p>{html_lib.escape(p)}</p>" for p in parts)


def build_industry_html(
    contact: IndustryContact,
    campaign: Campaign,
    *,
    body: str,
    notes_html: str = "",
) -> str:
    """Assemble a short HTML email from AI-written body paragraphs."""
    greeting = f"<p>Hi {html_lib.escape(contact.first_name)},</p>"
    body_html = _paragraphs_to_html(body)
    sign_off = (
        f"<p>Best,<br>Sam Joseph "
        f'<a href="{INSTAGRAM_URL}">{INSTAGRAM_URL}</a></p>'
    )
    poster = ""
    if campaign.poster_url:
        link_open = (
            f'<a href="{campaign.tickets_url}">' if campaign.tickets_url else ""
        )
        link_close = "</a>" if campaign.tickets_url else ""
        poster = (
            f'<p style="margin-top:16px;">{link_open}'
            f'<img src="{campaign.poster_url}" width="320" alt="Edinburgh Fringe 2026 poster" '
            f'style="max-width:100%;height:auto;border:0;">{link_close}</p>'
        )
    return (
        "<!DOCTYPE html><html><body style=\"font-family:Arial,sans-serif;font-size:12pt;"
        "color:#222;line-height:1.5;\">"
        f"{notes_html}{greeting}{body_html}{sign_off}{poster}"
        "</body></html>"
    )


def write_industry_compose(
    output_path: Path,
    contact: IndustryContact,
    campaign: Campaign,
    *,
    subject: str,
    body: str,
    notes_html: str = "",
) -> tuple[Path, str]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    html = build_industry_html(contact, campaign, body=body, notes_html=notes_html)
    output_path.write_text(html, encoding="utf-8")
    return output_path, subject


def build_industry_compose_arg(
    *,
    contact: IndustryContact,
    subject: str,
    html_path: Path,
    from_email: str = FROM_EMAIL,
) -> str:
    return build_compose_arg(
        to_email=contact.email,
        subject=subject,
        html_path=html_path,
    )
