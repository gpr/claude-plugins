# Hooks rubric

Applied to `hooks/hooks.json` and every `scripts/*.sh` it references.

## Schema

- Top-level keys match a current hook event: `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `Stop`, `SubagentStop`, `SessionStart`, `SessionEnd`, `UserPromptSubmit`, `PreCompact`, `Notification`, `PermissionRequest`.
- `matcher` is specific. Wildcards (`*`) on `PreToolUse` are almost always wrong — they run on every tool call and inflate latency.
- `command` paths use `${CLAUDE_PLUGIN_ROOT}`. Hardcoded absolute paths (`/Users/...`, `/home/...`) are a defect.
- `timeout` (seconds) is set when the command can run long. Absent timeout on a script that shells out is a defect.

## Script quality

- `shellcheck scripts/*.sh` is clean. Run it via `Bash` and record findings.
- `set -euo pipefail` at the top of every non-trivial script.
- Input from stdin (the hook payload JSON) is parsed with `jq` when the script reads it; never `grep` + `sed` on JSON.
- No hardcoded paths, no author-specific directories, no machine-specific assumptions.
- Exit codes are meaningful: `0` = allow, non-zero = block/error depending on the hook.

## Security

- User input from the hook payload is never interpolated into a shell command unquoted.
- No secrets in the script or in `hooks.json`.
- Write operations are confined to project-relative paths.

## Event fit

- The chosen event matches the intent:
  - Validation that should block → `PreToolUse`.
  - Post-action side effects (lint, format) → `PostToolUse`.
  - Cleanup → `Stop` / `SessionEnd`.
  - Prompt rewriting → `UserPromptSubmit`.
- Flag hooks using the wrong event (e.g. formatting on `PreToolUse`, which blocks the edit).

## Proposals you may emit

- Replace hardcoded paths with `${CLAUDE_PLUGIN_ROOT}`.
- Tighten matchers.
- Add `set -euo pipefail` and `timeout` where missing.
- Replace ad-hoc JSON parsing with `jq`.
- Quote shell variables.

## Leave alone

- Business logic inside the scripts (not your area).
- Hook presence/absence decisions — propose in the report, do not add hooks as edits.
