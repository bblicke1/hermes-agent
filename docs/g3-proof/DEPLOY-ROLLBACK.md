# Approved-operator runbook — NOT EXECUTED

Cross-vendor review and an approved shared-runtime maintenance window are required before these commands. Drain turns and arrange to close/reopen each affected TUI/Desktop/serve backend; restarting the gateway alone does not reload already-running seat processes. These commands apply source only: dependency/lock files are unchanged, so no installs or client builds are required. No private DB is changed.

Verified service metadata on 2026-10-09: hermes-gateway.service runs the canonical `.hermes/bin/hermes gateway run`; hermes-relay.service runs canonical `venv/bin/python -m plugin.relay` from the ha-wake Relay worktree. Both are active. hermes-gateway-oren.service has no unit fragment here; do not invent a restart for it. Recheck unit paths and the client/backend owner list at deployment time.

## Deploy, after review and draining

```bash
set -euo pipefail
umask 077
G3_RUNTIME=/home/brad/.hermes/hermes-agent
G3_BUNDLE=/home/brad/worktrees/hermes-agent-author-198/docs/g3-proof
cd "$G3_BUNDLE"
sha256sum --check SHA256SUMS
# Stop on any failure; never force-apply, stash, reset, or overwrite local changes.
git -C "$G3_RUNTIME" apply --check "$G3_BUNDLE/runtime.patch"
G3_BACKUP=/home/brad/deploy-backups/g3-198-$(date -u +%Y%m%dT%H%M%SZ)
mkdir -p "$G3_BACKUP"
git -C "$G3_RUNTIME" rev-parse HEAD > "$G3_BACKUP/baseline-commit.txt"
git -C "$G3_RUNTIME" diff --binary > "$G3_BACKUP/preexisting.diff"
tar -C "$G3_RUNTIME" -czf "$G3_BACKUP/touched-source-before.tar.gz" -T "$G3_BUNDLE/runtime-files.txt"
cp "$G3_BUNDLE/runtime.patch" "$G3_BACKUP/runtime.patch"
printf '%s\n' 328aa69e22818718fa545905bff81eb199f70a0d > "$G3_BACKUP/patch-commit.txt"
git -C "$G3_RUNTIME" apply "$G3_BUNDLE/runtime.patch"
git -C "$G3_RUNTIME" diff --check
git -C "$G3_RUNTIME" apply --reverse --check "$G3_BUNDLE/runtime.patch"
systemctl --user restart hermes-gateway.service hermes-relay.service
systemctl --user is-active hermes-gateway.service hermes-relay.service
```

Record the backup path, baseline commit, patch commit and existing dirty-overlay state in the deployment receipt. This is a patch overlay, not a claim that the dirty live checkout equals the patch commit. Already-running TUI/serve processes must be reopened by their owners after the approved drain, using their existing launcher/profile/session identity. For an explicitly chosen TUI session, its owner can run:

```bash
/home/brad/.hermes/hermes-agent/.hermes/bin/hermes -p "$APPROVED_PROFILE" chat --resume "$APPROVED_SESSION_ID"
```

Live acceptance: use a separately approved synthetic bot/human session; verify structured authors after reopen, explicit bot prefixes with role=user in TUI/Desktop/Relay, Brad's user rendering, queued order, and immediate subscribed visibility. Do not use production deliveries as test fixtures. Unit tests do not prove these gates.

## Rollback, after the same approved drain

```bash
set -euo pipefail
G3_RUNTIME=/home/brad/.hermes/hermes-agent
G3_PATCH=/home/brad/worktrees/hermes-agent-author-198/docs/g3-proof/runtime.patch
git -C "$G3_RUNTIME" apply --reverse --check "$G3_PATCH"
git -C "$G3_RUNTIME" apply --reverse "$G3_PATCH"
git -C "$G3_RUNTIME" diff --check
systemctl --user restart hermes-gateway.service hermes-relay.service
systemctl --user is-active hermes-gateway.service hermes-relay.service
```

Reopen affected clients as above. If reverse-check fails after another update/change, stop for reconciliation; do not restore the tar wholesale or reset the checkout. Rollback removes this source overlay only. New stored author metadata remains readable and is not deleted; old clients may again render deliveries as users. There is no schema rollback.

## Re-apply after hermes update

Local patches can be lost during update. Preserve code commits `3991b5e4ea986b8861bbc0b79a3b6a7d8b0d03b7` and `328aa69e22818718fa545905bff81eb199f70a0d`, `review.patch`, `runtime.patch` and this worktree outside the live install. First check whether upstream has adopted the author contract. If it has not, prepare a new isolated worktree at the *approved new runtime baseline*, cherry-pick both code commits in order, resolve conflicts there, rerun the focused tests with an existing compatible Hermes test interpreter, and regenerate the runtime patch before review/deployment. Do not replay the old patch blindly or apply main wholesale.

```bash
git -C /home/brad/.hermes/hermes-agent worktree add /home/brad/worktrees/hermes-agent-author-198-reapply -b author-persist-198-reapply HEAD
git -C /home/brad/worktrees/hermes-agent-author-198-reapply cherry-pick 3991b5e4ea986b8861bbc0b79a3b6a7d8b0d03b7 328aa69e22818718fa545905bff81eb199f70a0d
```

`review.patch` is also a portable `git apply` bundle in a clean review worktree. Future conflicts need review; no update hook or automatic deployment was installed.


## G3fix compatibility and history policy

This revision writes only `display_metadata.author` on bot rows, with existing display_kind unchanged; it never emits kind=delivery or adds a schema column. The old SessionDB encoder/decoder retains arbitrary JSON metadata (`hermes_state_messages.py:169-199,359-364`); reopen retires only the specific `_queued_prompt` flag (`hermes_state_sessions.py:542`). Drained author-bearing rows survive synthetic end/reopen tests. Old readers see ordinary role=user rows and may lose attribution after source rollback; no data cleanup or migration is needed. The superseded 3991b5e patch was never deployed, so no production delivery-kind rows need conversion.

Before deploying this revision, record reviewed fix commit `328aa69e22818718fa545905bff81eb199f70a0d` (the patch-commit receipt above is pinned to it). Preserve both code commits (3991b5e plus this fix round) when reapplying after an update, or use the regenerated complete review.patch. Never replay only the original code commit: that restores the reviewed defects.

The model-facing bot prefix deliberately changes wire bytes for already-attributed history once when moving from the old implementation. Drain and reopen affected backends in the approved window; never hot-reload serving seats. Within the revised runtime, identical authored content/sidecars yield identical live and restored wire prefixes. Rollback removes prefixes on future requests but leaves stored author metadata and original content intact; reopen clients again as part of that same drain.

Historical rows lacking a reliable transport author remain unlabeled. No prose inference or bulk private-history backfill is authorized. This round does not deploy, restart services, inspect production messages, or claim physical/live acceptance.
