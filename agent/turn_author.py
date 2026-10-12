"""Who wrote the user side of a turn, carried from the dispatcher into the recipient's turn.

The dispatcher sets ``HERMES_TURN_AUTHOR`` on the recipient's one-shot subprocess only. A cached
gateway agent sees several authors over its lifetime, so the author is read per turn, never per agent.
"""

from __future__ import annotations

import json
import os
import socket
import unicodedata
from typing import Any, Dict, Mapping, MutableMapping, Optional

TURN_AUTHOR_ENV = "HERMES_TURN_AUTHOR"

_MAX_FIELD_LEN = 200


_DROPPED_CATEGORIES = frozenset({"Cc", "Cs", "Cn", "Co"})
_TRUTHY = frozenset({"true", "1", "yes"})


def _clean_text(value: Any) -> Optional[str]:
    """Strip whitespace, control and unassigned characters, then cap the length. None when nothing is left.
    Format characters and non-breaking spaces stay so emoji sequences and display names survive."""
    if not isinstance(value, str):
        return None
    text = "".join(ch for ch in value if unicodedata.category(ch) not in _DROPPED_CATEGORIES).strip()
    if not text:
        return None
    return text[:_MAX_FIELD_LEN]


def _bot_flag(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in _TRUTHY
    return isinstance(value, (bool, int)) and bool(value)


def bot_author_id(profile: str, origin: Optional[str] = None) -> str:
    """``bot:<profile>`` for a bot on the recipient's own install, ``bot:<origin>/<profile>`` for one on another
    install. The origin is the Desktop's connection id on a relayed dm and the sender's hostname on a peer dm."""
    origin = (origin or "").strip()
    return f"bot:{origin}/{profile}" if origin else f"bot:{profile}"


def local_origin() -> str:
    """This machine's hostname as an author-id origin, cleaned like any author field. Empty when unknown."""
    try:
        host = socket.gethostname()
    except Exception:
        return ""
    # A slash would split the id into a different origin and profile at parse time.
    return (_clean_text(host) or "").replace("/", "")


def parse_turn_author(raw: Any) -> Optional[dict[str, Any]]:
    """Normalize a dict or JSON string into ``{"id", "name", "is_bot"}``; None for anything else or without id and name.
    The id is whatever the transport knows the sender by: ``bot:<profile>`` on a bot-mode delivery inside one
    install, ``bot:<connection>/<profile>`` when the Desktop relayed it from another machine,
    ``bot:<hostname>/<profile>`` on a peer dm, the platform user id elsewhere.
    An ``origin`` field qualifies a bare ``bot:<profile>`` id the same way."""
    try:
        if isinstance(raw, (str, bytes)):
            raw = json.loads(raw)
        if not isinstance(raw, Mapping):
            return None
        author = {
            "id": _clean_text(raw.get("id")),
            "name": _clean_text(raw.get("name")),
            "is_bot": _bot_flag(raw.get("is_bot")),
        }
        if author["id"] is None and author["name"] is None:
            return None
        origin = _clean_text(raw.get("origin"))
        if origin and author["id"] and author["id"].startswith("bot:") and "/" not in author["id"]:
            author["id"] = _clean_text(bot_author_id(author["id"][len("bot:"):], origin))
        return author
    except Exception:
        return None


def turn_author_from_env(environ: Mapping[str, str] = os.environ) -> Optional[dict[str, Any]]:
    """The author the dispatcher placed in ``HERMES_TURN_AUTHOR``, or None."""
    return parse_turn_author(environ.get(TURN_AUTHOR_ENV))


def take_turn_author_from_env(environ: MutableMapping[str, str] = os.environ) -> Optional[dict[str, Any]]:
    """Read and remove ``HERMES_TURN_AUTHOR`` so subprocesses started during the turn do not inherit it."""
    return parse_turn_author(environ.pop(TURN_AUTHOR_ENV, None))


def turn_author_env(author: dict[str, Any]) -> dict[str, str]:
    """The environment entry a dispatcher merges into a child's env."""
    return {TURN_AUTHOR_ENV: json.dumps(author, separators=(",", ":"))}


def a2a_key(author: Optional[dict[str, Any]]) -> Optional[str]:
    """``a2a:<bot id>``, the shared name for a bot author's turns. None for a human or an id-less bot."""
    if not isinstance(author, dict) or not author.get("is_bot") or not author.get("id"):
        return None
    return f"a2a:{author['id']}"


def delivery_display(author: Any, display_kind: Optional[str] = None,
                     display_metadata: Optional[dict[str, Any]] = None) -> tuple[Optional[str], Optional[dict[str, Any]]]:
    """Keep event types unchanged; only bot transport authors need durable attribution."""
    parsed = parse_turn_author(author)
    if parsed is None or not parsed["is_bot"]:
        return display_kind, display_metadata
    return display_kind, {**(display_metadata or {}), "author": parsed}


def delivery_author(message: Mapping[str, Any]) -> Optional[dict[str, Any]]:
    """Read bot provenance independently of synthetic timeline kinds."""
    metadata = message.get("display_metadata")
    author = parse_turn_author(metadata.get("author")) if isinstance(metadata, Mapping) else None
    return author if message.get("role") == "user" and author and author["is_bot"] else None


def is_bot_delivery(message: Mapping[str, Any]) -> bool:
    return delivery_author(message) is not None


def delivery_author_name(message: Mapping[str, Any]) -> str:
    """Short, redacted labels cannot introduce transcript delimiters or human authority."""
    from agent.redact import redact_sensitive_text

    author = delivery_author(message)
    if author is None:
        return str(message.get("role", "unknown")).upper()
    # Redact BEFORE filtering/capping so a truncated secret cannot evade the redactor.
    raw = redact_sensitive_text(author["name"] or author["id"] or "Bot",
                                force=True, redact_url_credentials=True)
    label = "".join(ch for ch in raw if ch.isascii() and (ch.isalnum() or ch in " ._:/-"))
    return label.strip()[:64] or "Bot"


def transcript_author_label(message: Mapping[str, Any]) -> str:
    if not is_bot_delivery(message):
        return str(message.get("role", "unknown")).upper()
    return "BOT " + delivery_author_name(message)


def delivery_content(message: Mapping[str, Any], content: Any) -> Any:
    """Prefix a bot's text or structured content; leave attachments intact."""
    if not is_bot_delivery(message):
        return content
    prefix = f"[{transcript_author_label(message)}]\n"
    legacy_prefix = f"[Bot delivery: {transcript_author_label(message)}; not the human user]\n"
    prefixes = (prefix, legacy_prefix)
    if isinstance(content, str):
        return content if content.startswith(prefixes) else prefix + content
    if isinstance(content, list):
        first = content[0] if content else None
        if isinstance(first, dict) and first.get("type") == "text" and isinstance(first.get("text"), str) and first["text"].startswith(prefixes):
            return content
        return [{"type": "text", "text": prefix}, *content]
    return content


def project_delivery_message(message: dict[str, Any], content_key: str = "content") -> dict[str, Any]:
    """Display-only copy; raw history and provider roles remain untouched.

    A round-tripped display row cannot acquire system authority. The model wire
    formats its own content from raw provenance, never from this display projection.
    """
    if not is_bot_delivery(message):
        return message
    return {**message, content_key: delivery_content(message, message.get(content_key))}
