# Step 9: reopen (failure path)

Part of the `sdd:change` lead workflow: read when a step sends you to step 9.
Step numbers refer to SKILL.md.

A wrong or untestable criterion or invariant goes back to the spec, never into the code or the tests.
A contract file that cannot carry a criterion (tester, implementer or verifier says so) is the
same: reopen, then contract-designer (after the spec-author when a criterion changes).
`sdd checkpoint <id> --status draft --phase spec -m "chore(<id>): reopen spec"`,
resume spec-author with the BLOCKED report, then Gate 1 for
the affected units only, then re-plan the affected tasks, re-run their test tasks
(then `sdd freeze <id>` again), then implementation. A Baseline test rewritten after code has changed is
refused by `freeze`: you then run `sdd freeze <id> --after-code` yourself (the verifier's
run on the base commit is then its only proof).
A `size: fix` change adds at most new criteria: when it needs more (a changed criterion,
a section, an invariant, an ADR), re-triage it as a full change. Set `size: change` in intent.md,
`sdd checkpoint <id> --status draft --phase spec -m "chore(<id>): re-triage as change"`,
start spec-author with the finding, then step 3.
