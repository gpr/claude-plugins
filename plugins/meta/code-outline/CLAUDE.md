# code-outline

- The hook must fail open: every error path in `outline-gate.sh` ends in `exit 0` with no stdout.
- `enrich.sh` runs `claude -p` with `CODE_OUTLINE_INNER=1` so the nested session's Reads are not intercepted. Keep that guard.
- Outlines go to `.kb/files/` (not `.kb/` root) to avoid collisions with documentalist-agent's OKF files.
- Never write to `.kb/` non-atomically: tmp file + `mv`.
