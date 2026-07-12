#!/usr/bin/env python3
"""Load and personalise Thunderbird outreach templates."""

from __future__ import annotations

import base64
import re
import urllib.error
import urllib.request
from datetime import datetime
from email import policy
from email.header import decode_header, make_header
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from pathlib import Path

from campaigns import DEFAULT_CAMPAIGN_ID, Campaign, PRESS, get_campaign

REPO_ROOT = Path(__file__).resolve().parents[2]
# Legacy cache paths (press campaign); new runs use campaign-specific paths.
DEFAULT_CACHE = REPO_ROOT / "data" / ".press-compose-base.eml"
DEFAULT_CACHE_META = REPO_ROOT / "data" / ".press-compose-base.json"
THUNDERBIRD_PROFILE = Path.home() / (
    "Library/Thunderbird/Profiles/magfbx3x.default-release"
)
FROM_EMAIL = "tansaku@gmail.com"
INSTAGRAM_URL = "https://www.instagram.com/tansaku/"
LOCAL_POSTER_PATH = REPO_ROOT / "assets" / "images" / "email-edinburgh-fringe-2026.jpg"
_poster_remote_ok: bool | None = None

GREETING_RE = re.compile(r"Hi\s+[^,<]+,\s*", re.IGNORECASE)
SIGN_OFF_RE = re.compile(r"Best, Sam Joseph\b", re.IGNORECASE)
BODY_OPEN_RE = re.compile(r"(<body[^>]*>)", re.IGNORECASE)
HOOK_BLOCK_RE = re.compile(
    r"(Hope you're well - Just sharing the press release for my upcoming Edinburgh show\.\s*)(.*?)(\s*Best, Sam Joseph)",
    re.DOTALL | re.IGNORECASE,
)
INDUSTRY_HOOK_BLOCK_RE = re.compile(
    r"(Hope you're well — I'm up at Edinburgh Fringe with a solo comedy hour and wanted to reach out\.\s*)(.*?)(\s*Best, Sam Joseph)",
    re.DOTALL | re.IGNORECASE,
)
IMG_TAG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
DATA_IMAGE_SRC_RE = re.compile(r'src="data:image/[^"]+"', re.IGNORECASE)
CID_IMAGE_SRC_RE = re.compile(r'src="cid:[^"]+"', re.IGNORECASE)
INTRO_PARAGRAPH_STYLE = "margin-top:0pt;margin-bottom:0pt;"
INTRO_PARAGRAPH_STYLE_SPACED = "margin-top:0pt;margin-bottom:12pt;"
PRE_WRAP_SPAN_RE = re.compile(
    r'(white-space:\s*pre-wrap;">)(.*?)(</span>)',
    re.DOTALL | re.IGNORECASE,
)
def _newlines_to_br(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\n\n", "<br><br>")
    return text.replace("\n", "<br>")


def normalize_line_breaks_for_compose(html: str) -> str:
    """Make intro line breaks survive Thunderbird's compose HTML importer."""
    marker = "Press Release"
    split_at = html.find(marker)
    if split_at < 0:
        prefix, suffix = html, ""
    else:
        prefix, suffix = html[:split_at], html[split_at:]

    prefix = prefix.replace(INTRO_PARAGRAPH_STYLE, INTRO_PARAGRAPH_STYLE_SPACED)

    def span_replacer(match: re.Match[str]) -> str:
        return match.group(1) + _newlines_to_br(match.group(2)) + match.group(3)

    prefix = PRE_WRAP_SPAN_RE.sub(span_replacer, prefix)
    return prefix + suffix


def replace_greeting_name(html: str, first_name: str) -> str:
    """Swap the template greeting name; spacing comes from the following <p> tags."""
    greeting = GREETING_RE.search(html)
    if not greeting:
        raise ValueError("Could not find greeting ('Hi …,') in press-release template")
    return GREETING_RE.sub(f"Hi {first_name},", html, count=1)


def discover_template_sources(profile_dir: Path | None = None) -> list[Path]:
    """Candidate Thunderbird template mbox files for tansaku@gmail.com."""
    profile = profile_dir or THUNDERBIRD_PROFILE
    candidates = [
        profile / "ImapMail/imap.gmail-1.com/Templates-1",
        profile / "ImapMail/imap.gmail.com/Templates-1",
        profile / "Mail/Local Folders/Templates",
        profile / "Mail/Local Folders/Templates-tansaku@gmail.com",
    ]
    return [path for path in candidates if path.exists() and path.stat().st_size > 0]


def _message_date(chunk: str) -> datetime | None:
    body = chunk
    if body.startswith("From - "):
        body = "\n".join(body.splitlines()[1:])
    try:
        message = BytesParser(policy=policy.default).parsebytes(
            body.encode("utf-8", errors="replace")
        )
    except (UnicodeError, ValueError):
        return None
    raw_date = message.get("Date")
    if not raw_date:
        return None
    try:
        return parsedate_to_datetime(raw_date)
    except (TypeError, ValueError, OverflowError):
        return None


def find_latest_template_message(
    campaign: Campaign,
    templates_paths: list[Path] | None = None,
) -> tuple[bytes, Path, datetime | None]:
    """Return the newest Thunderbird template for this campaign."""
    marker = campaign.subject_marker
    paths = templates_paths or discover_template_sources()
    if not paths:
        raise FileNotFoundError(
            f"No Thunderbird template folders found under {THUNDERBIRD_PROFILE}"
        )

    best: tuple[bytes, Path, datetime | None] | None = None
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        for chunk in text.split("\nFrom - "):
            if marker not in chunk:
                continue
            raw = chunk if chunk.startswith("From - ") else "From - " + chunk
            eml = "\n".join(raw.splitlines()[1:]).encode("utf-8")
            message_date = _message_date(raw)
            if best is None:
                best = (eml, path, message_date)
                continue
            _, _, best_date = best
            if message_date and (best_date is None or message_date > best_date):
                best = (eml, path, message_date)
            elif message_date is None and best_date is None:
                best = (eml, path, message_date)

    if best is None:
        spaced = marker.replace("_", " ")
        raise FileNotFoundError(
            f"No {campaign.label} template found. Save a Thunderbird template whose "
            f"subject contains '{spaced}'."
        )
    return best


def find_latest_press_message(
    templates_paths: list[Path] | None = None,
) -> tuple[bytes, Path, datetime | None]:
    return find_latest_template_message(PRESS, templates_paths)


def _newest_source_mtime(paths: list[Path]) -> float:
    return max(path.stat().st_mtime for path in paths)


def cache_is_stale(
    *,
    templates_paths: list[Path] | None = None,
    cache_path: Path | None = None,
) -> bool:
    paths = templates_paths or discover_template_sources()
    cache = cache_path or DEFAULT_CACHE
    if not paths or not cache.exists():
        return True
    return _newest_source_mtime(paths) > cache.stat().st_mtime


def cache_base_eml(
    campaign: Campaign,
    templates_paths: list[Path] | None = None,
    cache_path: Path | None = None,
    cache_meta_path: Path | None = None,
) -> Path:
    eml, source_path, message_date = find_latest_template_message(campaign, templates_paths)
    target = cache_path or campaign.cache_eml
    meta_path = cache_meta_path or campaign.cache_meta
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(eml)
    meta_path.write_text(
        (
            f'{{"campaign": "{campaign.id}", '
            f'"source": "{source_path}", '
            f'"message_date": "{message_date.isoformat() if message_date else ""}", '
            f'"cached_at": "{datetime.now().isoformat()}"}}\n'
        ),
        encoding="utf-8",
    )
    return target


def load_base_eml(
    campaign: Campaign,
    templates_paths: list[Path] | None = None,
    cache_path: Path | None = None,
    refresh: bool = False,
) -> bytes:
    paths = templates_paths or discover_template_sources()
    target = cache_path or campaign.cache_eml
    if refresh or cache_is_stale(templates_paths=paths, cache_path=target):
        cache_base_eml(campaign, paths, target)
    elif not target.exists():
        cache_base_eml(campaign, paths, target)
    return target.read_bytes()


def describe_cached_template(campaign: Campaign) -> str:
    meta_path = campaign.cache_meta
    if not meta_path.exists():
        return f"{campaign.id} template cache: not yet built"
    return meta_path.read_text(encoding="utf-8").strip()


def _parse_message(eml_bytes: bytes):
    return BytesParser(policy=policy.default).parsebytes(eml_bytes)


def _html_part(message):
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() == "text/html":
                return part
        raise ValueError("No text/html part in press-release template")
    if message.get_content_type() == "text/html":
        return message
    raise ValueError("Press-release template is not HTML")


def decode_subject(message, *, fallback: str) -> str:
    raw = message.get("Subject", fallback.replace("_", " "))
    if not raw:
        return fallback.replace("_", " ")
    try:
        return str(make_header(decode_header(raw)))
    except (UnicodeError, ValueError):
        return str(raw)


def _hosted_poster_available(poster_url: str) -> bool:
    global _poster_remote_ok
    if _poster_remote_ok is not None:
        return _poster_remote_ok
    try:
        request = urllib.request.Request(poster_url, method="HEAD")
        with urllib.request.urlopen(request, timeout=8) as response:
            _poster_remote_ok = response.status == 200
    except (urllib.error.URLError, OSError, ValueError):
        _poster_remote_ok = False
    return _poster_remote_ok


def resolve_poster_src(
    poster_url: str | None,
    *,
    embed_for_compose: bool = False,
) -> str | None:
    """Poster src for email HTML.

    Thunderbird compose often blocks remote images — embed locally for review drafts.
    Sent mail uses the hosted URL when live (~100KB JPEG, not the old 3.5MB inline).
    """
    if embed_for_compose and LOCAL_POSTER_PATH.exists():
        encoded = base64.b64encode(LOCAL_POSTER_PATH.read_bytes()).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"
    if poster_url and _hosted_poster_available(poster_url):
        return poster_url
    if LOCAL_POSTER_PATH.exists():
        encoded = base64.b64encode(LOCAL_POSTER_PATH.read_bytes()).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"
    return poster_url


def use_hosted_poster(
    html: str,
    *,
    poster_url: str,
    tickets_url: str | None = None,
) -> str:
    """Drop embedded megabyte images; use one small poster before the body copy."""
    html = IMG_TAG_RE.sub("", html)
    poster_src = resolve_poster_src(poster_url)
    if not poster_src:
        return html
    link_open = f'<a href="{tickets_url}">' if tickets_url else ""
    link_close = "</a>" if tickets_url else ""
    band = (
        f'<p style="margin:12pt 0 16pt 0;">{link_open}'
        f'<img src="{poster_src}" width="400" alt="I Think I\'m Turning Japanese — Edinburgh Fringe 2026" '
        f'style="max-width:100%;height:auto;border:0;">{link_close}</p>'
    )
    marker = "Press Release"
    split_at = html.find(marker)
    if split_at < 0:
        return html + band
    return html[:split_at] + band + html[split_at:]


def optimise_template_images(html: str, campaign: Campaign) -> str:
    """Prefer GitHub Pages-hosted images over inlined CID/data-URI blobs."""
    if campaign.poster_url:
        return use_hosted_poster(
            html,
            poster_url=campaign.poster_url,
            tickets_url=campaign.tickets_url,
        )
    # No hosted poster configured: swap cid/data URIs only if a remote URL is added later.
    html = DATA_IMAGE_SRC_RE.sub('src=""', html)
    html = CID_IMAGE_SRC_RE.sub('src=""', html)
    return html


def inject_contact_notes(html: str, notes_html: str) -> str:
    """Prepend a deletable metadata block inside <body>."""
    if not notes_html:
        return html
    if "press-contact-notes" in html:
        return html
    match = BODY_OPEN_RE.search(html)
    if not match:
        raise ValueError("Could not find <body> tag in press-release template")
    insert_at = match.end()
    return html[:insert_at] + notes_html + html[insert_at:]


def inject_sign_off_extras(
    html: str,
    *,
    include_instagram: bool = True,
    london_ps: str = "",
    required: bool = True,
) -> str:
    """Link Instagram after the sign-off name; optionally append a London preview p.s."""
    if not include_instagram and not london_ps.strip():
        return html

    marker = "Press Release"
    split_at = html.find(marker)
    if split_at < 0:
        prefix, suffix = html, ""
    else:
        prefix, suffix = html[:split_at], html[split_at:]

    sign_off = "Best, Sam Joseph"
    if include_instagram:
        sign_off = f'Best, Sam Joseph <a href="{INSTAGRAM_URL}">{INSTAGRAM_URL}</a>'
    if london_ps.strip():
        sign_off += f"<br><br>{_newlines_to_br(london_ps.strip())}"

    updated_prefix, count = SIGN_OFF_RE.subn(sign_off, prefix, count=1)
    if count != 1 and required:
        raise ValueError("Could not find sign-off ('Best, Sam Joseph') in press-release template")
    return (updated_prefix if count else prefix) + suffix


def inject_hook_line(
    html: str,
    hook_line: str,
    *,
    required: bool = True,
    industry_mode: bool = False,
) -> str:
    """Replace the template's default hook with a personalised angle."""
    hook_line = hook_line.strip()
    if not hook_line:
        return html

    def replacer(match: re.Match[str]) -> str:
        return f"{match.group(1)}{hook_line}{match.group(3)}"

    patterns = [INDUSTRY_HOOK_BLOCK_RE, HOOK_BLOCK_RE] if industry_mode else [HOOK_BLOCK_RE]
    for pattern in patterns:
        updated, count = pattern.subn(replacer, html, count=1)
        if count == 1:
            return updated
    if required:
        raise ValueError("Could not find hook block in email template")
    return html


def personalise_html(
    html: str,
    *,
    first_name: str,
    contact_notes_html: str = "",
    hook_line: str = "",
    include_instagram: bool = True,
    london_ps: str = "",
    require_hook_block: bool = True,
    require_sign_off_block: bool = True,
    industry_mode: bool = False,
) -> str:
    """Inject contact notes, swap greeting name, and optionally replace the hook."""
    html = inject_contact_notes(html, contact_notes_html)
    html = replace_greeting_name(html, first_name)
    if hook_line:
        html = inject_hook_line(
            html, hook_line, required=require_hook_block, industry_mode=industry_mode
        )
    html = inject_sign_off_extras(
        html,
        include_instagram=include_instagram,
        london_ps=london_ps,
        required=require_sign_off_block,
    )
    return normalize_line_breaks_for_compose(html)


def build_compose_html(
    *,
    campaign: Campaign,
    first_name: str,
    contact_notes_html: str = "",
    hook_line: str = "",
    include_instagram: bool = True,
    london_ps: str = "",
    templates_paths: list[Path] | None = None,
    refresh_template: bool = False,
    industry_mode: bool = False,
) -> tuple[str, str]:
    """Return (subject, personalised HTML body) ready for Thunderbird -compose."""
    eml_bytes = load_base_eml(campaign, templates_paths, refresh=refresh_template)
    message = _parse_message(eml_bytes)
    html = _html_part(message).get_content()
    html = optimise_template_images(html, campaign)
    html = personalise_html(
        html,
        first_name=first_name,
        contact_notes_html=contact_notes_html,
        hook_line=hook_line,
        include_instagram=include_instagram,
        london_ps=london_ps,
        require_hook_block=campaign.require_hook_block,
        require_sign_off_block=campaign.require_sign_off_block,
        industry_mode=industry_mode,
    )
    return decode_subject(message, fallback=campaign.subject_marker), html


def write_personalised_html(
    output_path: Path,
    *,
    campaign: Campaign,
    first_name: str,
    contact_notes_html: str = "",
    hook_line: str = "",
    include_instagram: bool = True,
    london_ps: str = "",
    templates_paths: list[Path] | None = None,
    refresh_template: bool = False,
    industry_mode: bool = False,
) -> tuple[Path, str]:
    subject, html = build_compose_html(
        campaign=campaign,
        first_name=first_name,
        contact_notes_html=contact_notes_html,
        hook_line=hook_line,
        include_instagram=include_instagram,
        london_ps=london_ps,
        templates_paths=templates_paths,
        refresh_template=refresh_template,
        industry_mode=industry_mode,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path, subject


def quote_compose_value(value: str) -> str:
    """Quote a value for Thunderbird -compose (single-quoted, escape apostrophes)."""
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def build_compose_arg(
    *,
    to_email: str,
    subject: str,
    html_path: Path,
    from_email: str = FROM_EMAIL,
) -> str:
    """Build the -compose option string for Thunderbird."""
    return ",".join(
        [
            f"from={quote_compose_value(from_email)}",
            f"to={quote_compose_value(to_email)}",
            f"subject={quote_compose_value(subject)}",
            "format=html",
            f"message={quote_compose_value(str(html_path.resolve()))}",
        ]
    )
