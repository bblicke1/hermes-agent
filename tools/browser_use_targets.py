"""Allowlisted CDP targets and profile-scoped named-session bindings."""

import subprocess
from dataclasses import dataclass
from threading import RLock
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

from hermes_constants import get_hermes_home

_RESERVED_PREFIX = "hermes-target-"
_BINDINGS = {}
_LOCK = RLock()


class TargetError(RuntimeError):
    def __init__(self, error_type, message):
        super().__init__(message)
        self.error_type = error_type

    def result(self):
        return {"success": False, "error_type": self.error_type, "error": str(self)}


@dataclass(frozen=True)
class Binding:
    target: str
    url: str
    identity: str
    fenced: bool
    private: bool
    daemon: str
    task_id: str | None
    local: bool


def session_key(session):
    return f"{get_hermes_home().resolve()}::browser-target::{session}"


def is_target_key(key):
    return bool(key and key.startswith(session_key("")))


def bound_url(key):
    with _LOCK:
        binding = _BINDINGS.get(key)
        return binding.url if binding else None


def _discovery_url(url):
    parts = urlsplit(url)
    scheme = {"ws": "http", "wss": "https"}.get(parts.scheme, parts.scheme)
    return urlunsplit((scheme, parts.netloc, "/json/version", parts.query, ""))


def _probe_cdp(url):
    import requests
    from agent.proxy_bypass import loopback_request_kwargs

    discovery = _discovery_url(url)
    response = requests.get(discovery, timeout=5, **loopback_request_kwargs(discovery))
    response.raise_for_status()
    identity = response.json().get("webSocketDebuggerUrl")
    if not isinstance(identity, str) or urlsplit(identity).scheme not in ("ws", "wss"):
        raise ValueError("CDP discovery did not return a WebSocket endpoint")
    return identity


def _identity(url):
    import requests

    try:
        return _probe_cdp(url)
    except (requests.RequestException, OSError, ValueError, TypeError) as exc:
        raise TargetError("target_unreachable", "Browser target is unreachable; no fallback was attempted.") from exc


def _target_spec(target, config, env, default_route):
    from tools.browser_use_cli import _BOT_DESKTOP_BROWSER_SENTINEL, _PRIVATE_BROWSER_SENTINEL

    if target == "default":
        error = default_route()
        if error:
            raise TargetError("target_route_failed", error)
        url = env.get("BU_CDP_WS") or env.get("BU_CDP_URL")
        if not url:
            raise TargetError("target_unsupported_backend", "The default backend does not expose a CDP endpoint.")
        return url, bool(env.get(_BOT_DESKTOP_BROWSER_SENTINEL)), bool(env.get(_PRIVATE_BROWSER_SENTINEL))
    targets = config.get("targets", {})
    entry = targets.get(target) if isinstance(targets, dict) and isinstance(target, str) else None
    spec = {"url": entry} if isinstance(entry, str) else entry
    if not isinstance(spec, dict) or not isinstance(spec.get("url"), str) or not spec["url"].strip():
        raise TargetError("unknown_target", "Unknown browser target; choose a name configured in browser.targets.")
    fenced = spec.get("fenced", False)
    if not isinstance(fenced, bool):
        raise TargetError("invalid_target_config", "browser.targets fenced must be a boolean.")
    return spec["url"].strip(), fenced, False


def _revalidate(binding, config, env, default_route):
    try:
        url, fenced, private = _target_spec(binding.target, config, env, default_route)
    except TargetError as exc:
        raise TargetError("target_revoked", "The bound target is no longer available in current configuration; release it first.") from exc
    same_url = _discovery_url(url) == _discovery_url(binding.url) if binding.target == "default" else url == binding.url
    if not same_url or fenced != binding.fenced or private != binding.private:
        raise TargetError("target_revoked", "The bound target configuration changed; release it before rebinding.")
    if _identity(binding.url) != binding.identity:
        raise TargetError("target_identity_changed", "The target browser identity changed; release the session and rebind.")
    return binding


def _bind(key, target, config, env, default_route, task_id, local):
    binding = _BINDINGS.get(key)
    if binding:
        if target is not None and target != binding.target:
            raise TargetError("target_mismatch", "This session is bound to a different target; release it first.")
        return _revalidate(binding, config, env, default_route)
    url, fenced, private = _target_spec(target, config, env, default_route)
    identity = _identity(url)
    if any(_discovery_url(other.url) == _discovery_url(url) or other.identity == identity for other in _BINDINGS.values()):
        raise TargetError("target_busy", "Another named session owns this browser target; release it first.")
    binding = Binding(target, url, identity, fenced, private, _RESERVED_PREFIX + uuid4().hex, task_id, local)
    _BINDINGS[key] = binding
    return binding


def _export_binding(env, binding):
    from tools.browser_use_cli import _set_cdp_env, _BOT_DESKTOP_BROWSER_SENTINEL, _PRIVATE_BROWSER_SENTINEL

    for name in ("BU_CDP_WS", "BU_CDP_URL", "BU_AUTOSPAWN", _BOT_DESKTOP_BROWSER_SENTINEL, _PRIVATE_BROWSER_SENTINEL):
        env.pop(name, None)
    _set_cdp_env(env, binding.identity)
    if binding.fenced:
        env[_BOT_DESKTOP_BROWSER_SENTINEL] = "1"
    if binding.private:
        env[_PRIVATE_BROWSER_SENTINEL] = "1"
    env["BU_NAME"] = binding.daemon


def prepare_route(env, session, target, config, default_route, task_id=None, local=False):
    from tools.registry import tool_error

    with _LOCK:
        targeted = target is not None or (bool(session) and session_key(session) in _BINDINGS)
        try:
            if not targeted:
                error = default_route()
                return False, tool_error(error) if error else None
            if not session:
                raise TargetError("session_required", "target requires a named session.")
            binding = _bind(session_key(session), target, config, env, default_route, task_id, local)
            _export_binding(env, binding)
            return True, None
        except TargetError as exc:
            return targeted, tool_error(str(exc), success=False, error_type=exc.error_type)


def validated_binding(key):
    from tools import browser_use_cli as cli

    with _LOCK:
        binding = _BINDINGS.get(key)
        if binding is None:
            raise TargetError("session_unbound", "Start this named session with browser_exec target first.")
        env = cli._base_subprocess_env()
        session = key.removeprefix(session_key(""))
        return _revalidate(binding, cli._read_browser_cfg(), env,
                           lambda: cli._route_backend(env, session, binding.task_id, binding.local))


def vault_session(task_id, session):
    """Return only a supervisor key; prompt routing retains the caller's task id."""
    if not session:
        return task_id or "default", None
    from tools.browser_vault_tool import _ensure_supervisor

    key = session_key(session)
    try:
        if _ensure_supervisor(key) is None:
            raise TargetError("target_unreachable", "The named session's browser supervisor is unavailable.")
        return key, None
    except TargetError as exc:
        return key, exc.result()


def desktop_binding(key):
    with _LOCK:
        binding = _BINDINGS.get(key)
        return bool(binding and binding.fenced)


def _stop_binding(key, binding):
    from tools.browser_supervisor import SUPERVISOR_REGISTRY
    from tools import browser_use_cli as cli

    SUPERVISOR_REGISTRY.stop(key)
    cmd = cli._find_cli()
    if not cmd:
        raise RuntimeError("Browser harness is unavailable for release")
    env = cli._base_subprocess_env()
    env["BU_NAME"] = binding.daemon
    proc = cli._run_cli_killing_process_group([*cmd, "--reload"], "", env, 15)
    if proc.returncode:
        raise RuntimeError("Browser harness refused to stop the daemon")
    with cli._driven_daemons_lock:
        cli._driven_daemons.discard(binding.daemon)


def release_session(session, target=None):
    from tools.registry import tool_error, tool_result

    with _LOCK:
        key = session_key(session)
        binding = _BINDINGS.get(key)
        if binding is None:
            return tool_result(success=True, session=session, released=False)
        if target is not None and target != binding.target:
            return tool_error("Release target does not match the binding.", success=False, error_type="target_mismatch")
        try:
            _stop_binding(key, binding)
        except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
            raise TargetError("target_release_failed", "Could not stop the bound browser session; binding retained.") from exc
        del _BINDINGS[key]
        return tool_result(success=True, session=session, released=True)


def session_request(session, release, target):
    """Validate public names before either execution or release."""
    from tools.browser_use_cli import _SESSION_RE
    from tools.registry import tool_error

    if session and (not _SESSION_RE.match(session) or session.startswith(_RESERVED_PREFIX)):
        return tool_error("Invalid or reserved session name; use 1-64 letters, digits, dashes or underscores, excluding hermes-target-.")
    if release:
        if not session:
            return tool_error("release requires a named session.", success=False, error_type="session_required")
        try:
            return release_session(session, target)
        except TargetError as exc:
            return tool_error(str(exc), success=False, error_type=exc.error_type)
    return None
