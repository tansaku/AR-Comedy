#!/usr/bin/env python3
"""Generate personalised press-email hooks via OpenRouter."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

from contacts import MediaContact
from intros import _interest_hook, _org_hook
from sent_examples import SentHookExample, load_sent_hook_examples

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = REPO_ROOT / ".env"
HOOK_CACHE_PATH = REPO_ROOT / "data" / ".press-hook-cache.json"
CAMDEN_HOOK_CACHE_PATH = REPO_ROOT / "data" / ".camden-press-hook-cache.json"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "anthropic/claude-sonnet-4"
BASE_LINE = (
    "Hope you're well - Just sharing the press release for my upcoming Edinburgh show."
)

CAMDEN_BASE_LINE = (
    "Hope you're well - just sharing the press release for my Camden Fringe show "
    "at the Museum of Comedy."
)

SHOW_CONTEXT = """
Sam Joseph — British stand-up comedian, Edinburgh Fringe 2026.
Show: "I Think I'm Turning Japanese (I Really Think So, NOT!)" — culture-clash solo comedy
about marriage, language learning, and living between the UK and Japan (six years in Japan,
bilingual family life). Performed in London, Tokyo, Osaka, Brighton, Leicester, Camden.
Tone: warm, lightly self-deprecating, occasionally nerdy wordplay; not salesy or gushy.
""".strip()

CAMDEN_SHOW_CONTEXT = """
Sam Joseph - British stand-up comedian, Camden Fringe 2026.
Show: "I Think I'm Turning Japanese (I Really Think So, NOT!)" - 50-minute culture-clash solo comedy
about marriage, language learning, and living between the UK and Japan.
Venue: Museum of Comedy, London. Date: Thursday 13 August 2026, 7:00pm.
Tickets: https://museumofcomedy.ticketsolve.com/ticketbooth/shows/873664754
Camden Fringe listing: https://camdenfringe.com/events/i-think-im-turning-japanese-i-really-think-so-not/
Press tickets: boxoffice@museumofcomedy.com
Tone: warm, lightly self-deprecating British humour; not salesy or gushy.
Use ASCII hyphens only, not em dashes.
""".strip()


def _campaign_context(campaign_id: str) -> tuple[str, str]:
    if campaign_id == "camden-press":
        return CAMDEN_SHOW_CONTEXT, CAMDEN_BASE_LINE
    return SHOW_CONTEXT, BASE_LINE


def load_dotenv(path: Path = ENV_PATH) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def openrouter_configured() -> bool:
    load_dotenv()
    return bool(os.environ.get("OPENROUTER_API_KEY"))


def _hook_cache_path(campaign_id: str) -> Path:
    if campaign_id == "camden-press":
        return CAMDEN_HOOK_CACHE_PATH
    return HOOK_CACHE_PATH


def _load_hook_cache(campaign_id: str = "press") -> dict[str, str]:
    path = _hook_cache_path(campaign_id)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _save_hook_cache(cache: dict[str, str], *, campaign_id: str = "press") -> None:
    path = _hook_cache_path(campaign_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=2) + "\n", encoding="utf-8")


def clear_hook_cache(*, campaign_id: str = "press") -> None:
    path = _hook_cache_path(campaign_id)
    if path.exists():
        path.unlink()


def rule_based_hook(contact: MediaContact, *, campaign_id: str = "press") -> str:
    fallback = (
        "thought this might be up your alley for Camden Fringe coverage."
        if campaign_id == "camden-press"
        else "thought this might be up your alley for Edinburgh Fringe coverage."
    )
    return _org_hook(contact) or _interest_hook(contact) or fallback


def _format_examples(examples: list[SentHookExample], limit: int = 8) -> str:
    if not examples:
        return "(No sent examples yet.)"
    lines = []
    for example in examples[-limit:]:
        lines.append(
            f"- {example.name} ({example.organisation}) <{example.email}> → \"{example.hook}\""
        )
    return "\n".join(lines)


def _build_prompt(
    contact: MediaContact,
    examples: list[SentHookExample],
    *,
    campaign_id: str = "press",
    web_url: str = "",
    web_blurb: str = "",
) -> str:
    show_context, base_line = _campaign_context(campaign_id)
    camden_rules = ""
    web_section = ""
    if campaign_id == "camden-press":
        camden_rules = """
Rules for Camden list contacts:
- The "Interests" field is only a coarse list section (often "Theatre" for all fringe bloggers). Do NOT claim they cover theatre, comedy, or a specific beat unless the organisation name or website snippet supports it.
- Do NOT invent editorial angles or open with vague flattery ("Given your fringe coverage", "Given your theatre focus", etc.).
- Prefer starting with "I thought you might appreciate…" (or similar) and a concrete angle about the show - culture clash, Japan/UK, family, language - not their supposed beat.
- Use ASCII hyphens only, not em dashes.
- Use a specific detail from the organisation name or website snippet when you have one; otherwise a warm general line about the show is fine.
"""
        if web_url or web_blurb:
            web_section = f"""
Publication website: {web_url or "unknown"}
Website snippet: {web_blurb or "Not available."}
"""
    return f"""You help a comedian write one short personalised hook sentence for a press email.

{show_context}
{camden_rules}
The email already has this fixed opening (do NOT repeat it):
"{base_line}"

Your job: write ONLY the next sentence or two — the hook/angle that connects Sam, the show,
and this specific journalist/publication. Keep it to 1-2 sentences, max ~35 words.
British English. Light humour welcome; no emojis; no exclamation marks unless truly needed.

Recipient:
- Name: {contact.name}
- Organisation: {contact.organisation}
- Job title: {contact.job_title}
- Country: {contact.country}
- Interests (coarse list tag): {contact.interests}
{web_section}
Examples from emails Sam already sent (match this voice and specificity):
{_format_examples(examples)}

Reply with ONLY the hook text — no greeting, no sign-off, no quotes, no markdown."""


def _parse_hook_response(content: str, *, base_line: str = BASE_LINE) -> str:
    hook = (content or "").strip()
    hook = hook.strip("\"'")
    hook = re.sub(r"^hook:\s*", "", hook, flags=re.IGNORECASE)
    hook = re.sub(r"\s+", " ", hook).strip()
    if hook.lower().startswith(base_line.lower()):
        hook = hook[len(base_line) :].strip(" .")
    return hook


def generate_hook_llm(
    contact: MediaContact,
    *,
    examples: list[SentHookExample] | None = None,
    use_cache: bool = True,
    campaign_id: str = "press",
    web_url: str = "",
    web_blurb: str = "",
) -> str:
    load_dotenv()
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY not set")

    _, base_line = _campaign_context(campaign_id)
    cache_key = contact.email.lower()
    if use_cache:
        cache = _load_hook_cache(campaign_id)
        if cache_key in cache:
            return cache[cache_key]

    examples = examples if examples is not None else load_sent_hook_examples()
    model = os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL)
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You write concise, specific press-email hooks for a comedy Fringe show. "
                    "Output only the hook sentence(s), nothing else. Never invent beats or "
                    "coverage areas that are not supported by the contact details."
                ),
            },
            {
                "role": "user",
                "content": _build_prompt(
                    contact,
                    examples,
                    campaign_id=campaign_id,
                    web_url=web_url,
                    web_blurb=web_blurb,
                ),
            },
        ],
        "temperature": 0.8,
        "max_tokens": 120,
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

    content = body["choices"][0]["message"]["content"]
    hook = _parse_hook_response(content, base_line=base_line)
    if not hook:
        raise RuntimeError("OpenRouter returned an empty hook")
    hook = _normalize_hook(hook, campaign_id=campaign_id)

    if use_cache:
        cache = _load_hook_cache(campaign_id)
        cache[cache_key] = hook
        _save_hook_cache(cache, campaign_id=campaign_id)
    return hook


def _normalize_hook(hook: str, *, campaign_id: str) -> str:
    if campaign_id == "camden-press":
        from camden_press_content import ascii_hyphens

        return ascii_hyphens(hook)
    return hook


def draft_hook(
    contact: MediaContact,
    *,
    use_llm: bool = True,
    examples: list[SentHookExample] | None = None,
    campaign_id: str = "press",
    use_cache: bool = True,
    web_url: str = "",
    web_blurb: str = "",
) -> tuple[str, str]:
    """Return (hook_line, source) where source is 'llm', 'cache', or 'rules'."""
    cache_key = contact.email.lower()
    if use_llm and openrouter_configured():
        try:
            cache = _load_hook_cache(campaign_id)
            if use_cache and cache_key in cache:
                return _normalize_hook(cache[cache_key], campaign_id=campaign_id), "cache"
            hook = generate_hook_llm(
                contact,
                examples=examples,
                use_cache=use_cache,
                campaign_id=campaign_id,
                web_url=web_url,
                web_blurb=web_blurb,
            )
            return hook, "llm"
        except (RuntimeError, urllib.error.URLError, KeyError, json.JSONDecodeError) as exc:
            print(f"LLM hook failed ({exc}); using rule-based fallback.", flush=True)
    return rule_based_hook(contact, campaign_id=campaign_id), "rules"
