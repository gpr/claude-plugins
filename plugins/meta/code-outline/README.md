# code-outline

Claude Code plugin. A `PreToolUse` hook on `Read` blocks **full** reads of large source files and returns an outline instead: sections with line ranges, an intra-file call graph and a one-line Haiku description per section. The agent then reads only the ranges it needs with `offset`/`limit`.

## Install

```
/plugin marketplace add <path-or-repo>
/plugin install code-outline@gpr-plugins
```

Local test: `claude --plugin-dir ./plugins/meta/code-outline`

## How it works

1. Read is partial (`offset`, `limit` or `pages` set), file is small, unsupported, outside the project or under `.kb/` → passes through untouched.
2. Otherwise the file's sha256 is compared with `source_sha256` in `.kb/files/<path>/<name.ext>.md`.
3. Missing or stale → `scripts/outline.py` (tree-sitter) writes a **skeleton** immediately and `scripts/enrich.sh` starts in the background: one `claude -p --model haiku` call fills the `desc:` lines and flips `status: skeleton` → `enriched`.
4. The Read is denied with the outline as the reason. To read the whole file anyway: `offset=1`, `limit=<lines>`.

The hook fails open: any error lets the normal Read happen.

## Limits

- First read of a new or changed file shows `desc: (pending)`; the next read has descriptions.
- Call graph is name-based and intra-file only (no type resolution). Other callees appear as `external:`.
- `claude -p` is a full CLI run with its own cost. Files above `CODE_OUTLINE_MAX_BYTES` skip enrichment.
- `.kb/files/` is a cache; consider adding it to `.gitignore`.

## Environment variables

| Variable | Default | Effect |
|---|---|---|
| `CODE_OUTLINE_DISABLE` | `0` | `1` turns the hook off |
| `CODE_OUTLINE_MIN_LINES` | `200` | files shorter than this are read normally |
| `CODE_OUTLINE_MAX_BYTES` | `200000` | larger files skip Haiku enrichment |

## Searching the cache

The `kb-grep` skill (`scripts/kb-grep.py`, stdlib Python) greps the outlines and prints `path:start-end  signature — description  [call graph]`, so the agent can jump straight to the right range. Hits from outlines whose source changed are marked stale.

Requires `jq`, `uv`, the `claude` CLI, and `sha256sum` or `shasum`. A SessionStart hook pre-fetches the tree-sitter dependency so the first Read stays under the hook timeout.
