# Agents rubric

Applied to every `agents/<name>.md`.

## Frontmatter

- `name` is kebab-case and matches the filename.
- `description` leads with **when to trigger**, not what the agent is. Claude routes on this field.
- `description` names concrete scenarios. Include `<example>` blocks when the agent's trigger conditions are non-obvious.
- `model` is one of `opus` / `sonnet` / `haiku` and is justified by the task:
  - `haiku` — trivial dispatch, fixed-format checks.
  - `sonnet` — standard multi-file work.
  - `opus` — architectural reasoning, cross-cutting refactors.
- `effort` (`low`/`medium`/`high`) and `maxTurns` are set when present; a 30-turn default is fine for most agents.
- `tools` list (if present) is minimal — every entry must be referenced in the system prompt.

## System prompt

- Imperative voice.
- Opens with the agent's role in one sentence; no repetition of the description.
- Working rules are numbered, each ≤3 lines.
- Output format section is explicit when the agent is called programmatically.
- No conversational padding, no "I'll help you…" prose.
- Security defaults (no SQL injection, no secret leakage, etc.) stated once when applicable; not restated per rule.

## Trigger strength

- Description names user vocabulary + file/symbol patterns where relevant.
- For auto-triggered agents: include at least one `<example>` block showing user input → assistant trigger.
- For orchestrator-only agents: state "Only invoked by <orchestrator>. Do not trigger on user input directly."

## Proposals you may emit

- Rewrite descriptions to lead with trigger conditions.
- Remove duplication between `name`, `description`, and the system prompt's opening line.
- Tighten numbered rules.
- Collapse verbose "you should…" prose into imperatives.
- Add `<example>` blocks where the trigger is ambiguous.

## Leave alone

- Domain expertise content — the agent's subject-matter advice is not your area.
- `model` downgrades unless the task is demonstrably trivial.
