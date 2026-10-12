"""Delivery reachability follows TUI session transitions (#254)."""
import contextlib
import logging
import hashlib
import json
import threading
import time
import uuid
from types import SimpleNamespace

import pytest

from hermes_state import SessionDB
from tools import bot_live_delivery as delivery
from tui_gateway import compute_host_bridge, methods_session, session_compression, session_lifecycle
from tui_gateway.method_ctx import rebind


@pytest.fixture
def runtime(monkeypatch, tmp_path):
    db = SessionDB(db_path=tmp_path / "state.db")
    namespace = {"__name__": "tui_gateway.server", "__package__": "tui_gateway", "_sessions": {}, "_sessions_lock": threading.RLock(),
                 "_session_source": lambda s: s.get("source", "tui"),
                 "_session_home": lambda s: tmp_path,
                 "logger": logging.getLogger(__name__), "contextlib": contextlib,
                 "_transfer_active_session_slot": lambda *a, **k: True,
                 "_restart_slash_worker": lambda *a: None,
                 "_ok": lambda rid, result: {"result": result},
                 "_attach_todo_state": lambda payload, record: payload}
    namespace.update(
        threading=threading, time=time, _profile_home=lambda profile: tmp_path,
        _profile_build_scope=lambda home: contextlib.nullcontext(),
        _str_param=lambda params, name: str(params.get(name) or ""),
        _flag=lambda params, name: bool(params.get(name)),
        _new_runtime_ids=lambda params: (uuid.uuid4().hex, "tui"),
        _new_session_key=lambda: uuid.uuid4().hex,
        _coerce_seed_history=lambda messages: [],
        _resolve_create_cwd=lambda *a: (False, str(tmp_path), False),
        _enable_gateway_prompts=lambda: None,
        _load_show_reasoning=lambda: False, _load_tool_progress_mode=lambda: "default",
        current_transport=lambda: None, _stdio_transport=object(),
        _transport_auth_user_id=lambda transport: None,
        _register_session_cwd=lambda session: None,
        _schedule_agent_build=lambda sid: None,
        _schedule_session_cap_enforcement=lambda: None,
        _history_to_messages=lambda history, **kwargs: list(history),
        _lazy_info_route=lambda *a: {}, git_probe=SimpleNamespace(branch=lambda cwd: ""),
        _project_info_for_cwd=lambda cwd: {}, DESKTOP_BACKEND_CONTRACT={},
        _response_profile_name=lambda profile: "test",
    )
    for module, names in (
        (session_lifecycle, ("_write_tui_delivery_status", "_retire_tui_delivery_locked", "_refresh_tui_delivery_locked", "_register_open_tui_delivery", "_finalize_delivery_advertisement")),
        (session_compression, ("_sync_session_key_after_compress",)),
        (compute_host_bridge, ("_compute_host_adopt_frame_meta",)),
        (methods_session, ("_create_session", "_resume_response",)),
    ):
        for name in names:
            if hasattr(module, name):
                namespace[name] = rebind(getattr(module, name), namespace)
    server = SimpleNamespace(**namespace)
    yield tmp_path, db, server
    db.close()


def owner(home, key):
    return delivery.find_session_live_owner(home, key, resolve_tip=False)


def status(home, key):
    name = hashlib.sha256(key.encode()).hexdigest() + ".json"
    return json.loads((home / "runtime/seat_delivery_status" / name).read_text())


def open_session(home, server, key="A", sid="live-A"):
    session = {"source": "tui", "profile_home": str(home), "session_key": key,
               "history_lock": threading.Lock(), "agent": None, "created_at": 0}
    server._sessions[sid] = session
    return sid, session


def test_compression_readvertises_and_retires_previous_key(runtime):
    home, db, server = runtime
    sid, session = open_session(home, server)
    old = session["session_key"]
    # Publication before any turn, independent of lazy agent construction.
    server._register_open_tui_delivery(sid, session)
    original = owner(home, old)
    db.create_session(old, "tui")
    queued = delivery.deliver_to_live_owner(home, original, "before compression")
    db.end_session(old, "compression")
    db.create_session("child", "tui", parent_session_id=old)
    session["agent"] = SimpleNamespace(session_id="child")
    server._sync_session_key_after_compress(sid, session)
    assert session["session_key"] == "child"
    assert owner(home, "child")["live_session_id"] == original["live_session_id"]
    assert owner(home, old) is None
    assert status(home, old)["reachable"] is False
    assert status(home, "child")["reachable"] is True
    claimed = delivery.claim_pending_delivery(home, owner(home, "child"))
    assert claimed["delivery_id"] == queued["delivery_id"]
    token = owner(home, "child")["lease_id"]
    server._register_open_tui_delivery(sid, session)
    assert owner(home, "child")["lease_id"] == token


def test_new_publishes_without_building_an_agent(runtime):
    home, _, server = runtime
    sid, session = open_session(home, server)
    old = session["session_key"]
    server._register_open_tui_delivery(sid, session)
    server._finalize_delivery_advertisement(session)
    created = server._create_session("new", {})["result"]
    new_sid = created["session_id"]
    new_session = server._sessions[new_sid]
    assert new_session["agent"] is None
    assert owner(home, old) is None
    assert owner(home, new_session["session_key"])["live_session_id"] == new_sid


def test_resume_publishes_without_building_an_agent(runtime):
    home, db, server = runtime
    sid, session = open_session(home, server)
    old = session["session_key"]
    server._register_open_tui_delivery(sid, session)
    db.create_session("resume-target", "tui", model="test-model")
    server._finalize_delivery_advertisement(session)
    new_sid, new_session = open_session(home, server, "resume-target", "resumed-live")
    ctx = SimpleNamespace(rid="resume", target="resume-target", omit_messages=False,
                          messages=lambda display: list(display))
    resumed = server._resume_response(ctx, new_sid, new_session, info={})["result"]
    assert owner(home, old) is None
    assert owner(home, "resume-target")["live_session_id"] == resumed["session_id"]


def test_double_compression_only_final_key_remains(runtime):
    home, _, server = runtime
    sid, session = open_session(home, server)
    old = session["session_key"]
    server._register_open_tui_delivery(sid, session)
    for key in ("B", "C"):
        session["agent"] = SimpleNamespace(session_id=key)
        server._sync_session_key_after_compress(sid, session)
    assert owner(home, old) is None
    assert owner(home, "B") is None
    assert owner(home, "C")["live_session_id"] == sid
    assert len(list((home / "runtime/seat_delivery_owners").glob("*.json"))) == 1


@pytest.mark.parametrize("failure", ["refused", "raised"])
def test_advertise_failure_does_not_break_switch(runtime, monkeypatch, failure):
    home, db, server = runtime
    sid, session = open_session(home, server)
    old = session["session_key"]
    server._register_open_tui_delivery(sid, session)
    original = owner(home, old)
    db.create_session(old, "tui")
    queued = delivery.deliver_to_live_owner(home, original, "before failed compression")
    db.end_session(old, "compression")
    db.create_session("new-key", "tui", parent_session_id=old)
    real_advertise = delivery.advertise_session
    def fail(*args, **kwargs):
        if failure == "raised":
            raise OSError("synthetic storage failure")
        kwargs["status"].update(reachable=False, reason="synthetic refusal")
    monkeypatch.setattr(delivery, "advertise_session", fail)
    session["agent"] = SimpleNamespace(session_id="new-key")
    server._sync_session_key_after_compress(sid, session)
    assert session["session_key"] == "new-key"
    assert owner(home, old) == original
    assert session["delivery_advertisement"]["lease_id"] == original["lease_id"]
    assert status(home, "new-key")["reachable"] is False
    monkeypatch.setattr(delivery, "advertise_session", real_advertise)
    server._register_open_tui_delivery(sid, session)
    recovered = owner(home, "new-key")
    assert recovered["live_session_id"] == sid
    assert recovered["lease_id"] == original["lease_id"]
    assert delivery.claim_pending_delivery(home, recovered)["id"] == queued["id"]
    assert owner(home, old) is None


def test_isolated_compression_refreshes_without_reentering_history_lock(runtime):
    home, _, server = runtime
    sid, session = open_session(home, server)
    old = session["session_key"]
    server._register_open_tui_delivery(sid, session)
    assert type(session["history_lock"]) is type(threading.Lock())
    with session["history_lock"]:
        server._compute_host_adopt_frame_meta(session, {"sid": sid, "session_key": "isolated-child"})
    assert owner(home, old) is None
    assert owner(home, "isolated-child")["live_session_id"] == sid


def test_readvertisement_cannot_inherit_an_unowned_token(runtime):
    home, _, server = runtime
    sid, session = open_session(home, server)
    server._register_open_tui_delivery(sid, session)
    previous = session["delivery_advertisement"]
    forged = dict(previous, lease_id="unowned-token")
    new = delivery.advertise_session(home, "new", sid, previous_advertisement=forged)
    assert new["lease_id"] != forged["lease_id"]
    assert new["lease_id"] != previous["lease_id"]


def test_retirement_failure_keeps_new_owner_and_retries_cleanup(runtime, monkeypatch):
    home, db, server = runtime
    sid, session = open_session(home, server)
    server._register_open_tui_delivery(sid, session)
    previous = owner(home, "A")
    db.create_session("A", "tui")
    queued = delivery.deliver_to_live_owner(home, previous, "before compression")
    db.end_session("A", "compression")
    db.create_session("B", "tui", parent_session_id="A")
    real_revoke = delivery.revoke_advertisement
    monkeypatch.setattr(delivery, "revoke_advertisement", lambda *a: (_ for _ in ()).throw(OSError("retirement failed")))
    session["agent"] = SimpleNamespace(session_id="B")
    server._sync_session_key_after_compress(sid, session)
    current = owner(home, "B")
    assert session["delivery_advertisement"]["session_id"] == "B"
    assert status(home, "B")["reachable"] is True
    assert status(home, "B")["delivery_token"] == current["lease_id"]
    assert current["lease_id"] == previous["lease_id"]
    assert len(list((home / "runtime/seat_delivery_owners").glob("*.json"))) == 2
    # Route refresh uses the observed exact key; wake resolves compression tips.
    assert delivery.find_session_live_owner(home, "A") == current
    assert delivery.find_session_live_owner(home, "B") == current
    fresh = delivery.deliver_to_live_owner(home, current, "after compression")
    assert delivery.claim_pending_delivery(home, current)["id"] == queued["id"]
    assert delivery.claim_pending_delivery(home, current)["id"] == fresh["id"]
    monkeypatch.setattr(delivery, "revoke_advertisement", real_revoke)
    server._register_open_tui_delivery(sid, session)
    assert owner(home, "A") is None
    assert not session.get("delivery_retirements")
    assert status(home, "A")["reachable"] is False
    assert owner(home, "B") == current


@pytest.mark.parametrize("malformed", ["missing-lock", "empty-sid"])
def test_resume_registration_skips_malformed_identity(runtime, caplog, malformed):
    _, _, server = runtime
    sid, session = open_session(None, server)
    if malformed == "missing-lock":
        session.pop("history_lock")
    else:
        sid = ""
    ctx = SimpleNamespace(rid="resume", target="A", omit_messages=False, messages=list)
    with caplog.at_level(logging.WARNING):
        response = server._resume_response(ctx, sid, session, info={})
    assert response["result"]["resumed"] == "A"
    assert "missing sid/history_lock" in caplog.text
    assert "delivery_advertisement" not in session


def test_isolated_compression_empty_sid_is_fail_open(runtime, caplog):
    _, _, server = runtime
    _, session = open_session(None, server)
    with session["history_lock"], caplog.at_level(logging.WARNING):
        server._compute_host_adopt_frame_meta(session, {"session_key": "B"})
    assert session["session_key"] == "B"
    assert "delivery_advertisement" not in session
    assert "missing sid/history_lock" in caplog.text


def test_resume_paint_does_not_wait_on_busy_registry_and_history(runtime):
    _, _, server = runtime
    sid, session = open_session(None, server)
    ctx = SimpleNamespace(rid="resume", target="A", omit_messages=False, messages=list)
    done = threading.Event()
    results = []
    def resume():
        try:
            results.append(server._resume_response(ctx, sid, session, info={}))
        finally:
            done.set()
    # Another gateway operation owns these locks. A paint must not wait for
    # delivery publication: previous registration blocked on the registry here.
    with server._sessions_lock, session["history_lock"]:
        worker = threading.Thread(target=resume, daemon=True)
        worker.start()
        completed = done.wait(2)
    worker.join(timeout=2)
    assert completed, "resume paint blocked on optional delivery registration"
    assert results[0]["result"]["session_id"] == sid
    server._register_open_tui_delivery(sid, session)
    assert session["delivery_advertisement"]["live_session_id"] == sid


def test_registration_with_already_held_history_does_not_self_deadlock(runtime):
    _, _, server = runtime
    sid, session = open_session(None, server)
    done = threading.Event()
    def attach():
        with session["history_lock"]:
            server._register_open_tui_delivery(sid, session)
        done.set()
    worker = threading.Thread(target=attach, daemon=True)
    worker.start()
    assert done.wait(2), "registration re-acquired a non-reentrant history lock"
    worker.join(timeout=2)


def test_unchanged_advertisement_does_not_write(runtime, monkeypatch):
    home, _, server = runtime
    sid, session = open_session(home, server)
    server._register_open_tui_delivery(sid, session)
    original = dict(session["delivery_advertisement"])
    def unexpected_write(*args, **kwargs):
        pytest.fail("unchanged advertisement caused a durable write")
    monkeypatch.setattr(delivery, "atomic_json_write", unexpected_write)
    server._register_open_tui_delivery(sid, session)
    assert session["delivery_advertisement"] == original


def test_carry_forward_requires_current_process_birth(runtime):
    home, _, server = runtime
    sid, session = open_session(home, server)
    server._register_open_tui_delivery(sid, session)
    previous = dict(session["delivery_advertisement"])
    previous["process_start"] -= 1
    current = delivery.advertise_session(home, "B", sid, previous_advertisement=previous)
    assert current["lease_id"] != previous["lease_id"]


def test_compression_races_idle_registration_without_blocking_paint(runtime, monkeypatch):
    home, _, server = runtime
    sid, session = open_session(home, server)
    server._register_open_tui_delivery(sid, session)
    entered = threading.Event()
    release = threading.Event()
    painted = threading.Event()
    errors = []
    real_advertise = delivery.advertise_session
    def paused_advertise(profile_home, key, live_sid, **kwargs):
        if key == "B":
            entered.set()
            assert release.wait(4), "compression publication was never released"
        return real_advertise(profile_home, key, live_sid, **kwargs)
    monkeypatch.setattr(delivery, "advertise_session", paused_advertise)
    session["agent"] = SimpleNamespace(session_id="B")
    def compress():
        try:
            server._sync_session_key_after_compress(sid, session)
        except BaseException as exc:
            errors.append(exc)
    def paint():
        server._register_open_tui_delivery(sid, session)
        painted.set()
    compressor = threading.Thread(target=compress, daemon=True)
    compressor.start()
    assert entered.wait(2)
    painter = threading.Thread(target=paint, daemon=True)
    painter.start()
    try:
        completed = painted.wait(2)
    finally:
        release.set()
        compressor.join(2)
        painter.join(2)
    assert completed, "paint registration blocked on the compression history lock"
    assert not errors
    assert not compressor.is_alive() and not painter.is_alive()
    assert owner(home, "A") is None
    assert owner(home, "B")["live_session_id"] == sid
