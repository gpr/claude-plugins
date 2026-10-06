---
name: cog-config-doctor
description: Triage `cog.toml` configuration failures in this monorepo — pre-bump hook hangs or failures, branch_whitelist mismatch, tag_prefix breaking `cog check`, post-bump push errors, broken changelog templates. Trigger phrases include "configure cog", "edit cog.toml", "pre-bump hook", "release fails", "cog hook", "branch_whitelist", "cog bump stuck", "cog check fails".
---

`cog.toml` lives at the repo root and governs version policy. When `cog bump` or `cog check` misbehaves, the cause is almost always one of the patterns below. Diagnose, do not bypass.

## Pre-bump hook hangs or fails

Symptoms: `cog bump` prints `[pre-bump] running …` and never returns, or returns non-zero with the hook command's stderr.

- Identify the offending hook from `pre_bump_hooks` in `cog.toml`.
- Run the hook command directly (e.g. `task test`) and reproduce. Hooks inherit the user's shell, env, and `$PATH`.
- Common culprits: tasks waiting on stdin (interactive prompts), tasks that shell out to a dev server (`task frontend:dev`), or tests reading from a missing `.env`.
- Fix the underlying task. Do **not** delete the hook from `cog.toml` to "unstick" the release.

## branch_whitelist mismatch

Symptoms: `cog bump` exits with `Error: current branch '<x>' is not in branch_whitelist`.

- Read `cog.toml`: `branch_whitelist = ["main"]` or similar.
- Either switch to a whitelisted branch (`git switch main`) or — if the project genuinely releases from another branch — add it to the whitelist via a `chore(release):` commit.
- Never bump from a feature branch "just this once" by editing the whitelist temporarily.

## tag_prefix breaks `cog check`

Symptoms: `cog check` reports `no previous tag found` despite tags existing, or `cog bump` produces tags with the wrong prefix.

- Confirm `tag_prefix` in `cog.toml` (commonly `tag_prefix = "v"`) matches existing tags (`git tag -l | head`).
- If the repo has historical untagged-prefix tags, decide whether to retag or to set `tag_prefix = ""`. Discuss with the user — retagging rewrites history.

## post-bump push fails

Symptoms: `cog bump` succeeds locally (tag + commit created) but `post_bump_hooks` (`git push`, `git push origin {{version}}`) fail.

- Inspect the failure: auth, protected branch, or upstream not set.
- Do **not** rerun `cog bump` — the bump already happened. Push manually after fixing auth: `git push && git push --tags`.
- If the bump must be reverted, surface that to the user; never run `git tag -d` or `git reset --hard` without explicit approval.

## Broken changelog template

Symptoms: `cog changelog` errors with template parse failure, or output references the wrong owner/repo.

- Verify the `[changelog]` block: `template`, `remote`, `owner`, `repository`. `template = "remote"` is the default for GitHub.
- For custom templates, validate Tera syntax in a scratch file before saving.

## Authors map drift

Symptoms: changelog credits unknown emails or leaves `Co-authored-by` entries unmatched.

- Each contributor should appear in `[[changelog.authors]]` with `signature` (commit email) and `username` (GitHub).
- Add new entries when a teammate's first commit lands.

## When in doubt

Run `cog --help` and `cog bump --dry-run`. The dry-run reproduces the full flow including pre-bump hooks without creating commits or tags. Use it before every non-routine release.
