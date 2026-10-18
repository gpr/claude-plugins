#!/usr/bin/env python3
"""sdd.py - deterministic tooling for the spec-driven workflow.

Everything that must stay exact (spec merge, ID traceability, base-version
conflicts, test freezing, ADR status) lives here, so no agent ever has to
"rewrite" a spec. Output is terse on purpose: it is read by agents.

Living specs are OKF concepts: `specs/capabilities/<id>.md` (type Capability, acceptance
criteria AC-NN) and `specs/invariants/<id>.md` (type Invariant). Tests and tasks cite
`capabilities/<id>#AC-NN` and `invariants/<id>`. ADRs are `adrs/NNNN_<slug>.md`, cited ADR-NNNN.

Usually called through the plugin's `sdd` tool (mcp__sdd__sdd), args as a list.

Commands
  init                               create specs/ adrs/ changes/ tests/acceptance/, the concept
                                     templates and .claude/sdd.json
  config                             print the effective configuration (test commands, dirs)
  new <change> [--title T]           scaffold changes/<change>/
  status [<change>] [--json]         list changes / show one
  set-status <change> <status>       draft|approved|implementing|verified|archived
  delta-new <change> <concept> [--title T]
                                     capabilities/<id> or invariants/<id>: a new concept from its
                                     template, or a CapabilityDelta when the capability exists
  delta-stub <change> <ref> [--retire | --deprecate | --section NAME]
                                     copy living text with its base hash: <capability>#AC-NN,
                                     a capability section, or a whole invariant
  adr-new <title> [--supersedes ADR-NNNN]
  adr-accept <ADR-NNNN>              draft -> stable (+ deprecates the superseded one)
  check <change> [--tests]           traceability + conflicts (+ acceptance coverage)
  context <change> <task> [--plan]   minimal context bundle for one task
  freeze <change>                    record hashes of the change's acceptance tests
  verify-frozen <change>             fail if frozen acceptance tests were modified
  sync <change> [--dry-run] [--force]
                                     merge the delta into living specs, accept ADRs, archive
  bundle <specs|adrs|change> [--fix] validate (and repair) an OKF bundle
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
    "spec": "step 2: spec-author writes intent, capabilities, invariants, ADRs (files may be partial: sdd check)",
    "gate1": "step 3: show Gate 1 to the user",
    "plan": "step 4: planner writes plan.md and tasks.md",
    "gate2": "step 5: sdd check, then set-status implementing",
    "acceptance": "step 6: acceptance-tester for the open (test) tasks",
    "implement": "step 7: implementers for the open (impl) tasks",
    "verify": "step 8: verifier, then code-review",
    "sync": "step 8.4: sdd sync, then sdd finish",
    "done": "nothing left: the PR is ready for review",
}
TASK_RE = re.compile(r"^- \[( |x|X)\] (T\d+) \((test|impl|chore)\) (.*)$")
BASE_RE = re.compile(r"^<!--\s*base:\s*([0-9a-f]{8})\s*-->\s*$")

# OKF concepts of the living specs. Ids are paths below specs/ without `.md`.
CAP, INV = "capabilities", "invariants"
SEG = r"[a-z0-9][a-z0-9_]*"
SEG_RE = re.compile(SEG)
CONCEPT_ID_RE = re.compile(rf"(?:{CAP}|{INV})(?:/{SEG})+")
# A citation in tasks, plans and tests: `capabilities/<id>#AC-NN` or `invariants/<id>`.
REF_RE = re.compile(rf"(?<![\w/.-])((?:{CAP}|{INV})(?:/{SEG})+)(#AC-\d{{2,}})?(?![\w/-]|\.\w)")
AC_ID_RE = re.compile(r"AC-\d{2,}")
AC_HEAD_RE = re.compile(r"^### (AC-\d{2,}):\s*(.*)$")
RETIRED_RE = re.compile(r"^- \*\*Retired\*\*:?\s*(.*)$")
ADR_RE = re.compile(r"ADR-\d{4}")
ADR_FILE_RE = re.compile(r"(\d{4})_([a-z0-9_]+)\.md")
OKF_STATUSES = ("draft", "stable", "deprecated")
CAP_SECTIONS = ["Intent", "Scope", "Acceptance criteria", "Invariants", "Decisions", "Verification"]
INV_SECTIONS = ["Statement", "Scope", "Rationale", "Enforcement", "Examples", "Exceptions"]
# Units a CapabilityDelta can replace besides its ACs; Title and Description are front matter.
EDITABLE = ["Title", "Description"] + [s for s in CAP_SECTIONS if s != "Acceptance criteria"]
DELTA_SECTIONS = ("ADDED", "MODIFIED", "RETIRED", "SECTIONS")


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
    "adr_dir": "adrs",
    "acceptance_dir": "tests/acceptance",
    "acceptance_cmd": "pytest -q {files}",
    "unit_cmd": "pytest -q tests/unit",
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
RESERVED = {"index.md", "log.md"}    # generated OKF files, never concepts
OKF_VERSION = "0.2"
LOG_TITLE = "# Update Log\n"


def log_head() -> str:
    """A new OKF log: okf rejects a log without a date group, so it opens with its creation."""
    return f"{LOG_TITLE}\n## {_dt.date.today().isoformat()}\n* **Creation**: Initialized OKF bundle.\n"
TEMPLATES = Path(__file__).resolve().parent.parent / "skills" / "change" / "templates"
# Concept templates, overridable per repo in <bundle>/.templates/ (the lintel layout).
CONCEPT_TEMPLATES = {"Capability": (SPECS, "capability.md.tmpl"), "Invariant": (SPECS, "invariant.md.tmpl"),
                     "ADR": (ADRS, "adr.md.tmpl")}

COMMENT_RE = re.compile(r"<!--(?!\s*base:).*?-->", re.S)
ANY_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
PLACEHOLDER_RE = re.compile(r"<[A-Za-z][^<>\n]*>")


def strip_comments(text: str, keep_base: bool = True) -> str:
    """Drop HTML comments (template guidance); `keep_base` keeps `<!-- base: -->` markers."""
    return re.sub(r"\n{3,}", "\n\n", (COMMENT_RE if keep_base else ANY_COMMENT_RE).sub("", text))


def masked(lines: list[str]) -> list[str]:
    """`lines` with every HTML comment blanked, line count kept: headings are found on these."""
    text = ANY_COMMENT_RE.sub(lambda m: "\n" * m.group(0).count("\n"), "\n".join(lines))
    return text.split("\n")


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


def now_utc() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def author() -> str:
    """OKF actor for `generated.by`: OKF_AUTHOR, else human:<git user>, else process:sdd."""
    if os.environ.get("OKF_AUTHOR"):
        return os.environ["OKF_AUTHOR"]
    name = os.environ.get("GIT_AUTHOR_NAME", "")
    if not name:
        try:
            name = subprocess.run(["git", "config", "user.name"], cwd=ROOT, capture_output=True,
                                  text=True, timeout=10).stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            name = ""
    return f"human:{name.lower().replace(' ', '_')}" if name else "process:sdd"


def digest(lines: list[str]) -> str:
    """Base hash of a unit: comments dropped, trailing spaces and blank edges ignored."""
    text = strip_comments("\n".join(lines), keep_base=False)
    norm = "\n".join(l.rstrip() for l in text.split("\n")).strip("\n")
    return hashlib.sha256(norm.encode()).hexdigest()[:8]


def trim(lines: list[str]) -> list[str]:
    """`lines` without leading and trailing blank lines."""
    a, b = 0, len(lines)
    while a < b and not lines[a].strip():
        a += 1
    while b > a and not lines[b - 1].strip():
        b -= 1
    return lines[a:b]


# ------------------------------------------------------------ front matter --
_PLAIN_RE = re.compile(r"[A-Za-z0-9_./@+-]+|[a-z]+:[^\s:#]+")
_NUMBERISH_RE = re.compile(r"[-+.]?(\d[\d_]*)?(\.[\d_]*)?([eE][-+]?\d+)?|0x[0-9a-fA-F_]+|0o[0-7_]+")


def yaml_quote(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def scalar(s: str) -> str:
    """A string as a YAML scalar: plain when that reads back unchanged, else double-quoted."""
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return s
    if _PLAIN_RE.fullmatch(s) and not _NUMBERISH_RE.fullmatch(s) and s[0] not in "-.@" \
            and s.lower() not in ("null", "true", "false", "~", "yes", "no", "on", "off"):
        return s
    return yaml_quote(s)


def _split_flow(s: str) -> list[str]:
    out, depth, cur, quote = [], 0, "", None
    for ch in s:
        if quote:
            cur += ch
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote, cur = ch, cur + ch
        elif ch in "[{":
            depth, cur = depth + 1, cur + ch
        elif ch in "]}":
            depth, cur = depth - 1, cur + ch
        elif ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def parse_inline(s: str):
    s = s.strip()
    if s in ("", "null", "~"):
        return None
    if s.startswith("[") and s.endswith("]"):
        return [parse_inline(x) for x in _split_flow(s[1:-1])]
    if s.startswith("{") and s.endswith("}"):
        out = {}
        for x in _split_flow(s[1:-1]):
            k, _, v = x.partition(":")
            out[k.strip()] = parse_inline(v)
        return out
    if len(s) >= 2 and s[0] == s[-1] == '"':
        return re.sub(r'\\(.)', r"\1", s[1:-1])
    if len(s) >= 2 and s[0] == s[-1] == "'":
        return s[1:-1].replace("''", "'")
    return s


def _parse_block(lines: list[str]):
    """An indented block: a sequence (`- x`, `- k: v`) or a one-level mapping."""
    ind = min(len(l) - len(l.lstrip()) for l in lines)
    if lines[0].strip().startswith("- "):
        items: list = []
        for l in lines:
            body = l[ind:]
            if body.startswith("- "):
                head = body[2:]
                if re.match(r"^[\w-]+:(\s|$)", head):
                    k, _, v = head.partition(":")
                    items.append({k.strip(): parse_inline(v)})
                else:
                    items.append(parse_inline(head))
            elif isinstance(items[-1:] and items[-1], dict) and ":" in body:
                k, _, v = body.strip().partition(":")
                items[-1][k.strip()] = parse_inline(v)
        return items
    out = {}
    for l in lines:
        if len(l) - len(l.lstrip()) == ind and ":" in l:
            k, _, v = l.strip().partition(":")
            out[k.strip()] = parse_inline(v)
    return out


def parse_value(raw: str):
    first, *rest = raw.split("\n")
    rest = [l for l in rest if l.strip() and not l.strip().startswith("#")]
    if not first.strip() and rest:
        return _parse_block(rest)
    return parse_inline(first)


def render_value(v) -> str:
    """Text after `key:` for a value (inline with a leading space, or an indented block)."""
    if v is None:
        return " null"
    if isinstance(v, dict):
        return "".join(f"\n  {k}: {scalar(str(x))}" for k, x in v.items()) if v else " {}"
    if isinstance(v, list):
        if not v:
            return " []"
        if all(isinstance(x, dict) for x in v):
            out = ""
            for item in v:
                for i, (k, x) in enumerate(item.items()):
                    out += f"\n  {'- ' if i == 0 else '  '}{k}: {scalar(str(x))}"
            return out
        return " [" + ", ".join(scalar(str(x)) for x in v) + "]"
    return " " + scalar(str(v))


class FM:
    """Front matter as ordered raw entries (key -> text after `key:`, continuation lines
    included), so keys sdd does not manage round-trip byte for byte."""

    def __init__(self, raw: dict[str, str] | None = None):
        self.raw = dict(raw or {})

    @classmethod
    def parse(cls, block: str) -> "FM":
        raw: dict[str, str] = {}
        key = None
        for line in block.split("\n"):
            m = re.match(r"^([A-Za-z_][\w-]*):(.*)$", line)
            if m:
                key = m.group(1)
                raw[key] = m.group(2)
            elif key is not None:
                raw[key] += "\n" + line
        return cls(raw)

    def get(self, k: str, default=None):
        v = parse_value(self.raw[k]) if k in self.raw else None
        return default if v is None else v

    def str(self, k: str) -> str:
        v = self.get(k)
        return v if isinstance(v, str) else ""

    def list(self, k: str) -> list:
        v = self.get(k)
        return v if isinstance(v, list) else []

    def __contains__(self, k: str) -> bool:
        return k in self.raw

    def set(self, k: str, v):
        self.raw[k] = render_value(v)

    def setdefault(self, k: str, v):
        if k not in self.raw:
            self.set(k, v)

    def pop(self, k: str):
        self.raw.pop(k, None)

    def copy(self) -> "FM":
        return FM(self.raw)

    def text(self) -> str:
        return "".join(f"{k}:{v.rstrip()}\n" for k, v in self.raw.items())

    def __eq__(self, other) -> bool:
        return isinstance(other, FM) and self.text() == other.text()


@dataclass
class Doc:
    fm: FM
    body: str


def split_doc(text: str) -> Doc:
    if not text.startswith("---\n"):
        return Doc(FM(), text)
    end = text.find("\n---", 3)
    if end < 0:
        return Doc(FM(), text)
    return Doc(FM.parse(text[4:end]), text[end + 4:].lstrip("\n"))


def read_doc(path: Path) -> Doc:
    return split_doc(path.read_text())


def doc_text(fm: FM, body: str) -> str:
    return "---\n" + fm.text() + "---\n\n" + body.lstrip("\n")


def atomic_write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content)
    os.replace(tmp, path)


def write_doc(path: Path, fm: FM, body: str):
    atomic_write(path, doc_text(fm, body))


def sources_of(fm: FM) -> list[str]:
    """The `sources[].resource` paths (a plain string entry counts as its resource)."""
    out = []
    for s in fm.list("sources"):
        r = s.get("resource") if isinstance(s, dict) else s
        if isinstance(r, str) and r:
            out.append(r)
    return out


def sources_entries(fm: FM) -> list:
    """`sources` as OKF entries: plain strings become `{resource: <path>}`."""
    return [s if isinstance(s, dict) else {"resource": s} for s in fm.list("sources") if s]


def merge_sources(fm: FM, extra: list):
    have = sources_entries(fm)
    seen = {s.get("resource") for s in have}
    for s in extra:
        if s.get("resource") not in seen:
            have.append(s)
            seen.add(s.get("resource"))
    fm.set("sources", sorted(have, key=lambda s: str(s.get("resource", ""))))


# --------------------------------------------------------- concept bodies --
@dataclass
class Section:
    name: str          # "" for the preamble (the `# Title` heading)
    lines: list[str]   # without the `## ` heading

    @property
    def content(self) -> list[str]:
        return trim(self.lines)


def split_sections(body: str) -> list[Section]:
    lines = body.split("\n")
    secs = [Section("", [])]
    for line, m in zip(lines, masked(lines)):
        if m.startswith("## "):
            secs.append(Section(m[3:].strip(), []))
        else:
            secs[-1].lines.append(line)
    return secs


def join_sections(secs: list[Section]) -> str:
    out = trim(secs[0].lines) if secs else []
    for s in secs[1:]:
        out += ["", f"## {s.name}", ""] + s.content
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out).strip("\n")) + "\n"


@dataclass
class AC:
    id: str
    title: str
    lines: list[str]               # heading + body, base comment removed
    base: str | None = None

    @property
    def text(self) -> str:
        return "\n".join(trim(self.lines))

    @property
    def digest(self) -> str:
        return digest(self.lines)

    @property
    def retired(self) -> str | None:
        """The retirement reason ('' when given without one), or None for a live AC."""
        for l in self.lines[1:]:
            m = RETIRED_RE.match(l.strip())
            if m:
                return m.group(1).strip()
        return None

    def has(self, word: str) -> bool:
        return any(l.strip().startswith(f"- **{word}**") for l in self.lines)


def split_acs(lines: list[str]) -> tuple[list[str], list[AC]]:
    pre: list[str] = []
    acs: list[AC] = []
    for line, m in zip(lines, masked(lines)):
        h = AC_HEAD_RE.match(m)
        if h:
            acs.append(AC(h.group(1), h.group(2).strip(), [line]))
        elif not acs:
            pre.append(line)
        else:
            b = BASE_RE.match(line.strip())
            if b:
                acs[-1].base = b.group(1)
            else:
                acs[-1].lines.append(line)
    return pre, acs


def split_subsections(lines: list[str]) -> tuple[list[str], list[tuple[str, list[str]]]]:
    """`### Name` blocks of a section: (lines before the first, [(name, lines)])."""
    pre: list[str] = []
    subs: list[tuple[str, list[str]]] = []
    for line, m in zip(lines, masked(lines)):
        if m.startswith("### "):
            subs.append((m[4:].strip(), []))
        elif subs:
            subs[-1][1].append(line)
        else:
            pre.append(line)
    return pre, subs


def ac_sort_key(ac: AC) -> int:
    return int(ac.id[3:])


def h1(body: str) -> str:
    return next((l[2:].strip() for l in body.split("\n") if l.startswith("# ")), "")


class Concept:
    """A Capability or Invariant document, as front matter plus `##` sections."""

    def __init__(self, path: Path, doc: Doc):
        self.path, self.fm, self.secs = path, doc.fm, split_sections(doc.body)

    @classmethod
    def load(cls, path: Path) -> "Concept":
        return cls(path, read_doc(path))

    @property
    def type(self) -> str:
        return self.fm.str("type")

    @property
    def title(self) -> str:
        return self.fm.str("title") or h1("\n".join(self.secs[0].lines)) or self.path.stem

    @property
    def status(self) -> str:
        return self.fm.str("status") or "stable"

    def section(self, name: str) -> Section | None:
        return next((s for s in self.secs[1:] if s.name == name), None)

    def acs(self) -> list[AC]:
        s = self.section("Acceptance criteria")
        return split_acs(s.lines)[1] if s else []

    def set_acs(self, acs: list[AC]):
        s = self.section("Acceptance criteria")
        if s is None:
            s = Section("Acceptance criteria", [])
            self.put_section(s)
        pre = trim(split_acs(s.lines)[0])
        lines = pre[:]
        for a in sorted(acs, key=ac_sort_key):
            lines += [""] + trim(a.lines)
        s.lines = [""] + trim(lines) + [""]

    def put_section(self, new: Section):
        """Replace the section of that name, else insert it in template order."""
        for i, s in enumerate(self.secs):
            if i and s.name == new.name:
                self.secs[i] = new
                return
        order = CAP_SECTIONS if self.type == "Capability" else INV_SECTIONS
        rank = order.index(new.name) if new.name in order else len(order)
        at = len(self.secs)
        for i, s in enumerate(self.secs[1:], 1):
            if s.name in order and order.index(s.name) > rank:
                at = i
                break
        self.secs.insert(at, new)

    def unit_lines(self, name: str) -> list[str] | None:
        """Current text of an EDITABLE unit (Title/Description from front matter)."""
        if name == "Title":
            return [self.title]
        if name == "Description":
            return [self.fm.str("description")]
        s = self.section(name)
        return s.content if s else None

    def set_unit(self, name: str, lines: list[str]):
        text = " ".join(l.strip() for l in trim(lines))
        if name == "Title":
            self.fm.set("title", text)
            pre = self.secs[0].lines
            for i, l in enumerate(pre):
                if l.startswith("# "):
                    pre[i] = f"# {text}"
                    break
            else:
                self.secs[0].lines = [f"# {text}", ""] + pre
        elif name == "Description":
            self.fm.set("description", text)
        else:
            self.put_section(Section(name, [""] + trim(lines) + [""]))

    @property
    def body(self) -> str:
        return join_sections(self.secs)

    @property
    def digest(self) -> str:
        return digest(self.body.split("\n"))

    def render(self) -> str:
        return doc_text(self.fm, self.body)


def placeholder_lines(body: str) -> list[str]:
    """Lines that still hold a template placeholder such as `<actor>` (code spans ignored)."""
    out = []
    for l in strip_comments(body, keep_base=False).split("\n"):
        if PLACEHOLDER_RE.search(re.sub(r"`[^`]*`", "", l)):
            out.append(l.strip())
    return out


def links_in(lines: list[str]) -> list[str]:
    return re.findall(r"\]\(([^)\s]+)\)", strip_comments("\n".join(lines), keep_base=False))


def adr_of_link(target: str) -> str | None:
    m = ADR_FILE_RE.fullmatch(target.rsplit("/", 1)[-1].split("#")[0])
    return f"ADR-{m.group(1)}" if m else None


def concept_problems(c: Concept, where: str, kind: str) -> list[tuple[str, str]]:
    """Structural findings of a Capability or Invariant, as (ERROR|WARN, message)."""
    out: list[tuple[str, str]] = []
    err = lambda m: out.append(("ERROR", f"{where}: {m}"))
    warn = lambda m: out.append(("WARN", f"{where}: {m}"))
    if c.type != kind:
        err(f"type is '{c.type or '-'}', expected {kind}")
        return out
    if not c.fm.str("title") or PLACEHOLDER_RE.search(c.fm.str("title")):
        err("front matter needs a title")
    if not c.fm.str("description") or PLACEHOLDER_RE.search(c.fm.str("description")):
        warn("front matter needs a one-sentence description")
    if c.fm.str("status") not in OKF_STATUSES:
        err(f"status '{c.fm.str('status') or '-'}' is not one of {'/'.join(OKF_STATUSES)}")
    deprecated = c.status == "deprecated"
    if kind == "Capability":
        for name in ("Intent", "Scope", "Acceptance criteria"):
            s = c.section(name)
            if s is None:
                err(f"no '## {name}' section")
            elif name != "Acceptance criteria" and not s.content:
                err(f"'## {name}' is empty")
        acs = c.acs()
        if not acs and not deprecated:
            err("no acceptance criterion (### AC-NN: <name>)")
        seen: set[str] = set()
        for a in acs:
            if a.id in seen:
                err(f"{a.id} appears twice (ids are never reused)")
            seen.add(a.id)
            if a.retired is None and not deprecated:
                missing = [w for w in ("Given", "When", "Then") if not a.has(w)]
                if missing:
                    err(f"{a.id} has no {'/'.join(f'**{w}**' for w in missing)} line")
            elif a.retired == "":
                warn(f"{a.id} is retired without a reason")
    else:
        st = c.section("Statement")
        if st is None or not st.content:
            err("no '## Statement'")
        enf = c.section("Enforcement")
        if enf is None or not any(re.match(r"^- \**Check\**:", l.strip()) for l in enf.content):
            err("'## Enforcement' needs a '- Check:' line")
        ex = c.section("Examples")
        subs = dict(split_subsections(ex.lines)[1]) if ex else {}
        for name in ("Holds", "Violation"):
            if name not in subs:
                err(f"'## Examples' needs a '### {name}' case")
            elif not all(any(l.strip().startswith(f"- **{w}**") for l in subs[name]) for w in ("Given", "Then")):
                err(f"'### {name}' needs **Given** and **Then** lines")
        for name in ("Rationale", "Exceptions"):
            if c.section(name) is None:
                warn(f"no '## {name}' section")
    for l in placeholder_lines(c.body)[:3]:
        warn(f"template placeholder left: {l[:80]}")
    return out


def link_problems(c: Concept, where: str, target: Path, change: Path | None) -> list[tuple[str, str]]:
    """Links of the Invariants and Decisions sections that resolve to nothing."""
    out = []
    for name in ("Invariants", "Decisions"):
        s = c.section(name)
        for link in links_in(s.lines) if s else []:
            if link.startswith(("http://", "https://", "#")) or PLACEHOLDER_RE.search(link):
                continue
            dest = (target.parent / link.split("#")[0]).resolve()
            in_change = False
            if change is not None:
                try:
                    in_change = (change / "specs" / dest.relative_to(SPECS.resolve())).exists()
                except ValueError:
                    pass
            if not dest.exists() and not in_change:
                out.append(("WARN", f"{where}: link '{link}' in '## {name}' does not resolve"))
            elif dest.suffix == ".md" and dest.exists() and read_doc(dest).fm.str("status") == "deprecated":
                out.append(("WARN", f"{where}: '## {name}' links deprecated {link}"))
    return out


def linked_invariants(c: Concept, lines: list[str] | None = None) -> set[str]:
    """Invariant ids the `## Invariants` section of capability `c` links to."""
    if lines is None:
        s = c.section("Invariants")
        lines = s.lines if s else []
    out = set()
    for link in links_in(lines):
        try:
            cid = (c.path.parent / link.split("#")[0]).resolve().relative_to(SPECS.resolve()).with_suffix("")
        except ValueError:
            continue
        if cid.as_posix().startswith(INV + "/"):
            out.add(cid.as_posix())
    return out


# --------------------------------------------------------------- living ---
def is_hidden(rel: Path) -> bool:
    return any(p.startswith(".") for p in rel.parts)


def bundle_files(root: Path) -> list[Path]:
    """Every .md file of a bundle except index/log and anything under a dot-directory."""
    if not root.exists():
        return []
    return sorted(f for f in root.rglob("*.md")
                  if f.name not in RESERVED and not is_hidden(f.relative_to(root)))


def cid_of(path: Path, root: Path = SPECS) -> str:
    return path.relative_to(root).with_suffix("").as_posix()


def kind_of(cid: str) -> str:
    return "Capability" if cid.startswith(CAP + "/") else "Invariant"


def living_concepts() -> dict[str, Concept]:
    """Concept id -> Concept, for every well-placed concept under specs/."""
    out = {}
    for f in bundle_files(SPECS):
        cid = cid_of(f)
        if CONCEPT_ID_RE.fullmatch(cid):
            out[cid] = Concept.load(f)
    return out


@dataclass
class Unit:
    """A traceable unit: one acceptance criterion or one invariant."""
    ref: str
    concept: Concept
    ac: AC | None = None

    @property
    def gone(self) -> str | None:
        """Why the unit is no longer in force (retired AC, deprecated concept), else None."""
        if self.concept.status == "deprecated":
            return "deprecated"
        if self.ac is not None and self.ac.retired is not None:
            return "retired"
        return None


def units_of(cid: str, c: Concept) -> dict[str, Unit]:
    if c.type == "Capability":
        return {f"{cid}#{a.id}": Unit(f"{cid}#{a.id}", c, a) for a in c.acs()}
    return {cid: Unit(cid, c)}


def all_units(concepts: dict[str, Concept]) -> dict[str, Unit]:
    out: dict[str, Unit] = {}
    for cid, c in concepts.items():
        out.update(units_of(cid, c))
    return out


def next_ac(acs: list[AC]) -> str:
    return f"AC-{max((ac_sort_key(a) for a in acs), default=0) + 1:02d}"


# ---------------------------------------------------------------- deltas ---
@dataclass
class Delta:
    """One file under changes/<c>/specs/: a new concept, an invariant replacement, or a
    CapabilityDelta (per-unit changes to an existing capability)."""
    cid: str
    path: Path
    doc: Doc
    kind: str = "new"                       # new | replace | modify
    added: list[AC] = field(default_factory=list)
    modified: list[AC] = field(default_factory=list)
    retired: list[AC] = field(default_factory=list)
    sections: list[tuple[str, str | None, list[str]]] = field(default_factory=list)  # name, base, lines

    @property
    def target(self) -> Path:
        return SPECS / f"{self.cid}.md"

    @property
    def type(self) -> str:
        return self.doc.fm.str("type")

    @property
    def base(self) -> str | None:
        return self.doc.fm.str("base") or None

    @property
    def deprecate(self) -> bool:
        return self.doc.fm.str("status") == "deprecated"

    def concept(self) -> Concept:
        """The delta as a concept at its living path, template guidance dropped."""
        return Concept(self.target, Doc(self.doc.fm.copy(), strip_comments(self.doc.body, keep_base=False)))


def delta_files(change: Path) -> list[Path]:
    return bundle_files(change / "specs")


def load_delta(change: Path, f: Path, living: dict[str, Concept]) -> Delta:
    cid = cid_of(f, change / "specs")
    d = Delta(cid, f, read_doc(f))
    if d.type == "CapabilityDelta":
        d.kind = "modify"
        for s in split_sections(d.doc.body)[1:]:
            if s.name == "SECTIONS":
                for name, lines in split_subsections(s.lines)[1]:
                    base = None
                    keep = []
                    for l in lines:
                        b = BASE_RE.match(l.strip())
                        if b:
                            base = b.group(1)
                        else:
                            keep.append(l)
                    d.sections.append((name, base, strip_comments("\n".join(keep), keep_base=False).split("\n")))
            elif s.name in DELTA_SECTIONS:
                getattr(d, s.name.lower()).extend(split_acs(s.lines)[1])
    elif cid in living:
        d.kind = "replace"
    return d


def load_deltas(change: Path, living: dict[str, Concept]) -> list[Delta]:
    return [load_delta(change, f, living) for f in delta_files(change)]


def apply_delta(d: Delta, living: dict[str, Concept]) -> tuple[Concept, list[str]]:
    """The living concept after the delta, and log lines. Assumes `collect` found no error."""
    stamp = now_utc()
    if d.kind in ("new", "replace"):
        c = d.concept()
        c.fm.pop("base")
        if not d.deprecate:
            c.fm.set("status", "stable")
        if c.type == "Capability":
            c.set_acs(c.acs())
        log = [f"{'DEPRECATED' if d.deprecate else 'ADDED' if d.kind == 'new' else 'MODIFIED'} {d.cid}"]
        if c.type == "Capability":
            log[0] += f" ({', '.join(a.id for a in c.acs())})"
    else:
        old = living[d.cid]
        c = Concept(old.path, Doc(old.fm.copy(), old.body))
        acs = {a.id: a for a in c.acs()}
        log = []
        for a in d.modified:
            acs[a.id] = AC(a.id, a.title, strip_comments("\n".join(a.lines), keep_base=False).split("\n"))
            log.append(f"MODIFIED {d.cid}#{a.id}")
        for a in d.retired:
            reason = a.retired or ""
            acs[a.id] = AC(a.id, acs[a.id].title, [f"### {a.id}: {acs[a.id].title}", "", f"- **Retired**: {reason}"])
            log.append(f"RETIRED  {d.cid}#{a.id}")
        for a in d.added:
            acs[a.id] = AC(a.id, a.title, strip_comments("\n".join(a.lines), keep_base=False).split("\n"))
            log.append(f"ADDED    {d.cid}#{a.id}")
        c.set_acs(list(acs.values()))
        for name, _, lines in d.sections:
            c.set_unit(name, lines)
            log.append(f"SECTION  {d.cid} {name}")
        if d.deprecate:
            c.fm.set("status", "deprecated")
            log.append(f"DEPRECATED {d.cid}")
        merge_sources(c.fm, sources_entries(d.doc.fm))
    gen = c.fm.get("generated")
    gen = dict(gen) if isinstance(gen, dict) else {}
    gen.setdefault("by", author())
    gen["at"] = stamp
    c.fm.set("generated", gen)
    c.fm.set("sources", sources_entries(c.fm))
    return c, log


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


def refs_in(text: str) -> list[str]:
    return sorted({m.group(1) + (m.group(2) or "") for m in REF_RE.finditer(text)})


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
            "refs": refs_in(rest),
            "adrs": sorted(set(ADR_RE.findall(rest))),
            "blocked_by": blocked,
        })
    return tasks


def adr_files() -> dict[str, Path]:
    """ADR-NNNN -> adrs/NNNN_<slug>.md."""
    out = {}
    for f in sorted(ADRS.glob("[0-9][0-9][0-9][0-9]_*.md")) if ADRS.exists() else []:
        if ADR_FILE_RE.fullmatch(f.name):
            out[f"ADR-{f.name[:4]}"] = f
    return out


def acceptance_hits(refs: set[str]) -> dict[str, list[Path]]:
    hits: dict[str, list[Path]] = {r: [] for r in refs}
    if not ACCEPT.exists() or not refs:
        return hits
    for f in sorted(ACCEPT.rglob("*")):
        if not f.is_file():
            continue
        try:
            found = set(refs_in(f.read_text(errors="ignore")))
        except OSError:
            continue
        for r in found & refs:
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
    write_indexes(d)
    print(f"created {d.relative_to(ROOT)}/ (index.md intent.md plan.md tasks.md specs/)")


def cmd_init(args):
    made = []
    for d in (SPECS, ADRS, CHANGES, ACCEPT):
        if not d.exists():
            d.mkdir(parents=True)
            made.append(str(d.relative_to(ROOT)) + "/")
    if not _cfg_file.exists():
        atomic_write(_cfg_file, json.dumps(DEFAULT_CFG, indent=2) + "\n")
        made.append(str(_cfg_file.relative_to(ROOT)) + " (edit acceptance_cmd / unit_cmd)")
    for bundle in (SPECS, ADRS):
        for name, text in (("index.md", None), ("log.md", log_head())):
            p = bundle / name
            if not p.exists():
                atomic_write(p, text if text is not None else build_indexes(bundle)[p])
                made.append(str(p.relative_to(ROOT)))
    for kind, (bundle, name) in CONCEPT_TEMPLATES.items():
        p = bundle / ".templates" / name
        if not p.exists():
            atomic_write(p, (TEMPLATES / name).read_text())
            made.append(str(p.relative_to(ROOT)))
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


def intent_fm(d: Path) -> FM:
    return read_doc(d / "intent.md").fm


def cmd_status(args):
    as_json = "--json" in args
    args = [a for a in args if a != "--json"]
    dirs = [change_dir(args[0])] if args else sorted(
        p for p in CHANGES.glob("*") if (p / "intent.md").exists())
    if as_json:
        out = []
        for d in dirs:
            fm = intent_fm(d)
            st = load_state(d)
            out.append({
                "id": d.name, "title": fm.str("title") or d.name, "status": fm.str("status") or "?",
                "size": fm.str("size") or "change",
                "phase": st.get("phase"), "pr": st.get("pr"), "branch": st.get("branch"),
                "requires": st.get("requires", []),
                "adrs": [a for a in fm.list("adrs") if isinstance(a, str)],
                "tasks": [{"id": t["id"], "kind": t["kind"], "done": t["done"],
                           "refs": t["refs"]} for t in parse_tasks(d)],
            })
        archived = len(list((CHANGES / "archive").glob("*"))) if (CHANGES / "archive").exists() else 0
        print(json.dumps({"root": str(ROOT), "changes": out, "archived": archived}))
        return
    for d in dirs:
        fm = intent_fm(d)
        tasks = parse_tasks(d)
        done = sum(t["done"] for t in tasks)
        st = load_state(d)
        extra = (f"  phase={st['phase']}" if st.get("phase") else "") + (f"  pr=#{st['pr']}" if st.get("pr") else "") \
            + (f"  requires={','.join(st['requires'])}" if st.get("requires") else "")
        print(f"{d.name}  status={fm.str('status') or '?'}  tasks={done}/{len(tasks)}  "
              f"size={fm.str('size') or '?'}{extra}")
        if args:
            for t in tasks:
                print(f"  {'x' if t['done'] else ' '} {t['id']} ({t['kind']}) "
                      f"{','.join(t['refs'])} blocked-by={','.join(t['blocked_by']) or '-'}")


def cmd_set_status(args):
    if len(args) != 2 or args[1] not in STATUSES:
        die(f"usage: set-status <change> <{'|'.join(STATUSES)}>")
    d = change_dir(args[0])
    doc = read_doc(d / "intent.md")
    old = doc.fm.str("status") or "draft"
    doc.fm.set("status", args[1])
    write_doc(d / "intent.md", doc.fm, doc.body)
    print(f"{d.name}: {old} -> {args[1]}")


def concept_template(kind: str) -> str:
    """The repo's own template (<bundle>/.templates/) if present, else the plugin's."""
    bundle, name = CONCEPT_TEMPLATES[kind]
    own = bundle / ".templates" / name
    return (own if own.exists() else TEMPLATES / name).read_text()


def fill_template(text: str, title: str) -> str:
    """Fill a concept template the way lintel's new-concept.sh does: title, heading,
    author and timestamps; every other `<placeholder>` stays for the writer."""
    out, t, h = [], False, False
    for line in text.split("\n"):
        if line.startswith("title: <") and not t:
            line, t = f"title: {yaml_quote(title)}", True
        elif line.startswith("# <") and not h:
            line, h = f"# {title}", True
        out.append(line.replace("human:<id>", author()).replace("<YYYY-MM-DDTHH:MM:SSZ>", now_utc())
                   .replace("<YYYY-MM-DD>", _dt.date.today().isoformat()))
    return "\n".join(out)


def concept_arg(arg: str) -> str:
    cid = arg.removesuffix(".md").removeprefix(f"{CFG['specs_dir']}/")
    if not CONCEPT_ID_RE.fullmatch(cid):
        die(f"'{arg}' is not a concept id: {CAP}/<id> or {INV}/<id>, lowercase snake_case segments")
    return cid


def capability_delta_text(cid: str, c: Concept) -> str:
    return render_template("capability-delta.md", "---\ntype: CapabilityDelta\n---\n\n## ADDED\n",
                           id=cid, title=c.title, next=next_ac(c.acs()),
                           target=f"{CFG['specs_dir']}/{cid}.md")


def cmd_delta_new(args):
    if len(args) < 2:
        die("usage: delta-new <change> <capabilities/<id>|invariants/<id>> [--title T]")
    d, cid = change_dir(args[0]), concept_arg(args[1])
    f = d / "specs" / f"{cid}.md"
    if f.exists():
        die(f"{f.relative_to(ROOT)} already exists")
    living = living_concepts()
    if cid in living:
        if kind_of(cid) == "Invariant":
            die(f"{cid} exists: copy it with `delta-stub {d.name} {cid}` and edit the copy")
        atomic_write(f, capability_delta_text(cid, living[cid]))
        note = f" (CapabilityDelta; next free {next_ac(living[cid].acs())})"
    else:
        title = opt(args, "--title") or cid.rsplit("/", 1)[-1].replace("_", " ").capitalize()
        atomic_write(f, fill_template(concept_template(kind_of(cid)), title))
        note = f" (new {kind_of(cid)})"
    write_indexes(d)
    print(f"created {f.relative_to(ROOT)}{note}")


def put_in_section(text: str, section: str, entry: str) -> str:
    """Insert `entry` at the top of `## section`, appending the section when it is missing."""
    lines = text.split("\n")
    for i, m in enumerate(masked(lines)):
        if m.strip() == f"## {section}":
            return "\n".join(lines[:i + 1] + ["", entry.strip("\n"), ""] + lines[i + 1:])
    return text.rstrip("\n") + f"\n\n## {section}\n\n{entry.strip()}\n"


def cmd_delta_stub(args):
    if len(args) < 2:
        die("usage: delta-stub <change> <capabilities/<id>#AC-NN | capabilities/<id> --section NAME "
            "| capabilities/<id> --deprecate | invariants/<id> [--deprecate]> [--retire]")
    d = change_dir(args[0])
    cid, _, ac_id = args[1].partition("#")
    cid = concept_arg(cid)
    living = living_concepts()
    if cid not in living:
        die(f"{cid} not in living specs (write a new concept with `delta-new`)")
    c = living[cid]
    f = d / "specs" / f"{cid}.md"
    rel = f.relative_to(ROOT)
    if kind_of(cid) == "Invariant":
        if ac_id or "--section" in args or "--retire" in args:
            die("an invariant is replaced as a whole: `delta-stub <change> invariants/<id> [--deprecate]`")
        if f.exists():
            die(f"{rel} already exists")
        fm = c.fm.copy()
        fm.set("base", c.digest)
        if "--deprecate" in args:
            fm.set("status", "deprecated")
        atomic_write(f, doc_text(fm, c.body))
        write_indexes(d)
        print(f"{'DEPRECATE' if '--deprecate' in args else 'REPLACE'} {cid} base={c.digest} -> {rel}")
        return
    text = f.read_text() if f.exists() else capability_delta_text(cid, c)
    if split_doc(text).fm.str("type") != "CapabilityDelta":
        die(f"{rel} is not a CapabilityDelta")
    if ac_id:
        a = next((x for x in c.acs() if x.id == ac_id), None)
        if a is None:
            die(f"{cid}#{ac_id} not in living specs (new criteria go under ## ADDED, next free {next_ac(c.acs())})")
        if a.retired is not None:
            die(f"{cid}#{ac_id} is retired")
        if re.search(rf"^### {ac_id}:", strip_comments(text, keep_base=False), re.M):
            die(f"{ac_id} already present in {rel}")
        retire = "--retire" in args
        section = "RETIRED" if retire else "MODIFIED"
        lines = a.lines[:1] + [f"<!-- base: {a.digest} -->"]
        lines += ["", "- **Retired**: <why it is retired>"] if retire else a.lines[1:]
        text = put_in_section(text, section, "\n".join(trim(lines)))
        msg = f"{section} {cid}#{ac_id} base={a.digest}"
    elif opt(args, "--section"):
        name = opt(args, "--section")
        if name not in EDITABLE:
            die(f"--section takes one of {'|'.join(EDITABLE)}")
        if re.search(rf"^### {re.escape(name)}\s*$", strip_comments(text, keep_base=False), re.M):
            die(f"section {name} already present in {rel}")
        cur = c.unit_lines(name)
        base = [f"<!-- base: {digest(cur)} -->"] if cur is not None else []
        text = put_in_section(text, "SECTIONS", "\n".join([f"### {name}"] + base + [""] + (cur or [f"<new {name}>"])))
        msg = f"SECTION {cid} {name} base={digest(cur) if cur is not None else '-'}"
    elif "--deprecate" in args:
        doc = split_doc(text)
        doc.fm.set("status", "deprecated")
        doc.fm.set("base", c.digest)
        text = doc_text(doc.fm, doc.body)
        msg = f"DEPRECATE {cid} base={c.digest}"
    else:
        die("give <capability>#AC-NN, --section NAME or --deprecate")
    atomic_write(f, text)
    write_indexes(d)
    print(f"{msg} -> {rel}")


def cmd_adr_new(args):
    if not args:
        die("usage: adr-new <title> [--supersedes ADR-NNNN]")
    sup = None
    if "--supersedes" in args:
        i = args.index("--supersedes")
        sup = args[i + 1] if i + 1 < len(args) else ""
        args = args[:i] + args[i + 2:]
        if sup not in adr_files():
            die(f"{sup} does not exist")
    title = " ".join(args)
    files = adr_files()
    n = max((int(k[4:]) for k in files), default=0) + 1
    slug = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")[:50] or "decision"
    path = ADRS / f"{n:04d}_{slug}.md"
    doc = split_doc(fill_template(concept_template("ADR"), title))
    if sup:
        doc.fm.set("supersedes", [files[sup].stem])
    write_doc(path, doc.fm, doc.body)
    write_indexes(ADRS)
    print(f"ADR-{n:04d} -> {path.relative_to(ROOT)}")


def accept_adr(num: str, dry: bool = False) -> list[str]:
    files = adr_files()
    if num not in files:
        return [f"{num} does not exist"]
    doc = read_doc(files[num])
    st = doc.fm.str("status")
    if st == "stable":
        return []
    if st != "draft":
        return [f"{num} status is {st or '-'}, expected draft"]
    by_stem = {p.stem: (k, p) for k, p in files.items()}
    sups = [s for s in doc.fm.list("supersedes") if isinstance(s, str)]
    missing = [s for s in sups if s not in by_stem]
    if missing:
        return [f"{num} supersedes missing {', '.join(missing)}"]
    if dry:
        return []
    doc.fm.set("status", "stable")
    doc.fm.set("decided", _dt.date.today().isoformat())
    write_doc(files[num], doc.fm, doc.body)
    for s in sups:
        old = read_doc(by_stem[s][1])
        old.fm.set("status", "deprecated")
        old.fm.set("superseded_by", files[num].stem)
        write_doc(by_stem[s][1], old.fm, old.body)
    note = f" (supersedes {', '.join(by_stem[s][0] for s in sups)})" if sups else ""
    append_log(ADRS, f"* **Update**: {num} accepted{note}")
    write_indexes(ADRS)
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
def _escape(text: str) -> str:
    return re.sub(r"([\\\[\]<>&])", r"\\\1", text.replace("\r", " ").replace("\n", " "))


def _encode(name: str) -> str:
    return "".join(c if c.isascii() and (c.isalnum() or c in "-._~/") else
                   "".join(f"%{b:02X}" for b in c.encode()) for c in name)


def build_indexes(root: Path) -> dict[Path, str]:
    """Every index.md of a bundle, as `okf index` writes them: entries grouped under a
    `# <type>` heading, sorted by title, subdirectories described from their entries.
    Dot-directories (.templates/) are left out."""
    md = [f for f in root.rglob("*.md") if not is_hidden(f.relative_to(root))] if root.exists() else []
    dirs = {root}
    for f in md:
        p = f.parent
        while p != root:
            dirs.add(p)
            p = p.parent
    descs: dict[Path, str] = {}
    out: dict[Path, str] = {}
    for d in sorted(dirs, key=lambda p: (-len(p.relative_to(root).parts), p.as_posix())):
        entries = []
        for child in sorted(d.iterdir(), key=lambda p: p.name):
            if child.name in RESERVED:
                continue
            if child.is_file() and child.suffix == ".md":
                fm = read_doc(child).fm
                entries.append((fm.str("type") or "Other", fm.str("title") or child.stem,
                                _encode(child.name), fm.str("description")))
            elif child.is_dir() and child in dirs:
                entries.append(("Subdirectories", child.name, _encode(child.name) + "/index.md",
                                descs.get(child, "")))
        groups: dict[str, list] = {}
        for e in entries:
            groups.setdefault(e[0], []).append(e)
        sections = []
        for typ in sorted(groups):
            rows = sorted(groups[typ], key=lambda e: e[1].lower())
            sections.append("\n".join([f"# {_escape(typ)}", ""] + [
                f"* [{_escape(t)}]({link})" + (f" - {_escape(desc)}" if desc else "")
                for _, t, link, desc in rows]))
        body = "\n\n".join(sections) + "\n" if sections else ""
        if d == root:
            out[d / "index.md"] = f'---\nokf_version: "{OKF_VERSION}"\n---\n' + ("\n" + body if body else "")
        elif body:
            out[d / "index.md"] = body
            titles = [t for _, t, _, _ in entries if t]
            descs[d] = entries[0][3] if len(entries) == 1 and entries[0][3] else \
                f"Contains {len(entries)} entries: {', '.join(titles) or 'no titled entries'}."
    return out


def write_indexes(root: Path):
    for p, text in build_indexes(root).items():
        if not p.exists() or p.read_text() != text:
            atomic_write(p, text)


def append_log(root: Path, entry: str):
    """Add `entry` under today's `## YYYY-MM-DD` heading of <root>/log.md (newest first)."""
    log = root / "log.md"
    text = log.read_text() if log.exists() else LOG_TITLE
    today = _dt.date.today().isoformat()
    lines = text.rstrip("\n").split("\n")
    first = next((i for i, l in enumerate(lines) if l.startswith("## ")), None)
    if first is not None and lines[first].strip() == f"## {today}":
        lines.insert(first + 1, entry)
    elif first is not None:
        lines[first:first] = [f"## {today}", entry, ""]
    else:
        lines += ["", f"## {today}", entry]
    atomic_write(log, "\n".join(lines) + "\n")


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

    def add(self, found: list[tuple[str, str]]):
        for level, msg in found:
            self.issue(level, msg)


def rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


def is_old_format(doc: Doc) -> bool:
    """A concept or delta of the REQ/INV block format sdd used before OKF concepts."""
    return doc.fm.str("type") in ("spec", "invariant", "spec-delta", "invariant-delta") or \
        re.search(r"^### (REQ|INV)-[A-Z0-9]+-\d{3}:", doc.body, re.M) is not None


OLD_FORMAT = ("old sdd format (REQ/INV blocks): rewrite it as a Capability or Invariant concept "
              "(see sdd:formats); there is no automatic migration")


def check_indexes(rep: Report, root: Path, level: str = "ERROR"):
    """Every index.md of the bundle as `build_indexes` writes it. `level` WARN for a change,
    whose files agents write directly (checkpoint and sync regenerate its indexes)."""
    expected = build_indexes(root)
    for p, text in sorted(expected.items()):
        cur = p.read_text() if p.exists() else None
        if cur is None:
            rep.issue(level, f"{rel(p)}: missing", lambda p=p, text=text: atomic_write(p, text))
        elif cur != text:
            rep.issue(level, f"{rel(p)}: stale (not what `okf index` would write for this directory)",
                      lambda p=p, text=text: atomic_write(p, text))
    for p in sorted(root.rglob("index.md")) if root.exists() else []:
        if p not in expected and not is_hidden(p.relative_to(root)):
            rep.issue("WARN", f"{rel(p)}: index of a directory without concepts", lambda p=p: p.unlink())


def check_log(rep: Report, root: Path):
    log = root / "log.md"
    if not log.exists():
        rep.issue("ERROR", f"{rel(log)}: missing", lambda: atomic_write(log, log_head()))
    elif not re.search(r"^## \d{4}-\d{2}-\d{2}\s*$", log.read_text(), re.M):
        rep.issue("ERROR", f"{rel(log)}: no `## YYYY-MM-DD` entry (okf rejects it)",
                  lambda: atomic_write(log, log.read_text().rstrip("\n") + "\n\n" + log_head().split("\n", 1)[1]))
    elif re.search(r"^- \d{4}-\d{2}-\d{2} ", log.read_text(), re.M):
        rep.issue("WARN", f"{rel(log)}: old sdd log lines (`- <date> ...`); OKF groups entries under `## <date>`")


def _fix_concept(path: Path, fm: FM, body: str):
    write_doc(path, fm, body)


def check_specs(rep: Report):
    if not SPECS.exists():
        rep.issue("ERROR", f"{rel(SPECS)}/ missing", lambda: SPECS.mkdir(parents=True))
        if not SPECS.exists():
            return
    for f in bundle_files(SPECS):
        cid = cid_of(f)
        doc = read_doc(f)
        if is_old_format(doc):
            rep.issue("ERROR", f"{rel(f)}: {OLD_FORMAT}")
            continue
        if not CONCEPT_ID_RE.fullmatch(cid):
            rep.issue("ERROR", f"{rel(f)}: concepts live in {rel(SPECS)}/{CAP}/ or {rel(SPECS)}/{INV}/, "
                      "with lowercase snake_case names")
            continue
        fm = doc.fm.copy()
        changed = []
        if not fm.str("title") and h1(doc.body):
            fm.set("title", h1(doc.body))
            changed.append("title")
            rep.issue("ERROR", f"{rel(f)}: no title in front matter (fix takes the heading)", lambda: None)
        c = Concept(f, Doc(fm if rep.fix else doc.fm, doc.body))
        rep.add([x for x in concept_problems(c, rel(f), kind_of(cid))
                 if not ("needs a title" in x[1] and "title" in changed)])
        rep.add(link_problems(c, rel(f), f, None))
        entries = sources_entries(fm)
        kept = [s for s in entries if (ROOT / re.sub(r":\d+(-\d+)?$", "", str(s.get("resource", "")))).exists()
                or re.match(r"^[a-z]+://", str(s.get("resource", "")))]
        for s in entries:
            if s not in kept:
                rep.issue("WARN", f"{rel(f)}: source '{s.get('resource')}' not found", lambda: None)
        if any(not isinstance(s, dict) for s in fm.list("sources")):
            rep.issue("WARN", f"{rel(f)}: sources are plain strings; OKF wants `- resource: <path>`", lambda: None)
        if kept != fm.list("sources") and ("sources" in fm or kept):
            fm.set("sources", kept)
            changed.append("sources")
        body = doc.body
        if c.type == "Capability":
            ids = [ac_sort_key(a) for a in c.acs()]
            if ids != sorted(ids):
                rep.issue("ERROR", f"{rel(f)}: acceptance criteria not sorted by id", lambda: None)
                c.set_acs(c.acs())
                body = c.body
                changed.append("order")
        if rep.fix and changed:
            _fix_concept(f, fm, body)
    check_indexes(rep, SPECS)
    check_log(rep, SPECS)
    for d in sorted((p for p in SPECS.rglob("*") if p.is_dir() and not is_hidden(p.relative_to(SPECS))),
                    reverse=True):
        if not any(d.iterdir()):
            rep.issue("WARN", f"{rel(d)}/: empty directory", lambda d=d: d.rmdir())
    for f in sorted(SPECS.rglob("*")):
        if f.is_file() and f.suffix != ".md" and not is_hidden(f.relative_to(SPECS)):
            rep.issue("WARN", f"{rel(f)}: not a concept (only .md files belong in specs/)")


def check_adrs(rep: Report):
    if not ADRS.exists():
        rep.issue("ERROR", f"{rel(ADRS)}/ missing", lambda: ADRS.mkdir(parents=True))
        if not ADRS.exists():
            return
    nums: dict[str, Path] = {}
    stems = {p.stem for p in adr_files().values()}
    for f in bundle_files(ADRS):
        if not ADR_FILE_RE.fullmatch(f.name) or f.parent != ADRS:
            old = re.fullmatch(r"ADR-(\d{4})-(.*)\.md", f.name)
            rep.issue("ERROR", f"{rel(f)}: " + (
                f"old sdd ADR name: rename it {old.group(1)}_{old.group(2).replace('-', '_')}.md "
                "and move it to the ADR template (type: ADR, status draft/stable/deprecated)" if old
                else f"ADRs are {rel(ADRS)}/NNNN_<snake_case_slug>.md"))
            continue
        num = f"ADR-{f.name[:4]}"
        if num in nums:
            rep.issue("ERROR", f"{rel(f)}: {num} also used by {rel(nums[num])}")
        nums[num] = f
        doc = read_doc(f)
        fm = doc.fm
        if fm.str("type") != "ADR":
            rep.issue("ERROR", f"{rel(f)}: type is '{fm.str('type') or '-'}', expected ADR")
        if fm.str("status") not in OKF_STATUSES:
            rep.issue("ERROR", f"{rel(f)}: status '{fm.str('status') or '-'}' is not one of {'/'.join(OKF_STATUSES)}")
        if not fm.str("title"):
            rep.issue("ERROR", f"{rel(f)}: front matter needs a title")
        for k in ("supersedes", "superseded_by"):
            v = fm.get(k)
            for s in (v if isinstance(v, list) else [v] if isinstance(v, str) else []):
                if s not in stems:
                    rep.issue("ERROR", f"{rel(f)}: {k} '{s}' is not an ADR of {rel(ADRS)}/")
        if fm.str("status") == "deprecated" and not fm.str("superseded_by"):
            rep.issue("WARN", f"{rel(f)}: deprecated without superseded_by (rejected?)")
        secs = {s.name for s in split_sections(doc.body)[1:]}
        for name in ("Context", "Decision", "Consequences"):
            if name not in secs:
                rep.issue("ERROR" if name == "Decision" else "WARN", f"{rel(f)}: no '## {name}' section")
    check_indexes(rep, ADRS)
    check_log(rep, ADRS)


def check_change(rep: Report, change: Path):
    for name, kind in (("intent.md", "intent"), ("plan.md", "plan"), ("tasks.md", "tasks")):
        f = change / name
        if not f.exists():
            continue
        doc = read_doc(f)
        if doc.fm.str("type") != kind:
            def fix(f=f, doc=doc, kind=kind):
                fm = FM({"type": render_value(kind)})
                fm.raw.update({k: v for k, v in doc.fm.raw.items() if k != "type"})
                write_doc(f, fm, doc.body)
            rep.issue("WARN", f"{rel(f)}: front matter lacks 'type: {kind}'", fix)
    living = living_concepts()
    ddir = change / "specs"
    for f in delta_files(change):
        cid = cid_of(f, ddir)
        doc = read_doc(f)
        if is_old_format(doc):
            rep.issue("ERROR", f"{rel(f)}: {OLD_FORMAT}")
            continue
        if not CONCEPT_ID_RE.fullmatch(cid):
            rep.issue("ERROR", f"{rel(f)}: deltas live in specs/{CAP}/ or specs/{INV}/ "
                      "(the living path), with lowercase snake_case names")
            continue
        typ = doc.fm.str("type")
        allowed = ("Capability", "CapabilityDelta") if kind_of(cid) == "Capability" else ("Invariant",)
        if typ not in allowed:
            rep.issue("ERROR", f"{rel(f)}: type '{typ or '-'}' does not fit {cid} ({' or '.join(allowed)})")
            continue
        fm = doc.fm.copy()
        if typ == "CapabilityDelta" and fm.str("target") != f"{CFG['specs_dir']}/{cid}.md":
            fm.set("target", f"{CFG['specs_dir']}/{cid}.md")
        if "sources" not in fm or any(not isinstance(s, dict) for s in fm.list("sources")):
            fm.set("sources", sources_entries(fm))
        if fm != doc.fm:
            rep.issue("WARN", f"{rel(f)}: front matter incomplete (target, sources as `- resource:` entries)",
                      lambda f=f, fm=fm, body=doc.body: write_doc(f, fm, body))
    check_indexes(rep, change, "WARN")


def bundle_check(target: str, fix: bool = False) -> Report:
    rep = Report(fix)
    if target == "specs":
        check_specs(rep)
    elif target == "adrs":
        check_adrs(rep)
    else:
        check_change(rep, change_dir(target))
    return rep


def cmd_bundle(args):
    fix = "--fix" in args
    args = [a for a in args if a != "--fix"]
    if len(args) != 1:
        die("usage: bundle <specs|adrs|change> [--fix]")
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


def check_delta(d: Delta, living: dict[str, Concept], change: Path, errs: list, warns: list,
                touched: dict[str, str], texts: dict[str, Unit]):
    """Validate one delta against the living specs; record the units it touches."""
    where = rel(d.path)
    cur = living.get(d.cid)

    def touch(ref: str, kind: str, unit: Unit | None):
        if ref in touched:
            errs.append(f"{where} {ref}: appears twice in this change")
        touched[ref] = kind
        if unit is not None:
            texts[ref] = unit

    def report(found):
        for level, msg in found:
            (errs if level == "ERROR" else warns).append(msg)

    if d.kind == "modify":
        if cur is None:
            errs.append(f"{where}: CapabilityDelta but {rel(d.target)} does not exist (write the full Capability)")
            return
        if cur.status == "deprecated":
            errs.append(f"{where}: {d.cid} is deprecated")
            return
        acs = {a.id: a for a in cur.acs()}
        for a in d.added:
            if a.id in acs:
                errs.append(f"{where} {d.cid}#{a.id}: ADDED but the id exists in {rel(cur.path)} "
                            f"(ids are never reused; next free {next_ac(cur.acs())})")
            missing = [w for w in ("Given", "When", "Then") if not a.has(w)]
            if missing:
                errs.append(f"{where} {d.cid}#{a.id}: no {'/'.join(f'**{w}**' for w in missing)} line")
            touch(f"{d.cid}#{a.id}", "ADDED", Unit(f"{d.cid}#{a.id}", cur, a))
        for kind, blocks in (("MODIFIED", d.modified), ("RETIRED", d.retired)):
            for a in blocks:
                ref = f"{d.cid}#{a.id}"
                old = acs.get(a.id)
                if old is None:
                    errs.append(f"{where} {ref}: {kind} but not in {rel(cur.path)}")
                elif old.retired is not None:
                    errs.append(f"{where} {ref}: already retired")
                elif not a.base:
                    errs.append(f"{where} {ref}: missing <!-- base: --> (use delta-stub)")
                elif a.base != old.digest:
                    errs.append(f"{where} {ref}: CONFLICT base {a.base} != current {old.digest} "
                                f"(living spec changed since this delta was written)")
                if kind == "MODIFIED":
                    missing = [w for w in ("Given", "When", "Then") if not a.has(w)]
                    if missing:
                        errs.append(f"{where} {ref}: no {'/'.join(f'**{w}**' for w in missing)} line")
                elif not a.retired or PLACEHOLDER_RE.search(a.retired):
                    errs.append(f"{where} {ref}: RETIRED needs '- **Retired**: <reason>'")
                touch(ref, kind, Unit(ref, cur, a))
        for name, base, lines in d.sections:
            if name not in EDITABLE:
                errs.append(f"{where}: '### {name}' under SECTIONS is not one of {', '.join(EDITABLE)}")
                continue
            now = cur.unit_lines(name)
            if now is not None and not base:
                errs.append(f"{where} {d.cid} {name}: missing <!-- base: --> (use delta-stub --section)")
            elif now is not None and base != digest(now):
                errs.append(f"{where} {d.cid} {name}: CONFLICT base {base} != current {digest(now)}")
            if not trim(lines) or any(PLACEHOLDER_RE.search(l) for l in lines if l.startswith("<new ")):
                errs.append(f"{where} {d.cid} {name}: empty replacement")
        if d.deprecate:
            if d.added or d.modified:
                errs.append(f"{where}: a deprecated capability takes no ADDED or MODIFIED criteria")
            if d.base != cur.digest:
                errs.append(f"{where}: " + (f"CONFLICT base {d.base} != current {cur.digest}" if d.base
                                            else "deprecation without base (use delta-stub --deprecate)"))
            for a in cur.acs():
                ref = f"{d.cid}#{a.id}"
                if a.retired is None and ref not in touched:
                    touch(ref, "RETIRED", Unit(ref, cur, a))
        if not (d.added or d.modified or d.retired or d.sections or d.deprecate):
            warns.append(f"{where}: CapabilityDelta changes nothing")
        return
    c = d.concept()
    report(concept_problems(c, where, kind_of(d.cid)))
    report(link_problems(c, where, d.target, change))
    if d.kind == "new":
        if d.base:
            errs.append(f"{where}: base given but {rel(d.target)} does not exist")
        if c.type == "Capability":
            for a in c.acs():
                if a.retired is not None:
                    errs.append(f"{where} {d.cid}#{a.id}: a new capability has no retired criteria")
                touch(f"{d.cid}#{a.id}", "ADDED", Unit(f"{d.cid}#{a.id}", c, a))
        else:
            touch(d.cid, "ADDED", Unit(d.cid, c))
        return
    # replace: an existing invariant (a Capability is changed with a CapabilityDelta)
    if c.type == "Capability":
        errs.append(f"{where}: {d.cid} exists; change it with a CapabilityDelta (`delta-new` writes one)")
        return
    if not d.base:
        errs.append(f"{where} {d.cid}: replaces a living invariant without base (use delta-stub)")
    elif d.base != cur.digest:
        errs.append(f"{where} {d.cid}: CONFLICT base {d.base} != current {cur.digest} "
                    f"(living spec changed since this delta was written)")
    touch(d.cid, "DEPRECATED" if d.deprecate else "MODIFIED", Unit(d.cid, c))


def collect(change: Path):
    """Run every structural check. Returns (errors, warnings, info)."""
    errs, warns = [], []
    fm = intent_fm(change)
    if fm.str("status") not in STATUSES:
        errs.append(f"intent.md: status '{fm.str('status')}' invalid")
    living = living_concepts()
    units = all_units(living)
    deltas = load_deltas(change, living)
    touched: dict[str, str] = {}      # ref -> ADDED|MODIFIED|RETIRED|DEPRECATED
    texts: dict[str, Unit] = {}       # ref -> unit as this change leaves it
    for d in deltas:
        if CONCEPT_ID_RE.fullmatch(d.cid) and not is_old_format(d.doc):
            check_delta(d, living, change, errs, warns, touched, texts)
    gone_invs = {r for r, k in touched.items() if k == "DEPRECATED"}
    by_cid = {d.cid: d for d in deltas}
    for cid, c in living.items() if gone_invs else []:
        if c.type != "Capability" or c.status == "deprecated":
            continue
        d = by_cid.get(cid)
        new = next((lines for n, _, lines in d.sections if n == "Invariants"), None) if d else None
        for inv in sorted(linked_invariants(c, new) & gone_invs):
            warns.append(f"{cid} still lists {inv}, deprecated by this change: replace its Invariants section")
    if not touched and not any(d.kind == "modify" and d.sections for d in deltas) and fm.str("size") != "fix":
        warns.append("no spec delta in this change")
    rep = bundle_check(change.name)
    errs += [f"bundle: {e}" for e in rep.errs]
    warns += [f"bundle: {w}" for w in rep.warns]
    phase = load_state(change).get("phase")
    if phase and (phase not in PHASES or fm.str("status") not in PHASE_STATUSES[phase]):
        warns.append(f"state.json phase '{phase}' does not fit status '{fm.str('status')}'")

    def ref_problem(r: str, kind: str | None = None) -> str | None:
        cid, _, ac = r.partition("#")
        if kind_of(cid) == "Capability" and not ac:
            return f"names capability {cid}; reference its criteria ({cid}#AC-NN)"
        if kind_of(cid) == "Invariant" and ac:
            return f"{r}: invariants have no acceptance criteria"
        if r not in touched and r not in units:
            return f"references unknown {r}"
        if r not in touched and units[r].gone:
            return f"references {units[r].gone} {r}"
        if kind == "test" and touched.get(r) in ("RETIRED", "DEPRECATED"):
            return f"tests {touched[r].lower()} {r}"
        return None

    tasks = parse_tasks(change)
    ids = [t["id"] for t in tasks]
    for t in tasks:
        if ids.count(t["id"]) > 1:
            errs.append(f"tasks.md:{t['line']} duplicate {t['id']}")
        for b in t["blocked_by"]:
            if b not in ids:
                errs.append(f"tasks.md:{t['line']} {t['id']} blocked-by unknown {b}")
        for r in t["refs"]:
            p = ref_problem(r, t["kind"])
            if p:
                errs.append(f"tasks.md:{t['line']} {t['id']} {p}")
        if t["kind"] in ("test", "impl") and not t["refs"]:
            errs.append(f"tasks.md:{t['line']} {t['id']} ({t['kind']}) references no acceptance criterion or invariant")
    adrs = adr_files()
    referenced_adrs = {a for a in fm.list("adrs") if isinstance(a, str)}
    for t in tasks:
        referenced_adrs |= set(t["adrs"])
    for a in sorted(referenced_adrs):
        if a not in adrs:
            errs.append(f"{a} referenced but no file in {CFG['adr_dir']}/")
        elif read_doc(adrs[a]).fm.str("status") == "deprecated":
            errs.append(f"{a} is deprecated; reference its successor")
    linked = set()
    for d in deltas:
        if d.kind != "modify":
            s = d.concept().section("Decisions")
            linked |= {x for x in (adr_of_link(l) for l in links_in(s.lines)) if x} if s else set()
        for name, _, lines in d.sections:
            if name == "Decisions":
                linked |= {x for x in (adr_of_link(l) for l in links_in(lines)) if x}
    for a in sorted(linked - referenced_adrs):
        if a in adrs and read_doc(adrs[a]).fm.str("status") == "draft":
            warns.append(f"{a} is linked under Decisions but not in intent.md adrs: sync will not accept it")
    plan = change / "plan.md"
    if plan.exists():
        ptxt = strip_comments(plan.read_text())
        for r in refs_in(ptxt):
            p = ref_problem(r)
            if p and not p.startswith("names capability"):
                errs.append(f"plan.md {p}")
        for a in sorted(set(ADR_RE.findall(ptxt))):
            if a not in adrs:
                errs.append(f"plan.md references unknown {a}")

    for r, kind in sorted(touched.items()):
        if kind in ("RETIRED", "DEPRECATED"):
            continue
        kinds = {t["kind"] for t in tasks if r in t["refs"]}
        if tasks and "test" not in kinds:
            errs.append(f"{r}: no (test) task")
        if tasks and "impl" not in kinds and kind_of(r) == "Capability":
            errs.append(f"{r}: no (impl) task")
    if not tasks and fm.str("status") not in ("draft",):
        errs.append("tasks.md has no tasks")
    test_ids = {t["id"] for t in tasks if t["kind"] == "test"}
    # Units that must be covered by acceptance tests: everything the delta adds/modifies,
    # plus existing units a test task targets (the `fix` path).
    test_refs = {r for r, k in touched.items() if k in ("ADDED", "MODIFIED")}
    test_refs |= {r for t in tasks if t["kind"] == "test" for r in t["refs"] if r in touched or r in units}
    for t in tasks:
        if t["kind"] == "impl":
            needed = {x["id"] for x in tasks if x["kind"] == "test" and set(x["refs"]) & set(t["refs"])}
            if needed and not needed & set(t["blocked_by"]):
                warns.append(f"{t['id']}: impl not blocked-by its test task(s) {','.join(sorted(needed))}")
    return errs, warns, {"touched": touched, "tasks": tasks, "deltas": deltas, "living": living,
                         "units": units, "texts": texts, "test_ids": test_ids, "test_refs": test_refs}


def cmd_check(args):
    if not args:
        die("usage: check <change> [--tests]")
    d = change_dir(args[0])
    errs, warns, info = collect(d)
    if "--tests" in args:
        for r, files in sorted(acceptance_hits(info["test_refs"]).items()):
            if not files:
                errs.append(f"{r}: no acceptance test mentions it in {CFG['acceptance_dir']}/")
        gone = {r for r, k in info["touched"].items() if k in ("RETIRED", "DEPRECATED")}
        for r, files in sorted(acceptance_hits(gone).items()):
            for f in files:
                warns.append(f"{r} {info['touched'][r].lower()} but still referenced in {f.relative_to(ROOT)}")
        undone = [t["id"] for t in info["tasks"] if not t["done"]]
        if undone:
            errs.append(f"open tasks: {','.join(undone)}")
    for w in warns:
        print(f"WARN  {w}")
    for e in errs:
        print(f"ERROR {e}")
    print(f"{'FAIL' if errs else 'OK'} {d.name}: {len(info['touched'])} unit(s), "
          f"{len(info['tasks'])} tasks, {len(errs)} errors, {len(warns)} warnings")
    sys.exit(1 if errs else 0)


def section_text(c: Concept, name: str, d: Delta | None = None) -> str:
    """A capability section as this change leaves it (a SECTIONS entry wins)."""
    for n, _, lines in d.sections if d else []:
        if n == name:
            return "\n".join(trim(lines))
    s = c.section(name)
    return "\n".join(s.content) if s else ""


def cmd_context(args):
    if len(args) < 2:
        die("usage: context <change> <task> [--plan]")
    d = change_dir(args[0])
    tasks = parse_tasks(d)
    t = next((x for x in tasks if x["id"] == args[1]), None)
    if not t:
        die(f"{args[1]} not in tasks.md")
    _, _, info = collect(d)
    units, texts, touched = info["units"], info["texts"], info["touched"]
    deltas = {x.cid: x for x in info["deltas"]}
    print(f"# Context {d.name} {t['id']} ({t['kind']})\n\n{t['raw']}\n")
    for b in t["blocked_by"]:
        dep = next((x for x in tasks if x["id"] == b), None)
        if dep:
            print(f"depends on: {dep['raw']}")
    by_cap: dict[str, list[str]] = {}
    invs: list[str] = []
    for r in t["refs"]:
        if r in texts or r in units:
            (by_cap.setdefault(r.partition("#")[0], []) if "#" in r else invs).append(r)
    if by_cap:
        print("\n## Acceptance criteria\n")
    for cid, refs in by_cap.items():
        c = (texts.get(refs[0]) or units[refs[0]]).concept
        print(f"### {cid}: {c.title}\n")
        intent = section_text(c, "Intent", deltas.get(cid))
        if intent:
            print(f"Intent: {intent}\n")
        for r in refs:
            u = texts.get(r) or units[r]
            print(f"<!-- {touched[r] + ' in this change' if r in touched else 'unchanged, ' + rel(u.concept.path)} -->")
            print(u.ac.text.replace("### ", "#### ", 1) + "\n")
    if invs:
        print("## Invariants\n")
    for r in invs:
        u = texts.get(r) or units[r]
        print(f"### {r}: {u.concept.title}")
        print(f"<!-- {touched[r] + ' in this change' if r in touched else 'unchanged, ' + rel(u.concept.path)} -->\n")
        for s in u.concept.secs[1:]:
            print(f"#### {s.name}\n" + "\n".join(x.replace("### ", "##### ", 1) for x in s.content) + "\n")
    if t["kind"] == "impl":
        held = {r: u for r, u in units.items() if "#" not in r and not u.gone}
        held.update({r: u for r, u in texts.items() if "#" not in r})
        for r, k in touched.items():
            if k == "DEPRECATED":
                held.pop(r, None)
        rest = [r for r in sorted(held) if r not in t["refs"]]
        if rest:
            print("## Invariants in force (do not break; `sdd context` of a task naming one prints it in full)\n")
            for r in rest:
                st = section_text(held[r].concept, "Statement").split("\n")[0]
                print(f"- {r}: {held[r].concept.title}" + (f" — {st}" if st else ""))
            print()
    adrs = adr_files()
    if t["adrs"]:
        print("## Decisions\n")
    for a in t["adrs"]:
        if a in adrs:
            doc = read_doc(adrs[a])
            body = strip_comments(doc.body)
            m = re.search(r"^## Decision[ \t]*\n(.*?)(?=^## |\Z)", body, re.S | re.M)
            title = doc.fm.str("title") or h1(body) or a
            text = (m.group(1) if m else "").strip() or "(Decision section is empty: report this)"
            print(f"{a}: {title} [{doc.fm.str('status')}]\n{text}\n")
    if t["kind"] == "impl" and ACCEPT.exists():
        hits = acceptance_hits(set(t["refs"]))
        files = sorted({str(f.relative_to(ROOT)) for fs in hits.values() for f in fs})
        if files:
            print("## Frozen acceptance tests (read-only, make them pass)\n")
            print("\n".join(files) + "\n")
    plan = strip_comments(read_doc(d / "plan.md").body) if (d / "plan.md").exists() else ""
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
    files = {f for fs in acceptance_hits(info["test_refs"]).values() for f in fs}
    return {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(files)}


def cmd_freeze(args):
    if not args:
        die("usage: freeze <change>")
    d = change_dir(args[0])
    snap = frozen_set(d)
    if not snap:
        die("no acceptance test references this change's criteria or invariants; nothing to freeze", 1)
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
    for rel_path, h in snap.items():
        p = ROOT / rel_path
        if not p.exists():
            print(f"ERROR {rel_path} deleted after freeze")
            bad += 1
        elif hashlib.sha256(p.read_bytes()).hexdigest() != h:
            print(f"ERROR {rel_path} modified after freeze")
            bad += 1
    print(f"{'FAIL' if bad else 'OK'} {len(snap)} frozen file(s), {bad} tampered")
    sys.exit(1 if bad else 0)


def cmd_sync(args):
    if not args:
        die("usage: sync <change> [--dry-run] [--force]")
    d = change_dir(args[0])
    dry, force = "--dry-run" in args, "--force" in args
    doc = read_doc(d / "intent.md")
    fm = doc.fm
    if fm.str("status") != "verified" and not force:
        die(f"status is {fm.str('status')}; sync requires verified (or --force)", 1)
    errs, _, info = collect(d)
    errs += [f"specs bundle: {e}" for e in bundle_check("specs").errs]
    if errs:
        for e in errs:
            print(f"ERROR {e}")
        die("fix errors before sync (a specs bundle error: `bundle specs --fix`)", 1)
    adr_list = [a for a in fm.list("adrs") if isinstance(a, str)]
    adr_errs = [e for a in adr_list for e in accept_adr(a, dry=True)]
    if adr_errs:
        for e in adr_errs:
            print(f"ERROR {e}")
        die("ADR problems", 1)
    results = [apply_delta(x, info["living"]) for x in info["deltas"]]
    log = [line for _, lines in results for line in lines]
    for line in log:
        print(line)
    if dry:
        print(f"DRY-RUN ok, {len(log)} change(s), ADRs to accept: {','.join(adr_list) or '-'}")
        return
    for c, _ in results:
        atomic_write(c.path, c.render())
    write_indexes(SPECS)
    summary = "; ".join(" ".join(l.split()) for l in log) or "no spec change"
    append_log(SPECS, f"* **Update**: {d.name}: {summary}")
    for a in adr_list:
        accept_adr(a)
    today = _dt.date.today().isoformat()
    fm.set("status", "archived")
    fm.set("archived", today)
    write_doc(d / "intent.md", fm, doc.body)
    write_indexes(d)
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
    write_indexes(d)
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
    st, fm = load_state(d), intent_fm(d)
    phase = st.get("phase")
    print(f"worktree {wt}")
    print(f"branch {branch}")
    print(f"pr {st.get('pr') or '-'} {st.get('pr_url') or ''}".rstrip())
    print(f"status {fm.str('status') or '?'}")
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
