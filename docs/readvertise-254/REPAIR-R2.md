# #254 final repair r2

engine result: needed repair

Runtime repair commit: `834a4444784`. Python 3.14 is the authoritative gate environment per PM's final repair brief. Fable r2 was approve_with_changes with zero high; all requested remaining changes are addressed. No additional Fable round is requested. Chief deployment authorization is still required; no deployment or existing seat/PM/gateway/pane changes/restarts occurred.

| Finding | Fix / evidence |
|---|---|
| R2-1 | Only the three stale poller fixtures changed: mock `find_session_live_owner(home, key, resolve_tip=False)` instead of the canonical-title API. Entire neighboring file: six passed, including all three previously red tests. Runtime poller unchanged. |
| R2-2 | Real-import integration samples all three production in-process callers: `session.compress` RPC via `_compress_live`, slash path `_compress_live_with_feedback`, post-turn `_absorb_turn_result` after real history commit. Each entry to `_sync_session_key_after_compress` has history_lock=False. The real manual-compress busy context releases history before its body; turn commit releases history before sync. Thus its existing blocking key-swap lock is retained without a defer mechanism. Synthetic summary/agent output; real caller wiring, locks, DB continuation rows and delivery advertisements. |
| R2-3 | Revocation matches both lease_id and live_session_id before deleting. Deferred-retirement tests re-advertise the old key under another live ID, including a shared-token case; its advertisement and healthy status survive cleanup. Shared-token regression fails on r1. |
| R2-4 | Finalization flushes pending retirements unconditionally, even with no current advertisement and on a repeated finalize cleanup retry. The absent-advertisement regression fails on r1. |
| R2-5 | Disk predecessor carry-forward uses `.get()` for all identity fields. Five real malformed/legacy disk records fail closed without raising or inheriting the old token. Existing `_read_advertisement` also rejects missing owner fields or failed birth-time validation. |
| R2-6 | Python 3.14 explicitly authoritative in this handoff and final gate receipt. The old Python 3.11 run remains historical diagnostics, not an acceptance gate. No dependency/import/guard workaround. |
| R2-7 | Warning on the 12th consecutive registration deferral for a session; subsequent deferrals are debug until successful lock acquisition resets the counter. Tests cover one warning per sequence and recovery/reset. Poll cadence is 5 seconds: about a minute for 12 eligible idle attempts, not a promise to interrupt a busy turn. |
| R2-8 | Live proof restores the predecessor as a controlled scratch-only second-owner fixture after actual `/new`. Real route refresher dry-run returns would-update without writing, selects the new exact owner, then real route publication and seat_wake settle the second exact reply while both files exist. Fixture removed; all proof resources cleaned up. |

## Gate checks

- `HERMES_PYTHON=/home/brad/.hermes/installs/66cef3827c817e6e/test-environment/gen-0d5891f1091642ea909f2ee4a8cf4321/venv/bin/python HERMES_TEST_FILE_RETRIES=0 scripts/run_tests.sh tests/tui_gateway/test_delivery_readvertisement.py tests/tools/test_bot_live_owner_delivery.py tests/tui_gateway/test_delivery_transition_integration.py tests/tui_gateway/test_bot_live_owner_delivery.py` — 48 passed, no retry. `repair-r2-python-314.txt`.
- R1 `45caaa30f29` with `-k 'deferred_retirement_preserves or finalize_flushes'` — two regressions failed and one unchanged-token control passed, `repair-r2-base-red.txt`.
- `python3 docs/readvertise-254/live_proof.py` — PASS. Production Python 3.14.7 runs the worktree backend; existing compiled TUI, synthetic LAN model, scratch seat-test-254 only. Same PID, actual `/new`, old lease retired, both exact replies/read-acks, dual-owner dry-run and wake resolution, cleanup verified.
- `ruff check --config ruff.strict.toml tools/bot_live_delivery.py tui_gateway/session_lifecycle.py tests/tui_gateway/test_delivery_readvertisement.py tests/tui_gateway/test_delivery_transition_integration.py tests/tui_gateway/test_bot_live_owner_delivery.py docs/readvertise-254/live_proof.py` — PASS; commit hook — PASS.
- `git diff --check`, patch forward/reverse exact bytes, final reviewed source diff equivalence and current-live `git apply --check` — PASS. No application. Provenance: `repair-r2-patch-check.json`.

## Compression lock map

Production Python search shows three actual call expressions: `tui_gateway/methods_session.py::_compress_live`, `tui_gateway/methods_slash.py::_compress_live_with_feedback`, and `tui_gateway/prompt_turn.py::_absorb_turn_result`. `session_workdir.py` has a documentation mention only.

RPC compression enters `_manual_compress_turn`: history is acquired to set running/manual flags, then released before yielding. `_compress_live` releases its before/after snapshot contexts before syncing. Slash compression enters the same busy context and releases its snapshot context before syncing. Post-turn `run_body` invokes `_absorb_turn_result` without a history context; its actual `_commit_turn_history` releases history on return before sync. Real-wiring samples assert `[rpc:false, slash:false, turn:false]`, alongside the existing resume/activate samples and compression/paint race regression. These are assertions on actual runtime lock state, not source-text tests.
