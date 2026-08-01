#!/usr/bin/env python3
"""Draft personalised email intros for press outreach."""

from __future__ import annotations

import re

from contacts import MediaContact

LONDON_PREVIEW_PS = (
    "p.s. I'm also running a few London previews over the next few weeks. "
    "If a press ticket would be useful, boxoffice@museumofcomedy.com can help."
)

CAMDEN_PRESS_PS = (
    "p.s. Press tickets for Camden Fringe (13 Aug, Museum of Comedy): "
    "boxoffice@museumofcomedy.com"
)

# Shown in the grey contact-notes box during review mode only.
LONDON_PREVIEW_NOTE = (
    "I'm also running a few London previews over the next few weeks — "
    "if a press ticket would be useful, boxoffice@museumofcomedy.com can help."
)

CAMDEN_PRESS_NOTE = (
    "Camden Fringe: 13 August, 7pm, Museum of Comedy. "
    "Press tickets via boxoffice@museumofcomedy.com if useful."
)


def _interest_hook(contact: MediaContact) -> str | None:
    interests = contact.interests or ""
    has_comedy = "Comedy" in interests
    has_theatre = "Theatre" in interests
    if has_comedy and not has_theatre:
        return None
    if has_theatre and not has_comedy:
        return (
            "I know you're theatre rather than comedy, but despite the laughs "
            "I think my show has some theatric value. Anyway on the off chance :-)"
        )
    return None


def _org_hook(contact: MediaContact) -> str | None:
    org = (contact.organisation or "").strip()
    if not org:
        return None

    lowered = org.lower()
    hooks: list[tuple[str, str]] = [
        (
            "university of edinburgh",
            "I was once a student at Edinburgh, a long time ago in a galaxy, "
            "well this galaxy in fact :-)",
        ),
        (
            "the student",
            "I was once a student at Edinburgh, a long time ago in a galaxy, "
            "well this galaxy in fact :-)",
        ),
        (
            "wee review",
            "hope the Wee Review stays mighty — this one's a culture-clash hour "
            "that might suit your comedy/theatre beat.",
        ),
        (
            "fest magazine",
            "figured Fest might enjoy a show that's basically fringe-by-experience "
            "rather than fringe-by-brief :-)",
        ),
        (
            "radio",
            "not sure if radio counts as theatre, but the stories travel well out loud.",
        ),
        (
            "review",
            "always slightly nervous emailing reviewers — but the show's had kind "
            "words in Brighton so far.",
        ),
        (
            "theatre",
            "it's stand-up, but there's a fair bit of theatrical storytelling in there.",
        ),
        (
            "comedy",
            "thought this might be up your comedy alley — culture clash, marriage, "
            "and accidental Japanification.",
        ),
        (
            "magazine",
            "hoping this might make a fun magazine story — British awkwardness vs "
            "Japanese politeness, with jokes.",
        ),
        (
            "blog",
            "thought your readers might enjoy a fish-out-of-water hour in Edinburgh.",
        ),
        (
            "scotland",
            "bringing a slightly confused Brit back to Scotland for the Fringe.",
        ),
    ]
    for needle, line in hooks:
        if needle in lowered:
            return line

    clean_org = re.sub(r"https?://", "", org).strip(" /")
    if clean_org and len(clean_org) <= 60:
        return f"thought this might be of interest for {clean_org}."
    return None


def draft_intro(contact: MediaContact, *, campaign_id: str = "press") -> str:
    """Return a first-pass intro paragraph for human review (rule-based)."""
    if campaign_id == "camden-press":
        base = (
            "Hope you're well — just sharing the press release for my Camden Fringe show "
            "at the Museum of Comedy."
        )
    else:
        base = "Hope you're well - Just sharing the press release for my upcoming Edinburgh show."
    hook = _org_hook(contact) or _interest_hook(contact)
    if hook:
        return f"{base}  {hook}"
    return base


def draft_hook_line(
    contact: MediaContact,
    *,
    use_llm: bool = True,
    examples=None,
    campaign_id: str = "press",
    use_cache: bool = True,
    web_url: str = "",
    web_blurb: str = "",
) -> tuple[str, str]:
    """Return (hook_only, source) — hook is injected into the template body."""
    from llm_hook import draft_hook

    return draft_hook(
        contact,
        use_llm=use_llm,
        examples=examples,
        campaign_id=campaign_id,
        use_cache=use_cache,
        web_url=web_url,
        web_blurb=web_blurb,
    )


def draft_london_note(contact: MediaContact, *, campaign_id: str = "press") -> str:
    if campaign_id == "camden-press":
        return CAMDEN_PRESS_NOTE
    return LONDON_PREVIEW_NOTE if contact.is_london_relevant else ""


def draft_london_ps(contact: MediaContact, *, campaign_id: str = "press") -> str:
    if campaign_id == "camden-press":
        return CAMDEN_PRESS_PS
    return LONDON_PREVIEW_PS if contact.is_london_relevant else ""
