#!/usr/bin/env python3
"""Generate personalised industry outreach via OpenRouter (incl. auto-router)."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from industry_contacts import IndustryContact
from llm_hook import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "openrouter/auto"

INDUSTRY_SHOW_CONTEXT = """
Sam Joseph — British stand-up comedian, Edinburgh Fringe 2026.
Show: "I Think I'm Turning Japanese (I Really Think So, NOT!)" — 50-minute culture-clash solo
comedy about marriage, language learning, and living between the UK and Japan.
Venue: Just the Tonic at The Caves — The Spare Room.
Dates: 20–30 August 2026, 21:05 nightly.
Tickets: https://edinburgh.justthetonic.com/event/88:5767/

Objective: put the show on this person's radar so they might attend while in Edinburgh.
This is NOT a press release — a short, warm, specific invite to see the show or connect.
Tone: personable, lightly self-deprecating British humour; not salesy or desperate.
""".strip()

BASE_LINE = (
    "Hope you're well — I'm up at Edinburgh Fringe with a solo comedy hour and wanted to reach out."
)


@dataclass(frozen=True)
class IndustryApproach:
    should_contact: bool
    priority: str
    fit_summary: str
    hook: str
    skip_reason: str = ""


def _openrouter_payload(prompt: str, *, system: str, max_tokens: int = 280) -> dict:
    load_dotenv()
    model = os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL)
    payload: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,
        "max_tokens": max_tokens,
    }
    if model == "openrouter/auto" or model.endswith("/auto"):
        tradeoff = int(os.environ.get("OPENROUTER_AUTO_TRADEOFF", "3"))
        payload["plugins"] = [
            {"id": "auto-router", "cost_quality_tradeoff": tradeoff},
        ]
    return payload


def _call_openrouter(payload: dict) -> dict:
    load_dotenv()
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY not set")
    request = urllib.request.Request(
        OPENROUTER_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://comedy.neurogrid.com",
            "X-Title": "AR-Comedy industry outreach",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenRouter error {exc.code}: {detail}") from exc


def _parse_approach_json(content: str) -> IndustryApproach:
    text = (content or "").strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]
    data = json.loads(text)
    hook = str(data.get("hook", "")).strip()
    return IndustryApproach(
        should_contact=bool(data.get("should_contact", True)),
        priority=str(data.get("priority", "medium")).strip().lower(),
        fit_summary=str(data.get("fit_summary", "")).strip(),
        hook=hook,
        skip_reason=str(data.get("skip_reason", "")).strip(),
    )


def _build_prompt(contact: IndustryContact, *, audience: str) -> str:
    return f"""You help a comedian decide whether and how to invite one Edinburgh Fringe industry
contact to see his show. Audience list type: {audience}.

{INDUSTRY_SHOW_CONTEXT}

The email template already opens with (do NOT repeat):
"{BASE_LINE}"

Return JSON only:
{{
  "should_contact": true/false,
  "priority": "high|medium|low",
  "fit_summary": "One sentence on why they are/aren't a good fit",
  "hook": "1-2 sentences to insert after the opening line — specific to them (empty if should_contact is false)",
  "skip_reason": "Brief reason if should_contact is false, else empty"
}}

Rules:
- should_contact=false if they won't be in town during the show, aren't interested in comedy,
  or their stated preferences clearly exclude this kind of solo stand-up.
- hook max ~45 words, British English, warm not pushy.
- Reference their role, organisation, or stated interests when possible.

Contact profile:
{contact.profile_text()}
"""


def generate_industry_approach(
    contact: IndustryContact,
    *,
    audience: str = "programmer",
) -> IndustryApproach:
    prompt = _build_prompt(contact, audience=audience)
    payload = _openrouter_payload(
        prompt,
        system=(
            "You assess Fringe industry outreach fit and write short email hooks. "
            "Reply with valid JSON only."
        ),
    )
    body = _call_openrouter(payload)
    content = body["choices"][0]["message"]["content"]
    model_used = body.get("model", payload["model"])
    approach = _parse_approach_json(content)
    if not approach.should_contact and not approach.skip_reason:
        approach = IndustryApproach(
            should_contact=False,
            priority="low",
            fit_summary=approach.fit_summary or "Not a strong fit",
            hook="",
            skip_reason=approach.fit_summary or "Low fit",
        )
    print(f"  LLM model: {model_used}", flush=True)
    return approach


def approach_to_storage(approach: IndustryApproach) -> tuple[str, str, str]:
    if not approach.should_contact:
        return "", f"SKIP: {approach.skip_reason or approach.fit_summary}", "skip"
    return approach.hook, approach.fit_summary, approach.priority
