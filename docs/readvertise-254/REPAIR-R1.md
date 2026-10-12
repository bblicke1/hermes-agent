# #254 repair r1

engine result: needed repair

Runtime repair commit: `63ac68b5e0ed9bca35715bc1d04918c6c8c94075`. No deployment, existing seat/PM/gateway/pane changes or restarts.

## Findings to fix

| Finding | Repair / evidence |
|---|---|
| F1 | Warm resume/activate refresh inside the history-locked `_rebind_live_transport`; no registration there. Lock map is commented in `_register_open_tui_delivery`. Optional registration takes both locks without waiting. Real threaded unpersisted/warm resume and activate verify resume→history locking; timed paint/compression regressions fail before repair. |
| F2 | Refusal/exception preserves predecessor advertisement and token. Both failure tests queue mail before compression and prove it remains claimable after retry. |
| F3 | Replacement is committed to memory and new-key status before predecessor retirement. Exact predecessor cleanup is retained in `delivery_retirements` and retried at idle/close. Retirement-failure test proves new admission, FIFO, status, and eventual cleanup. |
| F4 | Real `session.close` and `session.create` handlers verify retirement before replacement publication; the live proof drives the actual TUI `/new` and confirmation. |
| F5 | Real `_poll_bot_live_delivery_once` test covers false reachability, missing advertisement, refused publication, and subsequent automatic retry. |
| F6 | Dual records are intentional during publish→retire and cleanup failure. Exact-key resolution is deterministic; resolving an old compression key selects the tip. Test admits/claims old and new mail FIFO with both files present. Route refresh hashes the observed exact ID; wake admission resolves that protected route ID. No directory enumeration chooses a recipient. Dead-process birth-time validation fences each stale file after crash. |
| F7 | Missing history lock skips with warning; resume payload still returns. |
| F8 | Empty live ID skips with warning; compute-host session-key adoption still succeeds. |
| F9 | Locked attach/compression use conservative fencing (no unproven local retirement). Snapshot-based retirement is only available from unlocked registration. Documented in the helper. |
| F10 | Same PID/live-ID advertisement already returns the existing record before UUID/write. Regression test prohibits any atomic JSON write on an unchanged refresh. |
| F11 | Patch regenerated from runtime commit `63ac68b5e0ed9bca35715bc1d04918c6c8c94075`; forward/reverse exact-byte checks and current-live `git apply --check` passed. Provenance in `repair-r1-patch-check.json`; no application. |
| F12 | Carry-forward requires current process birth time on both disk and predecessor record. Forged-birth test verifies a fresh token. |

## Lock audit

`_resume_reuse_live_locked` originally held `_session_resume_lock` (a plain Lock), not history or sessions lock at its old registration statement. `_live_session_payload` releases history before returning. `_resume_live_unpersisted` likewise releases its resume/history scopes before its outer registration. The reviewed warm self-reacquisition premise was not present at those exact statements; the regression risk is unnecessary blocking in optional paint publication and future registration from a held history lock.

After repair, live transport attachment refreshes under its caller's existing history lock and never takes a delivery snapshot or re-acquires history. Warm reuse and activate have no extra registration call. Unpersisted resume's outside-lock registration remains for the no-transport case and is idempotent. `_attach_built_agent` releases `_sessions_lock` before `_announce_built_agent` starts services, so startup registration is outside the registry lock. The integration test binds a real stdio transport and captures `(history held=True, sessions owned=False, resume held=True)` at all three attach sites.

Direct optional registration snapshots only if `_sessions_lock` is immediately available, releases it, and enters history only if immediately available. It cannot wait while a paint or attachment is holding other resources; the existing idle tick retries. Locked compression/transport attach calls the common locked helper directly. No lock-inspection shortcut substitutes for actually acquiring the locks.

## Verification

- `HERMES_PYTHON=/home/brad/.hermes/installs/66cef3827c817e6e/test-environment/gen-0d5891f1091642ea909f2ee4a8cf4321/venv/bin/python HERMES_TEST_FILE_RETRIES=0 scripts/run_tests.sh tests/tui_gateway/test_delivery_readvertisement.py tests/tools/test_bot_live_owner_delivery.py tests/tui_gateway/test_delivery_transition_integration.py` — 33 passed (17 transitions/failures/concurrency, 15 mailbox invariants, one real-import gateway handler/lock integration). `repair-r1-python-314.txt`.
- Pre-repair `6076d9f58fb` with the five selected publication/retirement/concurrency tests — five failed, `repair-r1-base-red.txt`.
- The same three files were run with the original contract Python 3.11 pin: 17 passed, one integration failed at the known pre-existing `typing.Generator` import; the 15 old mailbox tests hit the pre-existing environment real-home I/O guard before execution. `repair-r1-python-contract.txt`. No dependency install, import workaround, guard relaxation, or unrelated repair was performed; the already-approved Python 3.14 environment supplies the complete compatible check above.
- `python3 docs/readvertise-254/live_proof.py` — PASS. Real worktree stdio backend on production Python 3.14.7; scratch `seat-test-254` only. Both exact replies plus durable read-acks; `/new` rotates IDs, retains backend PID, retires old lease. Operator route publication remains explicit. All owned proof resources cleaned up.
- Strict ruff on changed Python, commit hook and `git diff --check` — PASS.
- Runtime patch forward/reverse exact bytes and current-live apply check — PASS (`repair-r1-patch-check.json`).

Fable r2 and Chief deployment authorization remain open. These receipts do not claim deployment or real-seat acceptance.
