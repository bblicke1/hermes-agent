# TUI pinned todos and visible steering — #180 / #182

Worktree: `/home/brad/worktrees/hermes-agent-tui-live-177`, branch `tui-live-sections`.
Base: `1e0c7730d79`. No live deployment, configuration change, or dependency installation.

The checklist now lives in AppLayout's composer dock, outside virtual transcript rows.
Its measured six-row maximum reduces the ScrollBox viewport by six rows; collapsing
reduces it by two. Long items truncate, with `+N more` for overflow. Unfinished work
stays pinned between turns; completed/cancelled work disappears after completion.

Accepted busy-input steering appends one user row with a dim `↪ steered` label.
Rejections and RPC failures retain the existing system line and queue fallback.
Expanded paste payloads reach the RPC while the visible acknowledgment stays compact.
Rows are added only to the submitting session, so a delayed reply cannot contaminate
a switched session. Height cache keys and estimates include the extra label row.

The existing gateway already persists delivered steers: `steer_user_row` carries
`display_kind: steer`, the engine flushes it idempotently to SessionDB, and gateway
history unwraps the model-only wrapper. UI history now renders that metadata. Resume
also projects pending in-flight corrections, counting persisted matching rows within
the current prompt suffix to avoid duplication while retaining repeated corrections.
The temporary synthetic SessionDB test verifies double flushing yields one plain,
tagged user row. Resume tests include an assistant echo and repeated equal corrections.

## Checks

Use the existing bundled Node via
`PATH=/home/brad/.hermes/tools/node-26.7.0-linux-x64/bin:$PATH`.

```
npm test --prefix ui-tui -- src/__tests__/details.test.ts src/__tests__/virtualHeights.test.ts src/__tests__/createGatewayEventHandler.test.ts src/__tests__/createSlashHandler.test.ts src/__tests__/thinkingLiveCollapse.test.tsx src/__tests__/thinkingMoaReferenceVisibility.test.tsx src/__tests__/liveSections.test.tsx src/__tests__/pinnedTodos.test.tsx src/__tests__/steerSubmission.test.tsx src/__tests__/turnStore.test.ts src/__tests__/useSubmission.test.ts src/__tests__/useSessionLifecycle.test.ts
# Test Files 12 passed (12); Tests 245 passed (245)
scripts/run_tests.sh tests/agent/test_steer_compaction_persistence.py tests/tui_gateway/test_todo_state_events.py tests/tui_gateway/test_config_set_display_toggles.py
# 3 files, 14 tests passed, 0 failed
npm run typecheck --prefix ui-tui
# exit 0
npm run build --prefix ui-tui
# built ui-tui/dist/entry.js; exit 0
git diff --check
# exit 0
```

Logs are adjacent. The real Ink AppLayout test runs at 40 columns / 24 rows,
with the latest user row absent from virtual history, and checks pinned placement,
overflow, exact viewport reduction, collapse, unfinished retention, and busy/idle hide.
The mounted useSubmission test exercises queued, rejected, and failed RPCs.

## Synthetic terminal proof

`ui-tui/scripts/visual/pinned-todos-steer.tsx` mounts the actual AppLayout with 180
synthetic history rows and ten todos; `submitSteer` uses a fake accepted RPC.
Herdr visible-pane captures show running, scrolled-to-top, steered, collapsed,
and ended states. The pinned panel stays above input while transcript history
scrolls. Ended capture hides the completed list and retains the steered row.
The throwaway workspace was closed. This proves components with synthetic data;
live model acceptance remains blocked by the phase-1 1Password authentication gate.

Reproduce with root esbuild, as in the phase-1 evidence README, substituting
`ui-tui/scripts/visual/pinned-todos-steer.tsx` and `/tmp/tui-phase2-3-proof.mjs`.

Delivery is one cumulative patch at `~/.hermes/patches/tui-live-sections.patch`.
It is checked against the dirty live checkout and applied in a detached scratch
worktree, where the G3 author runtime patch is checked on top. Chief deploys.
