#!/usr/bin/env python3
"""Suggest press-email greetings (the addressee after 'Hi ') via OpenRouter."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

from camden_greeting import rule_based_greeting
from contacts import MediaContact
from llm_hook import load_dotenv, openrouter_configured

REPO_ROOT = Path(__file__).resolve().parents[2]
GREETING_CACHE_PATH = REPO_ROOT / "data" / ".camden-press-greeting-cache.json"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "anthropic/claude-sonnet-4"


def _load_greeting_cache() -> dict[str, str]:
    if not GREETING_CACHE_PATH.exists():
        return {}
    return json.loads(GREETING_CACHE_PATH.read_text(encoding="utf-8"))


def _save_greeting_cache(cache: dict[str, str]) -> None:
    GREETING_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    GREETING_CACHE_PATH.write_text(json.dumps(cache, indent=2) + "\n", encoding="utf-8")


def _build_prompt(
    contact: MediaContact,
    *,
    web_url: str = "",
    web_blurb: str = "",
) -> str:
    web_section = ""
    if web_url or web_blurb:
        web_section = f"""
Publication website: {web_url or "unknown"}
Website snippet: {web_blurb or "Not available."}
"""
    return f"""You help a comedian choose how to open a press email greeting.

The email will begin: Hi {{addressee}},

Your job: reply with ONLY the addressee — the words that come after "Hi " and before the comma.
Do NOT include "Hi", commas, or a trailing full stop.

Choose the most natural option:
- A person's first name when you are confident the contact is an individual (e.g. Sarah, Bianca)
- A publication/team form when the name column is clearly a blog, magazine, or outlet
  (e.g. "Youngish Perspective folks", "Timeout team", "Chortle team")
- Drop leading articles (A/An/The) from publication names — use "Youngish Perspective folks"
  not "A Youngish Perspective folks"
- "there" for generic inboxes (press@, hello@, info@) with no identifiable person

Rules:
- The "Name" column is often a publication title, NOT a person — do not take the first word
  as a first name (e.g. "A Young(ish) Perspective" is a blog, not someone called A)
- Prefer the job-title person field when present and clearly a human name
- Prefer the email local part only when it is clearly a personal name (e.g. bianca@…)
- British English; warm and professional; no emojis

Contact:
- Name column: {contact.name}
- Email: {contact.email}
- Organisation: {contact.organisation}
- Job title: {contact.job_title}
- Country: {contact.country}
{web_section}
Reply with ONLY the addressee text — nothing else."""


def _parse_greeting_response(content: str) -> str:
    greet = (content or "").strip()
    greet = greet.strip("\"'")
    greet = re.sub(r"^hi\s+", "", greet, flags=re.IGNORECASE)
    greet = greet.rstrip(",").strip()
    greet = re.sub(r"\s+", " ", greet).strip()
    if greet.lower() in {"there", "team", "folks"}:
        return greet.lower() if greet.lower() == "there" else greet
    return greet


def generate_greeting_llm(
    contact: MediaContact,
    *,
    use_cache: bool = True,
    web_url: str = "",
    web_blurb: str = "",
) -> str:
    load_dotenv()
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY not set")

    cache_key = contact.email.lower()
    if use_cache:
        cache = _load_greeting_cache()
        if cache_key in cache:
            return cache[cache_key]

    model = os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL)
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You choose email greeting addressees for press outreach. "
                    "Output only the addressee (after 'Hi '), never the full greeting line."
                ),
            },
            {"role": "user", "content": _build_prompt(contact, web_url=web_url, web_blurb=web_blurb)},
        ],
        "temperature": 0.4,
        "max_tokens": 40,
    }
    request = urllib.request.Request(
        OPENROUTER_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://comedy.neurogrid.com",
            "X-Title": "AR-Comedy press outreach",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenRouter error {exc.code}: {detail}") from exc

    greet = _parse_greeting_response(body["choices"][0]["message"]["content"])
    if not greet:
        raise RuntimeError("OpenRouter returned an empty greeting")

    if use_cache:
        cache = _load_greeting_cache()
        cache[cache_key] = greet
        _save_greeting_cache(cache)
    return greet


def draft_greeting(
    contact: MediaContact,
    *,
    use_llm: bool = True,
    use_cache: bool = True,
    web_url: str = "",
    web_blurb: str = "",
) -> tuple[str, str]:
    """Return (addressee_after_hi, source) where source is llm, cache, or rules."""
    cache_key = contact.email.lower()
    if use_llm and openrouter_configured():
        try:
            cache = _load_greeting_cache()
            if use_cache and cache_key in cache:
                return cache[cache_key], "cache"
            greet = generate_greeting_llm(
                contact,
                use_cache=use_cache,
                web_url=web_url,
                web_blurb=web_blurb,
            )
            return greet, "llm"
        except (RuntimeError, urllib.error.URLError, KeyError, json.JSONDecodeError) as exc:
            print(f"LLM greeting failed ({exc}); using rule-based fallback.", flush=True)
    return rule_based_greeting(contact), "rules"
