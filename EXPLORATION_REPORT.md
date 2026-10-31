# Exploration Report — Tool Usage, Instruction Sources, Priorities

Session date: 2026-10-31 · Working dir: `/opt/gregory.rome/workspaces/gpr/claude-plugins` · Mode: auto (background job), sandbox on, Concise style · Collector: v1.0.0

All findings below were checked against files and settings on disk, not assumed.

---

## 1. Instruction sources

| Code | Source | Scope |
| --- | --- | --- |
| SYS | Claude Code system prompt, tool descriptions, background-job rules | Every turn |
| SBX | Seatbelt sandbox (`~/.claude/settings.json` `sandbox`), 50 `permissions.deny` rules, harness write protections on `.claude/**` | Every Bash call / file edit |
| HOOK | User `PreToolUse` (Bash `rm` with `-r`+`-f` → blocked); project `PostToolUse` (JSON validity check, `chmod +x` on `plugins/*/scripts/*.sh`) | Bash `rm *`; Edit/Write |
| G | `/Users/gregory.rome/PERSONAL_AND_CONFIDENTIAL/.claude/CLAUDE.md` (33 lines), loaded | All projects |
| P | `/opt/gregory.rome/workspaces/gpr/claude-plugins/CLAUDE.md` (99 lines), loaded | This repo |
| N | `plugins/backend/python-uv-project/CLAUDE.md`, `plugins/backend/rails/CLAUDE.md`, `plugins/frontend/react-vite-stack/CLAUDE.md`; on demand | When working in those plugin dirs |
| R | `rules/instructions.md` (path-scoped: `**/CLAUDE.md`, `.claude/{skills,agents,rules}/**`), `rules/testing.md` (path-scoped: test files); loaded only when paths match | Matching files only |
| MCP | `claude-artifacts` (publish finished work), `branch-usage` | Every turn |
| SKILL | Skill and agent descriptions in the system prompt | When a trigger matches |

### Priority weight scale

| Weight | Meaning | Can I deviate? |
| --- | --- | --- |
| **5 — Enforced** | Blocked/required by sandbox, deny rule, hook, or harness | No |
| **4 — Mandatory** | Explicit must/never/always rule or required procedure | Only with explicit user approval |
| **3 — Preferred** | "Prefer X over Y" / default tool choice | Yes, with a stated reason |
| **2 — Conditional** | Applies only when a trigger condition is met | Yes, when the condition is absent |
| **1 — Opportunistic** | Available, no instruction drives it | Use only when it fits |
| **0 — Unavailable** | Instructed but not usable this session | n/a — fallback required |

**Conflict resolution order:** `Enforced (SBX/HOOK/SYS safety) > user's message in chat > P > G > H > SYS defaults. CLAUDE.md overrides default harness behavior, but never safety or enforcement.`

---

## 2. Tool matrix

Each section lists tools by priority weight, highest first; ties keep catalog order.

### 2.1 Local exploration (core)

| Tool | How I use it | Source(s) | Weight |
| --- | --- | --- | --- |
| `trash` | Only delete path; `rm -rf` is hook- and deny-blocked; runs outside the sandbox | G ("recoverable delete"), HOOK (rm guard), SBX (`Bash(rm -rf *)` deny) | 5 |
| `Read` | Default for reading files; never `cat`/`head`/`tail` via Bash | SYS ("Avoid using this tool to run cat") | 4 |
| `jq` / `yq` | Settings, `plugin.json`, `hooks.json`, frontmatter; never ad-hoc scripts | G ("use directly, never custom scripts"), P (Validation step 1) | 4 |
| `git add` (specific files) | Stage named files; `git add -p` when audit fixes and features share files | SYS (commit before finishing a worktree job), P (Tips: "use `git add -p`") | 4 (worktree changes) / 2 (otherwise) |
| `git` (read-only) | `git status -sb`, `log`, `diff --stat` for state; runs outside the sandbox | SYS (git guidance), SBX (`excludedCommands: git`) | 3 |
| `Bash` + `ast-grep` | Code-pattern search (signatures, imports, class defs) | G ("prefer over Grep or rg") | 3 |
| `Bash` + `rg` | Text search across `plugins/**/*.md`, `hooks.json`; the working search tool since `Grep` is not exposed | P (allow `Bash(rg *)`) | 2 |
| `Bash` + `fd` | Locate plugin dirs/files by name | P (allow `Bash(fd *)`) | 1 |
| `LSP` (deferred) | Unavailable: every `*-lsp` plugin is `false` in `plugins_effective` | SKILL (`python-uv-project:lsp`) | 0 |
| `Grep` / `Glob` built-ins | Unavailable: not exposed this session; use `rg` / `fd` | G (names Grep, lines 8, 10, 11) | 0 |

### 2.2 Delegation and broad search

| Tool | How I use it | Source(s) | Weight |
| --- | --- | --- | --- |
| `Workflow` | Only on explicit opt-in ("ultracode", "use a workflow") | SYS ("ONLY call this tool when … opted into") | 5 |
| `Agent` → `Explore` | Noisy multi-directory sweeps where only the conclusion matters | SYS ("spawn a subagent when you have the Agent tool") | 2 |
| `Agent` → `claude-code-guide` | Questions about Claude Code features, hooks, plugin fields | SKILL ("questions … about Claude Code") | 2 |
| `Agent` → `docs-cross-checker` | When plugin-validator flags a field as unknown | P (Tips: "delegate to `@agent-docs-cross-checker`") | 2 |
| `Agent` → okf-search | Listed, but `okf_bundles` is empty | SKILL | 1 |
| `Agent` → `Plan` | Design before large changes | SKILL | 1 |
| `repomix` CLI | Pack a plugin dir for a whole-tree read; no instruction drives it | none (`/opt/homebrew/bin/repomix`) | 1 |
| `Agent` → documentalist | Unavailable: plugin enabled, but agent not exposed and `kb_dir` is false | none | 0 |
| repomix MCP | Unavailable: all three `repomix-*` plugins are `false` | none | 0 |
| `Agent` → `plugin-dev:plugin-validator` | Unavailable: `plugin-dev@claude-plugins-official` is `false`; agent not listed | P ("review it with `@agent-plugin-dev:plugin-validator`") | 0 |

### 2.3 Documentation and external lookups

| Tool | How I use it | Source(s) | Weight |
| --- | --- | --- | --- |
| `WebFetch` / `WebSearch` | Deferred (load via ToolSearch); fetch `code.claude.com/docs/en/plugins-reference.md`; check registries before adding deps | G ("verify current stable version"), P (Tips: "via WebFetch") | 4 (before adding deps) / 2 (otherwise) |
| `ToolSearch` | Load deferred schemas before calling them | SYS ("calling them directly will fail") | 4 |
| context7 MCP | Unavailable: unauthenticated (only `authenticate` tools exposed); fall back to WebFetch | G ("check docs via context7") | 0 |

### 2.4 Process and interaction

| Tool | How I use it | Source(s) | Weight |
| --- | --- | --- | --- |
| `Edit` / `Write` | Read before edit; blocked in the shared checkout until a worktree exists; `.json` writes re-validated by hook | SYS ("This is enforced"), HOOK (PostToolUse `jq .`), SBX (`settings.json` write-denied) | 5 |
| `Skill` | Invoke on `/<skill>` and on matching triggers | SYS ("invoke it via Skill") | 4 |
| `AskUserQuestion` | Before interface/schema/CI/settings changes; otherwise decide and state the assumption | G ("Ask first on big decisions") | 4 (big decisions) / 1 (otherwise) |
| `dangerouslyDisableSandbox` | Only after a sandbox-caused "Operation not permitted"; never for credentials | SYS ("Do NOT … unless"), P (Sandbox gotchas) | 4 |
| Memory | Save user/feedback facts; dir exists with 0 files and no `MEMORY.md` | SYS (Memory section) | 2 |
| `ReportFindings` | Only when code-review instructions ask for typed findings | SYS (tool description) | 2 |
| `Artifact` | Unavailable: not exposed; publishing goes through the `claude-artifacts` MCP (2.5) | none | 0 |

### 2.5 Out of scope for local exploration

| Tool | Source | Weight |
| --- | --- | --- |
| `claude-artifacts` MCP | MCP ("publishes it and gives the person the link") | 2 |
| `branch-usage` MCP | MCP | 1 |
| `pdf-viewer` MCP | SKILL (`pdf-viewer:*`) | 1 |
| `plugin:context7:context7` MCP | unauthenticated (see 2.3) | 0 |
| `plugin:atlassian:atlassian` MCP | unauthenticated | 0 |
| `plugin:design:*` MCPs (atlassian, figma, intercom, linear, notion, slack) | unauthenticated | 0 |
| `plugin:engineering:datadog` MCP | unauthenticated | 0 |
| `plugin:marketing:*` MCPs (ahrefs, canva, klaviyo, similarweb, supermetrics) | unauthenticated | 0 |
| `plugin:product-management:*` MCPs (amplitude, amplitude-eu, clickup, fireflies, monday, pendo, similarweb) | unauthenticated | 0 |
| `devel`, `incident_io` MCPs (user scope) | configured in `mcp_servers_configured`, no tools in session | 0 |

---

## 3. Exploration procedure (priority-ordered)

1. **Scope check (W4, G/P)** — stay in the project root; state a reason before widening.
2. **State (W3)** — `git status -sb`, `git log --oneline -10`, `git diff --stat`.
3. **Local context (W4/W2)** — nearest `CLAUDE.md` / `README.md` to the target; read not-loaded rules by hand when touching matching paths; OKF `index.md` only for non-vendored bundles.
4. **Targeted search (W3–4)** — `rg -n '<pattern>' plugins/<domain>/<plugin>` and `fd '<name>' plugins` (no `Grep`/`Glob` this session; `.gitignore` is not allowlist-style, so no `--no-ignore`) → `Read` the narrowed files. `ast-grep` / LSP only for code symbols.
5. **Structured data (W4)** — `jq` / `yq` on settings, manifests, frontmatter.
6. **Broad questions (W2)** — `Agent` → `Explore` for noisy multi-directory sweeps. No `Workflow` without opt-in.
7. **Docs (W3)** — `WebFetch` of `code.claude.com/docs/en/*.md` (load via `ToolSearch`) or the `docs-cross-checker` agent; context7 is unauthenticated.
8. **Exclusions** — skip nothing sensitive (`sensitive_top_level` is empty); skip `.vscode/` and vendored dirs unless the task requires them.
9. **Decisions (W4)** — ask before interface, schema, settings or CI changes; otherwise decide, state the assumption, and continue.

---

## 4. Proposed improvements

Ranked by severity tier, then check ID. Each item is a proposal only; none has been applied.

| # | Check | Problem (verified) | Proposal | Files |
| --- | --- | --- | --- | --- |
| 1 | C01 | SYS requires temp files in `$CLAUDE_JOB_DIR/tmp`, but writes there fail: `operation not permitted: …/.claude/jobs/63c6a677/tmp/tooling-audit.json` (sandbox `denyWithinAllow` lists `…/.claude/jobs`). `append_targets` is empty, so this is a session finding, not a collector one. | Remove `…/.claude/jobs` from the harness deny list for `tmp/` (a Claude Code change), or tell background jobs to use `$TMPDIR`. | `/Users/gregory.rome/PERSONAL_AND_CONFIDENTIAL/.claude/settings.json` |
| 2 | C02 | P mandates `@agent-plugin-dev:plugin-validator` (lines 12, 62) and `/plugin-dev:create-plugin` (line 7), but `plugins_effective["plugin-dev@claude-plugins-official"]` is `false` in the checked-out tree. P line 63 mandates `/plugin-auditor:audit-plugin`; `plugin-auditor` is in `marketplace.json` but enabled nowhere. Note: `origin/main` (checkout is behind 89) already sets `enabledPlugins: {"plugin-dev@claude-plugins-official": true}`, so `git pull` fixes the first half. | Run `git pull --ff-only`, then add `"plugin-auditor@gpr-plugins": true` to project `enabledPlugins`, or change P step 4 to "load with `claude --plugin-dir plugins/meta/plugin-auditor`". | `/opt/gregory.rome/workspaces/gpr/claude-plugins/.claude/settings.json` |
| 3 | C03 | G line 8 ("prefer over Grep or rg") and lines 10–11 (`jq`/`yq` "replaces Grep/…") name the `Grep` built-in, which is not exposed this session. | Change line 8 to "prefer over `rg` for code patterns" and drop `Grep` from the replaces cells on lines 10–11. | `/Users/gregory.rome/PERSONAL_AND_CONFIDENTIAL/.claude/CLAUDE.md` |
| 4 | C04 | `sandbox_path_issues` lists 4 `~` paths. The session's effective config expands `~/.cache` and `~/.config` to `/Users/gregory.rome/…`, but `allowUnixSockets` still shows the literal `~/.orbstack/run/docker.sock`, which can match nothing. | Replace with `"/Users/gregory.rome/.orbstack/run/docker.sock"` in `sandbox.network.allowUnixSockets`. | `/Users/gregory.rome/PERSONAL_AND_CONFIDENTIAL/.claude/settings.json` |
| 5 | C05 | context7 is unauthenticated (only `authenticate` / `complete_authentication` exposed) though G lines 7 and 33 route library docs through it. About 20 other plugin MCPs are unauthenticated, and user-scope `devel` / `incident_io` expose no tools. | Run `/mcp` and authenticate context7; run `claude mcp list` for the `devel` / `incident_io` errors, or remove unused ones with `claude mcp remove <name> -s user`. | `/Users/gregory.rome/PERSONAL_AND_CONFIDENTIAL/.claude.json` |
| 6 | C10 | G line 31 and P line 13 both state the Conventional Commits rule with the same type lists and the refactor-vs-fix rule (~2 duplicated lines). | Reduce P line 13 to the P-specific part ("Use `fix` only for released issues") and drop the type lists. | `/opt/gregory.rome/workspaces/gpr/claude-plugins/CLAUDE.md` |
| 7 | C13 | `memory.memory_files` is 0 and `index_exists` is false. | Save one project memory (e.g. which validator plugins must be enabled), or leave empty if unwanted. | `/Users/gregory.rome/PERSONAL_AND_CONFIDENTIAL/.claude/projects/-opt-gregory-rome-workspaces-gpr-claude-plugins/memory/MEMORY.md` |

---

## 5. Verification evidence

- `instruction_files`: G (always, 33 lines), P (always, 99 lines), 3 × N (on-demand), 2 × R (path-scoped); no H and no `not-loaded` entries, so C08 and C09 did not trigger.
- `plugins_effective`: `plugin-dev@claude-plugins-official: false`, all `*-lsp` false, all `repomix-*` false, `context7@claude-plugins-official: true`, `documentalist-agent@gpr-plugins: true`. `git diff main HEAD -- .claude/settings.json` (worktree is on `origin/main`) shows `plugin-dev@claude-plugins-official: true` added upstream.
- `plugin_matches_for_refs`: `context7` → `true` (enabled, but unauthenticated per session tools).
- `instruction_tool_refs`: G `Grep` lines 8, 10, 11; P `WebFetch` line 93; P `jq` line 60.
- `sandbox_path_issues`: 4 entries (`~/.cache` ×2, `~/.config`, `~/.orbstack/run/docker.sock`); session sandbox shows `allowWithinDeny: ["/Users/gregory.rome/.cache","/Users/gregory.rome/.config"]` and `allowUnixSockets: ["/var/run/docker.sock","~/.orbstack/run/docker.sock"]`.
- Job tmp write: `(eval):1: operation not permitted: /Users/gregory.rome/PERSONAL_AND_CONFIDENTIAL/.claude/jobs/63c6a677/tmp/tooling-audit.json`.
- `settings_files[].hook_events`: user `PreToolUse` (`if: Bash(rm *)`, "BLOCKED: Use trash instead of rm -rf"), project `PostToolUse`; G's "blocked by hooks" matches, so C11 did not trigger.
- `cli_tools`: all 14 paths present (plus `shellcheck`), so C06 did not trigger.
- `gitignore.allowlist_style: false`, so C07 did not trigger. `kb_dir: false` and the documentalist agent is not exposed, so C12 did not trigger.
- `memory`: `exists: true`, `memory_files: 0`, `index_exists: false` → C13.
- `append_targets: []`, `okf_bundles: []`, `sensitive_top_level: []`, no `inactive-copy` settings, so C01 (collector side) and C14 did not trigger.
- `mcp_servers_configured`: `devel`, `incident_io` (user); neither has tools in the session.
- `git`: branch `main`, 0 modified, 2 untracked (`.vscode/`, `plugins/dev/`), `main...origin/main [behind 89]`.
- No previous `EXPLORATION_REPORT.md` existed, so there is no state diff.
- `git check-ignore -v EXPLORATION_REPORT.md` exited 1: this report is not git-ignored.
