# fix(transcript): persist delivery authors across replay and readers

When `message_agent` or a native mailbox delivers an attributed bot turn, its sender reaches per-turn memory hooks but disappears from the stored message. Restoring the session consequently presents bot speech as the human's input, and session_search/background curation flatten it to USER.

Store normalized `{id,name,is_bot}` in `display_metadata.author`, using `display_kind=delivery` for ordinary bot turns. Stamp it before both agent crash persistence and gateway accept-time writes, retaining it when a queued row is replaced at drain. Preserve existing hidden/process/event types and metadata. Provider requests retain their existing role/content and strip display metadata.

Project ordinary bot deliveries as labeled system rows in both display APIs. This gives existing TUI, Desktop and Relay clients a non-user representation without introducing provider roles or requiring client builds. Raw SQLite/search/memory records preserve the structured author. Search retains display metadata; summary records and review digests label bot authors, and warm-cache review prompts append provenance without rewriting prior context.

Validation: 17 Python tests pass across the two touched test files; unchanged base has 7 regression failures and 10 passes. TUI reader: 1 pass. Desktop hydration: 2 passes with a focused node config (standard Vite config lacks its installed Babel plugin; media presentation/connector labels mocked). Scoped ruff, staged code-health (zero blocking/advisory), and git diff --check pass. No installs, runtime deployment, restarts, or private session reads.

Related: NousResearch/hermes-agent#107520 supplies transport/memory attribution; #78593 proposes structured Discord origin metadata; #109548 carries voice context. This fixes durable generic delivery attribution using the existing sidecar, retaining `origin`/other metadata. Author labels grant no authority. Legacy unattributed rows are not guessed or backfilled; isolated compute-host transport still has no author field. Live subscribed delivery visibility and physical client acceptance remain separate gates.
