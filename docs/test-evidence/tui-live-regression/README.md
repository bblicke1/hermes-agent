# Chief regression repair — #177

The four original `src/lib/liveProgress.test.ts` failures reproduced (4 failed,
3 passed). The merger introduced `inlineDiffs: []` on shelves without diffs.
The field is optional: only shelves carrying diffs need ownership metadata, so
empty merges now retain their existing object shape. Original tests are unchanged;
existing liveSections ownership tests still verify rebasing source tool indices.

Bundled Node, reused dependencies, no installations or live deployment.

```
npm test --prefix ui-tui -- src/lib/liveProgress.test.ts
# Before repair: 4 failed, 3 passed
npm test --prefix ui-tui -- --reporter=json --outputFile=/tmp/tui-177-full-results.json
# 181 files; 1636 passed, 2 skipped, 0 failed; success true
npm run typecheck --prefix ui-tui
# exit 0
npm run build --prefix ui-tui
# exit 0; built ui-tui/dist/entry.js
git diff --check
# exit 0
```

All four shelf tests pass. The previously reported baseline-failure files also pass
in this environment: subscriptionOverlay (23 tests), appChromeBlockedTimers
(29 tests), ink-backpressure (4 tests). No tests were excluded or expectations changed.
The existing Vitest alias uses this checkout's Ink source instead of the reused
installed bundle. Full-suite summary is adjacent. A subprocess emitted a missing
`ruamel.yaml` diagnostic; Vitest nevertheless reports all tests passed and no
unhandled errors. No dependency work was attempted.

Regenerated cumulative patch against `1e0c7730d79` passes the dirty-live apply check.
Applied in the detached scratch checkout, it also permits the G3 runtime patch
apply check. Chief remains responsible for deployment.
