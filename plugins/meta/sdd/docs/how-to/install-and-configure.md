---
type: How-to Guide
title: Install and configure sdd in a repository
description: Install the plugin at project scope, initialise the workflow folders, set the test commands and publish the config so changes can start.
tags: [sdd, how-to, install, configuration]
sources:
  - resource: ../../README.md
  - resource: ../../tools/sdd.py
generated:
  by: claude-code
  at: 2026-10-18T00:00:00Z
---

# Install and configure sdd in a repository

**Before you start:** Python 3.9+ as `python3`, a git remote named `origin`, and `gh` authenticated if you want PRs opened for you.

1. Add the marketplace and install at **project** scope, from the repository:

   ```
   /plugin marketplace add gpr/claude-plugins
   /plugin install sdd@gpr-plugins
   ```

   Choose project scope when asked. At user scope the plugin would guard `specs/` and `adrs/` and make the main conversation a lead in every repo.

2. Initialise. In a repository that already has code, tests or ADRs, follow [Adopt sdd in an existing repository](adopt-an-existing-repo.md) instead. Ask Claude to change something, or run `/sdd:change` with a request. The lead calls `sdd init` on first use. Or run it yourself:

   ```
   python3 <plugin>/tools/sdd.py init
   ```

   ```
   created: specs/, adrs/, changes/, tests/acceptance/, .claude/sdd.json (edit acceptance_cmd / unit_cmd), specs/index.md, specs/log.md, adrs/index.md, adrs/log.md, specs/.templates/capability.md.tmpl, specs/.templates/invariant.md.tmpl, adrs/.templates/adr.md.tmpl, .gitignore (/.claude/worktrees/)
   ```

3. Edit `.claude/sdd.json` for your stack. The two keys you almost always change:

   ```json
   {
     "acceptance_cmd": "pytest -q {files}",
     "unit_cmd": "pytest -q tests/unit"
   }
   ```

   `{files}` is replaced with the acceptance test files to run. Change the directory names, `base_branch`, `branch_prefix` or `worktree_dir` only if you need to. All keys: [Configuration](../reference/configuration.md).

4. Commit and push the config and `.gitignore` to the base branch. `sdd start` refuses until `origin/<base>` has `.claude/sdd.json`, because each change's worktree starts from there.

   ```
   git add .claude/sdd.json .gitignore specs adr changes tests/acceptance
   git commit -m "chore: set up sdd"
   git push
   ```

   Git doesn't track empty directories. That's fine: `sdd` recreates them as needed.

5. Check: `/sdd` opens the status pane and says how to start a change.

To try the plugin without installing it: `claude --plugin-dir ./plugins/meta/sdd`.
