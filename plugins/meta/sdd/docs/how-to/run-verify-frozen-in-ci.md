---
type: How-to Guide
title: Run verify-frozen and check in CI
description: Fail a pull request when its frozen acceptance tests were modified or its traceability is broken.
tags: [sdd, how-to, ci, freeze]
sources:
  - resource: ../../tools/sdd.py
  - resource: ../../README.md
generated:
  by: claude-code
  at: 2026-10-17T00:00:00Z
---

# Run verify-frozen and check in CI

The guard's Bash check is a heuristic. Hashing the frozen files in CI catches any change to them, however it was made.

1. Vendor or fetch `sdd.py`. It is a single file with no dependencies. Pin a release tag of the plugin, e.g. copy `plugins/meta/sdd/tools/sdd.py` from tag `sdd-<version>` into `tools/sdd.py`.

2. Add a job that runs, for every open change in the PR:

   ```yaml
   # .github/workflows/sdd.yml
   name: sdd
   on: pull_request
   jobs:
     frozen:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         - uses: actions/setup-python@v5
           with: { python-version: '3.12' }
         - name: verify frozen tests and traceability
           run: |
             set -e
             for d in changes/*/; do
               id=$(basename "$d")
               [ "$id" = archive ] && continue
               [ -f "$d/intent.md" ] || continue
               if [ -f "$d/frozen.json" ]; then python3 tools/sdd.py verify-frozen "$id"; fi
               python3 tools/sdd.py check "$id"
             done
   ```

3. What a failure looks like:

   ```
   ERROR tests/acceptance/test_greeting.py modified after freeze
   FAIL 1 frozen file(s), 1 tampered
   ```

## Notes

- Only changes that already ran `freeze` have a `frozen.json`. Before the acceptance phase, there's nothing to verify.
- `check` without `--tests` passes while tasks are open. Add `--tests` only for changes whose status is `verified`, if you want CI to require full coverage before sync.
- A legitimate test change goes through a reopened spec and a new `freeze` (see [Reopen a spec](reopen-a-spec.md)), which updates `frozen.json` in the same PR.
