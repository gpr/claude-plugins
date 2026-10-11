#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["tree-sitter-language-pack"]
# ///
"""Print a markdown outline skeleton: sections, line ranges, intra-file call graph.

Usage: outline.py <abs_path> <rel_path> <sha256>
Call graph is name-based and intra-file only (no type resolution).
"""
import datetime
import sys
from pathlib import Path

from tree_sitter_language_pack import get_parser

LANGS = {
    "py": "python", "rb": "ruby", "ts": "typescript", "tsx": "tsx", "js": "javascript",
    "jsx": "javascript", "mjs": "javascript", "cjs": "javascript", "go": "go", "rs": "rust",
    "java": "java", "sh": "bash", "bash": "bash", "php": "php", "c": "c", "h": "c",
    "cpp": "cpp", "hpp": "cpp", "cs": "csharp", "kt": "kotlin", "swift": "swift",
}
DEF_TYPES = {
    "function_definition", "function_declaration", "function_item", "method_definition",
    "method_declaration", "method", "singleton_method", "class_definition", "class_declaration",
    "class", "module", "struct_item", "impl_item", "trait_item", "enum_item", "interface_declaration",
    "constructor_declaration",
}
FUNC_VALUES = {"arrow_function", "function_expression", "function"}
CALL_TYPES = {"call", "call_expression", "method_invocation", "invocation_expression", "command"}


def name_of(node):
    n = node.child_by_field_name("name")
    if n is None:
        # C/C++: the name sits under nested declarators (int *f(void) -> function_declarator -> identifier)
        d = node.child_by_field_name("declarator")
        while d is not None and d.child_by_field_name("declarator") is not None:
            d = d.child_by_field_name("declarator")
        if d is not None and d.type == "function_declarator":
            d = d.child_by_field_name("declarator") or d
        n = d
    if n is None and node.type == "impl_item":
        n = node.child_by_field_name("type")  # Rust: impl Foo { ... }
    return n.text.decode(errors="replace") if n else None


def is_func_declarator(node):
    """JS/TS: `const f = () => {}` / `const f = function () {}`."""
    if node.type != "variable_declarator":
        return False
    v = node.child_by_field_name("value")
    return v is not None and v.type in FUNC_VALUES and node.child_by_field_name("name") is not None


def callee_name(call):
    f = (call.child_by_field_name("function") or call.child_by_field_name("method")
         or call.child_by_field_name("name") or (call.children[0] if call.children else None))
    if f is None:
        return None
    text = f.text.decode(errors="replace")
    return text.replace("::", ".").split(".")[-1].split("(")[0].strip() or None


def collect_defs(node, out, depth=0):
    for ch in node.children:
        if ch.type in DEF_TYPES and name_of(ch):
            # Python: start at the decorators so reading the range includes them
            top = ch.parent if ch.parent is not None and ch.parent.type == "decorated_definition" else ch
            out.append({"node": ch, "name": name_of(ch), "depth": depth,
                        "start": top.start_point[0] + 1, "end": ch.end_point[0] + 1})
            collect_defs(ch, out, depth + 1)
        elif is_func_declarator(ch):
            # span the whole statement so `export const` is included
            outer = ch.parent if ch.parent and ch.parent.type in ("lexical_declaration", "variable_declaration") else ch
            if outer.parent is not None and outer.parent.type == "export_statement":
                outer = outer.parent
            out.append({"node": ch, "name": name_of(ch), "depth": depth, "span": outer,
                        "start": outer.start_point[0] + 1, "end": outer.end_point[0] + 1})
            collect_defs(ch, out, depth + 1)
        else:
            collect_defs(ch, out, depth)


def calls_in(node, acc, top=True):
    # skip nested definitions: they report their own calls
    if not top and ((node.type in DEF_TYPES and name_of(node)) or is_func_declarator(node)):
        return
    if node.type in CALL_TYPES:
        n = callee_name(node)
        if n:
            acc.append(n)
    for ch in node.children:
        calls_in(ch, acc, False)


def main():
    if sys.argv[1:2] == ["--warm"]:
        sys.exit(0)  # only used to pre-fetch dependencies via `uv run --script`
    abs_path, rel_path, sha = sys.argv[1:4]
    ext = Path(abs_path).suffix.lstrip(".")
    lang = LANGS.get(ext)
    if not lang:
        sys.exit(1)
    src = Path(abs_path).read_bytes()
    root = get_parser(lang).parse(src).root_node
    total = src.count(b"\n") + (0 if src.endswith(b"\n") else 1)

    defs = []
    collect_defs(root, defs)
    if not defs:
        sys.exit(1)
    names = {d["name"] for d in defs}
    called_by = {}
    for d in defs:
        calls = []
        # calls from this def's own body (nested defs report their own)
        calls_in(d["node"], calls)
        d["calls"] = sorted({c for c in calls if c in names and c != d["name"]})
        d["external"] = sorted({c for c in calls if c not in names})[:10]
        for c in d["calls"]:
            called_by.setdefault(c, set()).add(d["name"])

    out = ["---", f"source: {rel_path}", f"source_sha256: {sha}", f"lines: {total}",
           "status: skeleton", f"generated: {datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')}",
           "---", f"# {rel_path}", ""]
    first = min(d["start"] for d in defs)
    if first > 1:
        out += [f"## L1-{first - 1} preamble", "- desc: _(pending)_", ""]
    for d in sorted(defs, key=lambda x: (x["start"], x["depth"])):
        sig = (d.get("span") or d["node"]).text.decode(errors="replace").splitlines()[0].strip()[:120]
        out.append(f"{'#' * min(d['depth'] + 2, 6)} L{d['start']}-{d['end']} {sig}")
        parts = []
        if d["calls"]:
            parts.append("calls: " + ", ".join(d["calls"]))
        if called_by.get(d["name"]):
            parts.append("called by: " + ", ".join(sorted(called_by[d["name"]])))
        if d["external"]:
            parts.append("external: " + ", ".join(d["external"]))
        if parts:
            out.append("- " + " · ".join(parts))
        out += ["- desc: _(pending)_", ""]
    last = max(d["end"] for d in defs)
    if last < total:
        # top-level code after the last definition (e.g. `if __name__ == "__main__":`)
        out += [f"## L{last + 1}-{total} epilogue", "- desc: _(pending)_", ""]
    print("\n".join(out))


if __name__ == "__main__":
    main()
