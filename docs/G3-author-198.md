# G3 fix round / hermes-evolution #198 — COMPLETE, staged for review

Worktree `/home/brad/worktrees/hermes-agent-author-198`, branch `author-persist-198`; runtime base `1e0c7730d791f5ce855c5c78935cfea6fb1e43a9`. Fix commit `328aa69e22818718fa545905bff81eb199f70a0d`. This round supersedes the behavior in `3991b5e`. Read G3fix-brief.md and every finding in fable-g3.json in full. No deployment, service restart, install, seat send, private transcript read, or private DB change occurred.

Ordinary bot turns persist only `display_metadata.author={id,name,is_bot}`; `display_kind` keeps its prior value. Human authors add no new metadata. Labels start with BOT, redact credentials before label filtering, allow only ASCII letters/digits and limited punctuation, and cap the name at 64 characters. Display copies retain role=user and carry an explicit bot prefix. Model requests independently prefix raw attributed content, including restored api_content sidecars and multimodal content; display projections never build model history. Summaries and review digests use the same short label; search exposes author_label.

## Finding receipt

| Finding | Fix or rebuttal with evidence |
|---|---|
| F1 high | Fixed: `agent/turn_author.py:106` preserves display_kind and uses the dedicated author key. Unsafe readers confirmed: `agent/context_compressor.py:4506` treats non-steer kinds as synthetic; `:5842` excludes them from human projections; `hermes_state_search.py:789` SQL excludes typed rows from user recall. Existing hidden/event kinds retain their meaning. Restore and API regression tests retain attributed rows. |
| F2 high | Rebutted retirement premise and tested: `hermes_state_sessions.py:542` checks exactly `$._queued_prompt`, never metadata truthiness. The queue/drain regression ends/reopens the synthetic session and proves the unmarked author-bearing replacement stays active. |
| F3 high | Rebutted missing writer/reset: `agent/turn_context.py:1051-1052` parses and unconditionally assigns _turn_author before turn setup, including None for humans. A real build_turn_context regression proves bot then human reset even if setup fails. `tui_gateway/session_auto_continue.py:168` writes the queue envelope author. `agent/turn_facade.py:155` forwards the author inside the session turn lease. |
| F4 high | Fixed: `agent/turn_author.py:126` centralizes forced secret/URL redaction, delimiter/control/bidi filtering and a 64-character label cap. All new display, model, digest, search and compression interpolations use this label. Even a bot named Brad displays BOT Brad and explicitly says it is not the human user. |
| F5 high | Implemented: `agent/turn_context.py:1305` prefixes the wire content from durable author metadata after sidecar substitution. The role stays user. A synthetic DB restore test proves live/replayed bytes match, human content stays unchanged, and raw history is untouched. |
| F6 medium | Fixed: `agent/turn_author.py:155` removes the system-role projection entirely. `_history_to_messages` consumers in `tui_gateway/methods_session.py:377,483,686,2022,2092,2137` and `compute_host.py:493` produce RPC/display results; raw history builds seeds/model context. Wire formatting reads raw provenance directly. A seed round-trip regression also proves no system authority is introduced. |
| F7 medium | Fixed: `tools/session_search_tool.py:247` adds the derived author_label to every shaped result; restore/search test proves BOT Alpha is present. |
| F8 medium | Rebutted: `agent/turn_author.py:9,13` already import json and Mapping. Exercised directly by the label/metadata tests. |
| F9 medium | Fixed: DEPLOY-ROLLBACK.md documents metadata-only compatibility, loss of labels after rollback, approval/cache transition, and no guessed historical backfill. No new display_kind or schema value is emitted. Synthetic reopen proves author metadata is not a retirement marker. |
| F10 medium | Fixed: `tui_gateway/methods_prompt.py:784` sends attribution in existing compute metadata; `compute_host_bridge.py:62` serializes it; `compute_host.py:270` passes it into the recipient; `prompt_turn.py:1135` recovers the author and `:795` forwards it to the agent. Queue drain uses the same channel at `session_auto_continue.py:510`. Tests cover the real parent frame, child admission, and queued isolated dispatch. |
| F11 medium | Fixed: `agent/turn_author.py:122` provides is_bot_delivery; no BOT-prefix string tests remain. Labels omit full author JSON. Compression human-only anchors/projections also check the metadata predicate. |
| F12 low | Fixed: removed the redundant index-based author appendix from background-review prompts; attribution stays inline in `_digest_history` (`agent/background_review.py:343`) and the model wire prefix. |
| F13 low | Fixed: delivery_display adds author metadata only for bots (`agent/turn_author.py:110`); human no-op is tested. |
| F14 low | Fixed: restored the original think-block comment and method spacing; imports are outside the per-message digest loop. Added behavior tests; code-health growth is zero in the oversized compressor. |
| F15 low | Fixed: display/summary/wire all key on the same bot metadata predicate, independent of existing event kinds; structured content gets one text prefix without losing attachments. Idempotence and attachment preservation are tested. |

## Verification and artifacts

The two touched Python test files pass 25 tests with retries disabled through scripts/run_tests.sh and the existing Python 3.14 test venv. The same revised tests on the prior production patch (3991b5e) fail 11 and pass 14, proving the regression targets; production files were restored byte-for-byte after that isolated worktree-only run. TUI reader: 1 pass; Desktop hydration: 2 passes, using the existing focused config and dependency symlinks. No dependencies were installed. Scoped ruff, code health against the exact runtime base, and git diff --check pass.

review.patch contains the complete production-and-tests diff against the runtime base, usable with git apply in a clean review worktree. runtime.patch contains only the 11 listed production files; SHA256SUMS covers both patches and runtime-files.txt. Logs are in g3-proof. The prior patch and this round's code commits are preserved on the same branch.

## Remaining deployment gates

Nothing deployed. Cross-vendor review and an approved drained maintenance window still precede runtime application. The bot prefix changes provider bytes for known-attributed rows once at upgrade, so do not hot-reload a serving seat; reopen affected backends during the approved window. Legacy unattributed rows remain ambiguous and are not guessed from text. Physical TUI/Desktop/Relay rendering and subscribed live visibility still require separately approved synthetic acceptance. Third-party consumers that discard metadata need their own attribution support.
