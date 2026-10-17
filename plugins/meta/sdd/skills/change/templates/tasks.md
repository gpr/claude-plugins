---
type: tasks
change: {{id}}
---

# Tasks: {{title}}

<!-- Format (parsed by sdd.py, keep exactly):
- [ ] T1 (test) What the tests cover — REQ-XXX-001, REQ-XXX-002
- [ ] T2 (impl) What gets built — REQ-XXX-001 ADR-0003 | blocked-by: T1 | files: src/a.py, src/b.py
Kinds: test (acceptance-tester), impl (implementer), chore (no REQ needed).
Every ADDED/MODIFIED REQ needs >=1 test task and >=1 impl task.
Every ADDED/MODIFIED INV needs >=1 test task (no impl task required).
Every impl task is blocked-by the test task(s) covering its REQs.
`files:` lets the lead run impl tasks in parallel when they don't overlap.
-->
