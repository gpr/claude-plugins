---
description: Draft a conventional-commit message that cog verify will accept
argument-hint: [optional context]
allowed-tools: Bash, Read
---

Draft a conventional-commit message for the currently-staged changes.

Load the `cog-versioning` skill before drafting if it is not already in context.

## Steps

1. Run `git status --short` and `git diff --cached` to see what is staged.
2. If nothing is staged, run `git diff` and report what is unstaged. Ask the user how they want to stage — recommend `git add -p` for partial staging rather than `git add -A`.
3. Identify the right commit type and scope from the diff:
   - Type follows the rules in the `cog-versioning` skill.
   - Scope is the package the change touches (`frontend`, `website`, `<backend>`, `release`, `task`, `deps`, `memory`).
   - If the diff spans multiple unrelated scopes, suggest splitting the commit and stop.
4. Draft a subject line: imperative, lowercase, ≤72 chars, no trailing period.
5. If the change is non-trivial, draft a 1–3 line body explaining *why*, not *what*.
6. If the change breaks a public contract, append `!` after the scope and add a `BREAKING CHANGE:` footer.
7. If $ARGUMENTS is provided, treat it as additional context the user wants reflected in the message.
8. Show the draft and ask: commit as-is, edit, or revise.
9. On confirmation, run `cog verify "<message>"` first. If it fails, fix the message and verify again before committing.
10. Commit with `git commit -m "<message>"`. For multi-line messages, use a HEREDOC:

    ```bash
    git commit -m "$(cat <<'EOF'
    <message>
    EOF
    )"
    ```

Do not use `--no-verify`. Do not skip `cog verify`. Do not amend without explicit user confirmation.
