# Monitors rubric

Audit clauses for `monitors/monitors.json`.

- `monitors.json` parses as JSON (`jq .`). Syntax errors are a defect.
- Each monitor entry has `name`, `command`, and `trigger` (interval or event). Missing fields are a defect.
- `command` uses `${CLAUDE_PLUGIN_ROOT}` — no hardcoded paths.
- Interactive-only caveat stated in README when a monitor is present (monitors do not run in headless/SDK mode).
- Interval choices are justified — a 5-second poll on a log file is typically wasteful; prefer event-driven `tail -F` patterns.

## Proposals you may emit

- Fix `monitors.json` schema errors.
- Replace hardcoded paths with `${CLAUDE_PLUGIN_ROOT}`.
- Replace short polling intervals on log files with event-driven patterns.

## Leave alone

- Addition or removal of monitor entries — recommendations only.
- The monitored command's business logic.
