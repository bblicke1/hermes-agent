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
_REAL_STOP = targets._stop_binding


def endpoint(url):
    return url.replace('http://', 'ws://') + '/devtools/browser/synthetic-id'



@pytest.fixture(autouse=True)
def routing(monkeypatch):
    targets._BINDINGS.clear()
    monkeypatch.setattr(cli, '_read_browser_cfg', lambda: {'targets': {'observe': 'http://127.0.0.1:9341', 'other': 'http://127.0.0.1:9342'}})
    monkeypatch.setattr(cli, '_base_subprocess_env', lambda: {'BU_CDP_URL': 'http://127.0.0.1:9340'})
    monkeypatch.setattr(cli, '_find_cli', lambda: ['fake-harness'])
    monkeypatch.setattr(cli, '_workspace_dir', lambda _: None)
    monkeypatch.setattr(targets, '_probe_cdp', endpoint)
    monkeypatch.setattr(targets, '_stop_binding', lambda *args: None)
    class Calls(list):
        attached = []
    calls = Calls()
    calls.attached = []
    monkeypatch.setattr(cli, '_attach_vault_supervisor', lambda env, key: calls.attached.append((env.copy(), key)))
    monkeypatch.setattr(cli, '_run_cli_killing_process_group', lambda cmd, code, env, timeout: (
        calls.append(env.copy()) or subprocess.CompletedProcess(cmd, 0, 'ok', '')))
    yield calls
    targets._BINDINGS.clear()


def execute(**args):
    return json.loads(registry.get_entry('browser_exec').handler({'code': 'print(page_info())', **args}, task_id='flow'))


def test_allowlist_binding_reuse_and_mismatch(routing):
    assert execute(session='money', target='observe')['success']
    assert routing[-1]['BU_CDP_WS'] == endpoint('http://127.0.0.1:9341')
    assert execute(session='money')['success']
    assert routing[-1]['BU_CDP_WS'] == endpoint('http://127.0.0.1:9341')
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
    assert routing[-1]['BU_CDP_WS'] == endpoint('http://127.0.0.1:9340')


def test_binding_is_profile_scoped(monkeypatch, tmp_path, routing):
    assert execute(session='money', target='observe')['success']
    monkeypatch.setattr(targets, 'get_hermes_home', lambda: tmp_path / 'other-profile')
    assert execute(session='money', target='other')['success']
    assert routing[-1]['BU_CDP_WS'] == endpoint('http://127.0.0.1:9342')
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
    assert attached[0]['cdp_url'] == endpoint('http://127.0.0.1:9341')
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
    assert attached[0]['cdp_url'] == endpoint('http://127.0.0.1:9341')
    assert any('synthetic-password' in expression for expression in expressions)
    assert 'synthetic-password' not in json.dumps(result)


def test_fenced_target_keeps_desktop_lease_provenance(monkeypatch, routing):
    monkeypatch.setattr(cli, '_read_browser_cfg', lambda: {'targets': {
        'desktop': {'url': 'http://127.0.0.1:9341', 'fenced': True}}})
    from tools import browser_tool_session
    fenced = []
    monkeypatch.setattr(browser_tool_session, 'run_fenced',
                        lambda session, fn: fenced.append(session) or fn())
    assert execute(session='desktop', target='desktop')['success']
    assert execute(session='desktop')['success']
    assert vault._bot_desktop_browser_session(targets.session_key('desktop'))
    assert vault._fenced_page_op('flow', lambda: 'done', session_name='desktop') == 'done'
    assert len(fenced) == 3
    assert all(session['features']['local'] for session in fenced)


def test_reserved_daemon_namespace_cannot_be_adopted(routing):
    assert execute(session='money', target='observe')['success']
    daemon = routing[-1]['BU_NAME']
    result = execute(session=daemon)
    assert 'reserved' in result['error']
    assert len(routing) == 1


@pytest.mark.parametrize('config', [{}, {'targets': {'observe': 'http://127.0.0.1:9999'}},
                                   {'targets': {'observe': {'url': 'http://127.0.0.1:9341', 'fenced': True}}}])
def test_changed_allowlist_revokes_exec_and_vault(monkeypatch, routing, config):
    assert execute(session='money', target='observe')['success']
    monkeypatch.setattr(cli, '_read_browser_cfg', lambda: config)
    assert execute(session='money')['error_type'] == 'target_revoked'
    result = json.loads(registry.get_entry('browser_vault_fill').handler(
        {'session': 'money', 'handle': 'vault_missing'}, task_id='flow'))
    assert result['error_type'] == 'target_revoked'
    assert len(routing) == 1


def test_identity_change_requires_release_and_rebind(monkeypatch, routing):
    assert execute(session='money', target='observe')['success']
    old_daemon = routing[-1]['BU_NAME']
    monkeypatch.setattr(targets, '_probe_cdp', lambda url: endpoint(url).replace('synthetic-id', 'new-id'))
    assert execute(session='money')['error_type'] == 'target_identity_changed'
    result = json.loads(registry.get_entry('browser_vault_fill').handler(
        {'session': 'money', 'handle': 'vault_missing'}, task_id='flow'))
    assert result['error_type'] == 'target_identity_changed'
    assert execute(session='money', release=True)['released']
    assert execute(session='money', target='observe')['success']
    assert routing[-1]['BU_NAME'] != old_daemon
    assert routing[-1]['BU_CDP_WS'].endswith('/new-id')


def test_one_live_binding_per_endpoint_across_profiles(monkeypatch, tmp_path, routing):
    assert execute(session='money', target='observe')['success']
    monkeypatch.setattr(targets, 'get_hermes_home', lambda: tmp_path / 'other-profile')
    assert execute(session='other', target='observe')['error_type'] == 'target_busy'


def test_release_stops_only_bound_resources_and_frees_endpoint(monkeypatch, routing):
    assert execute(session='money', target='observe')['success']
    stopped = []
    monkeypatch.setattr(targets, '_stop_binding', lambda key, binding: stopped.append((key, binding)))
    result = json.loads(registry.get_entry('browser_exec').handler({'session': 'money', 'release': True}, task_id='flow'))
    assert result['released']
    assert stopped[0][0] == targets.session_key('money')
    assert stopped[0][1].daemon == routing[0]['BU_NAME']
    assert targets.bound_url(targets.session_key('money')) is None
    assert execute(session='other', target='observe')['success']


def test_supervisor_attach_key_tracks_target_or_real_task(routing):
    assert execute(session='ordinary')['success']
    assert routing.attached[-1][1] == 'flow'
    assert execute(session='money', target='observe')['success']
    assert routing.attached[-1][1] == targets.session_key('money')
    assert routing.attached[-1][0]['BU_CDP_WS'] == endpoint('http://127.0.0.1:9341')


def test_default_backend_errors_keep_cause_and_no_cdp_is_distinct(monkeypatch):
    monkeypatch.setattr(cli, '_base_subprocess_env', dict)
    monkeypatch.setattr(cli, '_route_backend', lambda *a, **kw: 'consent is disabled')
    result = execute(session='money', target='default')
    assert result['error_type'] == 'target_route_failed'
    assert result['error'] == 'consent is disabled'
    monkeypatch.setattr(cli, '_route_backend', lambda *a, **kw: None)
    assert execute(session='money', target='default')['error_type'] == 'target_unsupported_backend'


def test_default_decision_and_binding_are_serialized(monkeypatch, tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    monkeypatch.setattr(targets, 'get_hermes_home', lambda: tmp_path)
    entered, bind_attempted, default_finished = Event(), Event(), Event()
    def default_route():
        entered.set()
        assert bind_attempted.wait(3)
        default_finished.set()
    def probe(url):
        assert default_finished.is_set()
        return endpoint(url)
    monkeypatch.setattr(targets, '_probe_cdp', probe)
    def bind():
        assert entered.wait(3)
        bind_attempted.set()
        return targets.prepare_route({}, 'same', 'observe', cli._read_browser_cfg(), lambda: None)
    with ThreadPoolExecutor(max_workers=2) as pool:
        default = pool.submit(targets.prepare_route, {}, 'same', None, {}, default_route)
        targeted = pool.submit(bind)
        assert default.result(timeout=3) == (False, None)
        assert targeted.result(timeout=3) == (True, None)


@pytest.fixture
def named_vault(monkeypatch, tmp_path, routing):
    from agent.vault_store import VaultStore
    import agent.vault_store
    store = VaultStore(base_dir=tmp_path / 'vault')
    monkeypatch.setattr(agent.vault_store, 'get_vault_store', lambda: store)
    assert execute(session='money', target='observe')['success']
    expressions = []
    supervisor = SimpleNamespace(
        focus_page=lambda *a, **kw: {'ok': False},
        evaluate_runtime=lambda expression: expressions.append(expression) or {'ok': True, 'result': 'https://wrong.test/login'})
    class Registry:
        def get(self, key):
            return supervisor
        def get_or_start(self, **kwargs):
            assert kwargs['task_id'] == targets.session_key('money')
            assert kwargs['cdp_url'] == endpoint('http://127.0.0.1:9341')
            return supervisor
    monkeypatch.setattr(browser_supervisor, 'SUPERVISOR_REGISTRY', Registry())
    return store, supervisor, expressions


def test_bound_wrong_origin_refuses_before_secret_resolution(named_vault):
    store, _, expressions = named_vault
    meta = store.add_item('login', 'Synthetic', {'identifier_type': 'username', 'identifier': 'synthetic-user',
                                              'password': 'wrong-origin-canary'}, origin='https://example.test')
    result = json.loads(registry.get_entry('browser_vault_fill').handler(
        {'session': 'money', 'handle': meta.id}, task_id='real-conversation'))
    assert result['error_type'] == 'origin_mismatch'
    assert all('wrong-origin-canary' not in expression for expression in expressions)
    assert 'wrong-origin-canary' not in json.dumps(result)


@pytest.mark.parametrize('decision', ['accept', 'decline', 'unavailable'])
def test_bound_payment_requires_real_approval_surface(monkeypatch, named_vault, decision):
    from tools import approval_context, approval_prompt
    store, supervisor, expressions = named_vault
    card = {'card_number': '4111111111111111', 'name_on_card': 'Synthetic', 'exp_month': '07', 'exp_year': '2029', 'cvc': '321'}
    meta = store.add_item('payment', 'Synthetic card', card, origin='https://shop.test')
    supervisor.focus_page = lambda *a, **kw: {'ok': True}
    controls = [{'label': 'Card number', 'autocomplete': 'cc-number', 'index': 0, 'type': 'text'}]
    supervisor.evaluate_runtime = lambda expression: expressions.append(expression) or {
        'ok': True, 'result': json.dumps({'filled': 1} if card['card_number'] in expression else controls)}
    approvals = []
    def approve(*args, **kwargs):
        approvals.append(approval_context._approval_session_id.get())
        return decision
    monkeypatch.setattr(approval_prompt, 'request_elicitation_consent', approve)
    tokens = approval_context.set_current_observability_context(session_id='real-conversation')
    try:
        result = json.loads(registry.get_entry('browser_vault_fill').handler(
            {'session': 'money', 'handle': meta.id}, task_id='real-conversation'))
    finally:
        approval_context.reset_current_observability_context(tokens)
    assert approvals == ['real-conversation']
    if decision == 'accept':
        assert result['success']
        assert any(card['card_number'] in expression for expression in expressions)
    else:
        assert result['error_type'] == 'payment_declined'
        assert not expressions
    assert card['card_number'] not in json.dumps(result)


def test_dead_bound_supervisor_never_reads_default_browser(monkeypatch, named_vault):
    _, supervisor, _ = named_vault
    def dead(_):
        raise RuntimeError('supervisor disconnected')
    supervisor.evaluate_runtime = dead
    from tools import browser_tool_session
    fallback = []
    monkeypatch.setattr(browser_tool_session, '_run_browser_command', lambda *a, **kw: fallback.append(a))
    key, error = targets.vault_session('real-conversation', 'money')
    assert error is None
    result = vault._eval_js(key, 'window.location.href')
    assert result['success'] is False and result['error_type'] == 'target_unreachable'
    assert not fallback


def test_save_login_retains_real_task_and_named_browser(monkeypatch, named_vault):
    from agent.vault_backends import unlock
    _, supervisor, _ = named_vault
    supervisor.evaluate_runtime = lambda _: {'ok': True, 'result': 'https://example.test/login'}
    monkeypatch.setattr(unlock, 'can_prompt_here', lambda: True)
    monkeypatch.setattr(unlock, 'get_save_login_prompt_callback', lambda: lambda *a: {
        'identifier': 'synthetic-user', 'password': 'synthetic-password'})
    forwarded = []
    monkeypatch.setattr(vault, 'browser_vault_fill', lambda handle, **kwargs: forwarded.append(kwargs) or json.dumps({'success': True}))
    result = json.loads(registry.get_entry('browser_vault_save_login').handler(
        {'session': 'money'}, task_id='real-conversation'))
    assert result['success']
    assert forwarded == [{'task_id': 'real-conversation', 'session': 'money'}]


def test_release_resource_cleanup_uses_exact_supervisor_and_daemon(monkeypatch, routing):
    assert execute(session='money', target='observe')['success']
    key = targets.session_key('money')
    binding = targets._BINDINGS[key]
    stopped = []
    monkeypatch.setattr(browser_supervisor, 'SUPERVISOR_REGISTRY', SimpleNamespace(stop=stopped.append))
    _REAL_STOP(key, binding)
    assert stopped == [key]
    assert routing[-1]['BU_NAME'] == binding.daemon
    assert binding.daemon not in cli._driven_daemons


def test_bound_code_prompt_uses_active_conversation(monkeypatch, named_vault):
    from agent.vault_backends import unlock
    from tools import approval_context
    _, supervisor, expressions = named_vault
    controls = [{'type': 'text', 'autocomplete': 'one-time-code', 'index': 0, 'formIndex': 0}]
    def evaluate(expression):
        expressions.append(expression)
        if 'window.location.href' in expression:
            return {'ok': True, 'result': 'https://example.test/login'}
        return {'ok': True, 'result': json.dumps({'filled': 1} if '123456' in expression else controls)}
    supervisor.evaluate_runtime = evaluate
    prompts = []
    def prompt(site, hint):
        prompts.append((site, approval_context._approval_session_id.get()))
        return '123456'
    monkeypatch.setattr(unlock, 'can_prompt_here', lambda: True)
    monkeypatch.setattr(unlock, 'get_code_prompt_callback', lambda: prompt)
    tokens = approval_context.set_current_observability_context(session_id='real-conversation')
    try:
        result = json.loads(registry.get_entry('browser_vault_enter_code').handler(
            {'session': 'money'}, task_id='real-conversation'))
    finally:
        approval_context.reset_current_observability_context(tokens)
    assert result['success']
    assert prompts == [('example.test', 'real-conversation')]
    assert '123456' not in json.dumps(result)


def test_unfenced_observe_does_not_inherit_tasks_desktop_fence(monkeypatch, routing):
    from tools import browser_tool, browser_tool_session
    assert execute(session='money', target='observe')['success']
    monkeypatch.setattr(browser_tool, '_last_session_key', lambda key: key)
    monkeypatch.setattr(browser_tool, '_active_sessions', {'flow': {'features': {'local': True}}})
    fenced = []
    monkeypatch.setattr(browser_tool_session, 'run_fenced', lambda session, fn: fenced.append(session) or fn())
    assert vault._fenced_page_op('flow', lambda: 'done', session_name='money') == 'done'
    assert not fenced[-1]['features']['local']
    assert not vault._bot_desktop_browser_session(targets.session_key('money'))


def test_released_supervisor_key_cannot_fall_back(monkeypatch, routing):
    assert execute(session='money', target='observe')['success']
    key = targets.session_key('money')
    assert execute(session='money', release=True)['released']
    from tools import browser_tool_session
    fallbacks = []
    monkeypatch.setattr(browser_tool_session, '_run_browser_command', lambda *a, **kw: fallbacks.append(a))
    assert vault._eval_js(key, 'window.location.href')['error_type'] == 'session_unbound'
    assert vault._eval_js_secret(key, 'synthetic expression')['error_type'] == 'session_unbound'
    assert not fallbacks
