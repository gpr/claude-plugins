---
description: Regenerate or preview CHANGELOG.md without bumping
argument-hint: [from..to]
allowed-tools: Bash, Read
---

Regenerate `CHANGELOG.md` from commits without bumping the version or creating a tag.

Load the `cog-versioning` skill before starting if it is not already in context.

## Steps

1. If $ARGUMENTS is provided, treat it as a range and run `cog changelog $ARGUMENTS`. Otherwise run `cog changelog` for the unreleased range.
2. Capture the output — this is what the new changelog section would look like.
3. Show the user the proposed changelog content alongside the current `CHANGELOG.md` for context.
4. Ask before writing anything to disk.
5. If the user accepts, write the regenerated changelog. Stage the change but **do not commit** — leave that to the user (they can use `/commit` if they want).

## Constraints

- Never hand-edit `CHANGELOG.md` outside of `cog changelog` output.
- Do not run `cog bump` from this command — that's `/release`'s job.
- If the commit history fails `cog check`, surface the error and stop. The changelog will be wrong otherwise.
