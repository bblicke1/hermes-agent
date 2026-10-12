"""Real gateway handler/lock wiring against a temporary profile for #254."""
import json
import os
from pathlib import Path
import subprocess
import sys

from hermes_state import SessionDB

HANDLERS = '''
import json
import os
from pathlib import Path
import threading
from unittest.mock import patch
from tools import bot_live_delivery as delivery
from tui_gateway import server
from tui_gateway.transport import bind_transport, reset_transport

server._schedule_agent_build = lambda *a: None
server._schedule_session_cap_enforcement = lambda: None
server._maybe_schedule_auto_continue = lambda *a: None

def rpc(method, **params):
    token = bind_transport(server._stdio_transport)
    try:
        response = server.handle_request(dict(id="proof", method=method, params=params))
    finally:
        reset_transport(token)
    assert "error" not in response, response
    return response["result"]

def threaded(fn):
    done = threading.Event()
    errors = []
    def run():
        try:
            fn()
        except BaseException as exc:
            errors.append(exc)
        finally:
            done.set()
    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    assert done.wait(4), "production attach/resume deadlocked"
    worker.join(4)
    assert not worker.is_alive()
    if errors:
        raise errors[0]

assert server._get_db().get_session("seed")
created = rpc("session.create")
sid = created["session_id"]
session = server._sessions[sid]
key = session["session_key"]
home = server._session_home(session)
assert type(session["history_lock"]) is type(threading.Lock())
attach_refresh = server._refresh_tui_delivery_locked
lock_samples = []
def observed_refresh(live_sid, record, **kwargs):
    lock_samples.append((record["history_lock"].locked(), server._sessions_lock._is_owned(),
                         server._session_resume_lock.locked()))
    return attach_refresh(live_sid, record, **kwargs)
with patch.object(server, "_refresh_tui_delivery_locked", observed_refresh):
    # Unpersisted resume takes resume_lock then history_lock at transport attach.
    threaded(lambda: rpc("session.resume", session_id=key))
    # Persisted warm reuse takes the same locks through _live_session_payload.
    db = server._get_db()
    db.create_session(key, "tui", model="test-model")
    threaded(lambda: rpc("session.resume", session_id=key, omit_messages=True))
    threaded(lambda: rpc("session.activate", session_id=sid, omit_messages=True))
assert sum(sample == (True, False, True) for sample in lock_samples) >= 3, lock_samples

# The UI awaits session.close before session.create on /new. Drive those real
# RPC handlers and check retirement is committed before replacement publication.
assert rpc("session.close", session_id=sid)["closed"]
assert delivery.find_session_live_owner(home, key, resolve_tip=False) is None
real_advertise = delivery.advertise_session
def ordered_advertise(*args, **kwargs):
    assert delivery.find_session_live_owner(home, key, resolve_tip=False) is None
    return real_advertise(*args, **kwargs)
with patch.object(delivery, "advertise_session", ordered_advertise):
    replacement = rpc("session.create")
new_sid = replacement["session_id"]
current = server._sessions[new_sid]
assert current["session_key"] != key
assert delivery.find_session_live_owner(home, current["session_key"], resolve_tip=False)

# Exercise the actual idle tick, including failed reachability and absent ad.
delivery.revoke_advertisement(home, current.pop("delivery_advertisement"))
current["delivery_reachability"] = {"reachable": False}
def unavailable(*args, **kwargs):
    kwargs["status"].update(reachable=False, reason="synthetic publication refusal")
with patch.object(delivery, "advertise_session", unavailable):
    assert server._poll_bot_live_delivery_once(new_sid, current) is False
assert "delivery_advertisement" not in current
assert current["delivery_reachability"]["reachable"] is False
assert server._poll_bot_live_delivery_once(new_sid, current) is False
assert current["delivery_advertisement"]["session_id"] == current["session_key"]
assert current["delivery_reachability"]["reachable"] is True
rpc("session.close", session_id=new_sid)
(Path(os.environ["HERMES_HOME"]) / "handler-proof.json").write_text(
    json.dumps({"warm_resume_locks": lock_samples, "new_handler_ordering": True, "idle_tick_retry": True}), encoding="utf-8")
'''


def test_real_resume_attach_new_handlers_and_idle_tick(tmp_path):
    repo = Path(__file__).resolve().parents[2]
    home = tmp_path / 'profile'
    home.mkdir()
    (home / 'config.yaml').write_text(json.dumps({
        'model': {'default': 'test-model', 'provider': 'custom'},
        'plugins': {'enabled': []}, 'mcp_servers': {},
        'memory': {'memory_enabled': False, 'user_profile_enabled': False},
    }), encoding='utf-8')
    db = SessionDB(db_path=home / 'state.db')
    db.create_session('seed', 'tui', model='test-model')
    db.close()
    env = {k: v for k, v in os.environ.items() if k in {'PATH', 'LANG', 'USER', 'SHELL'}}
    env.update(HOME=str(tmp_path), HERMES_HOME=str(home), HERMES_RUNTIME_DIR=str(tmp_path / 'tools'),
               HERMES_DISABLE_LAZY_INSTALLS='1', PYTHONPATH=str(repo))
    result = subprocess.run([sys.executable, '-c', HANDLERS], env=env, cwd=tmp_path,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    evidence = json.loads((home / 'handler-proof.json').read_text(encoding='utf-8'))
    assert evidence['new_handler_ordering'] and evidence['idle_tick_retry']
