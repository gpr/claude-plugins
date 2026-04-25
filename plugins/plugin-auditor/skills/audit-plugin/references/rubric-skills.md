# Skills rubric

Applied to every `skills/<name>/SKILL.md`.

## Frontmatter

- `name` is kebab-case and matches the directory.
- `description` is in **third person** ("Audits X", not "I audit X" or "Use this to audit X").
- `description` names concrete trigger phrases or user intents Claude can match. Vague phrases ("for working with X") are a defect.
- For user-invoked skills: `argument-hint` and `allowed-tools` are present. `allowed-tools` lists only what the body actually uses.
- No unused frontmatter fields.

## Body

- Imperative voice. Instructions are **for Claude**, not **to the user**.
- Target length: 1,500–2,000 words. Flag bodies above 2,500 words that could be split via progressive disclosure.
- Progressive disclosure: detailed reference material (long examples, config dumps, large tables) belongs in `references/*.md`, not SKILL.md.
- No redundant restatement of the skill name or description.
- No greetings, no narration of what the skill "is" — jump to procedure.
- Code blocks are runnable as-is or clearly marked as templates.
- Hard rules / forbidden actions appear in a dedicated section at the end.

## Trigger strength

- At least two distinct trigger phrases in `description`.
- Triggers name user vocabulary (what the user would actually type), not internal jargon.
- If the skill only makes sense with an argument, the description says so.

## Proposals you may emit

- Rewrite weak descriptions to third-person + explicit triggers.
- Remove greetings, filler, duplicate restatement.
- Collapse verbose prose into bullets.
- Move oversized examples to `references/` (create the file) and insert a reference line.
- Tighten `allowed-tools` to the minimal set.

## Leave alone

- Domain content correctness (not your area).
- Author voice and stylistic preferences that do not violate the rubric.
