#!/usr/bin/env python3
"""Load and personalise the Edinburgh press-release Thunderbird template."""

from __future__ import annotations

import base64
import re
from datetime import datetime
from email import policy
from email.header import decode_header, make_header
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE = REPO_ROOT / "data" / ".press-compose-base.eml"
DEFAULT_CACHE_META = REPO_ROOT / "data" / ".press-compose-base.json"
THUNDERBIRD_PROFILE = Path.home() / (
    "Library/Thunderbird/Profiles/magfbx3x.default-release"
)
SUBJECT_MARKER = "ED_FRINGE_PRESS_RELEASE"
FROM_EMAIL = "tansaku@gmail.com"

GREETING_RE = re.compile(r"Hi\s+[^,<]+,\s*", re.IGNORECASE)
BODY_OPEN_RE = re.compile(r"(<body[^>]*>)", re.IGNORECASE)
HOOK_BLOCK_RE = re.compile(
    r"(Hope you're well - Just sharing the press release for my upcoming Edinburgh show\.\s*)(.*?)(\s*Best, Sam Joseph)",
    re.DOTALL | re.IGNORECASE,
)
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


def find_latest_press_message(
    templates_paths: list[Path] | None = None,
) -> tuple[bytes, Path, datetime | None]:
    """Return the newest ED FRINGE press-release template across Thunderbird folders."""
    paths = templates_paths or discover_template_sources()
    if not paths:
        raise FileNotFoundError(
            f"No Thunderbird template folders found under {THUNDERBIRD_PROFILE}"
        )

    best: tuple[bytes, Path, datetime | None] | None = None
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        for chunk in text.split("\nFrom - "):
            if SUBJECT_MARKER not in chunk:
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
                # Fall back to file modification order if dates are missing.
                best = (eml, path, message_date)

    if best is None:
        raise FileNotFoundError(
            "No press-release template found. Save a Thunderbird template whose "
            f"subject contains '{SUBJECT_MARKER.replace('_', ' ')}'."
        )
    return best


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
    templates_paths: list[Path] | None = None,
    cache_path: Path | None = None,
    cache_meta_path: Path | None = None,
) -> Path:
    eml, source_path, message_date = find_latest_press_message(templates_paths)
    target = cache_path or DEFAULT_CACHE
    meta_path = cache_meta_path or DEFAULT_CACHE_META
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(eml)
    meta_path.write_text(
        (
            f'{{"source": "{source_path}", '
            f'"message_date": "{message_date.isoformat() if message_date else ""}", '
            f'"cached_at": "{datetime.now().isoformat()}"}}\n'
        ),
        encoding="utf-8",
    )
    return target


def load_base_eml(
    templates_paths: list[Path] | None = None,
    cache_path: Path | None = None,
    refresh: bool = False,
) -> bytes:
    paths = templates_paths or discover_template_sources()
    target = cache_path or DEFAULT_CACHE
    if refresh or cache_is_stale(templates_paths=paths, cache_path=target):
        cache_base_eml(paths, target)
    elif not target.exists():
        cache_base_eml(paths, target)
    return target.read_bytes()


def describe_cached_template(cache_meta_path: Path | None = None) -> str:
    meta_path = cache_meta_path or DEFAULT_CACHE_META
    if not meta_path.exists():
        return "template cache: not yet built"
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


def decode_subject(message) -> str:
    raw = message.get("Subject", SUBJECT_MARKER.replace("_", " "))
    if not raw:
        return "ED FRINGE PRESS RELEASE"
    try:
        return str(make_header(decode_header(raw)))
    except (UnicodeError, ValueError):
        return str(raw)


def inline_cid_images(html: str, message) -> str:
    """Replace cid: image references with data URIs for Thunderbird compose."""
    for part in message.walk():
        if part.get_content_maintype() != "image":
            continue
        cid = part.get("Content-ID")
        if not cid:
            continue
        cid = cid.strip("<>")
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        mime = part.get_content_type()
        b64 = base64.b64encode(payload).decode("ascii")
        html = html.replace(f"cid:{cid}", f"data:{mime};base64,{b64}")
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


def inject_hook_line(html: str, hook_line: str) -> str:
    """Replace the template's default hook with a personalised angle."""
    hook_line = hook_line.strip()
    if not hook_line:
        return html

    def replacer(match: re.Match[str]) -> str:
        return f"{match.group(1)}{hook_line}{match.group(3)}"

    updated, count = HOOK_BLOCK_RE.subn(replacer, html, count=1)
    if count != 1:
        raise ValueError("Could not find hook block in press-release template")
    return updated


def personalise_html(
    html: str,
    *,
    first_name: str,
    contact_notes_html: str = "",
    hook_line: str = "",
) -> str:
    """Inject contact notes, swap greeting name, and optionally replace the hook."""
    html = inject_contact_notes(html, contact_notes_html)
    html = replace_greeting_name(html, first_name)
    if hook_line:
        html = inject_hook_line(html, hook_line)
    return normalize_line_breaks_for_compose(html)


def build_compose_html(
    *,
    first_name: str,
    contact_notes_html: str = "",
    hook_line: str = "",
    templates_paths: list[Path] | None = None,
    cache_path: Path | None = None,
    refresh_template: bool = False,
) -> tuple[str, str]:
    """Return (subject, personalised HTML body) ready for Thunderbird -compose."""
    eml_bytes = load_base_eml(templates_paths, cache_path, refresh=refresh_template)
    message = _parse_message(eml_bytes)
    html = _html_part(message).get_content()
    html = inline_cid_images(html, message)
    html = personalise_html(
        html,
        first_name=first_name,
        contact_notes_html=contact_notes_html,
        hook_line=hook_line,
    )
    return decode_subject(message), html


def write_personalised_html(
    output_path: Path,
    *,
    first_name: str,
    contact_notes_html: str = "",
    hook_line: str = "",
    templates_paths: list[Path] | None = None,
    cache_path: Path | None = None,
    refresh_template: bool = False,
) -> tuple[Path, str]:
    subject, html = build_compose_html(
        first_name=first_name,
        contact_notes_html=contact_notes_html,
        hook_line=hook_line,
        templates_paths=templates_paths,
        cache_path=cache_path,
        refresh_template=refresh_template,
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
