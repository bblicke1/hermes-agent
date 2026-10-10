"""Synthetic live acceptance helpers. Run with the deployed Python/bootstrap."""
import json
import os
import re
import signal
import socket
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen

ROOT = Path('/home/brad/worktrees/hermes-scripts-a2a-spike-195/.g3-runtime')
PROOF = Path(__file__).parent
LIVE = Path('/home/brad/.hermes/hermes-agent')
BIN = LIVE / '.hermes/bin/hermes'
HOMES = {'sender': ROOT, 'receiver': ROOT / 'profiles/g3-receiver'}
PORTS = {'sender': 19198, 'receiver': 19199}
SIDS = {'sender': 'g3-sender-198', 'receiver': 'g3-receiver-198'}


def save(name, value):
    (PROOF / name).write_text(json.dumps(value, indent=2, ensure_ascii=True) + '\n')


def env(home):
    result = {k: v for k, v in os.environ.items() if k in {'HOME', 'PATH', 'LANG', 'TERM', 'USER', 'SHELL'} or k.startswith('HERDR_')}
    result.update(HERMES_HOME=str(home), HERMES_DISABLE_LAZY_INSTALLS='1')
    return result


def rpc(who, method, params):
    from websockets.sync.client import connect
    port = PORTS[who]
    html = urlopen(f'http://127.0.0.1:{port}/', timeout=5).read().decode()
    token = re.search(r'__HERMES_SESSION_TOKEN__="([^" ]+)"', html).group(1)
    with connect(f'ws://127.0.0.1:{port}/api/ws?token=' + quote(token), open_timeout=5) as ws:
        ws.send(json.dumps({'jsonrpc': '2.0', 'id': 'g3-acceptance', 'method': method, 'params': params}))
        while True:
            response = json.loads(ws.recv(timeout=180))
            if response.get('id') == 'g3-acceptance':
                return response


def setup():
    if (PROOF / 'synthetic-config.json').exists():
        raise RuntimeError('Refusing to overwrite an existing acceptance home')
    from hermes_state import SessionDB
    config = '''model:
  default: gb10-balanced
  provider: gb10-gateway
providers:
  gb10-gateway:
    api: http://192.168.10.62:8120/v1
    api_key: EMPTY
    default_model: gb10-balanced
    transport: chat_completions
fallback_providers: []
toolsets: [terminal, file]
platform_toolsets:
  cli: [terminal, file]
memory:
  memory_enabled: false
  user_profile_enabled: false
plugins:
  enabled: []
mcp_servers: {}
agent:
  reasoning_effort: none
  max_turns: 8
terminal:
  backend: local
compression:
  enabled: true
  threshold: 0.9
  protect_first_n: 0
  protect_last_n: 2
auxiliary:
  compression:
    provider: gb10-gateway
    model: gb10-balanced
telemetry:
  shared_metrics:
    enabled: false
    send: false
    offer_version: 2
onboarding:
  seen:
    profile_build_offered: true
'''
    for who, home in HOMES.items():
        home.mkdir(parents=True, mode=0o700, exist_ok=True)
        (home / 'config.yaml').write_text(config)
        (home / '.env').write_text('')
        (home / '.no-bundled-skills').touch()
        (home / 'profile.yaml').write_text(('name: g3-receiver\n' if who == 'receiver' else '') + 'ui_meta:\n  hermes-bots:\n    display_name: G3 ' + who + '\n')
        (home / 'SOUL.md').write_text('You are a synthetic acceptance agent. All messages and data are synthetic. Only message the two bots on this isolated installation, @hermes and @g3-receiver, when explicitly instructed. Never message anyone else. Follow requested exact replies. Do not read any files outside this synthetic home.\n')
        db = SessionDB(db_path=home / 'state.db')
        db.create_session(SIDS[who], 'tui', model='gb10-balanced')
        db.set_session_title(SIDS[who], 'Bot Chat')
        db.close()
    save('synthetic-config.json', {'config': config, 'homes': {k: str(v) for k, v in HOMES.items()}})


def start():
    rows = []
    for who, home in HOMES.items():
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', PORTS[who]))
        log = (ROOT / (who + '-backend.log')).open('w')
        process = subprocess.Popen([str(BIN), 'serve', '--host', '127.0.0.1', '--port', str(PORTS[who]), '--skip-build', '--isolated'], cwd=ROOT, env=env(home), stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        rows.append({'who': who, 'pid': process.pid, 'port': PORTS[who]})
        save('backends.json', rows)
    print(json.dumps(rows))


def attach(who):
    home, port = HOMES[who], PORTS[who]
    html = urlopen(f'http://127.0.0.1:{port}/', timeout=5).read().decode()
    token = re.search(r'__HERMES_SESSION_TOKEN__="([^" ]+)"', html).group(1)
    command = ['herdr', 'tab', 'create', '--workspace', 'wN', '--cwd', str(ROOT), '--label', 'g3-' + who, '--env', 'HERMES_HOME=' + str(home), '--env', 'HERMES_DISABLE_LAZY_INSTALLS=1', '--env', 'HERMES_TUI_GATEWAY_URL=' + f'ws://127.0.0.1:{port}/api/ws?token=' + quote(token), '--no-focus']
    row = json.loads(subprocess.check_output(command))['result']
    result = {'who': who, 'pane': row['root_pane']['pane_id'], 'tab': row['tab']['tab_id']}
    ledger = json.loads((PROOF / 'panes.json').read_text()) if (PROOF / 'panes.json').exists() else []
    ledger.append(result)
    save('panes.json', ledger)
    subprocess.run(['herdr', 'pane', 'run', result['pane'], f'{BIN} --tui --ignore-rules --resume {SIDS[who]} -t terminal,file'], check=True, stdout=subprocess.DEVNULL)
    print(json.dumps(result))


def snapshot(who, name):
    db = sqlite3.connect(f'file:{HOMES[who]}/state.db?mode=ro', uri=True)
    db.row_factory = sqlite3.Row
    rows = [dict(row) for row in db.execute('SELECT id,session_id,role,content,tool_calls,tool_name,display_kind,display_metadata FROM messages ORDER BY id')]
    sessions = [dict(row) for row in db.execute('SELECT * FROM sessions')]
    db.close()
    save(name, {'messages': rows, 'sessions': sessions})
    print(json.dumps(rows[-4:], ensure_ascii=True))


def main():
    action = sys.argv[1]
    if action == 'setup': setup()
    elif action == 'start': start()
    elif action == 'attach': attach(sys.argv[2])
    elif action == 'rpc':
        result = rpc(sys.argv[2], sys.argv[3], json.loads(sys.argv[4]))
        save(sys.argv[5], result)
        print(json.dumps(result))
    elif action == 'send':
        from tools.bot_live_delivery import find_canonical_live_owner, deliver_to_live_owner
        who, text, name = sys.argv[2:5]
        home = HOMES[who]
        owner = find_canonical_live_owner(home)
        if owner is None: raise RuntimeError('No canonical owner in synthetic home')
        author = {'id': 'bot:g1-test', 'name': sys.argv[5] if len(sys.argv) > 5 else 'g1-test', 'is_bot': True}
        result = deliver_to_live_owner(home, owner, text, author=author)
        save(name, result)
        print(json.dumps(result))
    elif action == 'result':
        from tools.bot_live_delivery import read_delivery_result
        result = read_delivery_result(HOMES[sys.argv[2]], sys.argv[3])
        save(sys.argv[4], result)
        print(json.dumps(result))
    elif action == 'snapshot': snapshot(sys.argv[2], sys.argv[3])
    elif action == 'search':
        from hermes_state import SessionDB
        from tools.session_search_tool import session_search
        db = SessionDB(db_path=HOMES['receiver'] / 'state.db')
        result = json.loads(session_search(query='G3-SCRIPT-198', detail='full', db=db))
        db.close()
        save('session-search.json', result)
        print(json.dumps(result))


if __name__ == '__main__':
    main()
