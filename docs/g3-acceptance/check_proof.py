"""Verify the saved synthetic live evidence, without opening any Hermes home."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).parent


def read(name):
    return json.loads((ROOT / name).read_text())


def turn(rows, marker):
    return next(row for row in rows if row['role'] == 'user' and marker in row['content'])


def author(row):
    return json.loads(row['display_metadata'] or '{}').get('author')


def main():
    results = []
    receiver = read('receiver-pre-compress-db.json')['messages']
    sender = read('sender-roundtrip-db.json')['messages']
    script = turn(receiver, 'G3-SCRIPT-198')
    assert script['role'] == 'user' and script['display_kind'] is None
    assert author(script) == {'id': 'bot:g1-test', 'name': 'g1-test', 'is_bot': True}
    assert read('script-receipt.json')['status'] == 'settled'
    results.append({'check': 1, 'result': 'PASS', 'evidence': 'receiver-script-db.json, script-receipt.json'})

    for marker in ['G3-HUMAN-198', 'G3-MODEL-198']:
        human = turn(receiver, marker)
        assert author(human) is None and not human['content'].startswith('[Bot delivery:')
    results.append({'check': 2, 'result': 'PASS', 'evidence': 'receiver-model-db.json (human before and after bot)'})

    restored = (ROOT / 'receiver-resumed-tui.txt').read_text()
    assert '❯ [Bot delivery: BOT g1-test; not the human user]' in restored
    assert '❯ G3-HUMAN-198.' in restored and '❯ G3-MODEL-198.' in restored
    results.append({'check': 3, 'result': 'PASS', 'evidence': 'receiver-resumed-tui.txt, panes.json'})

    reply = next(row['content'] for row in receiver if row['role'] == 'assistant' and 'G3-MODEL-198:' in row['content'])
    assert 'BOT g1-test' in reply and 'not Brad' in reply
    results.append({'check': 4, 'result': 'PASS', 'evidence': 'receiver-model-db.json, receiver-resumed-tui.txt'})

    ping = turn(receiver, 'G3-PING-198')
    pong = turn(sender, 'Message from')
    assert author(ping) == {'id': 'bot:default', 'name': 'hermes', 'is_bot': True}
    assert author(pong) == {'id': 'bot:g3-receiver', 'name': 'g3-receiver', 'is_bot': True}
    assert 'G3-PONG-198' in pong['content']
    for rows in [sender, receiver]:
        assert any(row['tool_name'] == 'message_agent' for row in rows)
    assert 'BOT hermes;' in (ROOT / 'receiver-spoof-resumed-tui.txt').read_text()
    assert 'BOT g3-receiver;' in (ROOT / 'sender-resumed-tui.txt').read_text()
    results.append({'check': 5, 'result': 'PASS', 'evidence': 'sender-roundtrip-db.json, receiver-roundtrip-db.json, both resumed TUI captures'})

    search = read('session-search.json')
    match = next(row for hit in search['results'] for row in hit['messages'] if row.get('id') == script['id'])
    assert match['author_label'] == 'BOT g1-test'
    assert search['results'][0]['link'].startswith('@session:g3-receiver/')
    results.append({'check': 6, 'result': 'PASS', 'evidence': 'session-search.json (receiver-home process, explicit receiver DB)'})

    compression = read('compression-with-padding-rpc.json')['result']
    assert compression['removed'] > 0 and compression['after_messages'] < compression['before_messages']
    assert not compression['summary']['noop'] and not compression['summary']['refused_would_grow']
    post = read('receiver-post-compress-db.json')['messages']
    summary = next(row['content'] for row in post if row['content'].startswith('[CONTEXT COMPACTION'))
    assert '[Bot delivery: BOT g1-test; not the human user]' in summary
    assert 'G3_ORIGIN_FACT=blue' in summary and '**not** by Brad' in summary
    results.append({'check': 7, 'result': 'PASS', 'evidence': 'compression-with-padding-rpc.json, receiver-post-compress-db.json (summary row 21)'})

    spoof = (ROOT / 'receiver-spoof-resumed-tui.txt').read_text()
    assert '[Bot delivery: BOT Brad; not the human user]' in spoof
    label = next(label for label in re.findall(r'\[Bot delivery: (BOT [^;]+);', spoof) if label.startswith('BOT Brad31m'))
    assert len(label.removeprefix('BOT ')) == 64
    assert label.isascii() and all(ch.isalnum() or ch in ' ._:/-' for ch in label)
    assert read('spoof-long-receipt.json')['status'] == 'settled'
    results.append({'check': 8, 'result': 'PASS', 'evidence': 'spoof admissions/receipts, receiver-spoof-resumed-tui.txt (64-character sanitized name)'})

    cleanup = read('cleanup.json')
    assert cleanup['remaining_synthetic_processes'] == []
    assert cleanup['remaining_test_tabs'] == [] and cleanup['listening_test_ports'] == []
    (ROOT / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
    print('8/8 requested live checks PASS; test panes, processes, and ports cleaned up.')


if __name__ == '__main__':
    main()
