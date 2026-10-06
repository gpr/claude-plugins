---
description: Run the full release flow — cog bump, changelog, tag, push
argument-hint: [auto|patch|minor|major]
allowed-tools: Bash, Read
---

Run the full release flow.

Load the `cog-versioning` skill before starting if it is not already in context.

## Pre-flight

1. Confirm the working tree is clean: `git status --porcelain`. If not, stop and ask.
2. Confirm the current branch is in `cog.toml`'s `branch_whitelist` (typically `main` or `master`). Read `cog.toml` to verify.
3. Run `cog check --from-latest-tag` to confirm history since the last release is clean. If it fails, stop and surface the offending commits.
4. Run `task test` and `task lint`. If either fails, stop. Do not bypass.

## Bump

5. Determine bump type:
   - If $ARGUMENTS is one of `auto`, `patch`, `minor`, `major`, use that flag (`--auto`, `--patch`, `--minor`, `--major`).
   - Otherwise, run `cog bump --dry-run` to preview, show the user, and ask which bump to use.
6. Run `cog bump --<type>`. This updates `CHANGELOG.md`, commits the change, and creates an annotated tag.
7. Show the resulting commit (`git log -1 --stat`) and tag (`git tag -l --sort=-creatordate | head -1`) to the user.

## Push

8. Ask before pushing.
9. On confirmation: `git push && git push --tags`.

## Failure handling

- If `cog bump` fails partway, do not retry blindly. Report the current state (latest commit, latest tag, working tree) and ask.
- Never run `git tag -d`, `git reset --hard`, or `git push --force` without explicit user confirmation, especially after a failed bump.
- If a pre-bump hook fails, fix the underlying issue and re-run `cog bump` — do not edit `cog.toml` to skip the hook.
