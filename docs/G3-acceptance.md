# G3 live acceptance — COMPLETE (hermes-evolution #198)

Executed 2026-10-09, approximately 23:19–23:24 ET, against the **deployed**
`/home/brad/.hermes/hermes-agent/.hermes/bin/hermes`, using the existing
`author-persist-198` worktree. G3 fix: `328aa69e22818718fa545905bff81eb199f70a0d`.
The deployed checkout retains baseline HEAD `1e0c7730d791f5ce855c5c78935cfea6fb1e43a9`
plus maintenance-window patches; HEAD alone is not the deployment identity.
`g3-acceptance/deployed-source.json` records actual installed file hashes. Ten
G3 files match the fix exactly. `tui_gateway/prompt_turn.py` additionally has
the installed voice-listener change shown in `deployed-prompt-turn-delta.diff`;
the G3 attribution portions match. All eleven hashes stayed unchanged during
the acceptance checks.

## Isolation and method

Read G3acc-brief.md, Chief's deployment handoff, G3-author-198.md and G1-a2a.md
in full. Reused G1's native mailbox method and the installed Herdr skill.
New synthetic installation beside G1:
`/home/brad/worktrees/hermes-scripts-a2a-spike-195/.g3-runtime/`.
Default home was sender (`g3-sender-198`); receiver was
`profiles/g3-receiver/` (`g3-receiver-198`). Both sessions were titled `Bot Chat`.
Dedicated loopback backends listened on **19198 / 19199**, both with
`--isolated --skip-build`; attached throwaway TUIs ran in Herdr **Workers** (`wN`).
`panes.json` records all five created tabs, including resume replacements.

Configuration pinned main and compression requests to the LAN `gb10-balanced`
provider, disabled memory/user profiles, configured no MCP servers, no enabled
plugins, and no fallback providers. Human fixtures were entered through the
receiver composer with `herdr pane send-text` plus Enter. Script wakes used
`find_canonical_live_owner` and `deliver_to_live_owner` with the exact bot author.
Every DB inspection explicitly addressed a throwaway home. No seat transcript,
seat DB, or real `~/.hermes/state.db` was inspected or changed. No runtime source
edit, rollback, service restart, producer migration, or production delivery was
performed.

## Results

| # | Check | Result | Observed evidence |
|---|---|---|---|
| 1 | Script wake `from: g1-test` persists author without changing role/kind | PASS | Receiver row 3: `role=user`, `display_kind=null`, `display_metadata.author={id:"bot:g1-test",name:"g1-test",is_bot:true}`. Native ticket settled with `G3-SCRIPT-ACK`. `receiver-script-db.json`, `script-admission.json`, `script-receipt.json`. |
| 2 | Human composer turn has no author/prefix | PASS | Rows 1 and 5, before and after the bot turn, have null metadata/kind and unchanged text. Resume shows ordinary unprefixed human turns. `receiver-model-db.json`, `receiver-resumed-tui.txt`. |
| 3 | Close/reopen receiver TUI preserves bot label and unprefixed human | PASS | Closed `wN:t9Y`, reopened/resumed as `wN:t90`. `herdr pane read` shows `❯ [Bot delivery: BOT g1-test; not the human user]` before G3-SCRIPT, and `❯ G3-HUMAN-198` / `❯ G3-MODEL-198` without a bot prefix. `receiver-resumed-tui.txt`, `panes.json`. |
| 4 | Model sees the bot identity | PASS | Human question supplied no expected label. Reply: “The previous G3-SCRIPT-198 message was sent by a bot, not Brad. The author label was: `[Bot delivery: BOT g1-test; not the human user]`.” `receiver-model-db.json` row 6. |
| 5 | Real `message_agent` round trip has the same attribution | PASS | Sender and receiver each invoked `message_agent`. Receiver row 7 has `{id:"bot:default",name:"hermes",is_bot:true}`; sender row 9 has `{id:"bot:g3-receiver",name:"g3-receiver",is_bot:true}`. Replies settled; restored TUIs show `BOT hermes` and `BOT g3-receiver`. `sender-roundtrip-db.json`, `receiver-roundtrip-db.json`, both resume captures. |
| 6 | Receiver-home `session_search` returns author_label | PASS | Actual deployed tool called in a receiver-home process, with explicit receiver SessionDB: matched row 3 has `author_label:"BOT g1-test"`, receiver-scoped session link. `session-search.json`. |
| 7 | Committed compression summary retains bot attribution | PASS | Manual `session.compress` reduced **20 → 4 messages**, **28,117 → 10,428 estimated request tokens**, removing 16 messages without fallback. Persisted summary row 21 quotes `BOT g1-test` and says the fact `G3_ORIGIN_FACT=blue` was supplied by bot g1-test, **not** Brad. `compression-with-padding-rpc.json`, `receiver-post-compress-db.json`, `compression-summary-rows.txt`. |
| 8 | Spoofed/unsafe names render BOT, sanitized/capped | PASS | `Brad` renders `[Bot delivery: BOT Brad; not the human user]`. A name containing newline, ESC, bidi format, delimiters and 140 Xs renders `BOT Brad31m` plus 57 Xs: **64 name characters**, ASCII, with controls/bidi/delimiters removed. Exact raw admission and settled receipt retained. `spoof-*-admission.json`, `spoof-*-receipt.json`, `receiver-spoof-resumed-tui.txt`. |

## Compression and execution qualifications

The first manual compression was an honest no-op: a short 16-message transcript
would have grown after summarization. `compression-rpc.json` preserves that
refusal. Added a native bot turn with 900 explicitly synthetic padding lines
and a final small human composer turn, then repeated the same supported manual
compression. The second pass committed; no artificial summary or DB rewrite
was used by the harness. The summary also contains the existing compressor's
verbatim “User Messages” padding appendix; the tested G3-SCRIPT fact and its
quoted author remain explicitly bot-attributed.

Startup incidents are recorded rather than treated as clean isolation proof:
one initial `hermes serve --help` invocation omitted HERMES_HOME and triggered
the default 1Password credential-loading hook (33 secrets reported loaded;
no secret values were printed or stored in committed evidence). Subsequent
launches set the synthetic home before startup. The new home's dependency
bootstrap initially refused a borrowed environment, then automatically
repaired dependencies despite `HERMES_DISABLE_LAZY_INSTALLS=1`. Dependency
state was confined to synthetic `.g3-runtime` and G1's synthetic environment
tree, shared through a dependency-directory symlink; no install command was
explicitly issued and no live dependency facts were intentionally changed.
Failed bootstrap files were preserved. The harness then used the live launcher
and live deployed code for every acceptance turn. These incidents do not
establish broader privacy or bootstrap acceptance.

## Cleanup and verification

All five created tabs were closed. Exact backend process groups **3595266**
and **3595267** were terminated. `cleanup.json` verifies **zero** remaining
test tabs, synthetic-home processes, or listeners on the two test ports.
Synthetic homes remain as local evidence; all committed transcripts are
synthetic. No existing Herdr tab or service was closed.

Run the saved-evidence verifier (stdlib only):

```sh
python3 docs/g3-acceptance/check_proof.py
git diff --check
```

Result: **8/8 requested live checks PASS; test panes, processes, and ports cleaned
up.** `check_proof.py` verifies saved evidence; it does not rerun live acceptance.
`harness.py` records native delivery, configured backends, TUI attachment,
explicit DB snapshots, search and manual-compression RPC helpers.

No failed-acceptance rollback handoff is required. This receipt covers the
eight synthetic G3 checks only; generic PM/seat addressing and production
producer migration remain separate work.
