# code-outline

- The hook must fail open: every error path in `outline-gate.sh` ends in `exit 0` with no stdout.
- `enrich.sh` runs `claude -p` with `CODE_OUTLINE_INNER=1` so the nested session's Reads are not intercepted. Keep that guard.
- Outlines go to `.kb/files/` (not `.kb/` root) to avoid collisions with documentalist-agent's OKF files. The ownership contract is the `.kb/` layout table in both READMEs; change both together. documentalist-agent reads outlines via the `kb_grep` name and the `.kb/files/<path>.md` path, so renaming either breaks it.
- Never write to `.kb/` non-atomically: tmp file + `mv`.
- `hooks/kb.ts` holds the pure outline parsing used by `kb_grep`; `hooks/register.ts` only does I/O (`rg`, `$.fs`). Keep the outline format in `scripts/outline.py` and `kb.ts` in sync, covered by `hooks/kb.test.ts` (`claude plugin test .`).
