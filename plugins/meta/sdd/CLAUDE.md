# sdd

- `tools/sdd.py` is the only code that writes specs, ADR statuses, `frozen.json` or the
  archive. Keep it deterministic (no model calls) and its output terse: agents read it.
  Every behavior change gets a case in `tests/test_sdd.py`
  (`python3 -m unittest discover -s plugins/meta/sdd/tests -p 'test_*.py'`).
- `hooks/guard.ts` holds the write rules as pure functions; `hooks/register.tsx` only does
  I/O (`$.fs`, `$.process`, `$.agent.list`) and drawing. Every rule change gets a case in
  `tests/guard.test.ts` (`claude plugin test plugins/meta/sdd`).
- The guard identifies the caller from `tool.call`'s `agentId` → `$.agent.list()` type.
  Plugin agents report `sdd:<name>`; `roleOf` maps only that prefix. Renaming an agent
  file renames its role: update `ROLES` and the agent tables in README and `skills/change`.
- The main conversation is the lead because `register.tsx`'s `prompt.compose` hook appends
  the `sdd:lead` section (`LEAD`). Keep it a short router: the workflow lives in
  `skills/change`. Not an agent with `settings.json` `agent`: a plugin agent's prompt
  would replace Claude Code's whole system prompt.
- `state.json` (phase, branch, base, PR, requires) is written only by `sdd.py` (`start`, `checkpoint`,
  `set-pr`, `requires`, `finish`); the guard refuses other writes. `PHASES` in `sdd.py` and
  `hooks/phase.ts` list the same ids (plus `done`): change both, and `PHASE_STATUSES`
  and the step names in `skills/change`, together. The git and `gh` calls stay in `sdd.py`
  (deterministic, tested against a real bare origin with a fake `gh` in `tests/test_sdd.py`).
- `hooks/phase.ts` maps a change (status, tasks, running agents) to a phase of
  `skills/change`, as pure functions tested in `tests/phase.test.ts`. A new step or
  status in the workflow changes `PHASES`/`phaseOf` and their tests together.
- Every workflow agent has `memory: project`. Claude Code names the directory after the
  agent type with non-alphanumerics folded to `-` (`.claude/agent-memory/sdd-planner/`);
  `memoryDirs` in guard.ts is the only `.claude/` exception for subagents. An agent added
  or renamed keeps its `memory:` line and its role-specific Memory section.
- Guard failure policy: refuse for subagents, allow for the lead (`.catch` in register.tsx).
- The `sdd` tool's per-subcommand roles live in `SDD_RULES` (guard.ts) and are restated in
  the tool description and README. Change all three together.
- Agents call `mcp__sdd__sdd`, never `python3 .../sdd.py`; the guard refuses the latter
  for subagents.
- File formats (Capability and Invariant concepts, CapabilityDelta sections, `<!-- base: -->`,
  citations, task lines, the OKF layout and index/log format of `specs/`, `adrs/` and
  `changes/<id>/`) are parsed by `sdd.py` and described in `skills/formats/SKILL.md` and
  `docs/reference/file-formats.md`. Change them together. The Capability, Invariant and ADR
  templates in `skills/change/templates/*.md.tmpl` are copies of lintel's
  (`specs/.templates/`, `adrs/.templates/`), except that capability.md.tmpl says how a test
  cites a criterion (comment or docstring, not the name) and when to add a Baseline line:
  keep the section names `sdd.py` checks in step.
- `build_indexes` mirrors `okf index` (okf-core `index.rs`) byte for byte, dot-directories
  aside; `TestSync.test_synced_bundles_are_okf_conformant` diffs them when `okf` is on PATH.
- `sdd.py bundle` (`bundle_check`, `check_specs`, `check_adrs`, `check_change`) is the one
  validator of the OKF layout; `collect` (`sdd check`) and `sync` call it, and the `bundle` mod tool in
  `register.tsx` wraps it with `checkBundle` (guard.ts). A new layout rule is a check there
  plus, if repairable, a fixer, with a case in `TestBundle`; fixes must stay idempotent.
- `docs/` is an OKF v0.2 bundle (Diátaxis). Each "change together" set above also has a
  page in `docs/reference/`; `docs/contributing/keep-in-sync.md` maps them. Update it in the
  same commit and add a dated entry to `docs/log.md`.
