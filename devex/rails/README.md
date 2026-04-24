# rails-api-backend (Claude Code plugin)

A Claude Code plugin for working on a Rails API-only backend.

## What's in it

- **Monitor** (`rails-dev-log`) — tails `log/development.log` in the background and surfaces errors, 5xx responses, and exceptions as notifications to Claude. Filtered so routine request noise doesn't flood the session.
- **Skills**
  - `rails-routes` — inspect and scaffold routes
  - `rails-migrations` — generate migrations, with a production-safety checklist
  - `rails-api-conventions` — controller shape, status codes, serialization, auth, pagination
- **Agent** (`rails-backend`) — a specialized subagent for multi-file backend work
- **Hook** (`PostToolUse` on `Write|Edit`) — runs `rubocop --autocorrect` on edited Ruby files, and optionally runs the matching RSpec file

## Install (local dev)

From your Rails project root:

```bash
claude --plugin-dir /path/to/rails-api-backend
```

On first run you'll be prompted for:

- `log_path` — usually `log/development.log`
- `error_pattern` — leave blank for the default (matches `ERROR|FATAL|Completed 5xx|Exception|NoMethodError|ActiveRecord::|ActionController::|ArgumentError|RuntimeError`)
- `run_tests_on_edit` — `true` or `false`. When `true`, the hook runs the matching `_spec.rb` after every edit to `app/**` or `lib/**`. Noisy but fast feedback; turn off if it gets in the way.

## Requirements

- Claude Code v2.1.105 or later (required for plugin monitors)
- `tail`, `grep` with `--line-buffered` (standard on Linux/macOS)
- Optional: `bundle`, `rubocop`, `rspec-core` in the Gemfile for the hook to do anything useful
- Optional: `jq` for robust hook payload parsing (falls back to grep if missing)

## Caveats

- **Monitors only run in interactive sessions.** Headless/SDK usage won't trigger the log tailer. Skills, agent, and hooks still work in headless.
- **Disabling mid-session doesn't stop the monitor** — it dies when the session ends. This is upstream behavior, not a bug here.
- The default error pattern is opinionated. If it surfaces too much (or too little), override it via `error_pattern` in user config.

## Layout

```
rails-api-backend/
├── .claude-plugin/plugin.json
├── monitors/monitors.json
├── scripts/
│   ├── tail-filtered.sh      # log tailer with regex filter
│   └── post-edit.sh          # rubocop + spec runner
├── skills/
│   ├── rails-routes/SKILL.md
│   ├── rails-migrations/SKILL.md
│   └── rails-api-conventions/SKILL.md
├── agents/rails-backend.md
├── hooks/hooks.json
└── README.md
```
