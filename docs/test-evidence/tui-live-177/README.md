# TUI live sections — #177 worker evidence

Base: `origin/main` and live HEAD both `1e0c7730d791f5ce855c5c78935cfea6fb1e43a9`.
Worktree: `/home/brad/worktrees/hermes-agent-tui-live-177`, branch `tui-live-sections`.
No live deployment or live configuration changes.

`live` is accepted globally, per section, through `/details`, config RPC validation,
and completion suggestions. It opens for the whole turn, folds at completion, and
allows manual reopening. Inline diffs are attached to a tool's detail body; merging
shelves preserves ownership. Final assistant patch narration removes the duplicate
patch while retaining the tool result. Height keys include patches and collapsed
history estimates omit their bodies.

## Checks

Use `PATH=/home/brad/.hermes/tools/node-26.7.0-linux-x64/bin:$PATH` for npm commands.
Dependencies are symlinked from the live checkout; no npm packages were installed.
Vitest resolves Ink from this worktree's source, avoiding the reused stale Ink bundle.

```
npm test --prefix ui-tui -- src/__tests__/details.test.ts src/__tests__/virtualHeights.test.ts src/__tests__/createGatewayEventHandler.test.ts src/__tests__/createSlashHandler.test.ts src/__tests__/thinkingLiveCollapse.test.tsx src/__tests__/thinkingMoaReferenceVisibility.test.tsx src/__tests__/liveSections.test.tsx
# Test Files 7 passed (7); Tests 222 passed (222)
scripts/run_tests.sh tests/tui_gateway/test_config_set_display_toggles.py
# 1 files, 6 tests passed, 0 failed
npm run typecheck --prefix ui-tui
# tsc --noEmit -p tsconfig.json; exit 0
npm run build --prefix ui-tui
# built ui-tui/dist/entry.js; exit 0
git diff --check
# exit 0
```

Logs: `tests.txt`, `gateway-tests.txt`, `typecheck.txt`, `build.txt`.
The new details/diff contracts were rerun with baseline `details.ts` and
`turnController.ts`: 4 failed, 121 passed (`base-red.txt`); current sources were
restored afterward. Tests also exercise actual Ink render, completion, and mouse
reopening for both global and per-section `live`, including reasoning after its
phase ends, subagents, activity, and diff ownership after shelf merging.

## Visual proof and its limit

Built `ui-tui/dist/entry.js` ran in a throwaway Herdr workspace with a throwaway
HERMES_HOME containing only a copied config.yaml (all sections live, inline_diffs
true) and a temporary terminal cwd. The old live `.venv` uses Python 3.11 and
cannot import the current agent's two-parameter Generator alias; the normal PM
environment supplied Python 3.14. Startup then requested 1Password authentication:
“No accounts configured for use with 1Password CLI.” No account was added and no
credentials were copied. A live model/write_file turn therefore could not run.
`live-model-unavailable.txt` records this limit.

Strongest substitute: `ui-tui/scripts/visual/live-sections.tsx` bundles the actual
MessageLine/ToolTrail Ink components, with synthetic completed terminal/write_file
rows and an attached unified diff, plus reasoning/subagent/activity data. Herdr
`pane read --source visible --format text` captured `running.txt`, `completed.txt`,
and `reopened.txt`. `c` completes the synthetic turn; an actual SGR mouse click on
the tools chevron reopens its retained diff. These are synthetic component proof,
not live gateway/model/file-mutation acceptance. All created workspaces were closed.

Reproduce the fixture with the existing root esbuild:

```
node_modules/.bin/esbuild ui-tui/scripts/visual/live-sections.tsx --bundle --platform=node --format=esm --alias:@hermes/ink=./ui-tui/packages/hermes-ink/src/entry-exports.ts --banner:js='import { createRequire } from "node:module"; const require = createRequire(import.meta.url);' --outfile=/tmp/tui-live-177-proof.mjs
node /tmp/tui-live-177-proof.mjs
```

## Update survival — Chief

The current updater attempts to restore autostashed local edits after a successful update when `updates.non_interactive_local_changes: stash`; the brief's assumption that there is no restore step is not accurate for this base (`hermes_cli/update_cmd.py`, `_restore_stashed_changes` in `update_cmd_stash.py`).
Restoration is skipped with `--keep-stash`, on failure/declined restore, or on conflicts; this local patch therefore has no guaranteed survival across future upstream changes.
After an update, inspect the update receipt and stash; restore the named stash first when it holds the edits, rather than blindly applying the patch twice.
If this feature is absent, Chief should run `git -C ~/.hermes/hermes-agent apply --check ~/.hermes/patches/tui-live-sections.patch`, apply it only on success, then rebuild ui-tui and rerun the scoped checks; deployment remains Chief's step.
