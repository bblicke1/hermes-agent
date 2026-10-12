# #254 — implementation ready; live proof blocked

Baseline: `5c52da9f5ca2c73d04bf3b43113fd5f427b3757b`, captured from the dirty live tree on 2026-10-12. All five runtime patch files matched live bytes before editing and again at handoff (`baseline-match.txt`). Never deploy this branch wholesale: its baseline includes unrelated live changes.

The common locked helper follows the current durable session key, publishes the replacement, retires the prior advertisement, and projects reachability for both IDs. Create/resume/activate and in-process/isolated compression call it. The live runtime ID stays stable across compression; a verified predecessor token carries forward so pre-compression queued mail stays claimable. Publication/refusal/storage errors log and leave the session transition usable. An idle poll retries publication.

## Checks

- `HERMES_PYTHON=/home/brad/.hermes/hermes-agent/venv/bin/python HERMES_TEST_FILE_RETRIES=0 scripts/run_tests.sh tests/tui_gateway/test_delivery_readvertisement.py` — 8 passed, with real advertisement/status/mailbox files and module seams. Covers close/create (/new lifecycle), resume response, compression, double rotation, refusal/exception recovery, isolated compression under a non-reentrant history lock, and forged predecessor fencing. Full backend/renderer E2E is not claimed.
- Same runner on the baseline with `-k 'not unowned_token'` — 7 failed (regressions); `base-red.txt`.
- `ruff check tui_gateway/session_lifecycle.py tui_gateway/session_compression.py tui_gateway/compute_host_bridge.py tui_gateway/methods_session.py tools/bot_live_delivery.py tests/tui_gateway/test_delivery_readvertisement.py` — passed.
- `git diff --check` and patch reverse-apply check — passed.
- Contract-wide direct pytest collection was not run: the brief restricts execution to affected tests and AGENTS.md requires the hermetic runner. Existing focused mailbox files hit the pinned Python environment's real-home I/O guard; those results are not green acceptance.

## Acceptance still required

The contract's Python 3.11 interpreter cannot import `tui_gateway.server`: the pre-existing `agent/turn_scripted_prelude.py:24` uses two `typing.Generator` arguments. `live-proof.txt` records an isolated import preflight and cleanup. No Herdr tab, route, or proof mail was created; no seat/gateway was edited/restarted. Permission to use the existing Python 3.14 test environment was requested; no assumption of approval was made.

Required before deployment: throwaway Workers tab + scratch `seat-test-254` home, private route publication, mail/seat_wake exact reply, `/new`, route refresh against the newly advertised key, second mail/wake exact reply without relaunch, cleanup; then Fable cross-vendor review and Chief deploy window. These gates remain open.

## Chief apply (after gates and authorization)

```bash
git -C /home/brad/.hermes/hermes-agent apply --check /home/brad/worktrees/hermes-agent-readvertise-254/docs/readvertise-254/runtime.patch
git -C /home/brad/.hermes/hermes-agent apply /home/brad/worktrees/hermes-agent-readvertise-254/docs/readvertise-254/runtime.patch
```

Seats and PMs running TUI backends pick up the change on approved relaunch. No gateway restart is required for the seat/PM TUI consumers. A `serve` process hosting TUI WebSocket sessions must also be relaunched in its own approved window. This worker performed none of those actions.

## Rollback

```bash
git -C /home/brad/.hermes/hermes-agent apply --check -R /home/brad/worktrees/hermes-agent-readvertise-254/docs/readvertise-254/runtime.patch
git -C /home/brad/.hermes/hermes-agent apply -R /home/brad/worktrees/hermes-agent-readvertise-254/docs/readvertise-254/runtime.patch
```

Relaunch only the consumers changed during the deploy window. Route publication must follow their observed current session IDs; do not fabricate or restore stale advertisements.
