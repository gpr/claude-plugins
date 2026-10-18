---
type: tasks
change: {{id}}
---

# Tasks: {{title}}

<!-- Format (parsed by sdd.py, keep exactly):
- [ ] T1 (test) What the tests cover — capabilities/xxx#AC-01, capabilities/xxx#AC-02
- [ ] T2 (impl) What gets built — capabilities/xxx#AC-01 ADR-0003 | blocked-by: T1 | files: src/a.py, src/b.py
- [ ] T3 (test) The check of a rule — invariants/yyy
Kinds: test (acceptance-tester), impl (implementer), chore (no reference needed).
Every ADDED/MODIFIED acceptance criterion needs >=1 test task and >=1 impl task.
Every ADDED/MODIFIED invariant needs >=1 test task (no impl task required).
Every impl task is blocked-by the test task(s) covering its criteria.
`files:` lets the lead run impl tasks in parallel when they don't overlap.
-->
