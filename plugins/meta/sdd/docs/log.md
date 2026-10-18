# Log

## 2026-10-18

**Update** Review fixes: block and multi-line YAML scalars, nested `null` and lists kept on rewrite, whole-concept hashes cover the front matter, SECTIONS keep sub-headings and reject duplicates, unknown CapabilityDelta sections and stray `###` headings are errors, Rationale links resolved, `specs`/`adrs`/`archive` reserved as change ids, the lead may edit `specs/.templates/`, quoted and pre-OKF ADR statuses stay locked. Updated: file-formats, bundles, cli, guard-rules.

**Update** Specs are lintel-style OKF concepts: Capability (acceptance criteria `AC-NN`, cited `capabilities/<id>#AC-NN`) and Invariant (Statement, Check, Holds/Violation), changed through per-unit CapabilityDeltas; ADRs are `adrs/NNNN_<slug>.md` with the OKF draft/stable/deprecated lifecycle; indexes and logs in the `okf index` format; the REQ/INV format is reported, not migrated. Rewritten: reference/file-formats, reference/bundles, how-to/write-a-delta-and-adr, how-to/resolve-sync-conflict, how-to/migrate-to-okf-layout (now the migration to concepts). Updated: cli, configuration, guard-rules, repo-layout, agents, known-limits, slash-commands, keep-in-sync, both tutorials, workflow overview, determinism, context bundles, guard design, install, dependencies, reopen. Command outputs are from real `sdd.py` runs in a scratch repository.

## 2026-10-17

**Update** `/sdd` pane: the active change (checked-out `sdd/<id>` branch, else the most active) shown in full with every task; the other changes in folding status groups. [Slash commands, band and panes](reference/slash-commands.md) and [Follow a change from the band and panes](how-to/use-the-band-and-panes.md).

**Update** OKF layout for `specs/` and changes: concept files, invariants (`INV` blocks, `#### Check:`), the `bundle` subcommand and `mcp__sdd__bundle` tool, `sync` by concept with `MOVED` and `specs/log.md`. New pages: reference/bundles.md, how-to/migrate-to-okf-layout.md. Updated: file-formats, cli, sdd-tool-roles, configuration, repo-layout, agents, guard-rules, keep-in-sync, the delta and conflict how-tos, both tutorials, determinism, context bundles. Command outputs are from real `sdd.py` runs in a scratch repository.

**Update** Mermaid diagrams: workflow flowchart (replaces the ASCII one), status state machine, full vs fix phase order, dependency-state decision, guard decision order, branch history (gitGraph), depth-first resume and base-hash conflict sequences, context-bundle flow, mod data flow, lead routing, sync file moves, resume outcomes.

**Create** Diátaxis documentation bundle for sdd 0.6.1: 2 tutorials, 9 how-to guides, 10 reference pages, 6 explanations, 3 contributing pages. Command outputs are from real `sdd.py` runs in a scratch repository.
