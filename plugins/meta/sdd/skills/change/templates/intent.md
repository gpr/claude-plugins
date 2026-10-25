---
type: intent
id: {{id}}
title: {{title}}
status: draft
size: change
surface:
adrs: []
created: {{date}}
---

# {{title}}

<!-- size: change (default) | fix (a test on an existing criterion) | baseline (records existing behavior only)
     surface (size: change): the public surface it adds or changes, a list of api | cli | ui, or none.
     none skips the contract step; anything else gets contract files reviewed at Gate 1. -->

## Why
<!-- The problem, who has it, what it costs today. 2-5 sentences. -->

## Outcome
<!-- Observable result when done. How a user/operator will notice. -->

## Scope
- 

## Non-goals
<!-- What this change deliberately does NOT do. Agents read this to avoid scope creep. -->
- 

## Success criteria
<!-- Measurable. Each one should map to at least one acceptance criterion
     (capabilities/<id>#AC-NN) or invariant (invariants/<id>) in the delta. -->
- 

## Open questions
<!-- Must be empty before Gate 1 approval. -->
