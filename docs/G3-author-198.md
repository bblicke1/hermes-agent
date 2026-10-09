# G3 / hermes-evolution #198 — COMPLETE, staged for cross-vendor review

Code commit: `3991b5e4ea986b8861bbc0b79a3b6a7d8b0d03b7`, branch `author-persist-198`, base `1e0c7730d791f5ce855c5c78935cfea6fb1e43a9`. Worktree: `/home/brad/worktrees/hermes-agent-author-198`. Read the complete G3 brief and G1-a2a.md. No live source edits, installs, deployment, restart, seat send, private transcript/database read or migration occurred.

## Minimal design and implementation

Existing `messages.display_kind` and JSON TEXT `display_metadata` (`hermes_state_common.py:471-473`) already round-trip arbitrary metadata. There is no need for a new column or migration. `display_identity` remains the dedupe hash, not sender identity. New ordinary bot rows retain provider `role=user` and exact authored content, with `display_kind=delivery` and `display_metadata.author={id,name,is_bot}`. Existing hidden/process/event kinds and other metadata remain intact. Normalization reuses `parse_turn_author`; labels confer no permission or authenticated identity.

| Seam | File:line | Behavior |
|---|---|---|
| Trusted ingress | `tui_gateway/methods_bot_relay.py:145-190`; `session_notifications.py:670`; `session_auto_continue.py:509` | Existing relaying principal/DeliveryAuthor or durable mailbox author reaches the recipient. The JSON author rejection remains unchanged. Queue envelopes retain the author and do not merge authored deliveries. |
| Agent's incoming dict | `agent/turn_context.py:655-704`, `:1051` | The per-turn parsed author is merged into the new/staged incoming message before turn-start crash flush. A later un-authored human turn remains untyped. |
| Accept-time persistence | `tui_gateway/methods_prompt.py:558`; `session_workdir.py:647-704` | Preserve attribution before agent build starts, rather than relying on later flush of an already-durable adopted row. |
| Busy queue | `tui_gateway/session_auto_continue.py:296-382` | Author survives the early acceptance row and its replacement at drain; queue-only markers are removed without dropping author. |
| Dispatch / reconnect snapshot | `tui_gateway/prompt_turn.py:1135`; `session_auto_continue.py:538` | Dispatch carries typed author metadata into the inflight snapshot and synthesized display annotation. Live subscriber behavior is a separate acceptance gate. |
| SQLite writer/reader | `agent/session_persistence.py:204-234`; `hermes_state_messages.py:169-199`, `:277`, `:359-364` | Existing encoding/decoding carries the metadata, including JSONL diversion; no schema change. |
| Display API readers | `tui_gateway/session_history.py:364`; `hermes_cli/web_routers/sessions.py:686-692`; `agent/turn_author.py:129` | Copy ordinary delivery rows into labeled system rows for display only; never rewrite SQLite or model context. |
| Existing clients | `ui-tui/src/domain/messages.ts:101-105`; `components/messageLine.tsx:163`; `apps/desktop/src/lib/chat-messages/hydration.ts:452`; Relay `ChatHandler.kt:1476-1497` | Existing system-row fallback renders bot name/content. Relay already decodes display metadata, but does not recognize delivery specifically; backend projection avoids needing a Relay release. No client production source changed. |
| Session search | `tools/session_search_tool.py:237-251` | Read/scroll/discover context rows retain display kind and metadata rather than flattening them away. |
| Memory / curation | `agent/memory_manager.py:229`, `:607`, `:733`, `:798`; `context_compressor.py:3613`, `:3647`; `background_review.py:342`, `:1319` | Raw memory-provider transcript egress retains metadata. Summary/digest text labels bots; fallback human asks exclude bots. Review prompts append an author map to new input, preserving warm cached history. The curator's scheduled skill lifecycle is not itself a transcript reader; memory/skill background review is covered. |
| Provider API | `agent/turn_context.py:1277`; `agent/message_metadata.py:42-47` | Existing persistence-only field removal strips display metadata; role/content and cached prefix stay unchanged. |

## Upstream survey

Canonical remotes: `origin=https://github.com/NousResearch/hermes-agent.git`, `fork=https://github.com/bblicke1/hermes-agent.git`. `git log -S DeliveryAuthor` found `6881e4d3fcd` (relay sender carried into live Bot Chat turn). Upstream searches on 2026-10-09 found [merged #107520](https://github.com/NousResearch/hermes-agent/pull/107520), which supplies transport/memory attribution but leaves this durable gap; [open #78593](https://github.com/NousResearch/hermes-agent/pull/78593) persists Discord origin under `display_metadata.origin`; [open #109548](https://github.com/NousResearch/hermes-agent/pull/109548) adds voice hook context. No exact generic delivery-author persistence patch was found in those searches. Preserve their metadata during reconciliation; no claim that an exhaustive upstream review was performed. No upstream PR opened or branch pushed.

## Verification

- Unchanged production base, with regression tests: **10 passed, 7 failed**. Each failure tests absent author persistence/projection/review handling; the API-copy invariant already passed.
- Patched production: **17 passed, 0 failed** in **6.4s**, across only `tests/agent/test_delivery_author_persistence.py` and `tests/tui_gateway/test_queued_prompt_persistence.py` in the final focused run.
- TUI transcript reader: **1 passed**. Desktop real hydration converter: **2 passed**, including object and serialized metadata.
- Existing canonical Hermes test venv, Python 3.14: `/home/brad/.hermes/installs/66cef3827c817e6e/test-environment/gen-0d5891f1091642ea909f2ee4a8cf4321/venv/bin/python`. The old `.venv` lacks pytest; no environment was built or repaired. Tests used `scripts/run_tests.sh`, with retries disabled and its synthetic HERMES_HOME isolation.
- Desktop's standard Vite config cannot load its missing `@rolldown/plugin-babel`. The focused node config uses existing workspace dependencies and mocks only filesystem/media presentation and connector-label constants; it does not prove full Desktop build/UI acceptance.
- An exploratory run while extending `test_turn_context.py` yielded **25 passes, 1 failure** in that file: its late AIAgent import invokes updater metadata probes beneath the canonical `.hermes` Git directory, rejected by the suite's real-home I/O guard. That unrelated test file was returned to its original bytes, and no guard/runtime/import workaround was installed. It is not included in the final touched-file test claim.
- Scoped ruff and commit hook: pass. Staged code-health against the exact base: **0 blocking, 0 advisory**. `git diff --check`: pass.
- Read-only `git apply --check runtime.patch` against the currently dirty live checkout: **pass**. Its five pre-existing modified file paths remain unchanged. No application occurred.

Commands and raw results are in [g3-proof](g3-proof/). The full commit diff is [review.patch](g3-proof/review.patch); production-only diff is [runtime.patch](g3-proof/runtime.patch). [PR-description.md](g3-proof/PR-description.md) is ready for upstream adaptation. [DEPLOY-ROLLBACK.md](g3-proof/DEPLOY-ROLLBACK.md) contains exact approved-operator commands and the update/re-apply procedure.

## Gates retained

Legacy rows without a known author cannot be backfilled from prose. Isolated compute-host transport still has no author field. Third-party consumers that discard metadata must adopt the author contract; metadata cannot force their interpretation. Display APIs project delivery rows as system, while raw DB/search provider roles remain user. Already-running clients need the approved runtime maintenance window before they can serve new projections. Physical TUI/Desktop/Relay restore and live subscribed delivery visibility have not been tested here. No generic arbitrary-seat addressing or producer cutover was added.

Next action: review the upstream description and runbook with the other vendor before authorizing deployment.
