"""Allowlisted CDP targets and profile-scoped named-session bindings."""

from hashlib import sha256
from threading import RLock
from urllib.parse import urlsplit, urlunsplit

from hermes_constants import get_hermes_home

_BINDINGS = {}
_LOCK = RLock()


def session_key(session):
    return f"{get_hermes_home().resolve()}::browser-target::{session}"


def bound_url(key):
    with _LOCK:
        binding = _BINDINGS.get(key)
        return binding[1] if binding else None


def _probe_cdp(url):
    import requests
    from agent.proxy_bypass import loopback_request_kwargs

    parts = urlsplit(url)
    scheme = {"ws": "http", "wss": "https"}.get(parts.scheme, parts.scheme)
    discovery = urlunsplit((scheme, parts.netloc, "/json/version", parts.query, ""))
    response = requests.get(discovery, timeout=5, **loopback_request_kwargs(discovery))
    response.raise_for_status()
    if not response.json().get("webSocketDebuggerUrl"):
        raise ValueError("CDP discovery did not return a WebSocket endpoint")


def route_target(env, session, target, config, default_route):
    """Bind explicit targets once; omitted targets reuse an existing binding."""
    import requests
    from tools.browser_use_cli import _set_cdp_env, _BOT_DESKTOP_BROWSER_SENTINEL, _PRIVATE_BROWSER_SENTINEL

    if target is not None and not session:
        return {"success": False, "error_type": "session_required", "error": "target requires a named session."}
    key = session_key(session)
    with _LOCK:
        binding = _BINDINGS.get(key)
        if binding and target is not None and target != binding[0]:
            return {"success": False, "error_type": "target_mismatch", "error": "This session is bound to a different target; use a new session name."}
        if binding:
            url = binding[1]
        elif target is None:
            return None
        elif target == "default":
            error = default_route()
            if error:
                return {"success": False, "error_type": "target_unreachable", "error": error}
            url = env.get("BU_CDP_WS") or env.get("BU_CDP_URL")
        else:
            targets = config.get("targets", {})
            url = targets.get(target) if isinstance(targets, dict) and isinstance(target, str) else None
            if not isinstance(url, str) or not url.strip():
                return {"success": False, "error_type": "unknown_target", "error": "Unknown browser target; choose a name configured in browser.targets."}
        try:
            if not url:
                raise ValueError("No CDP endpoint")
            _probe_cdp(url)
        except (requests.RequestException, OSError, ValueError, TypeError):
            return {"success": False, "error_type": "target_unreachable", "error": "Browser target is unreachable; no fallback was attempted."}
        flags = {name: env[name] for name in (_BOT_DESKTOP_BROWSER_SENTINEL, _PRIVATE_BROWSER_SENTINEL) if name in env}
        _BINDINGS[key] = binding or (target, url, flags)
        env.update(_BINDINGS[key][2])
        env.pop("BU_CDP_WS", None)
        env.pop("BU_CDP_URL", None)
        _set_cdp_env(env, url)
        env.pop("BU_AUTOSPAWN", None)
        # Avoid adopting a daemon started by an unbound session or another profile.
        env["BU_NAME"] = "hermes-target-" + sha256(key.encode()).hexdigest()[:32]
    return None


def vault_session(task_id, session):
    """Attach before any page read; never fall back to the task's default browser."""
    if not session:
        return task_id or "default", None
    from tools.browser_vault_tool import _ensure_supervisor

    key = session_key(session)
    if bound_url(key) is None:
        return key, {"success": False, "error_type": "session_unbound", "error": "Start this named session with browser_exec target first."}
    if _ensure_supervisor(key) is None:
        return key, {"success": False, "error_type": "target_unreachable", "error": "The named session's browser supervisor is unavailable."}
    return key, None


def prepare_route(env, session, target, config, default_route):
    from tools.registry import tool_error, tool_result

    targeted = target is not None or (bool(session) and bound_url(session_key(session)) is not None)
    if targeted:
        error = route_target(env, session, target, config, default_route)
        return targeted, tool_result(error) if error else None
    error = default_route()
    return targeted, tool_error(error) if error else None


def desktop_binding(key):
    from tools.browser_use_cli import _BOT_DESKTOP_BROWSER_SENTINEL

    with _LOCK:
        binding = _BINDINGS.get(key)
        return bool(binding and binding[2].get(_BOT_DESKTOP_BROWSER_SENTINEL))
