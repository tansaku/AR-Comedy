#!/usr/bin/env python3
"""Fetch a short text snippet from a contact's website for hook personalisation."""

from __future__ import annotations

import re
import urllib.error
import urllib.request

from contacts import MediaContact

GENERIC_EMAIL_DOMAINS = {
    "gmail.com",
    "googlemail.com",
    "yahoo.com",
    "yahoo.co.uk",
    "hotmail.com",
    "outlook.com",
    "icloud.com",
    "aol.com",
    "live.com",
    "me.com",
    "proton.me",
    "protonmail.com",
}


def site_url_from_email(email: str) -> str | None:
    domain = (email or "").split("@")[-1].lower().strip()
    if not domain or domain in GENERIC_EMAIL_DOMAINS:
        return None
    return f"https://{domain}"


def fetch_site_blurb(url: str, *, max_chars: int = 900) -> str:
    try:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "AR-Comedy-press-outreach/1.0"},
            method="GET",
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            raw = response.read(12000)
    except (urllib.error.URLError, OSError, ValueError):
        return ""

    html = raw.decode("utf-8", errors="replace")
    html = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
    html = re.sub(r"(?is)<style.*?>.*?</style>", " ", html)
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


def contact_web_context(contact: MediaContact) -> tuple[str, str]:
    """Return (url_or_empty, blurb_or_empty)."""
    url = site_url_from_email(contact.email)
    if not url:
        return "", ""
    blurb = fetch_site_blurb(url)
    return url, blurb
