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
  delta-new <change> <capability>[/<concept>] | invariants/<category>[/<concept>]
                                     scaffold changes/<change>/specs/<group>/<concept>.md
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
  bundle <specs|change> [--fix]      validate (and repair) an OKF bundle: specs/ or changes/<change>/
Branch / PR / resume (git + gh; the lead runs them)
  start <change> --title T [--pr-title P] [--base B] [--requires a,b]
                                     branch sdd/<change>, worktree, scaffold, push, draft PR
  requires <change> [<dep>... | --clear]
                                     set (or show) the changes this one needs merged first
  deps <change>                      state of the required changes (exit 1 unless all merged)
  checkpoint <change> [--phase P] [-m MSG]
                                     record the phase, commit everything, push
  set-pr <change> <number> [--url U]  record a PR created by hand
  resume <change> [--pr N]           fetch the branch, (re)create its worktree, show the phase;
                                     refuses while a required change is not merged into the base
  finish <change>                    after sync: phase done, commit, push, mark the PR ready
Exit code: 0 ok, 1 errors found, 2 usage error.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

STATUSES = ["draft", "approved", "implementing", "verified", "archived"]
# Workflow phases (same ids as hooks/phase.ts PHASES, plus `done`), with the statuses a
# change may have while in each (a fix is still `draft` through plan and acceptance).
PHASES = ["spec", "gate1", "plan", "gate2", "acceptance", "implement", "verify", "sync", "done"]
PHASE_STATUSES = {
    "spec": {"draft"}, "gate1": {"draft"}, "plan": {"draft", "approved"},
    "gate2": {"draft", "approved"}, "acceptance": {"draft", "implementing"},
    "implement": {"implementing"}, "verify": {"implementing"}, "sync": {"verified"},
    "done": {"archived"},
}
PHASE_STEPS = {
    "spec": "step 2: spec-author writes intent, delta, ADRs (files may be partial: sdd check)",
    "gate1": "step 3: show Gate 1 to the user",
    "plan": "step 4: planner writes plan.md and tasks.md",
    "gate2": "step 5: sdd check, then set-status implementing",
    "acceptance": "step 6: acceptance-tester for the open (test) tasks",
    "implement": "step 7: implementers for the open (impl) tasks",
    "verify": "step 8: verifier, then code-review",
    "sync": "step 8.4: sdd sync, then sdd finish",
    "done": "nothing left: the PR is ready for review",
}
ADR_RE = re.compile(r"ADR-\d{4}")
TASK_RE = re.compile(r"^- \[( |x|X)\] (T\d+) \((test|impl|chore)\) (.*)$")
BASE_RE = re.compile(r"^<!--\s*base:\s*([0-9a-f]{8})\s*-->\s*$")
SECTION_RE = re.compile(r"^## (ADDED|MODIFIED|REMOVED)\s*$")


# ---------------------------------------------------------------- config ---
def project_root() -> Path:
    """Nearest ancestor with .claude/sdd.json, else with changes/ or specs/, else the git
    root. The search stops at the enclosing git root: nothing above the repo counts."""
    p = Path.cwd()
    chain: list[Path] = []
    for cand in (p, *p.parents):
        chain.append(cand)
        if (cand / ".git").exists():
            break
    for marker in (lambda c: (c / ".claude" / "sdd.json").exists(),
                   lambda c: (c / "changes").is_dir() or (c / "specs").is_dir()):
        for cand in chain:
            if marker(cand):
                return cand
    return chain[-1] if (chain[-1] / ".git").exists() else p


ROOT = project_root()
CFG = {
    "specs_dir": "specs",
    "changes_dir": "changes",
    "adr_dir": "adr",
    "acceptance_dir": "tests/acceptance",
    "acceptance_cmd": "pytest -q {files}",
    "unit_cmd": "pytest -q tests/unit",
    "req_id_pattern": "REQ-[A-Z0-9]+-[0-9]{3}",
    "inv_id_pattern": "INV-[A-Z0-9]+-[0-9]{3}",
    "concept_max_blocks": 5,         # REQ/INV blocks per concept file before `bundle` warns
    "base_branch": "",               # empty: the remote's default branch, else main
    "branch_prefix": "sdd/",
    "worktree_dir": ".claude/worktrees",
}
DEFAULT_CFG = dict(CFG)
_cfg_file = ROOT / ".claude" / "sdd.json"
if _cfg_file.exists():
    CFG.update(json.loads(_cfg_file.read_text()))

SPECS = ROOT / CFG["specs_dir"]
CHANGES = ROOT / CFG["changes_dir"]
ADRS = ROOT / CFG["adr_dir"]
ACCEPT = ROOT / CFG["acceptance_dir"]
INV_RE = re.compile(CFG["inv_id_pattern"])
ID_RE = re.compile(f"(?:{CFG['req_id_pattern']})|(?:{CFG['inv_id_pattern']})")
HEAD_RE = re.compile(r"^### (" + ID_RE.pattern + r"):\s*(.*)$")
INV_GROUP = "invariants"             # specs/invariants/<category>/<concept>.md holds INV blocks
RESERVED = {"index.md", "log.md"}    # generated OKF files, never concepts
OKF_VERSION = '"0.2"'
KEBAB_RE = re.compile(r"[a-z0-9][a-z0-9-]*")
TEMPLATES = Path(__file__).resolve().parent.parent / "skills" / "change" / "templates"


COMMENT_RE = re.compile(r"<!--(?!\s*base:).*?-->", re.S)


def strip_comments(text: str) -> str:
    """Drop HTML comments (template guidance), keep `<!-- base: -->` markers."""
    return re.sub(r"\n{3,}", "\n\n", COMMENT_RE.sub("", text))


def render_template(name: str, fallback: str, **vars: str) -> str:
    """Template `name` with `{{key}}` placeholders filled; `fallback` if it is missing."""
    src = TEMPLATES / name
    body = src.read_text() if src.exists() else fallback
    for k, v in vars.items():
        body = body.replace("{{" + k + "}}", v)
    return body


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


def fm_text(fm: dict, body: str) -> str:
    lines = ["---"]
    for k, v in fm.items():
        lines.append(f"{k}: [{', '.join(v)}]" if isinstance(v, list) else f"{k}: {v}")
    lines.append("---")
    return "\n".join(lines) + "\n\n" + body


def write_fm(path: Path, fm: dict, body: str):
    atomic_write(path, fm_text(fm, body))


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

    @property
    def has_check(self) -> bool:
        return any(l.startswith("#### Check:") for l in self.lines)


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


def is_inv(ident: str) -> bool:
    return INV_RE.fullmatch(ident) is not None


def is_inv_group(group: str) -> bool:
    return group == INV_GROUP or group.startswith(INV_GROUP + "/")


def title_of_stem(stem: str) -> str:
    return stem.replace("-", " ").capitalize()


def first_heading(lines: list[str]) -> str:
    return next((l[2:].strip() for l in lines if l.startswith("# ")), "")


def want_fm(group: str, stem: str, fm: dict, pre: list[str]) -> dict:
    """The front matter a living concept must carry; other keys are kept."""
    inv = is_inv_group(group)
    out = {"type": "invariant" if inv else "spec",
           "title": fm.get("title") or first_heading(pre) or title_of_stem(stem),
           ("category" if inv else "capability"): group.split("/")[-1] if inv else group,
           "sources": fm["sources"] if isinstance(fm.get("sources"), list) else []}
    for k, v in fm.items():
        out.setdefault(k, v)
    return out


def concept_name(path: Path, group: str) -> str:
    """File stem of a concept; a legacy `spec.md` is named after its group."""
    return group.split("/")[-1] if path.stem == "spec" else path.stem


@dataclass
class Concept:
    """One short living-spec file: front matter plus up to concept_max_blocks REQ/INV blocks."""
    path: Path
    fm: dict
    pre: list[str]
    blocks: list[Block]

    @classmethod
    def load(cls, path: Path, group: str) -> "Concept":
        fm, pre, blocks = {}, [], []
        if path.exists():
            fm, body = read_fm(path)
            pre, blocks = split_blocks(body.splitlines())
        fm = want_fm(group, path.stem, fm, pre)
        if not any(l.strip() for l in pre):
            pre = [f"# {fm['title']}", ""]
        return cls(path, fm, pre, blocks)

    def get(self, req: str) -> Block | None:
        return next((b for b in self.blocks if b.req == req), None)

    def render(self) -> str:
        body = "\n".join(self.pre).rstrip("\n") + "\n"
        for b in self.blocks:
            body += "\n" + b.text + "\n"
        return fm_text(self.fm, body)


def living_files() -> list[tuple[str, Path]]:
    """(group, file) of every concept under specs/: group is `<capability>` or `invariants/<category>`."""
    out = []
    if SPECS.exists():
        for f in sorted(SPECS.rglob("*.md")):
            rel = f.relative_to(SPECS).parent.as_posix()
            if f.name not in RESERVED and rel != ".":
                out.append((rel, f))
    return out


def all_living() -> dict[str, tuple[str, Block, Path]]:
    """REQ/INV id -> (group, block, concept file) across every living concept."""
    out: dict[str, tuple[str, Block, Path]] = {}
    for group, f in living_files():
        _, blocks = split_blocks(read_fm(f)[1].splitlines())
        for b in blocks:
            out[b.req] = (group, b, f)
    return out


@dataclass
class Delta:
    group: str                 # `<capability>` or `invariants/<category>`
    concept: str               # file stem of the target concept
    path: Path
    sources: list[str] = field(default_factory=list)
    added: list[Block] = field(default_factory=list)
    modified: list[Block] = field(default_factory=list)
    removed: list[Block] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def target(self) -> Path:
        return SPECS / self.group / f"{self.concept}.md"


def delta_files(change: Path) -> list[tuple[str, str, Path]]:
    """(group, concept, file) of each delta under changes/<c>/specs/. A flat `<cap>.md` is the
    legacy layout and maps to <cap>/<cap>."""
    out = []
    ddir = change / "specs"
    if ddir.exists():
        for f in sorted(ddir.rglob("*.md")):
            rel = f.relative_to(ddir)
            if f.name in RESERVED:
                continue
            group = f.stem if len(rel.parts) == 1 else rel.parent.as_posix()
            out.append((group, f.stem, f))
    return out


def load_deltas(change: Path) -> list[Delta]:
    out = []
    for group, concept, f in delta_files(change):
        fm, _ = read_fm(f)
        d = Delta(group, concept, f, fm["sources"] if isinstance(fm.get("sources"), list) else [])
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


# ------------------------------------------------------------------- state --
def load_state(change: Path) -> dict:
    f = change / "state.json"
    try:
        return json.loads(f.read_text()) if f.exists() else {}
    except ValueError:
        return {}


def save_state(change: Path, st: dict):
    st["updated"] = _dt.date.today().isoformat()
    atomic_write(change / "state.json", json.dumps(st, indent=2) + "\n")


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
            "reqs": sorted(set(ID_RE.findall(rest))),
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
            found = set(ID_RE.findall(f.read_text(errors="ignore")))
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
        (d / t).write_text(render_template(t, "", id=name, title=title, date=today))
    write_change_index(d)
    print(f"created {d.relative_to(ROOT)}/ (index.md intent.md plan.md tasks.md specs/)")


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
    for p, text in (build_spec_indexes() or {SPECS / "index.md": ""}).items():
        if p == SPECS / "index.md" and not p.exists():
            atomic_write(p, text or render_dir_index(SPECS, "", [], []))
            made.append(str(p.relative_to(ROOT)))
    if not (SPECS / "log.md").exists():
        atomic_write(SPECS / "log.md", SPEC_LOG_HEAD)
        made.append(str((SPECS / "log.md").relative_to(ROOT)))
    ignore = ROOT / ".gitignore"
    line = f"/{CFG['worktree_dir'].strip('/')}/"
    old = ignore.read_text() if ignore.exists() else ""
    if line not in old.splitlines():
        atomic_write(ignore, old + ("" if not old or old.endswith("\n") else "\n") + line + "\n")
        made.append(f".gitignore ({line})")
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
            st = load_state(d)
            out.append({
                "id": d.name, "title": title, "status": fm.get("status", "?"),
                "size": fm.get("size", "change"),
                "phase": st.get("phase"), "pr": st.get("pr"), "branch": st.get("branch"),
                "requires": st.get("requires", []),
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
        st = load_state(d)
        extra = (f"  phase={st['phase']}" if st.get("phase") else "") + (f"  pr=#{st['pr']}" if st.get("pr") else "") \
            + (f"  requires={','.join(st['requires'])}" if st.get("requires") else "")
        print(f"{d.name}  status={fm.get('status', '?')}  tasks={done}/{len(tasks)}  "
              f"size={fm.get('size', '?')}{extra}")
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


def delta_template(group: str, concept: str) -> str:
    name = "invariant-delta.md" if is_inv_group(group) else "delta.md"
    return render_template(name, "# Delta: {{concept}}\n\n## ADDED\n\n## MODIFIED\n\n## REMOVED\n",
                           group=group, concept=concept, capability=group.split("/")[-1],
                           target=f"{CFG['specs_dir']}/{group}/{concept}.md")


def cmd_delta_new(args):
    if len(args) != 2:
        die("usage: delta-new <change> <capability>[/<concept>] | invariants/<category>[/<concept>]")
    d, parts = change_dir(args[0]), args[1].split("/")
    inv = parts[0] == INV_GROUP
    if len(parts) not in ((2, 3) if inv else (1, 2)) or not all(KEBAB_RE.fullmatch(x) for x in parts):
        die("target must be <capability>[/<concept>] or invariants/<category>[/<concept>], kebab-case")
    group = "/".join(parts[:2] if inv else parts[:1])
    concept = parts[-1]
    f = d / "specs" / group / f"{concept}.md"
    if f.exists():
        die(f"{f.relative_to(ROOT)} already exists")
    atomic_write(f, delta_template(group, concept))
    write_change_index(d)
    print(f"created {f.relative_to(ROOT)}")


def cmd_delta_stub(args):
    if len(args) < 2:
        die("usage: delta-stub <change> <REQ|INV> [--remove]")
    d, req = change_dir(args[0]), args[1]
    living = all_living()
    if req not in living:
        die(f"{req} not in living specs (use ## ADDED for new requirements)")
    group, blk, src = living[req]
    concept = concept_name(src, group)
    section = "REMOVED" if "--remove" in args else "MODIFIED"
    f = d / "specs" / group / f"{concept}.md"
    text = f.read_text() if f.exists() else delta_template(group, concept)
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
    write_change_index(d)
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
    body = render_template("adr.md", "# {{num}}: {{title}}\n", num=num, title=title,
                           date=_dt.date.today().isoformat(), supersedes=sup or "")
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


# ------------------------------------------------------------- OKF bundles --
def concept_ids(path: Path) -> list[str]:
    return [b.req for b in split_blocks(read_fm(path)[1].splitlines())[1]]


def render_dir_index(d: Path, rel: str, concepts: list[Path], subs: list[Path]) -> str:
    fm = {"okf_version": OKF_VERSION} if not rel else {}
    fm.update({"type": "index", "title": rel or "Specs"})
    lines = [f"# {rel or 'Specs'}", ""]
    for s in subs:
        lines.append(f"- [{s.name}/]({s.name}/index.md)")
    for c in concepts:
        cfm, body = read_fm(c)
        title = cfm.get("title") or first_heading(body.splitlines()) or title_of_stem(c.stem)
        ids = ", ".join(concept_ids(c))
        lines.append(f"- [{title}]({c.name})" + (f" — {ids}" if ids else ""))
    return fm_text(fm, "\n".join(lines) + "\n")


def build_spec_indexes() -> dict[Path, str]:
    """Expected index.md of specs/ and of every directory below it that holds concepts."""
    out: dict[Path, str] = {}

    def walk(d: Path, rel: str) -> bool:
        concepts = sorted(f for f in d.glob("*.md") if f.name not in RESERVED)
        subs = [s for s in sorted(p for p in d.iterdir() if p.is_dir())
                if walk(s, f"{rel}/{s.name}" if rel else s.name)]
        if rel and not concepts and not subs:
            return False
        out[d / "index.md"] = render_dir_index(d, rel, concepts, subs)
        return True

    if SPECS.exists():
        walk(SPECS, "")
    return out


def build_change_index(change: Path) -> str:
    fm, _ = read_fm(change / "intent.md")
    title = fm.get("title") or change.name
    head = {"okf_version": OKF_VERSION, "type": "change", "title": title}
    lines = [f"# {title}", "", "- [Intent](intent.md)", "- [Plan](plan.md)", "- [Tasks](tasks.md)"]
    deltas = load_deltas(change)
    for heading, inv in (("Spec delta", False), ("Invariant delta", True)):
        rows = []
        for d in deltas:
            if is_inv_group(d.group) != inv:
                continue
            ops = "; ".join(f"{k.upper()} {', '.join(b.req for b in getattr(d, k))}"
                            for k in ("added", "modified", "removed") if getattr(d, k))
            rel = d.path.relative_to(change).as_posix()
            rows.append(f"- [{rel}]({rel})" + (f" — {ops}" if ops else ""))
        if rows:
            lines += ["", f"## {heading}", ""] + rows
    return fm_text(head, "\n".join(lines) + "\n")


def write_change_index(change: Path):
    atomic_write(change / "index.md", build_change_index(change))


class Report:
    """Findings of a bundle check. With fix=True a fixable finding is repaired and listed as fixed."""
    def __init__(self, fix: bool):
        self.fix, self.errs, self.warns, self.fixed = fix, [], [], []

    def issue(self, level: str, msg: str, fixer=None):
        if fixer is not None and self.fix:
            fixer()
            self.fixed.append(msg)
        else:
            (self.errs if level == "ERROR" else self.warns).append(msg + (" [fixable]" if fixer else ""))


def _drop_missing_sources(sources: list[str]) -> list[str]:
    return [s for s in sources if (ROOT / re.sub(r":\d+(-\d+)?$", "", s)).exists()]


def check_specs(rep: Report):
    rel = lambda p: p.relative_to(ROOT).as_posix()
    if not SPECS.exists():
        rep.issue("ERROR", f"{rel(SPECS)}/ missing", lambda: SPECS.mkdir(parents=True))
        if not SPECS.exists():
            return
    for f in sorted(SPECS.glob("*/spec.md")):          # legacy: one long spec.md per capability
        cap = f.parent.name
        dest = f.with_name(f"{cap}.md")
        if dest.exists():
            rep.issue("ERROR", f"{rel(f)}: legacy file, {rel(dest)} already exists")
        else:
            rep.issue("ERROR", f"{rel(f)}: legacy layout, expected {rel(dest)}", lambda f=f, dest=dest: f.rename(dest))
    seen: dict[str, Path] = {}
    for group, f in living_files():
        parts = f.relative_to(SPECS).parts
        want_depth = 3 if group.startswith(INV_GROUP + "/") else 2
        if len(parts) != want_depth or group == INV_GROUP:
            rep.issue("ERROR", f"{rel(f)}: concepts live in specs/<capability>/ or specs/{INV_GROUP}/<category>/")
            continue
        if not all(KEBAB_RE.fullmatch(x) for x in (*group.split("/"), f.stem)):
            rep.issue("ERROR", f"{rel(f)}: names must be kebab-case")
        concept = Concept.load(f, group)
        raw_fm, body = read_fm(f)
        fixes = []
        if concept.fm != raw_fm:
            fixes.append("front matter")
            rep.issue("ERROR", f"{rel(f)}: front matter incomplete (type, title, "
                      f"{'category' if is_inv_group(group) else 'capability'}, sources)", lambda: None)
        kept = _drop_missing_sources(concept.fm["sources"])
        for s in concept.fm["sources"]:
            if s not in kept:
                fixes.append("sources")
                rep.issue("WARN", f"{rel(f)}: source '{s}' not found", lambda: None)
        concept.fm["sources"] = kept
        ids = [b.req for b in concept.blocks]
        for b in concept.blocks:
            if is_inv(b.req) != is_inv_group(group):
                rep.issue("ERROR", f"{rel(f)}: {b.req} does not belong under specs/{group}/ "
                          f"({'INV in the spec tree' if is_inv(b.req) else 'REQ in the invariant tree'})")
            if b.req in seen:
                rep.issue("ERROR", f"{b.req}: defined in both {rel(seen[b.req])} and {rel(f)}")
            seen[b.req] = f
            if is_inv(b.req) and not b.has_check:
                rep.issue("WARN", f"{rel(f)} {b.req}: no '#### Check:'")
            if not is_inv(b.req) and not b.has_scenario:
                rep.issue("WARN", f"{rel(f)} {b.req}: no '#### Scenario:'")
        if not concept.blocks:
            rep.issue("ERROR", f"{rel(f)}: concept has no requirement blocks", lambda f=f: f.unlink())
            continue
        if ids != sorted(ids):
            fixes.append("order")
            rep.issue("ERROR", f"{rel(f)}: blocks not sorted by id", lambda: None)
        if len(ids) > CFG["concept_max_blocks"]:
            rep.issue("WARN", f"{rel(f)}: {len(ids)} blocks > {CFG['concept_max_blocks']}, split it by topic")
        if rep.fix and fixes:
            concept.blocks.sort(key=lambda b: b.req)
            atomic_write(f, concept.render())
    expected = build_spec_indexes()
    for p, text in sorted(expected.items()):
        cur = p.read_text() if p.exists() else None
        if cur is None or (p == SPECS / "index.md" and "okf_version" not in cur):
            rep.issue("ERROR", f"{rel(p)}: missing" if cur is None else f"{rel(p)}: no okf_version",
                      lambda p=p, text=text: atomic_write(p, text))
        elif cur != text:
            rep.issue("ERROR", f"{rel(p)}: stale (lists other concepts than the directory holds)",
                      lambda p=p, text=text: atomic_write(p, text))
    for p in sorted(SPECS.rglob("index.md")):
        if p not in expected:
            rep.issue("WARN", f"{rel(p)}: index of a directory without concepts", lambda p=p: p.unlink())
    log = SPECS / "log.md"
    if not log.exists():
        rep.issue("ERROR", f"{rel(log)}: missing", lambda: atomic_write(log, SPEC_LOG_HEAD))
    for d in sorted((p for p in SPECS.rglob("*") if p.is_dir()), reverse=True):
        if not any(d.iterdir()):
            rep.issue("WARN", f"{rel(d)}/: empty directory", lambda d=d: d.rmdir())
    for f in sorted(SPECS.rglob("*")):
        if f.is_file() and f.suffix != ".md":
            rep.issue("WARN", f"{rel(f)}: not a concept (only .md files belong in specs/)")


SPEC_LOG_HEAD = fm_text({"type": "log", "title": "Specs log"}, "# Log\n\n")


def check_change(rep: Report, change: Path):
    rel = lambda p: p.relative_to(ROOT).as_posix()
    for name, kind in (("intent.md", "intent"), ("plan.md", "plan"), ("tasks.md", "tasks")):
        f = change / name
        if not f.exists():
            continue
        fm, body = read_fm(f)
        if fm.get("type") != kind:
            rep.issue("WARN", f"{rel(f)}: front matter lacks 'type: {kind}'",
                      lambda f=f, fm=fm, body=body, kind=kind: write_fm(f, {"type": kind, **{k: v for k, v in fm.items() if k != "type"}}, body))
    ddir = change / "specs"
    for group, concept, f in delta_files(change):
        if len(f.relative_to(ddir).parts) == 1:          # legacy flat layout
            dest = ddir / f.stem / f.name
            if dest.exists():
                rep.issue("WARN", f"{rel(f)}: legacy flat delta, {rel(dest)} already exists")
            else:
                rep.issue("WARN", f"{rel(f)}: legacy layout, expected {rel(dest)}",
                          lambda f=f, dest=dest: (dest.parent.mkdir(parents=True, exist_ok=True), f.rename(dest)))
    for group, concept, f in delta_files(change):
        parts = f.relative_to(ddir).parts
        if len(parts) == 1:
            continue
        want_depth = 3 if group.startswith(INV_GROUP + "/") else 2
        if len(parts) != want_depth or group == INV_GROUP:
            rep.issue("ERROR", f"{rel(f)}: deltas live in specs/<capability>/ or specs/{INV_GROUP}/<category>/")
            continue
        if not all(KEBAB_RE.fullmatch(x) for x in (*group.split("/"), concept)):
            rep.issue("ERROR", f"{rel(f)}: names must be kebab-case")
        fm, body = read_fm(f)
        want = {"type": "invariant-delta" if is_inv_group(group) else "spec-delta",
                "target": f"{CFG['specs_dir']}/{group}/{concept}.md",
                "sources": fm["sources"] if isinstance(fm.get("sources"), list) else []}
        want.update({k: v for k, v in fm.items() if k not in want})
        if any(fm.get(k) != want[k] for k in ("type", "target")) or "sources" not in fm:
            rep.issue("WARN", f"{rel(f)}: front matter incomplete (type, target, sources)",
                      lambda f=f, want=want, body=body: write_fm(f, want, body))
    idx = change / "index.md"
    text = build_change_index(change)
    if not idx.exists():
        rep.issue("WARN", f"{rel(idx)}: missing", lambda: atomic_write(idx, text))
    elif idx.read_text() != text:
        rep.issue("WARN", f"{rel(idx)}: stale", lambda: atomic_write(idx, text))


def bundle_check(target: str, fix: bool = False) -> Report:
    rep = Report(fix)
    if target == "specs":
        check_specs(rep)
    else:
        check_change(rep, change_dir(target))
    return rep


def cmd_bundle(args):
    fix = "--fix" in args
    args = [a for a in args if a != "--fix"]
    if len(args) != 1:
        die("usage: bundle <specs|change> [--fix]")
    rep = bundle_check(args[0], fix)
    for m in rep.fixed:
        print(f"FIXED {m}")
    for w in rep.warns:
        print(f"WARN  {w}")
    for e in rep.errs:
        print(f"ERROR {e}")
    tail = f", {len(rep.fixed)} fixed" if fix else ""
    print(f"{'FAIL' if rep.errs else 'OK'} {args[0]}: {len(rep.errs)} errors, {len(rep.warns)} warnings{tail}")
    sys.exit(1 if rep.errs else 0)


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
                where = f"{d.path.relative_to(ROOT).as_posix()} {b.req}"
                if is_inv(b.req) != is_inv_group(d.group):
                    errs.append(f"{where}: {'INV' if is_inv(b.req) else 'REQ'} in the wrong tree "
                                f"(INV go under specs/{INV_GROUP}/<category>/, REQ under specs/<capability>/)")
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
                    elif cur[0] != d.group:
                        errs.append(f"{where}: lives in specs/{cur[0]}, not {d.group}")
                    elif not b.base:
                        errs.append(f"{where}: missing <!-- base: --> (use delta-stub)")
                    elif b.base != cur[1].digest:
                        errs.append(f"{where}: CONFLICT base {b.base} != current {cur[1].digest} "
                                    f"(living spec changed since this delta was written)")
                if kind != "removed" and is_inv(b.req) and not b.has_check:
                    errs.append(f"{where}: no '#### Check:' (how the invariant is verified)")
                elif kind != "removed" and not is_inv(b.req) and not b.has_scenario:
                    errs.append(f"{where}: no '#### Scenario:' (acceptance criteria required)")
    if not touched and fm.get("size") != "fix":
        warns.append("no spec delta in this change")
    rep = bundle_check(change.name)
    errs += [f"bundle: {e}" for e in rep.errs]
    warns += [f"bundle: {w}" for w in rep.warns]
    phase = load_state(change).get("phase")
    if phase and (phase not in PHASES or fm.get("status") not in PHASE_STATUSES[phase]):
        warns.append(f"state.json phase '{phase}' does not fit status '{fm.get('status')}'")

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
        for r in sorted(set(ID_RE.findall(ptxt))):
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
        if tasks and "impl" not in kinds and not is_inv(r):
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
    return errs, warns, {"touched": touched, "tasks": tasks, "deltas": deltas, "living": living,
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
    _, _, info = collect(d)
    living = info["living"]
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
    if t["kind"] == "impl":
        held = {i: b for i, (_, b, _) in living.items() if is_inv(i)}
        for i, b in info["blocks"].items():
            if is_inv(i):
                held[i] = b
        for i, k in info["touched"].items():
            if k == "REMOVED":
                held.pop(i, None)
        rest = [i for i in sorted(held) if i not in t["reqs"]]
        if rest:
            print("## Invariants in force (do not break; `sdd context` of a task naming one prints it in full)\n")
            print("\n".join(f"- {i}: {held[i].title}" for i in rest) + "\n")
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
    errs += [f"specs bundle: {e}" for e in bundle_check("specs").errs]
    if errs:
        for e in errs:
            print(f"ERROR {e}")
        die("fix errors before sync (a specs bundle error: `bundle specs --fix`)", 1)
    living = info["living"]
    concepts: dict[Path, Concept] = {}

    def concept(path: Path, group: str) -> Concept:
        return concepts.setdefault(path, Concept.load(path, group))

    log = []
    for delta in info["deltas"]:
        tgt = concept(delta.target, delta.group)
        tgt.fm["sources"] = sorted(set(tgt.fm["sources"]) | set(delta.sources))
        for b in delta.modified:
            _, _, src_path = living[b.req]
            src = concept(src_path, delta.group)
            src.blocks.remove(src.get(b.req))
            tgt.blocks.append(Block(b.req, b.title, b.lines))
            log.append(f"{'MODIFIED' if src is tgt else 'MOVED   '} {b.req}")
        for b in delta.removed:
            src = concept(living[b.req][2], delta.group)
            src.blocks.remove(src.get(b.req))
            log.append(f"REMOVED  {b.req}")
        for b in delta.added:
            tgt.blocks.append(Block(b.req, b.title, b.lines))
            log.append(f"ADDED    {b.req}")
    adr_list = fm.get("adrs", []) if isinstance(fm.get("adrs"), list) else []
    adr_errs = [e for a in adr_list for e in accept_adr(a, dry=True)]
    if adr_errs:
        for e in adr_errs:
            print(f"ERROR {e}")
        die("ADR problems", 1)
    for line in log:
        print(line)
    emptied = sorted(c.path for c in concepts.values() if not c.blocks)
    if dry:
        print(f"DRY-RUN ok, {len(log)} change(s), concepts emptied: {len(emptied)}, "
              f"ADRs to accept: {','.join(adr_list) or '-'}")
        return
    for c in concepts.values():
        if c.blocks:
            c.blocks.sort(key=lambda b: b.req)
            atomic_write(c.path, c.render())
        elif c.path.exists():
            c.path.unlink()
    rep = Report(True)
    check_specs(rep)                      # regenerates the indexes, drops emptied directories
    today = _dt.date.today().isoformat()
    summary = "; ".join(" ".join(l.split()) for l in log) or "no spec change"
    logf = SPECS / "log.md"
    atomic_write(logf, logf.read_text().rstrip("\n") + f"\n- {today} {d.name}: {summary}\n")
    for a in adr_list:
        accept_adr(a)
    fm["status"] = "archived"
    fm["archived"] = today
    write_fm(d / "intent.md", fm, body)
    dest = CHANGES / "archive" / f"{today}-{d.name}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(d), dest)
    print(f"synced {len(log)} change(s); ADRs accepted: {','.join(adr_list) or '-'}; "
          f"archived -> {dest.relative_to(ROOT)}")

# ---------------------------------------------------- branch / PR / resume --
def sh(cmd: list[str], cwd: Path | None = None) -> tuple[int, str]:
    """Run a command, (exit code, stdout+stderr). 127 when the program is missing."""
    try:
        p = subprocess.run(cmd, cwd=cwd or ROOT, capture_output=True, text=True, timeout=120)
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return 127, str(e)
    return p.returncode, (p.stdout + p.stderr).strip()


def git(*args: str, cwd: Path | None = None) -> tuple[int, str]:
    return sh(["git", *args], cwd)


def git_ok(*args: str, cwd: Path | None = None) -> str:
    code, out = git(*args, cwd=cwd)
    if code != 0:
        die(f"git {' '.join(args[:2])} failed: {out.splitlines()[-1] if out else code}", 1)
    return out


def base_branch(override: str | None = None) -> str:
    if override or CFG["base_branch"]:
        return override or CFG["base_branch"]
    code, out = git("symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    return out.removeprefix("origin/") if code == 0 and out else "main"


def pr_from(out: str) -> tuple[int | None, str]:
    m = re.search(r"https?://\S+/pull/(\d+)", out)
    return (int(m.group(1)), m.group(0)) if m else (None, "")


def push(wt: Path):
    code, out = git("push", "-u", "origin", "HEAD", cwd=wt)
    if code != 0:
        die(f"push failed: {out.splitlines()[-1] if out else code}", 1)


def commit_all(wt: Path, msg: str) -> bool:
    """Stage everything, commit if something is staged. True when a commit was made."""
    git_ok("add", "-A", cwd=wt)
    if git("diff", "--cached", "--quiet", cwd=wt)[0] == 0:
        return False
    git_ok("commit", "-m", msg, cwd=wt)
    return True


def opt(args: list[str], flag: str) -> str | None:
    return args[args.index(flag) + 1] if flag in args and args.index(flag) + 1 < len(args) else None


CHANGE_ID_RE = re.compile(r"[a-z0-9][a-z0-9-]{1,60}")


def parse_requires(raw: list[str], name: str) -> list[str]:
    out: list[str] = []
    for dep in (x for r in raw for x in r.split(",") if x):
        if not CHANGE_ID_RE.fullmatch(dep):
            die(f"required change '{dep}' is not a kebab-case id")
        if dep == name:
            die(f"{name} cannot require itself")
        if dep not in out:
            out.append(dep)
    return out


def is_archive_of(dirname: str, change: str) -> bool:
    """True for the archive directory `sync` makes for `change` (<date>-<change>)."""
    return re.fullmatch(rf"\d{{4}}-\d{{2}}-\d{{2}}-{re.escape(change)}", dirname) is not None


def archived_in(ref: str, dep: str) -> str | None:
    """Path of dep's archive directory in `ref` (a git ref), else None."""
    code, out = git("ls-tree", "--name-only", ref, f"{CFG['changes_dir']}/archive/")
    for line in out.splitlines() if code == 0 else []:
        if is_archive_of(line.rsplit("/", 1)[-1], dep):
            return line
    return None


def base_of(st: dict) -> str:
    return st.get("base") or base_branch()


def state_at(ref: str, path: str) -> dict | None:
    code, out = git("show", f"{ref}:{path}")
    try:
        return json.loads(out) if code == 0 else None
    except ValueError:
        return None


def dep_states(name: str, requires: list[str], base: str, wt: Path) -> list[dict]:
    """State of every required change, transitively, deepest first. `ok`: merged into the
    base and in wt's branch; `missing`: merged into the base, not yet in the branch; `ready`:
    finished (`finish` ran), its PR not merged; `open`: still being worked on, even if already
    synced; `unknown`: no branch found."""
    batch = [f"{CFG['branch_prefix']}{d}" for d in requires]
    if git("fetch", "origin", base, *batch)[0] == 0:
        fetched = set(batch)
    else:  # a missing branch fails the whole fetch: base alone, the others one by one
        git_ok("fetch", "origin", base)
        fetched = set()
    out: list[dict] = []
    seen: set[str] = set()

    def walk(deps: list[str], chain: list[str]):
        for dep in deps:
            if dep in chain:
                die(f"cycle {' -> '.join(chain + [dep])}", 1)
            if dep in seen:
                continue
            seen.add(dep)
            row = {"dep": dep, "state": "unknown", "detail": f"no branch {CFG['branch_prefix']}{dep}", "pr": None}
            if archived_in(f"origin/{base}", dep):
                arch_dir = wt / CFG["changes_dir"] / "archive"
                in_wt = arch_dir.is_dir() and any(is_archive_of(p.name, dep) for p in arch_dir.iterdir())
                row.update(state="ok" if in_wt else "missing",
                           detail="merged" if in_wt else f"merged into {base}, not in this branch")
            else:
                branch = f"{CFG['branch_prefix']}{dep}"
                nxt: list[str] = []
                if branch in fetched or git("fetch", "origin", branch)[0] == 0:
                    ref = f"origin/{branch}"
                    arch = archived_in(ref, dep)
                    st = (state_at(ref, f"{arch}/state.json") if arch
                          else state_at(ref, f"{CFG['changes_dir']}/{dep}/state.json")) or {}
                    pr = f" pr #{st['pr']}" if st.get("pr") else ""
                    row["pr"] = st.get("pr")
                    if arch and st.get("phase") == "done":
                        row.update(state="ready", detail=f"finished{pr}, awaits merge into {base}")
                    else:
                        row.update(state="open", detail=f"phase {st.get('phase') or '?'}{pr}"
                                   + (" (synced, `finish` not run)" if arch else ""))
                    nxt = st.get("requires", [])
                walk(nxt, chain + [dep])
            out.append(row)

    walk(requires, [name])
    return out


def dep_lines(rows: list[dict]) -> list[str]:
    return [f"{r['state']} {r['dep']} {r['detail']}" for r in rows]


def dep_next(rows: list[dict]) -> str:
    row = next(r for r in rows if r["state"] in ("open", "ready", "unknown"))
    if row["state"] == "ready":
        return f"merge the PR of {row['dep']}" + (f" (#{row['pr']})" if row["pr"] else "")
    return f"resume {row['dep']}" if row["state"] == "open" else f"{row['dep']} has no branch: check `requires`"


def blocked(rows: list[dict]) -> bool:
    return any(r["state"] in ("open", "ready", "unknown") for r in rows)


def missing(rows: list[dict]) -> bool:
    return any(r["state"] == "missing" for r in rows)


def bring_in_base(wt: Path, base: str):
    if git("status", "--porcelain", cwd=wt)[1]:
        die(f"uncommitted changes in {wt}: commit or stash them (or `checkpoint`), then retry", 1)
    code, out = git("merge", "--no-edit", f"origin/{base}", cwd=wt)
    if code != 0:
        files = git("diff", "--name-only", "--diff-filter=U", cwd=wt)[1].replace("\n", " ")
        git("merge", "--abort", cwd=wt)
        die(f"merging origin/{base} into the change branch failed "
            f"({files or (out.splitlines() or ['no output'])[-1]}): "
            f"merge it by hand in {wt}, then run `checkpoint` again", 1)
    push(wt)
    print(f"merged origin/{base} into the branch (required changes arrived)")


def cmd_start(args):
    if not args or args[0].startswith("-"):
        die("usage: start <change> --title T [--pr-title P] [--base B] [--requires a,b]")
    name = args[0]
    if not CHANGE_ID_RE.fullmatch(name):
        die("change id must be kebab-case")
    requires = parse_requires([opt(args, "--requires") or ""], name)
    title = opt(args, "--title") or name
    pr_title = opt(args, "--pr-title") or title
    base = base_branch(opt(args, "--base"))
    branch = CFG["branch_prefix"] + name
    wt = ROOT / CFG["worktree_dir"] / f"sdd-{name}"
    dep_rows = dep_states(name, requires, base, ROOT) if requires else []  # dies on a cycle, before any side effect
    if wt.exists() or git("rev-parse", "--verify", "-q", f"refs/heads/{branch}")[0] == 0:
        die(f"{branch} or {wt.relative_to(ROOT)} already exists; use `resume {name}`", 1)
    if not requires:  # otherwise dep_states fetched the base already
        git_ok("fetch", "origin", base)
    if git("cat-file", "-e", f"origin/{base}:.claude/sdd.json")[0] != 0:
        die(f"commit and push .claude/sdd.json (and .gitignore) to {base} first: the worktree starts from origin/{base}", 1)
    git_ok("worktree", "add", str(wt), "-b", branch, f"origin/{base}")
    try:
        code, out = sh([sys.executable, str(Path(__file__).resolve()), "new", name, "--title", title], wt)
        if code != 0:
            die(out, 1)
        d = wt / CFG["changes_dir"] / name
        save_state(d, {"phase": "spec", "branch": branch, "base": base, "pr": None, "pr_url": None,
                       "requires": requires})
        commit_all(wt, f"chore(sdd): start {name}")
        push(wt)
    except SystemExit:
        # nothing is published yet: drop the half-made worktree and branch so a retry is clean
        git("worktree", "remove", "--force", str(wt))
        git("branch", "-D", branch)
        raise
    body = (f"Spec-driven change `{name}`: {title}\n\nDraft until `sdd finish`. "
            f"Phase and PR are tracked in `{CFG['changes_dir']}/{name}/state.json`; "
            f"continue with `/sdd:change resume {name}`.")
    code, out = sh(["gh", "pr", "create", "--draft", "--base", base, "--head", branch,
                    "--title", pr_title, "--body", body], wt)
    num, url = pr_from(out) if code == 0 else (None, "")
    if num:
        st = load_state(d)
        st.update(pr=num, pr_url=url)
        save_state(d, st)
        commit_all(wt, f"chore(sdd): record PR #{num}")
        push(wt)
    print(f"worktree {wt}")
    print(f"branch {branch} (base {base})")
    if num:
        print(f"pr {num} {url}")
    else:
        print(f"PR missing ({(out.splitlines() or ['gh failed'])[-1][:120]}): create a draft PR for "
              f"{branch}, then run `set-pr {name} <number>`")
    if blocked(dep_rows):  # `missing`/`ok` don't matter: the branch was just cut from origin/<base>
        for line in dep_lines([r for r in dep_rows if r["state"] in ("open", "ready", "unknown")]):
            print(f"WARN requires {line}")
        print("WARN spec work may go on; plan and later phases wait until they are merged")
    print(f"next: EnterWorktree path={wt}")


def require_branch(st: dict, name: str):
    cur = git_ok("rev-parse", "--abbrev-ref", "HEAD")
    if cur != st["branch"]:
        die(f"on branch {cur}, expected {st['branch']}: enter the change's worktree (`resume {name}`)", 1)


def worktree_cwd(name: str) -> tuple[Path, dict]:
    """The change dir and state of a started change; refuses when HEAD is not its branch."""
    d = change_dir(name)
    st = load_state(d)
    if not st.get("branch"):
        die(f"{name} has no state.json; create changes with `start`", 1)
    require_branch(st, name)
    return d, st


def cmd_checkpoint(args):
    if not args or args[0].startswith("-"):
        die("usage: checkpoint <change> [--phase P] [-m MSG]")
    d, st = worktree_cwd(args[0])
    phase = opt(args, "--phase")
    if phase:
        if phase not in PHASES:
            die(f"phase must be one of {'|'.join(PHASES)}")
        if st.get("requires") and PHASES.index(phase) >= PHASES.index("plan"):
            base = base_of(st)
            rows = dep_states(args[0], st["requires"], base, ROOT)
            if blocked(rows):
                die("required changes are not merged: " + "; ".join(dep_lines(rows)) +
                    f". Next: {dep_next(rows)}", 1)
            if missing(rows):
                commit_all(ROOT, f"chore(sdd): {args[0]} checkpoint before merging base")
                bring_in_base(ROOT, base)
        st["phase"] = phase
        save_state(d, st)
    msg = opt(args, "-m") or f"chore(sdd): {args[0]} {st.get('phase', 'checkpoint')}"
    made = commit_all(ROOT, msg)
    push(ROOT)
    print(f"{'committed' if made else 'nothing to commit'}, pushed {st['branch']}, phase {st.get('phase')}")


def cmd_set_pr(args):
    if len(args) < 2 or not args[1].isdigit():
        die("usage: set-pr <change> <number> [--url U]")
    d, st = worktree_cwd(args[0])
    st.update(pr=int(args[1]), pr_url=opt(args, "--url") or st.get("pr_url"))
    save_state(d, st)
    commit_all(ROOT, f"chore(sdd): record PR #{args[1]}")
    push(ROOT)
    print(f"{args[0]}: pr {args[1]}")


def cmd_requires(args):
    if not args or args[0].startswith("-"):
        die("usage: requires <change> [<dep>... | --clear]")
    d, st = worktree_cwd(args[0])
    if len(args) == 1:
        print(",".join(st.get("requires", [])) or "-")
        return
    st["requires"] = [] if "--clear" in args else parse_requires(args[1:], args[0])
    rows = dep_states(args[0], st["requires"], base_of(st), ROOT) if st["requires"] else []  # dies on a cycle
    save_state(d, st)
    commit_all(ROOT, f"chore(sdd): {args[0]} requires {','.join(st['requires']) or 'nothing'}")
    push(ROOT)
    print(f"{args[0]}: requires {','.join(st['requires']) or '-'}")
    for line in dep_lines([r for r in rows if r["state"] in ("open", "ready", "unknown")]):
        print(f"WARN requires {line}")


def cmd_deps(args):
    if not args:
        die("usage: deps <change>")
    st = load_state(change_dir(args[0]))
    if not st.get("requires"):
        print(f"OK {args[0]}: requires nothing")
        return
    rows = dep_states(args[0], st["requires"], base_of(st), ROOT)
    for line in dep_lines(rows):
        print(line)
    stuck = blocked(rows)
    if stuck:
        print(f"next: {dep_next(rows)}")
    elif missing(rows):
        print("next: `checkpoint --phase <p>` or `resume` merges the base in")
    sys.exit(1 if stuck or missing(rows) else 0)


def worktree_of(branch: str) -> Path | None:
    _, out = git("worktree", "list", "--porcelain")
    path = None
    for line in out.splitlines():
        if line.startswith("worktree "):
            path = Path(line[9:])
        elif line == f"branch refs/heads/{branch}":
            return path
    return None


def cmd_resume(args):
    if not args or args[0].startswith("-"):
        die("usage: resume <change> [--pr N]")
    name = args[0]
    branch = None
    if opt(args, "--pr"):
        code, out = sh(["gh", "pr", "view", opt(args, "--pr"), "--json", "headRefName", "-q", ".headRefName"])
        if code != 0 or not out:
            die(f"gh pr view failed: {out[-120:]}", 1)
        branch = out.splitlines()[-1]
    else:
        branch = load_state(CHANGES / name).get("branch") or CFG["branch_prefix"] + name
    git_ok("fetch", "origin", branch)
    wt = worktree_of(branch)
    if wt is None:
        wt = ROOT / CFG["worktree_dir"] / f"sdd-{name}"
        if git("rev-parse", "--verify", "-q", f"refs/heads/{branch}")[0] == 0:
            git_ok("worktree", "add", str(wt), branch)
        else:
            git_ok("worktree", "add", "--track", "-b", branch, str(wt), f"origin/{branch}")
    code, out = git("pull", "--ff-only", "origin", branch, cwd=wt)
    if code != 0:
        die(f"cannot fast-forward {branch} in {wt}: {out.splitlines()[-1] if out else code}", 1)
    d = wt / CFG["changes_dir"] / name
    if not (d / "intent.md").exists():
        die(f"{branch} has no change '{name}' ({CFG['changes_dir']}/{name}/intent.md)", 1)
    st, fm = load_state(d), read_fm(d / "intent.md")[0]
    phase = st.get("phase")
    print(f"worktree {wt}")
    print(f"branch {branch}")
    print(f"pr {st.get('pr') or '-'} {st.get('pr_url') or ''}".rstrip())
    print(f"status {fm.get('status', '?')}")
    print(f"phase {phase or '-'}: {PHASE_STEPS.get(phase, 'no state.json: run `status` and derive the step')}")
    if st.get("requires"):
        base = base_of(st)
        rows = dep_states(name, st["requires"], base, wt)
        for line in dep_lines(rows):
            print(line)
        if blocked(rows):
            print(f"blocked: required changes are not merged into {base}")
            print(f"next: {dep_next(rows)}, then `resume {name}` again")
            sys.exit(1)
        if missing(rows):
            bring_in_base(wt, base)
    print(f"next: EnterWorktree path={wt}")


def cmd_finish(args):
    if not args:
        die("usage: finish <change>")
    name = args[0]
    hits = sorted(p for p in (CHANGES / "archive").glob(f"*-{name}")
                  if is_archive_of(p.name, name))
    if not hits:
        die(f"no archived change '{name}'; run sync first", 1)
    d = hits[-1]
    st = load_state(d)
    if not st.get("branch"):
        die(f"{name} has no state.json", 1)
    require_branch(st, name)
    st["phase"] = "done"
    save_state(d, st)
    made = commit_all(ROOT, f"chore(sdd): sync {name}")
    push(ROOT)
    print(f"{'committed' if made else 'nothing to commit'}, pushed {st['branch']}")
    if not st.get("pr"):
        print("no PR recorded: mark it ready by hand")
        return
    code, out = sh(["gh", "pr", "ready", str(st["pr"])])
    print(f"pr {st['pr']} ready for review" if code == 0 else
          f"WARN could not mark PR #{st['pr']} ready ({out[-120:]}): do it by hand")


COMMANDS = {
    "init": cmd_init, "config": cmd_config, "new": cmd_new, "status": cmd_status, "set-status": cmd_set_status,
    "delta-new": cmd_delta_new, "delta-stub": cmd_delta_stub, "adr-new": cmd_adr_new, "adr-accept": cmd_adr_accept,
    "check": cmd_check, "context": cmd_context, "freeze": cmd_freeze,
    "verify-frozen": cmd_verify_frozen, "sync": cmd_sync, "bundle": cmd_bundle,
    "start": cmd_start, "requires": cmd_requires, "deps": cmd_deps, "checkpoint": cmd_checkpoint, "set-pr": cmd_set_pr, "resume": cmd_resume,
    "finish": cmd_finish,
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(2)
    try:
        COMMANDS[sys.argv[1]](sys.argv[2:])
    except BrokenPipeError:  # output piped into head/grep -m
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
