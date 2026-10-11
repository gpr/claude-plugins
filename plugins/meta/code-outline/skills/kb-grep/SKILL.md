---
name: kb-grep
description: Search the code-outline cache in .kb/files/ to find which function, class or section of the project does something, and get its file and line range. Use before grepping or reading source files when you need to locate a symbol or behaviour.
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kb-grep.py:*)
---

# kb-grep

Search the cached outlines (names, signatures, one-line descriptions, call graph) instead of the source.

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/kb-grep.py [-F] [-p GLOB] [-n MAX] PATTERN
```

- `PATTERN` is a case-insensitive regex (`-F` for literal). It is matched against the signature, the description and the call-graph line.
- `-p 'src/**/*.py'` limits the search to matching source paths.
- Each hit is `path:start-end  signature — description  [calls … | called by …]`.

Read the hit with `Read(file_path=path, offset=start, limit=end-start+1)`. This is a partial read, so it is not intercepted.

Rules:
- Only files that were already fully read once have an outline. "no match" does not mean the code is absent: fall back to Grep.
- A hit marked `(stale…)` has line ranges from an older version of the file; check them before trusting.
- A missing description means Haiku enrichment is still pending; the signature and call graph are valid.
