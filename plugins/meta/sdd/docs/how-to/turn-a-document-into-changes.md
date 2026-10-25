---
type: How-to Guide
title: Turn a document into changes
description: Split a spec or PRD file into sdd changes with dependencies, approve the split, start every change and run the first with /sdd:from-doc.
tags: [sdd, how-to, prd, from-doc, requires]
sources:
  - resource: ../../skills/from-doc/SKILL.md
  - resource: ../../skills/change/SKILL.md
  - resource: ../../agents/spec-author.md
generated:
  by: claude-code
  at: 2026-10-25T00:00:00Z
---

# Turn a document into changes

A PRD usually holds several changes with an order between them. Writing it as one change gives one huge Gate 1. `/sdd:from-doc` splits it first.

**Before you start:** sdd is initialised ([Install and configure sdd](install-and-configure.md)) and the document is a file in the repository or on disk.

## 1. Run it

```
/sdd:from-doc docs/prd/checkout.md
```

The lead reads the document and has `Explore` map each requirement to the capabilities, invariants, ADRs and code it touches.

## 2. Review the split

You get one line per change (`id | type | triage | sections covered | requires`), the order, and the open questions: requirements no acceptance test could check, contradictions with living criteria or invariants, missing limits. Answer them, ask for another split, or stop. Items that need no spec (a refactor, a config change) are listed and not started.

## 3. Changes are started

After you approve, each change gets `sdd start` in dependency order: branch `sdd/<id>`, worktree, draft PR, `--requires` for real dependencies. Its intent.md gets one line under `## Why`:

```
Source: docs/prd/checkout.md § Payment retries
```

The document is cited, not copied. The spec-author reads the cited sections and writes the criteria; your wording never lands in `specs/` unchecked.

## 4. The first change runs

The lead runs the first change with no open dependency through the normal workflow (`resume <id>`). The others are listed with their dependencies. Continue each with `/sdd:change resume <id>`; one that requires an unmerged change can do its spec work but stops before `plan` ([Make a change depend on another](manage-dependencies.md)).

If the document changes after approval, run `/sdd:from-doc` again: only the affected changes are redone.

## Related

- [Resume a change](resume-a-change.md)
- [Slash commands](../reference/slash-commands.md#sddfrom-doc)
