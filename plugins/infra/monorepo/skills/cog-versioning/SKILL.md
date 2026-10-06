---
name: cog-versioning
description: Provides cocogito (cog) conventions for conventional commits, semantic version bumping, and changelog generation in this monorepo. Invoked when writing commit messages, running `cog verify`, bumping the version, regenerating the changelog, configuring `cog.toml`, or explaining the conventional-commit format. Trigger phrases include "cog", "cocogito", "conventional commit", "bump version", "changelog", "commit message", "cog verify".
---

Cocogito (`cog`) lives at the repo root. It enforces conventional commits, derives the next version, and generates `CHANGELOG.md`. There is one repo-wide version — no per-package versions.

## Commit format

```
<type>(<scope>)?<!>: <subject>

<body>

<footer>
```

- **type** — one of: `feat`, `fix`, `perf`, `refactor`, `docs`, `test`, `build`, `ci`, `chore`, `revert`, `style`.
- **scope** — package or area: `frontend`, `website`, `<backend>`, `release`, `task`, `deps`, `memory`. Optional but encouraged.
- **subject** — imperative, lowercase, no trailing period, ≤72 chars.
- **breaking change** — append `!` after type/scope (`feat(auth)!: ...`) and add a `BREAKING CHANGE:` footer.
- **body** — explain *why*, not *what*. Wrap at 72.
- **footers** — `Refs: #123`, `Co-authored-by: …`, `BREAKING CHANGE: …`.

Examples:

```
feat(frontend): add dark mode toggle
fix(auth): reject expired refresh tokens
chore(deps): bump pnpm to 9.5.0
docs(memory): document release flow in root CLAUDE.md
feat(billing)!: switch invoices to Stripe v2

BREAKING CHANGE: callers of /invoices must pass api-version: 2
```

## Bumping

`cog bump` reads commits since the last tag and picks the bump:

- Any `feat` → minor
- Only `fix` / `perf` → patch
- Any `BREAKING CHANGE` (or `!` marker) → major

Force a specific bump with `--minor`, `--major`, `--patch`, or `--auto` (default).

`cog bump` also:

- Updates `CHANGELOG.md`.
- Creates an annotated git tag.
- Commits the changelog with a `chore(version): <new>` message.
- Runs pre-bump and post-bump hooks defined in `cog.toml`.

Useful flags:

- `--dry-run` — preview the bump without changing anything.
- `--pre <suffix>` — prerelease (`--pre alpha`, `--pre rc.1`).
- `--skip-ci` — skip CI by appending `[skip ci]` to the bump commit.

## Verifying

- `cog verify "<message>"` — check a single message before committing.
- `cog check` — verify the entire commit history (used in CI).
- `cog check --from-latest-tag` — verify only commits since the last release.

If `cog check` fails on a historical commit, do not rewrite history without asking — it may break shared branches.

## Configuration

`cog.toml` at the repo root defines:

- Allowed types and their changelog sections (`changelog.type` map).
- Pre-bump hooks (`pre_bump_hooks` — usually `task test`, `task lint`).
- Post-bump hooks (`post_bump_hooks` — push branch and tag).
- Branch whitelist (`branch_whitelist`).
- Tag prefix (`tag_prefix = "v"`).
- Authors map (`[[changelog.authors]]`).

When changing the version policy, edit `cog.toml`, do not bypass it. Common edits:

```toml
[changelog]
path = "CHANGELOG.md"
template = "remote"
remote = "github.com"
owner = "<owner>"
repository = "<repo>"

pre_bump_hooks = [
  "task test",
  "task lint",
]

post_bump_hooks = [
  "git push",
  "git push origin {{version}}",
]
```

## Changelog

`CHANGELOG.md` is generated. Never hand-edit. To regenerate without bumping: `cog changelog`. To generate for a specific range: `cog changelog <from>..<to>`. To regenerate the entire file: `cog changelog --all`.

## Multi-backend caveat

Because there is one repo-wide version, a `feat(auth): …` and a `feat(frontend): …` produce a single bump. If you need independent versions per package, this is the wrong tool — switch to per-package `cog` configs or a different release manager. Flag this if it ever comes up.
