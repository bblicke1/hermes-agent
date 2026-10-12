"""Behavior contracts for allowlisted browser routing (#243)."""

import json
import subprocess
from types import SimpleNamespace

import pytest

from tools import browser_use_cli as cli
from tools import browser_use_targets as targets
from tools import browser_vault_tool as vault
from tools import browser_supervisor
from tools.registry import registry

_REAL_PROBE = targets._probe_cdp


@pytest.fixture(autouse=True)
def routing(monkeypatch):
    targets._BINDINGS.clear()
    monkeypatch.setattr(cli, '_read_browser_cfg', lambda: {'targets': {'observe': 'http://127.0.0.1:9341', 'other': 'http://127.0.0.1:9342'}})
    monkeypatch.setattr(cli, '_base_subprocess_env', lambda: {'BU_CDP_URL': 'http://127.0.0.1:9340'})
    monkeypatch.setattr(cli, '_find_cli', lambda: ['fake-harness'])
    monkeypatch.setattr(cli, '_workspace_dir', lambda _: None)
    monkeypatch.setattr(targets, '_probe_cdp', lambda _: None)
    monkeypatch.setattr(cli, '_attach_vault_supervisor', lambda *args: None)
    calls = []
    monkeypatch.setattr(cli, '_run_cli_killing_process_group', lambda cmd, code, env, timeout: (
        calls.append(env.copy()) or subprocess.CompletedProcess(cmd, 0, 'ok', '')))
    yield calls
    targets._BINDINGS.clear()


def execute(**args):
    return json.loads(registry.get_entry('browser_exec').handler({'code': 'print(page_info())', **args}, task_id='flow'))


def test_allowlist_binding_reuse_and_mismatch(routing):
    assert execute(session='money', target='observe')['success']
    assert routing[-1]['BU_CDP_URL'] == 'http://127.0.0.1:9341'
    assert execute(session='money')['success']
    assert routing[-1]['BU_CDP_URL'] == 'http://127.0.0.1:9341'
    assert execute(session='money', target='other')['error_type'] == 'target_mismatch'
    assert len(routing) == 2
    assert execute(session='second', target='other')['success']
    assert targets.bound_url(targets.session_key('money')) == 'http://127.0.0.1:9341'


@pytest.mark.parametrize('target', ['unknown', 'http://127.0.0.1:9222', ''])
def test_unknown_targets_never_launch(target, routing):
    assert execute(session='money', target=target)['error_type'] == 'unknown_target'
    assert not routing


def test_target_requires_session(routing):
    assert execute(target='observe')['error_type'] == 'session_required'
    assert not routing


def test_unreachable_target_never_falls_back(monkeypatch, routing):
    def unreachable(_):
        raise ConnectionError('offline')
    monkeypatch.setattr(targets, '_probe_cdp', unreachable)
    assert execute(session='money', target='observe')['error_type'] == 'target_unreachable'
    assert not routing
    assert targets.bound_url(targets.session_key('money')) is None


def test_default_and_omitted_routing(routing):
    assert execute(session='normal')['success']
    assert routing[-1]['BU_CDP_URL'] == 'http://127.0.0.1:9340'
    assert execute(session='explicit', target='default')['success']
    assert routing[-1]['BU_CDP_URL'] == 'http://127.0.0.1:9340'


def test_binding_is_profile_scoped(monkeypatch, tmp_path, routing):
    assert execute(session='money', target='observe')['success']
    monkeypatch.setattr(targets, 'get_hermes_home', lambda: tmp_path / 'other-profile')
    assert execute(session='money', target='other')['success']
    assert routing[-1]['BU_CDP_URL'] == 'http://127.0.0.1:9342'
    assert routing[-1]['BU_NAME'] != routing[0]['BU_NAME']


@pytest.mark.parametrize('name', ['browser_vault_fill', 'browser_vault_enter_code', 'browser_vault_save_login'])
def test_vault_named_session_attaches_before_page_read(monkeypatch, routing, name):
    assert execute(session='money', target='observe')['success']
    attached = []
    supervisor = SimpleNamespace(focus_page=lambda *a, **kw: {'ok': False},
                                 evaluate_runtime=lambda _: {'ok': True, 'result': 'about:blank'})
    class Registry:
        def get(self, key):
            return supervisor if attached else None
        def get_or_start(self, **kwargs):
            attached.append(kwargs)
            return supervisor
    monkeypatch.setattr(browser_supervisor, 'SUPERVISOR_REGISTRY', Registry())
    from tools import browser_tool_cdp
    monkeypatch.setattr(browser_tool_cdp, '_resolve_cdp_override', lambda url: url)
    monkeypatch.setattr(browser_tool_cdp, '_get_dialog_policy_config', lambda: ('dismiss', 5))
    args = {'session': 'money', 'handle': 'vault_missing'}
    result = json.loads(registry.get_entry(name).handler(args, task_id='flow'))
    assert not result['success']  # no login/code page or saved credential in this fixture
    assert attached[0]['cdp_url'] == 'http://127.0.0.1:9341'
    assert attached[0]['task_id'] == targets.session_key('money')


@pytest.mark.parametrize('name', ['browser_vault_fill', 'browser_vault_enter_code', 'browser_vault_save_login'])
def test_unbound_vault_session_refuses_without_default_page_access(monkeypatch, name):
    def unexpected(*args):
        raise AssertionError('default page must not be touched')
    monkeypatch.setattr(vault, '_eval_js', unexpected)
    result = json.loads(registry.get_entry(name).handler({'session': 'missing', 'handle': 'vault_missing'}, task_id='flow'))
    assert result['error_type'] == 'session_unbound'


def test_cdp_probe_requires_discovery_websocket(monkeypatch):
    import requests
    monkeypatch.setattr(requests, 'get', lambda *a, **kw: SimpleNamespace(
        raise_for_status=lambda: None, json=dict))
    with pytest.raises(ValueError, match='WebSocket'):
        _REAL_PROBE('http://127.0.0.1:9341')


def test_vault_fill_uses_bound_browser_socket(monkeypatch, tmp_path, routing):
    from agent.vault_store import VaultStore
    import agent.vault_store

    store = VaultStore(base_dir=tmp_path / 'vault')
    meta = store.add_item('login', 'Synthetic', {'identifier_type': 'username', 'identifier': 'synthetic-user', 'password': 'synthetic-password'}, origin='https://example.test')
    monkeypatch.setattr(agent.vault_store, 'get_vault_store', lambda: store)
    assert execute(session='money', target='observe')['success']
    attached, expressions = [], []
    controls = [{'type': 'password', 'autocomplete': 'current-password', 'index': 0, 'formIndex': 0}]
    def evaluate(expression):
        expressions.append(expression)
        return {'ok': True, 'result': json.dumps({'filled': 1} if 'synthetic-password' in expression else controls)}
    supervisor = SimpleNamespace(focus_page=lambda *a, **kw: {'ok': True}, evaluate_runtime=evaluate)
    class Registry:
        def get(self, key):
            assert key == targets.session_key('money')
            return supervisor if attached else None
        def get_or_start(self, **kwargs):
            attached.append(kwargs)
            return supervisor
    monkeypatch.setattr(browser_supervisor, 'SUPERVISOR_REGISTRY', Registry())
    from tools import browser_tool_cdp
    monkeypatch.setattr(browser_tool_cdp, '_resolve_cdp_override', lambda url: url)
    result = json.loads(registry.get_entry('browser_vault_fill').handler(
        {'session': 'money', 'handle': meta.id}, task_id='flow'))
    assert result['success'] and result['filled_fields'] == 1
    assert attached[0]['cdp_url'] == 'http://127.0.0.1:9341'
    assert any('synthetic-password' in expression for expression in expressions)
    assert 'synthetic-password' not in json.dumps(result)


def test_default_target_keeps_desktop_lease_provenance(monkeypatch, routing):
    monkeypatch.setattr(cli, '_base_subprocess_env', lambda: {
        'BU_CDP_URL': 'http://127.0.0.1:9340', cli._BOT_DESKTOP_BROWSER_SENTINEL: '1'})
    assert execute(session='desktop', target='default')['success']
    monkeypatch.setattr(cli, '_base_subprocess_env', dict)
    assert execute(session='desktop')['success']
    assert vault._bot_desktop_browser_session(targets.session_key('desktop'))
    from tools import browser_tool_session
    fenced = []
    monkeypatch.setattr(browser_tool_session, 'run_fenced',
                        lambda session, fn: fenced.append(session) or fn())
    assert vault._fenced_page_op('flow', lambda: 'done', session_name='desktop') == 'done'
    assert fenced[-1]['features']['local']
