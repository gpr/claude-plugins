# Adopt an area

Part of the `sdd:change` lead workflow: read when the request starts with `adopt`.
Step numbers refer to SKILL.md.

`adopt <area>` writes down what an existing area of the code does, as Baseline criteria
(sdd:formats), with passing acceptance tests, and changes no code.
Delegate to `Explore` (medium): the area's public surface, the files that implement it, and
existing tests for it, plus decisions the code commits to (with file evidence); skip this when
`sdd:discover` already gave these findings. `sdd start <area> --title "Baseline: <area>" --pr-title "docs(<area>): baseline spec"`,
enter the worktree, set `size: baseline` in intent.md, then steps 2.2-6 as usual (spec-author
with the Explore findings, told the change is an adopt; Gate 1 asks "is this what the code
does, and what it should keep doing?"). Step 6 ends with `--phase verify`; skip step 7 and the
code-review in step 8.1. A MISMATCH (step 6) in an adopt is either a wrong criterion
(spec-author) or a bug: drop that criterion from the adopt and offer a fix as its own change.
