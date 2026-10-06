---
name: agent-instructions-optimizer
description: Rewrites the body of an agent instruction file (any `agents/*.md` or similar system-prompt markdown) to apply Anthropic's prompt-engineering best practices while aggressively cutting tokens. Use ONLY when the user explicitly invokes this skill — e.g. `/agent-instructions-optimizer <path>`, "optimize this agent", "tighten agent instructions", "compress this agent prompt". Preserves YAML frontmatter (`description`, `tools`, `model`, etc.) byte-for-byte. Shows a unified diff and reports char/4 token delta before writing.
---

# Agent Instructions Optimizer

Rewrite the **body** of an agent instruction file to be tighter and more effective. Frontmatter stays untouched. User sees a diff and approves before any write.

## Inputs

- **Required**: path to one `*.md` file with YAML frontmatter and a system-prompt body.
- If the user says "optimize this agent" without a path, ask for one (or offer candidates from `agents/` directories in the cwd).

## Invocation discipline

This skill is explicit-invocation only. Do not trigger from proximate context (e.g. the user editing an agent file). Trigger only when the user names the skill or asks for agent-instruction optimization directly.

## Workflow

1. **Read** the target file. Split at the closing `---` of the frontmatter. Everything after that line is the body. Everything up to and including it is frontmatter.
2. **Snapshot** the body. Compute `chars_before = len(body)`; `tokens_before ≈ chars_before / 4`.
3. **Tight-draft gate.** Score the body against the rubric below *before* rewriting. If the body is already near-optimal, stop and report instead of rewriting. A draft is near-optimal when **all** of the following hold:
   - Opens with a one-line role/scope statement.
   - Instructions are already imperative (no "you should", "please", "try to").
   - No rationale-only paragraphs; any "why" is tied to edge-case judgment.
   - No duplicated rules across sections.
   - Output contract (if any) is a literal template, not prose.
   - Stop conditions / hard rules present and concrete.
   - No filler headers (sections with one bullet).

   If the gate passes, output:
   ```
   File: <path>
   VERDICT: already near-optimal — no rewrite proposed.
   TOKENS (body, char/4): ~<n>

   Why: <one line per rubric clause the draft already satisfies>
   ```
   Then stop. Do **not** produce cosmetic word-level edits (e.g. "Rewriting" → "Rewrite", "You may not propose" → "Out of scope"). Those are not worth a diff.

   If the user replies "force rewrite" or "nit-pick anyway", proceed to step 4 with reduced aggressiveness (target ≤10% cut) and flag each change as cosmetic.
4. **Rewrite** the body applying the rules below.
5. **Validate** the rewrite against the preservation checks.
6. **Show a unified diff** of the body only (`diff -u old new`) and the token delta:
   ```
   TOKENS: ~<before> → ~<after> (−<pct>%)    [char/4 heuristic]
   ```
7. **Ask for approval** before writing. If approved, write back: original frontmatter + `\n` + new body. Do not touch frontmatter bytes.
8. If the user rejects, offer: tweak a specific section, be less aggressive, or abort.

## Rewrite rules

Applied in order. Cut first, then reword.

### Cut

- Politeness, framing, meta: "please", "your job is to", "I'd like you to", "this is important because…".
- Redundant restatements of the same rule.
- Rationale that doesn't shift behavior. Keep rationale only when it helps Claude judge edge cases (feedback/project memory style: "Why: …"). Drop rationale that's just reassurance.
- Hedges: "try to", "when possible", "generally", "if applicable".
- Examples that merely restate an adjacent rule.
- Lists of prohibitions a single positive rule covers.
- Section headers with one item underneath — merge into parent.
- Self-evident software hygiene ("write clean code", "follow best practices").

### Compress

- Prose → imperative ("You should make sure to check X" → "Check X").
- Multiple related rules → one general rule.
- Bullet + explanatory sentence → bullet only, unless the explanation changes behavior.
- Repeated phrase across bullets → lift into parent.

### Keep (never cut for token count)

- Exact output formats, templates, schemas.
- Tool names and when-to-use conditions.
- File paths, command strings, version pins, env vars.
- Stop conditions, failure handling, escalation rules.
- Named roles and role boundaries ("Only invoked by X").
- First and last instructions (positional weight matters).

### Apply best-practice structure

- **Role up front** — one line, no competing personas.
- **Scope / when-invoked** — who calls this agent, what's out of scope.
- **Workflow or rules** — numbered steps if sequential, bullets if independent.
- **Output contract** — exact format the caller expects.
- **Stop conditions / failure handling** — what to do when stuck or blocked.
- Use markdown headers for sections; reserve XML tags for long (>500 tokens) bodies where structural parsing helps. Don't add XML to short prompts.
- Put non-negotiable constraints last as well as first.

## Preservation checks (run before showing diff)

Reject the rewrite and retry if any fails:

1. Every tool name mentioned in the original appears in the rewrite (unless the original mentioned it only to forbid it and the forbid rule survives in another form).
2. Every literal string the caller depends on (output template, command, file path, schema key) survives verbatim.
3. Every stop/escalation/permission rule survives in meaning.
4. Frontmatter bytes are identical to the input.
5. Rewrite is shorter than the original. If not, something went wrong — re-examine.

## Aggressiveness

Default: aggressive. Target 30–60% body reduction on verbose drafts; 10–25% on already-tight drafts. Never compress to the point of ambiguity — terse ≠ cryptic. If the original is already near-optimal, say so and skip the rewrite.

## Output to user

```
File: <path>
TOKENS (body, char/4): ~<before> → ~<after> (−<pct>%)

<unified diff of body>

DROPPED SECTIONS (whole sections / paragraphs removed):
- "<section heading or first 6 words>" — <one-line reason, e.g. "narrative retread of workflow", "user-specific config leak", "meta-commentary about the agent">
- …
(omit the whole list if no whole-section removals; only fine-grained edits)

COMPRESSION NOTES:
- <what categories were tightened — e.g. "converted first-person prose to imperatives", "merged 3 overlapping rules", "stripped hedges">

RISKS:
- <any behavior-preservation call that was close, or a section the user might still want — else "none">

Apply? [y/N / tweak / abort]
```

The **DROPPED SECTIONS** list is non-negotiable when whole sections are removed — it's the user's veto surface. If the user says "keep <section>", restore it verbatim and re-show the diff.

Write the file only after an affirmative response.

## What this skill does NOT do

- Does not modify frontmatter. If the user wants `description`/`tools`/`model` tuned, tell them to use a different tool (e.g. `plugin-auditor:agents-auditor`).
- Does not invent project context. If a section references a tool or convention the agent doesn't establish, leave the reference intact.
- Does not touch multiple files in one invocation. One file per run; loop externally if needed.
- Does not add personality, emojis, or flourish.
