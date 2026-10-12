"""Owned throwaway Herdr TUI proof for #254; no installs or live seat writes."""
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import time

REPO = Path(__file__).resolve().parents[2]
PROOF = Path(__file__).resolve().parent
PYTHON = Path('/home/brad/.hermes/tools/python-3.14.7+20260901-linux-x64/bin/python3')
SITES = Path('/home/brad/.hermes/installs/51181f1e9b6ad302/environments/b1b23c0085f246d39ba483c1c50d7e26/venv/lib/python3.14/site-packages')
SCRIPTS = Path('/home/brad/.hermes/scripts')
NAME = 'seat-test-254'


def command(*args):
    return subprocess.check_output(args, text=True, timeout=30)


def save(name, record):
    (PROOF / name).write_text(json.dumps(record, indent=2) + '\n')


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def wait(fn, seconds=120):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        result = fn()
        if result:
            return result
        time.sleep(.25)
    raise RuntimeError('proof deadline expired')


def main():
    assert os.environ.get('HERDR_ENV') == '1', 'requires managed Herdr pane'
    root = Path(tempfile.mkdtemp(prefix='hermes-readvertise-254-'))
    home = root / 'profiles' / NAME
    home.mkdir(parents=True, mode=0o700)
    os.environ['HERMES_HOME'] = str(root)
    os.environ['HERMES_RUNTIME_DIR'] = str(root / 'tools')
    os.environ['HERMES_DISABLE_LAZY_INSTALLS'] = '1'
    sys.path[:0] = [str(REPO), str(SITES), str(SCRIPTS)]
    from tools.bot_live_delivery import _advertisement_path, read_delivery_result
    from utils import atomic_json_write
    from agent_mail import ProducerMail
    # This dependency is an untracked, already-deployed ingress module. Its
    # mailbox imports resolve to the worktree module loaded above.
    seat_delivery = load_module('tools.seat_delivery', Path('/home/brad/.hermes/hermes-agent/tools/seat_delivery.py'))
    before_path = list(sys.path)
    refresh = load_module('proof_route_refresh', SCRIPTS / 'seat_routes_refresh.py')
    wake = load_module('proof_seat_wake', SCRIPTS / 'seat_wake.py')
    sys.path[:] = before_path
    # Provision a test-only identity in this proof process. No registry file is
    # edited and all discovery/lease validation remains real.
    identity = {NAME: {'profile': NAME, 'local_only': True}}
    refresh.SEATS = wake.SEATS = (NAME,)
    refresh.load = wake.load = lambda: identity
    refresh.PROFILES = wake.PROFILES = root / 'profiles'
    assert seat_delivery.find_session_live_owner.__module__ == 'tools.bot_live_delivery'
    cfg = dict(
        model={'default': 'gb10-balanced', 'provider': 'gb10-gateway'},
        providers={'gb10-gateway': {'api': 'http://192.168.10.62:8120/v1', 'api_key': 'EMPTY',
                                  'default_model': 'gb10-balanced', 'transport': 'chat_completions'}},
        fallback_providers=[], mcp_servers={}, toolsets=['terminal'], platform_toolsets={'cli': ['terminal']},
        plugins={'enabled': []}, memory={'memory_enabled': False, 'user_profile_enabled': False, 'provider': ''},
        terminal={'backend': 'local', 'cwd': str(root)}, compression={'enabled': False},
        agent={'reasoning_effort': 'none', 'max_turns': 8},
        telemetry={'shared_metrics': {'enabled': False, 'send': False, 'offer_version': 2}},
        onboarding={'seen': {'profile_build_offered': True}}, secrets={},
    )
    (home / 'config.yaml').write_text(json.dumps(cfg))
    (home / '.env').write_text('')
    (home / '.no-bundled-skills').touch()
    (home / 'SOUL.md').write_text(
        'You are seat-test-254, an isolated synthetic proof agent. '
        'When you receive a mail pointer, use terminal to cat ONLY that mail file, '
        'run the exact acknowledgement command supplied, then follow its payload. '
        'Reply with ONLY the exact requested token. No greeting, introduction, help text, punctuation, or explanation. Do not read other files or contact anyone.\n')
    active_file = root / 'active-session.json'
    launcher = root / 'launch.sh'
    env = {k: v for k, v in os.environ.items() if k in {'PATH', 'LANG', 'USER', 'SHELL', 'TERM'} or k.startswith('HERDR_')}
    env.update(HOME=str(root / 'os-home'), HERMES_HOME=str(home), HERMES_RUNTIME_DIR=str(root / 'tools'),
               HERMES_PYTHON=str(PYTHON), PYTHONPATH=str(REPO) + ':' + str(SITES),
               HERMES_PYTHON_SRC_ROOT=str(REPO), HERMES_DISABLE_LAZY_INSTALLS='1',
               HERMES_TUI_ACTIVE_SESSION_FILE=str(active_file), HERMES_CWD=str(root),
               HERMES_TUI_CWD=str(root), NODE_ENV='production',
               HERMES_TUI_DIR='/home/brad/.hermes/hermes-agent/ui-tui')
    (root / 'os-home').mkdir()
    # The existing compiled renderer starts a real stdio backend from REPO.
    # Preserve the new pane's injected Herdr context rather than this caller's.
    env = {k: v for k, v in env.items() if not k.startswith('HERDR_')}
    driver = root / 'hermes'
    driver.write_text('import os,subprocess,sys\n' +
                      'sys.exit(subprocess.call(["node", "/home/brad/.hermes/hermes-agent/ui-tui/dist/entry.js"], env=os.environ))\n')
    launcher.write_text('#!/bin/sh\n' + ''.join('export ' + k + '=' + shlex.quote(v) + '\n' for k, v in env.items()) +
                        'exec ' + shlex.join([str(PYTHON), str(driver), '--tui']) + '\n')
    launcher.chmod(0o700)
    tabs = []
    owner_pids = set()
    evidence = {'profile': NAME, 'scratch_root': str(root), 'interpreter': str(PYTHON),
                'backend_source': str(REPO), 'dependency_sites': str(SITES),
                'renderer': '/home/brad/.hermes/hermes-agent/ui-tui/dist/entry.js'}
    try:
        workspaces = json.loads(command('herdr', 'workspace', 'list'))['result']['workspaces']
        workspace = next(row['workspace_id'] for row in workspaces if row['label'] == 'Workers')
        created = json.loads(command('herdr', 'tab', 'create', '--workspace', workspace,
                                     '--cwd', str(root), '--label', NAME, '--no-focus'))['result']
        tab = created['tab']['tab_id']; pane = created['root_pane']['pane_id']
        tabs.append(tab)
        evidence.update(tab=tab, pane=pane)
        save('live-resources.json', evidence)
        command('herdr', 'pane', 'run', pane, str(launcher))
        def active_key():
            try:
                return json.loads(active_file.read_text()).get('session_id')
            except (OSError, ValueError):
                return None
        def first_advertisement():
            paths = list((home / 'runtime/seat_delivery_owners').glob('*.json'))
            if len(paths) == 1:
                record = json.loads(paths[0].read_text())
                return refresh.owner(home, record['session_id'])
        first = wait(first_advertisement)
        owner_pids.add(first['pid'])
        raw_env = Path('/proc/' + str(first['pid']) + '/environ').read_bytes().split(b'\0')
        backend_env = dict(row.decode().split('=', 1) for row in raw_env if b'=' in row)
        assert backend_env['HERMES_PYTHON_SRC_ROOT'] == str(REPO)
        evidence['backend_runtime'] = {'exe': str(Path('/proc/' + str(first['pid']) + '/exe').resolve()),
                                       'argv': Path('/proc/' + str(first['pid']) + '/cmdline').read_bytes().decode().split('\0'),
                                       'source': backend_env['HERMES_PYTHON_SRC_ROOT'],
                                       'profile_home': backend_env['HERMES_HOME']}
        assert evidence['backend_runtime']['exe'] == str(PYTHON.resolve())
        active_file = Path(backend_env['HERMES_TUI_ACTIVE_SESSION_FILE'])
        assert active_file.is_relative_to(root), active_file
        old = wait(active_key)
        assert first['session_id'] == old
        def recognized():
            result = subprocess.run(['herdr', 'agent', 'get', pane], capture_output=True, text=True)
            if result.returncode == 0:
                agent = json.loads(result.stdout)['result']['agent']
                return agent if agent.get('agent') == 'hermes' else None
        wait(recognized, 20)
        command('herdr', 'agent', 'rename', pane, NAME)
        def publish_observed(key):
            # Publish only the durable ID read from the renderer's active file.
            assert active_key() == key
            command('herdr', 'pane', 'report-agent-session', pane, '--source', 'herdr:hermes',
                    '--agent', 'hermes', '--seq', str(time.time_ns()), '--agent-session-id', key,
                    '--session-start-source', 'startup' if key == old else 'new')
            def observed():
                result = subprocess.run(['herdr', 'agent', 'get', pane], capture_output=True, text=True)
                if result.returncode:
                    return None
                agent = json.loads(result.stdout)['result']['agent']
                return agent if (agent.get('agent_session') or {}).get('value') == key else None
            agent = wait(observed, 15)
            # A new Herdr session generation may clear the presentation name.
            # Retain this test identity on our owned pane before route publication.
            if agent.get('name') != NAME:
                command('herdr', 'agent', 'rename', pane, NAME)
            return refresh.current_agent(NAME)
        evidence['first_herdr'] = publish_observed(old)
        evidence['first_route'] = refresh.refresh(NAME, profiles=root / 'profiles')
        mail = ProducerMail(root=root / 'run-state/mail', routes={})
        def deliver(token, phase):
            stored = mail.store(NAME, 'proof', 'proof-254', {'instruction': 'After acknowledging this mail, your ENTIRE response must be the single token ' + token + '. Output no greeting, introduction, /help text, extra lines, or explanation.'})
            result = wake.wake_seat_mail(stored, NAME, home / 'runtime/seat-routes.json')
            evidence[phase + '_admission'] = result
            def receipt():
                record = read_delivery_result(home, result['delivery_id'])
                if record and record['status'] not in ('queued', 'claimed'):
                    return record
            record = wait(receipt, 180)
            evidence[phase + '_receipt'] = record
            assert record['status'] == 'settled', record
            assert record['reply'].strip() == token, record['reply']
            sidecar = Path(stored + '.read.json')
            evidence[phase + '_read_ack'] = json.loads(sidecar.read_text(encoding='utf-8'))
            assert evidence[phase + '_read_ack']['reader'] == NAME
            capture = command('herdr', 'pane', 'read', pane, '--source', 'recent-unwrapped', '--lines', '100')
            (PROOF / (phase + '-tui.txt')).write_text(capture)
            save('live-results.json', evidence)
        deliver('G254-FIRST-ACK', 'first')
        command('herdr', 'agent', 'prompt', NAME, '/new')
        def confirmation():
            text = command('herdr', 'pane', 'read', pane, '--source', 'recent-unwrapped', '--lines', '35')
            return text if 'Start a new session?' in text else None
        evidence['new_confirmation'] = wait(confirmation, 15)
        # The work order explicitly authorizes /new in this throwaway profile.
        command('herdr', 'agent', 'send-keys', NAME, 'y')
        new = wait(lambda: (value if (value := active_key()) and value != old else None))
        second = wait(lambda: refresh.owner(home, new) if _advertisement_path(home, new).exists() else None)
        owner_pids.add(second['pid'])
        assert second['pid'] == first['pid'], 'backend must not relaunch'
        assert not _advertisement_path(home, old).exists(), 'previous lease must be retired'
        assert len(list((home / 'runtime/seat_delivery_owners').glob('*.json'))) == 1
        evidence.update(first_owner=first, second_owner=second, old_session_id=old, new_session_id=new,
                        same_backend_pid=True, previous_advertisement_retired=True)
        evidence['second_herdr'] = publish_observed(new)
        evidence['second_route'] = refresh.refresh(NAME, profiles=root / 'profiles')
        deliver('G254-SECOND-ACK', 'second')
        evidence['passed'] = True
    except Exception as exc:
        evidence['error'] = repr(exc)
        if tabs:
            try:
                (PROOF / 'failure-tui.txt').write_text(command('herdr', 'pane', 'read', evidence['pane'], '--source', 'recent-unwrapped', '--lines', '100'))
            except Exception:
                pass
        raise
    finally:
        for tab in tabs:
            command('herdr', 'tab', 'close', tab)
        for pid in owner_pids:
            wait(lambda: not Path('/proc/' + str(pid)).exists(), 20)
        shutil.rmtree(root)
        evidence['cleanup'] = {'tabs_closed': tabs, 'profile_removed': not home.exists(),
                               'scratch_root_removed': not root.exists(),
                               'owner_pids_exited': all(not Path('/proc/' + str(pid)).exists() for pid in owner_pids)}
        save('live-results.json', evidence)
        (PROOF / 'live-proof.txt').write_text(json.dumps(evidence, indent=2) + '\n')


if __name__ == '__main__':
    main()
