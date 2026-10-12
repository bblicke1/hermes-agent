# #254 — final repair r2 Chief handoff

Python 3.14 is the authoritative acceptance gate, per PM's final repair brief. Test interpreter: `/home/brad/.hermes/installs/66cef3827c817e6e/test-environment/gen-0d5891f1091642ea909f2ee4a8cf4321/venv/bin/python`. Live TUI proof interpreter: `/home/brad/.hermes/tools/python-3.14.7+20260901-linux-x64/bin/python3`. Earlier Python 3.11 failures are historical diagnostics and do not define this gate.

48 tests pass across the three repair test files plus the neighboring poller file (all six poller tests now green). The real compression caller samples prove history is released at all three sync sites. Both live exact replies/read-acks pass across `/new` in the same backend process; scratch dual-owner route dry-run and wake admission also pass. All owned proof resources are removed.

Successful proof: tab `wN:tEZ`, pane `wN:pF5`, session `20261012_172432_fa92f3` → `20261012_172444_f83b5a`. Operator publication read the renderer's actual active-session file, used Herdr's startup/new hints, and retained only the scratch test name. Real route/wake helpers used a process-local test identity, never a live registry edit. This proves lease maintenance with explicit operator route publication, not automatic production route refresh or deployed-seat acceptance.

Findings table, command/result evidence and lock audit: `REPAIR-R2.md`. Live receipts: `live-proof.txt`, `live-results.json`, `first-tui.txt`, `second-tui.txt`. Current patch provenance: `repair-r2-patch-check.json` (runtime source `834a4444784`, captured live baseline `5c52da9f5ca`, current live HEAD, SHA256, forward/reverse byte checks and live apply check). Re-verify at the deployment window; checks do not apply the patch.

Publication failure preserves the predecessor/token. Successful replacement is usable before retirement; failed cleanup retries exact generation records at idle/finalize. A dual-record window is deliberate, exact-key route resolution is deterministic, and both records are process-birth fenced. Revoke also matches live ID, and finalization retries pending records even without a current advertisement. Repeated registration contention warns on attempt 12, then resets after lock acquisition.

Fable r2: approve_with_changes, zero high. The requested final repairs are complete; PM requested no further Fable round. Chief deployment authorization is the next gate. No existing seats/PMs/gateway/panes were changed or restarted; nothing deployed.

## Chief apply (after deployment authorization)

Deploy only the incremental patch; the branch contains unrelated captured dirty-runtime baseline changes.

```bash
git -C /home/brad/.hermes/hermes-agent apply --check /home/brad/worktrees/hermes-agent-readvertise-254/docs/readvertise-254/runtime.patch
git -C /home/brad/.hermes/hermes-agent apply /home/brad/worktrees/hermes-agent-readvertise-254/docs/readvertise-254/runtime.patch
```

Seats/PM TUI backends pick up the code on their approved relaunch. A serve process hosting TUI WebSocket sessions also needs its own approved relaunch. No Hermes gateway restart is needed for these TUI consumers. This worker changed/restarted none of those existing processes.

## Rollback

```bash
git -C /home/brad/.hermes/hermes-agent apply --check -R /home/brad/worktrees/hermes-agent-readvertise-254/docs/readvertise-254/runtime.patch
git -C /home/brad/.hermes/hermes-agent apply -R /home/brad/worktrees/hermes-agent-readvertise-254/docs/readvertise-254/runtime.patch
```

Relaunch only the consumers changed during the deploy window. Republish routes against observed current IDs; never restore stale advertisements.
