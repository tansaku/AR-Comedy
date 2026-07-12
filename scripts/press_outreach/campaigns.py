#!/usr/bin/env python3
"""Outreach campaign definitions (press, industry, etc.)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

REPO_ROOT = Path(__file__).resolve().parents[2]
SITE_BASE = "https://comedy.neurogrid.com"

PRESS_POSTER_URL = f"{SITE_BASE}/assets/images/email-edinburgh-fringe-2026.jpg"
PRESS_TICKETS_URL = "https://edinburgh.justthetonic.com/event/88:5767/"

IndustrySchema = Literal["programmer", "agent"]


@dataclass(frozen=True)
class Campaign:
    id: str
    label: str
    subject_marker: str
    cache_eml: Path
    cache_meta: Path
    compose_dir: Path
    sync_state: Path
    default_numbers: Path
    industry_schema: IndustrySchema | None = None
    industry_audience: str = ""
    poster_url: str | None = None
    tickets_url: str | None = None
    require_hook_block: bool = True
    require_sign_off_block: bool = True
    use_llm_hooks: bool = True


def _campaign(
    *,
    id: str,
    label: str,
    subject_marker: str,
    numbers_filename: str,
    industry_schema: IndustrySchema | None = None,
    industry_audience: str = "",
    require_hook_block: bool = True,
    require_sign_off_block: bool = True,
    use_llm_hooks: bool = True,
    poster_url: str | None = None,
    tickets_url: str | None = None,
) -> Campaign:
    data = REPO_ROOT / "data"
    return Campaign(
        id=id,
        label=label,
        subject_marker=subject_marker,
        cache_eml=data / f".{id}-compose-base.eml",
        cache_meta=data / f".{id}-compose-base.json",
        compose_dir=data / f".{id}-compose-drafts",
        sync_state=data / f".{id}-outreach-sent-sync.json",
        default_numbers=data / numbers_filename,
        industry_schema=industry_schema,
        industry_audience=industry_audience,
        poster_url=poster_url,
        tickets_url=tickets_url,
        require_hook_block=require_hook_block,
        require_sign_off_block=require_sign_off_block,
        use_llm_hooks=use_llm_hooks,
    )


PRESS = _campaign(
    id="press",
    label="Edinburgh Fringe press release",
    subject_marker="ED_FRINGE_PRESS_RELEASE",
    numbers_filename="2026 Media Contact List .numbers",
    poster_url=PRESS_POSTER_URL,
    tickets_url=PRESS_TICKETS_URL,
)

INDUSTRY_UK = _campaign(
    id="industry-uk",
    label="Industry — UK programmers",
    subject_marker="INDUSTRY_UK_OUTREACH",
    numbers_filename="Comedy- UK - Programmers_ Festivals, Venues.numbers",
    industry_schema="programmer",
    industry_audience="UK comedy programmers, festivals and venues",
    require_hook_block=False,
    require_sign_off_block=False,
    poster_url=PRESS_POSTER_URL,
    tickets_url=PRESS_TICKETS_URL,
)

INDUSTRY_INTL = _campaign(
    id="industry-intl",
    label="Industry — international programmers",
    subject_marker="INDUSTRY_INTL_OUTREACH",
    numbers_filename="Comedy- International - Programmers_ Festivals, Venues .numbers",
    industry_schema="programmer",
    industry_audience="international comedy programmers, festivals and venues",
    require_hook_block=False,
    require_sign_off_block=False,
    poster_url=PRESS_POSTER_URL,
    tickets_url=PRESS_TICKETS_URL,
)

INDUSTRY_AGENTS = _campaign(
    id="industry-agents",
    label="Industry — agents & talent management",
    subject_marker="INDUSTRY_AGENTS_OUTREACH",
    numbers_filename="Agents, Casting, Talent Management.numbers",
    industry_schema="agent",
    industry_audience="agents, casting directors and talent managers",
    require_hook_block=False,
    require_sign_off_block=False,
    poster_url=None,
    tickets_url=None,
)

# Back-compat alias
INDUSTRY = INDUSTRY_UK

CAMPAIGNS: dict[str, Campaign] = {
    c.id: c
    for c in (PRESS, INDUSTRY_UK, INDUSTRY_INTL, INDUSTRY_AGENTS)
}
DEFAULT_CAMPAIGN_ID = "press"


def get_campaign(campaign_id: str) -> Campaign:
    key = (campaign_id or DEFAULT_CAMPAIGN_ID).strip().lower()
    if key == "industry":
        key = "industry-uk"
    if key not in CAMPAIGNS:
        known = ", ".join(sorted(CAMPAIGNS))
        raise ValueError(f"Unknown campaign {campaign_id!r}. Choose from: {known}")
    return CAMPAIGNS[key]
