#!/usr/bin/env python3
"""Build Camden Fringe press emails without a Thunderbird template."""

from __future__ import annotations

import html as html_lib

from camden_press_content import build_camden_release_html
from campaigns import CAMDEN_EMAIL_POSTER, Campaign
from contacts import MediaContact
from template import FROM_EMAIL, INSTAGRAM_URL, build_compose_arg, resolve_poster_src

DEFAULT_SUBJECT = (
    "CAMDEN FRINGE PRESS RELEASE: I Think I'm Turning Japanese (I Really Think So, NOT!)"
)

OPENING = (
    "Hope you're well — just sharing the press release for my Camden Fringe show "
    "at the Museum of Comedy."
)


def _intro_html(
    contact: MediaContact,
    *,
    greeting_addressee: str,
    hook_line: str,
    include_instagram: bool,
    london_ps: str,
) -> str:
    parts = [
        f"<p>Hi {html_lib.escape(greeting_addressee)},</p>",
        f"<p>{html_lib.escape(OPENING)}</p>",
    ]
    if hook_line.strip():
        parts.append(f"<p>{html_lib.escape(hook_line.strip())}</p>")

    sign_off = "Best, Sam Joseph"
    if include_instagram:
        sign_off += f' <a href="{INSTAGRAM_URL}">{INSTAGRAM_URL}</a>'
    parts.append(f"<p>{sign_off}</p>")
    if london_ps.strip():
        parts.append(f"<p>{html_lib.escape(london_ps.strip())}</p>")
    return "".join(parts)


def build_camden_html(
    contact: MediaContact,
    campaign: Campaign,
    *,
    greeting_addressee: str = "there",
    hook_line: str = "",
    notes_html: str = "",
    embed_poster: bool = False,
    include_instagram: bool = True,
    london_ps: str = "",
) -> str:
    intro = _intro_html(
        contact,
        greeting_addressee=greeting_addressee,
        hook_line=hook_line,
        include_instagram=include_instagram,
        london_ps=london_ps,
    )
    release = build_camden_release_html(campaign)

    poster = ""
    if campaign.poster_url:
        poster_src = resolve_poster_src(
            campaign.poster_url,
            embed_for_compose=embed_poster,
            local_poster_path=CAMDEN_EMAIL_POSTER,
        )
        if poster_src:
            poster = (
                f'<p style="margin-top:16px;">'
                f'<a href="{campaign.tickets_url}">'
                f'<img src="{poster_src}" width="320" alt="Camden Fringe 2026 poster" '
                f'style="max-width:100%;height:auto;border:0;"></a></p>'
            )

    return (
        "<!DOCTYPE html><html><body style=\"font-family:Arial,sans-serif;font-size:12pt;"
        "color:#222;line-height:1.5;\">"
        f"{notes_html}{intro}{release}{poster}"
        "</body></html>"
    )


def write_camden_compose(
    output_path,
    contact: MediaContact,
    campaign: Campaign,
    *,
    greeting_addressee: str = "there",
    hook_line: str = "",
    notes_html: str = "",
    embed_poster: bool = False,
    include_instagram: bool = True,
    london_ps: str = "",
    subject: str = DEFAULT_SUBJECT,
):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    html = build_camden_html(
        contact,
        campaign,
        greeting_addressee=greeting_addressee,
        hook_line=hook_line,
        notes_html=notes_html,
        embed_poster=embed_poster,
        include_instagram=include_instagram,
        london_ps=london_ps,
    )
    output_path.write_text(html, encoding="utf-8")
    return output_path, subject


def build_camden_compose_arg(
    *,
    contact: MediaContact,
    subject: str,
    html_path,
    from_email: str = FROM_EMAIL,
) -> str:
    return build_compose_arg(
        to_email=contact.email,
        subject=subject,
        html_path=html_path,
    )
