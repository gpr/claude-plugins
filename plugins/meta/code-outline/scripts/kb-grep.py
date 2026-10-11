#!/usr/bin/env python3
"""Search the code-outline cache (.kb/files/**/*.md).

Usage: kb-grep.py [-F] [-s] [-p PATH_GLOB] [-n MAX] PATTERN

Matches PATTERN (case-insensitive regex, or literal with -F) against each section's
signature, description and call-graph line. Prints one hit per line:

    <src path>:<start>-<end>  <signature>  — <description>  [calls: ... | called by: ...]

so the caller can Read the original file with offset=<start> limit=<end-start+1>.
Hits from an outline whose source changed since it was built are marked (stale).
Pure stdlib; no network, never writes.
"""
import argparse
import fnmatch
import hashlib
import os
import re
import sys
from pathlib import Path

HEADER = re.compile(r"^#+ L(\d+)-(\d+) (.*)$")


def find_root():
    d = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()).resolve()
    for p in [d, *d.parents]:
        if (p / ".kb" / "files").is_dir():
            return p
    return None


def parse(md):
    """Yield (meta, sections) for one outline file."""
    text = md.read_text(errors="replace")
    meta, body = {}, text
    if text.startswith("---\n"):
        head, _, body = text[4:].partition("\n---\n")
        for line in head.splitlines():
            k, _, v = line.partition(": ")
            meta[k] = v
    sections, cur = [], None
    for line in body.splitlines():
        m = HEADER.match(line)
        if m:
            cur = {"start": int(m[1]), "end": int(m[2]), "sig": m[3], "desc": "", "graph": ""}
            sections.append(cur)
        elif cur and line.startswith("- desc: "):
            d = line[8:].strip()
            cur["desc"] = "" if d == "_(pending)_" else d
        elif cur and line.startswith("- "):
            cur["graph"] = line[2:].strip()
    return meta, sections


def sha256(path):
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError:
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pattern")
    ap.add_argument("-F", "--fixed", action="store_true", help="literal match instead of regex")
    ap.add_argument("-p", "--path", help="only source paths matching this glob (e.g. 'src/**/*.py')")
    ap.add_argument("-n", "--max", type=int, default=50, help="max hits (default 50)")
    a = ap.parse_args()

    root = find_root()
    if not root:
        print("no .kb/files found: no outline has been generated in this project yet", file=sys.stderr)
        return 1
    try:
        rx = re.compile(re.escape(a.pattern) if a.fixed else a.pattern, re.I)
    except re.error as e:
        print(f"bad pattern: {e}", file=sys.stderr)
        return 2

    hits = pending = stale_files = 0
    shown = 0
    for md in sorted((root / ".kb" / "files").rglob("*.md")):
        meta, sections = parse(md)
        src = meta.get("source") or str(md.relative_to(root / ".kb" / "files"))[:-3]
        if a.path and not fnmatch.fnmatch(src, a.path):
            continue
        stale = sha256(root / src) != meta.get("source_sha256")
        for s in sections:
            if not rx.search(f"{s['sig']} {s['desc']} {s['graph']}"):
                continue
            hits += 1
            if shown >= a.max:
                continue
            shown += 1
            line = f"{src}:{s['start']}-{s['end']}  {s['sig']}"
            if s["desc"]:
                line += f"  — {s['desc']}"
            else:
                pending += 1
            if s["graph"]:
                line += f"  [{s['graph']}]"
            if stale:
                line += "  (stale: source changed since outline)"
                stale_files += 1
            print(line)
    if not hits:
        print("no match", file=sys.stderr)
        return 1
    if hits > shown:
        print(f"... {hits - shown} more hits, refine the pattern or raise -n", file=sys.stderr)
    if pending:
        print(f"note: {pending} hit(s) have no description yet (enrichment pending)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
