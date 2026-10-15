#!/usr/bin/env python3
"""sdd.py - deterministic tooling for the spec-driven workflow.

Everything that must stay exact (spec merge, ID traceability, base-version
conflicts, test freezing, ADR status) lives here, so no agent ever has to
"rewrite" a spec. Output is terse on purpose: it is read by agents.

Usually called through the plugin's `sdd` tool (mcp__sdd__sdd), args as a list.

Commands
  init                               create specs/ adr/ changes/ tests/acceptance/ + .claude/sdd.json
  config                             print the effective configuration (test commands, dirs)
  new <change> [--title T]           scaffold changes/<change>/
  status [<change>] [--json]         list changes / show one
  set-status <change> <status>       draft|approved|implementing|verified|archived
  delta-stub <change> <REQ> [--remove]
                                     copy the living REQ into the delta with its base hash
  adr-new <title> [--supersedes ADR-NNNN]
  adr-accept <ADR-NNNN>              proposed -> accepted (+ marks superseded one)
  check <change> [--tests]           traceability + conflicts (+ acceptance coverage)
  context <change> <task> [--plan]   minimal context bundle for one task
  freeze <change>                    record hashes of the change's acceptance tests
  verify-frozen <change>             fail if frozen acceptance tests were modified
  sync <change> [--dry-run] [--force]
                                     merge delta into living specs, accept ADRs, archive
Exit code: 0 ok, 1 errors found, 2 usage error.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

STATUSES = ["draft", "approved", "implementing", "verified", "archived"]
ADR_RE = re.compile(r"ADR-\d{4}")
TASK_RE = re.compile(r"^- \[( |x|X)\] (T\d+) \((test|impl|chore)\) (.*)$")
BASE_RE = re.compile(r"^<!--\s*base:\s*([0-9a-f]{8})\s*-->\s*$")
SECTION_RE = re.compile(r"^## (ADDED|MODIFIED|REMOVED)\s*$")


# ---------------------------------------------------------------- config ---
def project_root() -> Path:
    """Nearest ancestor with .claude/sdd.json, else with changes/ or specs/, else .git."""
    p = Path.cwd()
    chain = [p, *p.parents]
    for marker in (lambda c: (c / ".claude" / "sdd.json").exists(),
                   lambda c: (c / "changes").is_dir() or (c / "specs").is_dir(),
                   lambda c: (c / ".git").exists()):
        for cand in chain:
            if marker(cand):
                return cand
    return p


ROOT = project_root()
CFG = {
    "specs_dir": "specs",
    "changes_dir": "changes",
    "adr_dir": "adr",
    "acceptance_dir": "tests/acceptance",
    "acceptance_cmd": "pytest -q {files}",
    "unit_cmd": "pytest -q tests/unit",
    "req_id_pattern": "REQ-[A-Z0-9]+-[0-9]{3}",
}
DEFAULT_CFG = dict(CFG)
_cfg_file = ROOT / ".claude" / "sdd.json"
if _cfg_file.exists():
    CFG.update(json.loads(_cfg_file.read_text()))

SPECS = ROOT / CFG["specs_dir"]
CHANGES = ROOT / CFG["changes_dir"]
ADRS = ROOT / CFG["adr_dir"]
ACCEPT = ROOT / CFG["acceptance_dir"]
REQ_RE = re.compile(CFG["req_id_pattern"])
HEAD_RE = re.compile(r"^### (" + CFG["req_id_pattern"] + r"):\s*(.*)$")
TEMPLATES = Path(__file__).resolve().parent.parent / "skills" / "change" / "templates"


COMMENT_RE = re.compile(r"<!--(?!\s*base:).*?-->", re.S)


def strip_comments(text: str) -> str:
    """Drop HTML comments (template guidance), keep `<!-- base: -->` markers."""
    return re.sub(r"\n{3,}", "\n\n", COMMENT_RE.sub("", text))


def die(msg: str, code: int = 2):
    print(f"ERROR {msg}")
    sys.exit(code)


# ------------------------------------------------------------ front matter --
def read_fm(path: Path) -> tuple[dict, str]:
    text = path.read_text()
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end < 0:
        return {}, text
    fm: dict = {}
    for line in text[4:end].splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        v = v.strip()
        if v.startswith("[") and v.endswith("]"):
            fm[k.strip()] = [x.strip() for x in v[1:-1].split(",") if x.strip()]
        else:
            fm[k.strip()] = v
    return fm, text[end + 4:].lstrip("\n")


def write_fm(path: Path, fm: dict, body: str):
    lines = ["---"]
    for k, v in fm.items():
        lines.append(f"{k}: [{', '.join(v)}]" if isinstance(v, list) else f"{k}: {v}")
    lines.append("---")
    atomic_write(path, "\n".join(lines) + "\n\n" + body)


def atomic_write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content)
    os.replace(tmp, path)


# ------------------------------------------------------------ spec blocks --
@dataclass
class Block:
    req: str
    title: str
    lines: list[str]          # heading + body, base comment removed
    base: str | None = None

    @property
    def text(self) -> str:
        return "\n".join(self.lines).strip("\n")

    @property
    def digest(self) -> str:
        norm = "\n".join(l.rstrip() for l in self.lines).strip("\n")
        return hashlib.sha256(norm.encode()).hexdigest()[:8]

    @property
    def has_scenario(self) -> bool:
        return any(l.startswith("#### Scenario:") for l in self.lines)


def split_blocks(lines: list[str]) -> tuple[list[str], list[Block]]:
    pre, blocks, cur = [], [], None
    for line in lines:
        m = HEAD_RE.match(line)
        if m:
            cur = Block(m.group(1), m.group(2).strip(), [line])
            blocks.append(cur)
            continue
        if cur is None:
            pre.append(line)
            continue
        bm = BASE_RE.match(line.strip())
        if bm:
            cur.base = bm.group(1)
        else:
            cur.lines.append(line)
    return pre, blocks


@dataclass
class LivingSpec:
    path: Path
    pre: list[str]
    blocks: list[Block]

    @classmethod
    def load(cls, capability: str) -> "LivingSpec":
        path = SPECS / capability / "spec.md"
        if path.exists():
            pre, blocks = split_blocks(path.read_text().splitlines())
        else:
            pre, blocks = [f"# {capability}", ""], []
        return cls(path, pre, blocks)

    def get(self, req: str) -> Block | None:
        return next((b for b in self.blocks if b.req == req), None)

    def render(self) -> str:
        out = "\n".join(self.pre).rstrip("\n") + "\n"
        for b in self.blocks:
            out += "\n" + b.text + "\n"
        return out


def all_living() -> dict[str, tuple[str, Block]]:
    """REQ id -> (capability, block) across every living spec."""
    out: dict[str, tuple[str, Block]] = {}
    if SPECS.exists():
        for f in sorted(SPECS.glob("*/spec.md")):
            _, blocks = split_blocks(f.read_text().splitlines())
            for b in blocks:
                out[b.req] = (f.parent.name, b)
    return out


@dataclass
class Delta:
    capability: str
    added: list[Block] = field(default_factory=list)
    modified: list[Block] = field(default_factory=list)
    removed: list[Block] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def load_deltas(change: Path) -> list[Delta]:
    out = []
    ddir = change / "specs"
    if not ddir.exists():
        return out
    for f in sorted(ddir.glob("*.md")):
        d = Delta(f.stem)
        section, buf = None, []

        def flush():
            if section is None:
                return
            _, blocks = split_blocks(buf)
            getattr(d, section.lower()).extend(blocks)

        for line in f.read_text().splitlines():
            m = SECTION_RE.match(line)
            if m:
                flush()
                section, buf = m.group(1), []
            elif section:
                buf.append(line)
        flush()
        out.append(d)
    return out


# ------------------------------------------------------------------ change --
def change_dir(name: str) -> Path:
    p = CHANGES / name
    if not (p / "intent.md").exists():
        die(f"no change '{name}' (expected {p.relative_to(ROOT)}/intent.md)")
    return p


def parse_tasks(change: Path) -> list[dict]:
    f = change / "tasks.md"
    tasks = []
    if not f.exists():
        return tasks
    text = f.read_text()
    # blank out comments but keep line numbers stable
    text = COMMENT_RE.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    for n, line in enumerate(text.splitlines(), 1):
        m = TASK_RE.match(line.strip())
        if not m:
            continue
        rest = m.group(4)
        blocked = []
        bm = re.search(r"blocked-by:\s*([T\d,\s]+)", rest)
        if bm:
            blocked = re.findall(r"T\d+", bm.group(1))
        tasks.append({
            "id": m.group(2), "kind": m.group(3), "done": m.group(1) != " ",
            "text": rest, "line": n, "raw": line.strip(),
            "reqs": sorted(set(REQ_RE.findall(rest))),
            "adrs": sorted(set(ADR_RE.findall(rest))),
            "blocked_by": blocked,
        })
    return tasks


def adr_files() -> dict[str, Path]:
    out = {}
    if ADRS.exists():
        for f in ADRS.glob("ADR-[0-9][0-9][0-9][0-9]*.md"):
            out[f.name[:8]] = f
    return out


def acceptance_hits(reqs: set[str]) -> dict[str, list[Path]]:
    hits: dict[str, list[Path]] = {r: [] for r in reqs}
    if not ACCEPT.exists() or not reqs:
        return hits
    for f in sorted(ACCEPT.rglob("*")):
        if not f.is_file():
            continue
        try:
            found = set(REQ_RE.findall(f.read_text(errors="ignore")))
        except OSError:
            continue
        for r in found & reqs:
            hits[r].append(f)
    return hits


# ---------------------------------------------------------------- commands --
def cmd_new(args):
    if not args:
        die("usage: new <change> [--title T]")
    name = args[0]
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,60}", name):
        die("change id must be kebab-case")
    title = args[args.index("--title") + 1] if "--title" in args else name
    d = CHANGES / name
    if d.exists():
        die(f"{d.relative_to(ROOT)} already exists")
    (d / "specs").mkdir(parents=True)
    today = _dt.date.today().isoformat()
    for t in ["intent.md", "plan.md", "tasks.md"]:
        src = TEMPLATES / t
        body = src.read_text() if src.exists() else ""
        body = body.replace("{{id}}", name).replace("{{title}}", title).replace("{{date}}", today)
        (d / t).write_text(body)
    print(f"created {d.relative_to(ROOT)}/ (intent.md plan.md tasks.md specs/)")


def cmd_init(args):
    made = []
    for d in (SPECS, ADRS, CHANGES, ACCEPT):
        if not d.exists():
            d.mkdir(parents=True)
            made.append(str(d.relative_to(ROOT)) + "/")
    if not _cfg_file.exists():
        cfg = {k: v for k, v in DEFAULT_CFG.items() if k != "req_id_pattern"}
        atomic_write(_cfg_file, json.dumps(cfg, indent=2) + "\n")
        made.append(str(_cfg_file.relative_to(ROOT)) + " (edit acceptance_cmd / unit_cmd)")
    print(f"root {ROOT}")
    print("created: " + (", ".join(made) if made else "nothing, already initialised"))


def cmd_config(args):
    print(json.dumps({"root": str(ROOT), **CFG}, indent=2))


def cmd_status(args):
    as_json = "--json" in args
    args = [a for a in args if a != "--json"]
    dirs = [change_dir(args[0])] if args else sorted(
        p for p in CHANGES.glob("*") if (p / "intent.md").exists())
    if as_json:
        out = []
        for d in dirs:
            fm, body = read_fm(d / "intent.md")
            title = fm.get("title") or d.name
            out.append({
                "id": d.name, "title": title, "status": fm.get("status", "?"),
                "size": fm.get("size", "change"),
                "adrs": fm.get("adrs", []) if isinstance(fm.get("adrs"), list) else [],
                "tasks": [{"id": t["id"], "kind": t["kind"], "done": t["done"],
                           "reqs": t["reqs"]} for t in parse_tasks(d)],
            })
        archived = len(list((CHANGES / "archive").glob("*"))) if (CHANGES / "archive").exists() else 0
        print(json.dumps({"root": str(ROOT), "changes": out, "archived": archived}))
        return
    for d in dirs:
        fm, _ = read_fm(d / "intent.md")
        tasks = parse_tasks(d)
        done = sum(t["done"] for t in tasks)
        print(f"{d.name}  status={fm.get('status', '?')}  tasks={done}/{len(tasks)}  "
              f"size={fm.get('size', '?')}")
        if args:
            for t in tasks:
                print(f"  {'x' if t['done'] else ' '} {t['id']} ({t['kind']}) "
                      f"{','.join(t['reqs'])} blocked-by={','.join(t['blocked_by']) or '-'}")


def cmd_set_status(args):
    if len(args) != 2 or args[1] not in STATUSES:
        die(f"usage: set-status <change> <{'|'.join(STATUSES)}>")
    d = change_dir(args[0])
    fm, body = read_fm(d / "intent.md")
    old = fm.get("status", "draft")
    fm["status"] = args[1]
    write_fm(d / "intent.md", fm, body)
    print(f"{d.name}: {old} -> {args[1]}")


def cmd_delta_stub(args):
    if len(args) < 2:
        die("usage: delta-stub <change> <REQ> [--remove]")
    d, req = change_dir(args[0]), args[1]
    living = all_living()
    if req not in living:
        die(f"{req} not in living specs (use ## ADDED for new requirements)")
    cap, blk = living[req]
    section = "REMOVED" if "--remove" in args else "MODIFIED"
    f = d / "specs" / f"{cap}.md"
    text = f.read_text() if f.exists() else f"# Delta: {cap}\n"
    if f"### {req}:" in text:
        die(f"{req} already present in {f.relative_to(ROOT)}")
    lines = blk.lines[:1] + [f"<!-- base: {blk.digest} -->"]
    lines += ["Reason: <why it is removed>"] if section == "REMOVED" else blk.lines[1:]
    entry = "\n".join(lines).strip("\n")
    if f"## {section}" in text:
        text = re.sub(rf"(## {section}\s*\n)", lambda m: m.group(1) + "\n" + entry + "\n\n", text, 1)
    else:
        text = text.rstrip("\n") + f"\n\n## {section}\n\n{entry}\n"
    atomic_write(f, text)
    print(f"{section} {req} base={blk.digest} -> {f.relative_to(ROOT)}")


def cmd_adr_new(args):
    if not args:
        die("usage: adr-new <title> [--supersedes ADR-NNNN]")
    sup = None
    if "--supersedes" in args:
        i = args.index("--supersedes")
        sup = args[i + 1]
        args = args[:i] + args[i + 2:]
        if sup not in adr_files():
            die(f"{sup} does not exist")
    title = " ".join(args)
    nums = [int(k[4:]) for k in adr_files()]
    num = f"ADR-{(max(nums) + 1 if nums else 1):04d}"
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:50]
    path = ADRS / f"{num}-{slug}.md"
    tpl = TEMPLATES / "adr.md"
    body = tpl.read_text() if tpl.exists() else "# {{num}}: {{title}}\n"
    body = (body.replace("{{num}}", num).replace("{{title}}", title)
            .replace("{{date}}", _dt.date.today().isoformat())
            .replace("{{supersedes}}", sup or ""))
    atomic_write(path, body)
    print(f"{num} -> {path.relative_to(ROOT)}")


def accept_adr(num: str, dry: bool = False) -> list[str]:
    files = adr_files()
    if num not in files:
        return [f"{num} does not exist"]
    fm, body = read_fm(files[num])
    if fm.get("status") == "accepted":
        return []
    if fm.get("status") != "proposed":
        return [f"{num} status is {fm.get('status')}, expected proposed"]
    sup = fm.get("supersedes", "")
    if sup and sup not in files:
        return [f"{num} supersedes missing {sup}"]
    if dry:
        return []
    fm["status"] = "accepted"
    write_fm(files[num], fm, body)
    if sup:
        sfm, sbody = read_fm(files[sup])
        sfm["status"] = "superseded"
        sfm["superseded_by"] = num
        write_fm(files[sup], sfm, sbody)
    return []


def cmd_adr_accept(args):
    if not args:
        die("usage: adr-accept <ADR-NNNN>")
    errs = accept_adr(args[0])
    for e in errs:
        print(f"ERROR {e}")
    if not errs:
        print(f"{args[0]} accepted")
    sys.exit(1 if errs else 0)


def collect(change: Path):
    """Run every structural check. Returns (errors, warnings, info)."""
    errs, warns = [], []
    fm, _ = read_fm(change / "intent.md")
    if fm.get("status") not in STATUSES:
        errs.append(f"intent.md: status '{fm.get('status')}' invalid")
    living = all_living()
    deltas = load_deltas(change)
    touched: dict[str, str] = {}      # req -> ADDED|MODIFIED|REMOVED
    delta_blocks: dict[str, Block] = {}
    for d in deltas:
        for kind in ("added", "modified", "removed"):
            for b in getattr(d, kind):
                where = f"specs/{d.capability}.md {b.req}"
                if b.req in touched:
                    errs.append(f"{where}: appears twice in this change")
                touched[b.req] = kind.upper()
                delta_blocks[b.req] = b
                cur = living.get(b.req)
                if kind == "added":
                    if cur:
                        errs.append(f"{where}: ADDED but already exists in specs/{cur[0]}")
                    if b.base:
                        warns.append(f"{where}: base comment ignored on ADDED")
                else:
                    if not cur:
                        errs.append(f"{where}: {kind.upper()} but not in living specs")
                    elif cur[0] != d.capability:
                        errs.append(f"{where}: lives in specs/{cur[0]}, not {d.capability}")
                    elif not b.base:
                        errs.append(f"{where}: missing <!-- base: --> (use delta-stub)")
                    elif b.base != cur[1].digest:
                        errs.append(f"{where}: CONFLICT base {b.base} != current {cur[1].digest} "
                                    f"(living spec changed since this delta was written)")
                if kind != "removed" and not b.has_scenario:
                    errs.append(f"{where}: no '#### Scenario:' (acceptance criteria required)")
    if not touched and fm.get("size") != "fix":
        warns.append("no spec delta in this change")

    tasks = parse_tasks(change)
    ids = [t["id"] for t in tasks]
    for t in tasks:
        if ids.count(t["id"]) > 1:
            errs.append(f"tasks.md:{t['line']} duplicate {t['id']}")
        for b in t["blocked_by"]:
            if b not in ids:
                errs.append(f"tasks.md:{t['line']} {t['id']} blocked-by unknown {b}")
        for r in t["reqs"]:
            if r not in touched and r not in living:
                errs.append(f"tasks.md:{t['line']} {t['id']} references unknown {r}")
            if touched.get(r) == "REMOVED" and t["kind"] == "test":
                errs.append(f"tasks.md:{t['line']} {t['id']} tests removed {r}")
        if t["kind"] in ("test", "impl") and not t["reqs"]:
            errs.append(f"tasks.md:{t['line']} {t['id']} ({t['kind']}) references no REQ")
    adrs = adr_files()
    referenced_adrs = set(fm.get("adrs", []) if isinstance(fm.get("adrs"), list) else [])
    for t in tasks:
        referenced_adrs |= set(t["adrs"])
    for a in sorted(referenced_adrs):
        if a not in adrs:
            errs.append(f"{a} referenced but no file in {CFG['adr_dir']}/")
        else:
            st = read_fm(adrs[a])[0].get("status")
            if st in ("superseded", "deprecated"):
                errs.append(f"{a} is {st}; reference its successor")
    plan = change / "plan.md"
    if plan.exists():
        ptxt = strip_comments(plan.read_text())
        for r in sorted(set(REQ_RE.findall(ptxt))):
            if r not in touched and r not in living:
                errs.append(f"plan.md references unknown {r}")
        for a in sorted(set(ADR_RE.findall(ptxt))):
            if a not in adrs:
                errs.append(f"plan.md references unknown {a}")

    for r, kind in sorted(touched.items()):
        if kind == "REMOVED":
            continue
        kinds = {t["kind"] for t in tasks if r in t["reqs"]}
        if tasks and "test" not in kinds:
            errs.append(f"{r}: no (test) task")
        if tasks and "impl" not in kinds:
            errs.append(f"{r}: no (impl) task")
    if not tasks and fm.get("status") not in ("draft",):
        errs.append("tasks.md has no tasks")
    test_ids = {t["id"] for t in tasks if t["kind"] == "test"}
    # REQs that must be covered by acceptance tests: everything the delta adds/modifies,
    # plus existing REQs a test task targets (the `fix` path).
    test_reqs = {r for r, k in touched.items() if k != "REMOVED"}
    test_reqs |= {r for t in tasks if t["kind"] == "test" for r in t["reqs"]}
    for t in tasks:
        if t["kind"] == "impl":
            needed = {x["id"] for x in tasks if x["kind"] == "test" and set(x["reqs"]) & set(t["reqs"])}
            if needed and not needed & set(t["blocked_by"]):
                warns.append(f"{t['id']}: impl not blocked-by its test task(s) {','.join(sorted(needed))}")
    return errs, warns, {"touched": touched, "tasks": tasks, "deltas": deltas,
                         "blocks": delta_blocks, "test_ids": test_ids, "test_reqs": test_reqs}


def cmd_check(args):
    if not args:
        die("usage: check <change> [--tests]")
    d = change_dir(args[0])
    errs, warns, info = collect(d)
    if "--tests" in args:
        for r, files in sorted(acceptance_hits(info["test_reqs"]).items()):
            if not files:
                errs.append(f"{r}: no acceptance test mentions it in {CFG['acceptance_dir']}/")
        gone = {r for r, k in info["touched"].items() if k == "REMOVED"}
        for r, files in sorted(acceptance_hits(gone).items()):
            for f in files:
                warns.append(f"{r} removed but still referenced in {f.relative_to(ROOT)}")
        undone = [t["id"] for t in info["tasks"] if not t["done"]]
        if undone:
            errs.append(f"open tasks: {','.join(undone)}")
    for w in warns:
        print(f"WARN  {w}")
    for e in errs:
        print(f"ERROR {e}")
    print(f"{'FAIL' if errs else 'OK'} {d.name}: {len(info['touched'])} REQ, "
          f"{len(info['tasks'])} tasks, {len(errs)} errors, {len(warns)} warnings")
    sys.exit(1 if errs else 0)


def cmd_context(args):
    if len(args) < 2:
        die("usage: context <change> <task> [--plan]")
    d = change_dir(args[0])
    tasks = parse_tasks(d)
    t = next((x for x in tasks if x["id"] == args[1]), None)
    if not t:
        die(f"{args[1]} not in tasks.md")
    living = all_living()
    _, _, info = collect(d)
    print(f"# Context {d.name} {t['id']} ({t['kind']})\n\n{t['raw']}\n")
    for b in t["blocked_by"]:
        dep = next((x for x in tasks if x["id"] == b), None)
        if dep:
            print(f"depends on: {dep['raw']}")
    print("\n## Requirements\n")
    for r in t["reqs"]:
        if r in info["blocks"]:
            print(f"<!-- {info['touched'][r]} in this change -->")
            print(info["blocks"][r].text + "\n")
        elif r in living:
            print(f"<!-- unchanged, specs/{living[r][0]} -->")
            print(living[r][1].text + "\n")
    adrs = adr_files()
    if t["adrs"]:
        print("## Decisions\n")
    for a in t["adrs"]:
        if a in adrs:
            fm, body = read_fm(adrs[a])
            body = strip_comments(body)
            m = re.search(r"^## Decision[ \t]*\n(.*?)(?=^## |\Z)", body, re.S | re.M)
            title = body.strip().splitlines()[0] if body.strip() else a
            text = (m.group(1) if m else "").strip() or "(Decision section is empty: report this)"
            print(f"{title} [{fm.get('status')}]\n{text}\n")
    if t["kind"] == "impl" and ACCEPT.exists():
        hits = acceptance_hits(set(t["reqs"]))
        files = sorted({str(f.relative_to(ROOT)) for fs in hits.values() for f in fs})
        if files:
            print("## Frozen acceptance tests (read-only, make them pass)\n")
            print("\n".join(files) + "\n")
    plan = strip_comments(read_fm(d / "plan.md")[1]) if (d / "plan.md").exists() else ""
    if "--plan" in args and plan:
        print("## Plan\n")
        print(plan)
    elif t["kind"] == "test" and plan:
        m = re.search(r"^## Contracts\s*\n(.*?)(?=^## |\Z)", plan, re.S | re.M)
        if m and m.group(1).strip():
            print("## Contracts (from plan.md; the only plan section you get)\n")
            print(m.group(1).strip() + "\n")


def frozen_set(d: Path) -> dict[str, str]:
    _, _, info = collect(d)
    files = {f for fs in acceptance_hits(info["test_reqs"]).values() for f in fs}
    return {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(files)}


def cmd_freeze(args):
    if not args:
        die("usage: freeze <change>")
    d = change_dir(args[0])
    snap = frozen_set(d)
    if not snap:
        die("no acceptance test references this change's REQs; nothing to freeze", 1)
    atomic_write(d / "frozen.json", json.dumps(snap, indent=2) + "\n")
    print(f"froze {len(snap)} file(s) -> {(d / 'frozen.json').relative_to(ROOT)}")


def cmd_verify_frozen(args):
    if not args:
        die("usage: verify-frozen <change>")
    d = change_dir(args[0])
    f = d / "frozen.json"
    if not f.exists():
        die("no frozen.json; run freeze after the acceptance tests are written", 1)
    snap = json.loads(f.read_text())
    bad = 0
    for rel, h in snap.items():
        p = ROOT / rel
        if not p.exists():
            print(f"ERROR {rel} deleted after freeze")
            bad += 1
        elif hashlib.sha256(p.read_bytes()).hexdigest() != h:
            print(f"ERROR {rel} modified after freeze")
            bad += 1
    print(f"{'FAIL' if bad else 'OK'} {len(snap)} frozen file(s), {bad} tampered")
    sys.exit(1 if bad else 0)


def cmd_sync(args):
    if not args:
        die("usage: sync <change> [--dry-run] [--force]")
    d = change_dir(args[0])
    dry, force = "--dry-run" in args, "--force" in args
    fm, body = read_fm(d / "intent.md")
    if fm.get("status") != "verified" and not force:
        die(f"status is {fm.get('status')}; sync requires verified (or --force)", 1)
    errs, _, info = collect(d)
    if errs:
        for e in errs:
            print(f"ERROR {e}")
        die("fix errors before sync", 1)
    specs: dict[str, LivingSpec] = {}
    log = []
    for delta in info["deltas"]:
        ls = specs.setdefault(delta.capability, LivingSpec.load(delta.capability))
        for b in delta.modified:
            i = ls.blocks.index(ls.get(b.req))
            ls.blocks[i] = Block(b.req, b.title, b.lines)
            log.append(f"MODIFIED {b.req}")
        for b in delta.removed:
            ls.blocks.remove(ls.get(b.req))
            log.append(f"REMOVED  {b.req}")
        for b in delta.added:
            ls.blocks.append(Block(b.req, b.title, b.lines))
            log.append(f"ADDED    {b.req}")
    adr_list = fm.get("adrs", []) if isinstance(fm.get("adrs"), list) else []
    adr_errs = [e for a in adr_list for e in accept_adr(a, dry=True)]
    if adr_errs:
        for e in adr_errs:
            print(f"ERROR {e}")
        die("ADR problems", 1)
    for line in log:
        print(line)
    if dry:
        print(f"DRY-RUN ok, {len(log)} change(s), ADRs to accept: {','.join(adr_list) or '-'}")
        return
    for ls in specs.values():
        ls.blocks.sort(key=lambda b: b.req)
        atomic_write(ls.path, ls.render())
    for a in adr_list:
        accept_adr(a)
    fm["status"] = "archived"
    fm["archived"] = _dt.date.today().isoformat()
    write_fm(d / "intent.md", fm, body)
    dest = CHANGES / "archive" / f"{_dt.date.today().isoformat()}-{d.name}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(d), dest)
    print(f"synced {len(log)} change(s); ADRs accepted: {','.join(adr_list) or '-'}; "
          f"archived -> {dest.relative_to(ROOT)}")


COMMANDS = {
    "init": cmd_init, "config": cmd_config, "new": cmd_new, "status": cmd_status, "set-status": cmd_set_status,
    "delta-stub": cmd_delta_stub, "adr-new": cmd_adr_new, "adr-accept": cmd_adr_accept,
    "check": cmd_check, "context": cmd_context, "freeze": cmd_freeze,
    "verify-frozen": cmd_verify_frozen, "sync": cmd_sync,
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(2)
    try:
        COMMANDS[sys.argv[1]](sys.argv[2:])
    except BrokenPipeError:  # output piped into head/grep -m
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
