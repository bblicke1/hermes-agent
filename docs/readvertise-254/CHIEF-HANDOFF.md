# #254 — repair r1 ready for Fable r2

Baseline: `5c52da9f5ca2c73d04bf3b43113fd5f427b3757b`, captured from the dirty live tree on 2026-10-12. All five runtime patch files matched live bytes before editing and again at handoff (`baseline-match.txt`). Never deploy this branch wholesale: its baseline includes unrelated live changes.

The common locked helper follows the current durable session key, publishes the replacement, retires the prior advertisement, and projects reachability for both IDs. Create/resume/activate and in-process/isolated compression call it. The live runtime ID stays stable across compression; a verified predecessor token carries forward so pre-compression queued mail stays claimable. Publication/refusal/storage errors log and leave the session transition usable. An idle poll retries publication. Failed replacement publication preserves the predecessor token; failed retirement queues cleanup after the replacement is usable. See `REPAIR-R1.md` for the complete findings and lock audit.

## Current verification (repair r1)

`REPAIR-R1.md` contains the findings→fix table and exact commands/results. Python 3.14 checks: 33 passed; five targeted failures were reproduced on pre-repair code. The original contract Python 3.11 run retains the previously recorded environment/import failures, without a guard or dependency workaround.

The real handler integration now covers unpersisted/warm resume and activate with production lock ordering, close/create (/new) ordering, and the actual idle poll retry. The rerun live proof passed with both exact replies and cleanup. Strict ruff and current-live patch apply check passed. Patch provenance is recorded in `repair-r1-patch-check.json`; re-verify at deployment time.

## Live proof

`live-proof.txt` / `live-results.json` contain the successful real Herdr TUI proof; `first-tui.txt` and `second-tui.txt` capture the rendered exact replies. Only a scratch `seat-test-254` home and an owned Workers tab were used. The existing compiled renderer started the worktree `tui_gateway.entry` over its real stdio transport with production Python and already-installed dependency sites. No dependency installation, credentials, or live profile data were used; synthetic turns used the LAN gb10 model.

1. Operator publication read the renderer's actual active-session file, reported that observed ID to Herdr with the installed integration's startup/new hint, retained the test name on the same pane, and ran the real `seat_routes_refresh.refresh` with a process-local test identity against scratch profiles. No live registry was edited.
2. The real `seat_wake.wake_seat_mail` with that process-local test identity admitted immutable mail, and the TUI returned exactly `G254-FIRST-ACK` with an addressed durable read-ack.
3. `/new` was sent through Herdr and its throwaway confirmation accepted. The durable ID changed from `20261012_170206_be5250` to `20261012_170216_fb2527`; the backend PID stayed identical, the old advertisement disappeared, and only the new advertisement remained.
4. After operator route refresh against the observed new ID, the second real mail/wake returned exactly `G254-SECOND-ACK` with a durable read-ack, without backend/TUI relaunch.
5. The owned tab was closed, its backend exited, and the scratch profile/home was removed. `cleanup-audit.json` also verifies all prior proof-attempt tabs are closed.

The test identity and route helpers were injected only in the proof controller's own memory; ingress, advertisements, Herdr checks, turns, terminal acknowledgement, and receipts were real. This proves the lease repair plus operator route publication; it does not claim automatic production route publication or deployed-seat acceptance.

Fable r2 cross-vendor review and a Chief deploy window remain required. No existing seat, PM, live gateway, or pane was modified/restarted, and no deployment occurred.

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
