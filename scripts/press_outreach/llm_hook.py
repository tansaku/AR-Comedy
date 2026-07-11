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
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "anthropic/claude-sonnet-4"
BASE_LINE = (
    "Hope you're well - Just sharing the press release for my upcoming Edinburgh show."
)

SHOW_CONTEXT = """
Sam Joseph — British stand-up comedian, Edinburgh Fringe 2026.
Show: "I Think I'm Turning Japanese (I Really Think So, NOT!)" — culture-clash solo comedy
about marriage, language learning, and living between the UK and Japan (six years in Japan,
bilingual family life). Performed in London, Tokyo, Osaka, Brighton, Leicester, Camden.
Tone: warm, lightly self-deprecating, occasionally nerdy wordplay; not salesy or gushy.
""".strip()


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


def _load_hook_cache() -> dict[str, str]:
    if not HOOK_CACHE_PATH.exists():
        return {}
    return json.loads(HOOK_CACHE_PATH.read_text(encoding="utf-8"))


def _save_hook_cache(cache: dict[str, str]) -> None:
    HOOK_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    HOOK_CACHE_PATH.write_text(json.dumps(cache, indent=2) + "\n", encoding="utf-8")


def rule_based_hook(contact: MediaContact) -> str:
    return _org_hook(contact) or _interest_hook(contact) or (
        "thought this might be up your alley for Edinburgh Fringe coverage."
    )


def _format_examples(examples: list[SentHookExample], limit: int = 8) -> str:
    if not examples:
        return "(No sent examples yet.)"
    lines = []
    for example in examples[-limit:]:
        lines.append(
            f"- {example.name} ({example.organisation}) <{example.email}> → \"{example.hook}\""
        )
    return "\n".join(lines)


def _build_prompt(contact: MediaContact, examples: list[SentHookExample]) -> str:
    return f"""You help a comedian write one short personalised hook sentence for a press email.

{SHOW_CONTEXT}

The email already has this fixed opening (do NOT repeat it):
"{BASE_LINE}"

Your job: write ONLY the next sentence or two — the hook/angle that connects Sam, the show,
and this specific journalist/publication. Keep it to 1-2 sentences, max ~35 words.
British English. Light humour welcome; no emojis; no exclamation marks unless truly needed.

Recipient:
- Name: {contact.name}
- Organisation: {contact.organisation}
- Job title: {contact.job_title}
- Country: {contact.country}
- Interests: {contact.interests}

Examples from emails Sam already sent (match this voice and specificity):
{_format_examples(examples)}

Reply with ONLY the hook text — no greeting, no sign-off, no quotes, no markdown."""


def _parse_hook_response(content: str) -> str:
    hook = (content or "").strip()
    hook = hook.strip("\"'")
    hook = re.sub(r"^hook:\s*", "", hook, flags=re.IGNORECASE)
    hook = re.sub(r"\s+", " ", hook).strip()
    if hook.lower().startswith(BASE_LINE.lower()):
        hook = hook[len(BASE_LINE) :].strip(" .")
    return hook


def generate_hook_llm(
    contact: MediaContact,
    *,
    examples: list[SentHookExample] | None = None,
    use_cache: bool = True,
) -> str:
    load_dotenv()
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY not set")

    cache_key = contact.email.lower()
    if use_cache:
        cache = _load_hook_cache()
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
                    "Output only the hook sentence(s), nothing else."
                ),
            },
            {"role": "user", "content": _build_prompt(contact, examples)},
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
    hook = _parse_hook_response(content)
    if not hook:
        raise RuntimeError("OpenRouter returned an empty hook")

    if use_cache:
        cache = _load_hook_cache()
        cache[cache_key] = hook
        _save_hook_cache(cache)
    return hook


def draft_hook(
    contact: MediaContact,
    *,
    use_llm: bool = True,
    examples: list[SentHookExample] | None = None,
) -> tuple[str, str]:
    """Return (hook_line, source) where source is 'llm', 'cache', or 'rules'."""
    if use_llm and openrouter_configured():
        try:
            cache = _load_hook_cache()
            if contact.email.lower() in cache:
                return cache[contact.email.lower()], "cache"
            hook = generate_hook_llm(contact, examples=examples, use_cache=True)
            return hook, "llm"
        except (RuntimeError, urllib.error.URLError, KeyError, json.JSONDecodeError) as exc:
            print(f"LLM hook failed ({exc}); using rule-based fallback.", flush=True)
    return rule_based_hook(contact), "rules"
