"""Black-box tests for tools/sdd.py.

sdd.py resolves its root and config at import time from the cwd, so every test runs it
as a subprocess inside a throwaway git repo, the way the `sdd` tool calls it.

Run: python3 -m unittest discover -s plugins/meta/sdd/tests -p 'test_*.py'
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

SDD = Path(__file__).resolve().parent.parent / "tools" / "sdd.py"
OKF = shutil.which("okf")

FM = """\
---
type: {type}
title: "{title}"
description: "{desc}"
status: {status}
tags: []
generated:
  by: human:jdoe
  at: "2026-01-01T00:00:00Z"
sources: []
---
"""

LOGIN = FM.format(type="Capability", title="Login", desc="A user can log in.", status="stable") + """
# Login

## Intent

As a user, I can log in with my password, so that I reach my account.

## Scope

- In: password login
- Out: SSO

## Acceptance criteria

### AC-01: Good password

- **Given** user alice with password `s3cret`
- **When** she logs in with `s3cret`
- **Then** the response is 200

### AC-02: Lockout

- **Given** 5 failed logins for alice
- **When** she logs in again
- **Then** the response is 423

## Invariants

## Decisions

## Verification

- Tests: `tests/acceptance/test_login.py`
"""

NEW_CAP = FM.format(type="Capability", title="Tokens", desc="Expired tokens are rejected.", status="draft") + """
# Tokens

## Intent

As an API client, I get a clear error for an expired token, so that I refresh it.

## Scope

- In: access tokens

## Acceptance criteria

### AC-01: Expired token

- **Given** a token expired 1 second ago
- **When** it calls GET /v1/me
- **Then** the response is 401
"""

TOKEN_TASKS = ("- [x] T1 (test) t — capabilities/tokens#AC-01\n"
               "- [x] T2 (impl) i — capabilities/tokens#AC-01 | blocked-by: T1\n")

NO_SECRETS = FM.format(type="Invariant", title="No secret in logs", desc="No password is logged.",
                       status="stable") + """
# No secret in logs

## Statement

The system must never write a password or token to any log.

## Scope

All services.

## Rationale

Logs are widely readable.

## Enforcement

- Check: `test_no_secret_in_logs` at `tests/acceptance/test_logs.py`
- Runs: CI

## Examples

### Holds

- **Given** a login with password `s3cret`
- **Then** the check passes

### Violation

- **Given** a log line containing `s3cret`
- **Then** the check fails with `secret in log`

## Exceptions

None.
"""

AC_03 = """\
### AC-03: Expired session

- **Given** a session older than 30 days
- **When** alice calls GET /v1/me
- **Then** the response is 401
"""

LOGIN_REF = "capabilities/auth/login"


def put(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def dedent(s: str) -> str:
    return textwrap.dedent(s).lstrip("\n")


class SddCase(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="sdd-test-"))
        (self.root / ".git").mkdir()
        self.env = {**os.environ, "OKF_AUTHOR": "human:tester"}
        self.assertEqual(self.sdd("init")[0], 0)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    # ---------------------------------------------------------------- helpers --
    def sdd(self, *args: str) -> tuple[int, str]:
        p = subprocess.run([sys.executable, str(SDD), *args], cwd=self.root,
                           capture_output=True, text=True, timeout=30, env=self.env)
        return p.returncode, p.stdout + p.stderr

    def write(self, rel: str, text: str):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def read(self, rel: str) -> str:
        return (self.root / rel).read_text()

    def edit(self, rel: str, old: str, new: str):
        text = self.read(rel)
        self.assertIn(old, text)
        self.write(rel, text.replace(old, new, 1))

    def set_tasks(self, change: str, *lines: str):
        self.write(f"changes/{change}/tasks.md", "---\ntype: tasks\n---\n\n# Tasks\n\n" + "\n".join(lines) + "\n")

    def living(self):
        self.write(f"specs/{LOGIN_REF}.md", LOGIN)
        self.assert_ok(self.sdd("bundle", "specs", "--fix"))

    def new_change(self, name: str = "c1") -> str:
        code, out = self.sdd("new", name)
        self.assertEqual(code, 0, out)
        return name

    def added_change(self, name: str = "c1") -> str:
        """A clean change adding the Tokens capability with a test and an impl task."""
        self.new_change(name)
        self.write(f"changes/{name}/specs/capabilities/tokens.md", NEW_CAP)
        self.set_tasks(name,
                       "- [ ] T1 (test) Expired token — capabilities/tokens#AC-01",
                       "- [ ] T2 (impl) Reject expired — capabilities/tokens#AC-01 | blocked-by: T1")
        return name

    def delta(self, change: str = "c1") -> str:
        return f"changes/{change}/specs/{LOGIN_REF}.md"

    def accept_test(self, rel: str = "tests/acceptance/test_tokens.py", ref: str = "capabilities/tokens#AC-01"):
        self.write(rel, f"# {ref}\ndef test_expired():\n    assert True\n")
        return rel

    def assert_ok(self, res: tuple[int, str]):
        self.assertEqual(res[0], 0, res[1])

    def assert_fails(self, res: tuple[int, str], *needles: str, code: int = 1):
        self.assertEqual(res[0], code, res[1])
        for n in needles:
            self.assertIn(n, res[1])


# ------------------------------------------------------------------ setup ----
class TestInitConfigNew(SddCase):
    def test_init_creates_layout_templates_and_config(self):
        for d in ("specs", "adrs", "changes", "tests/acceptance"):
            self.assertTrue((self.root / d).is_dir(), d)
        for t in ("specs/.templates/capability.md.tmpl", "specs/.templates/invariant.md.tmpl",
                  "adrs/.templates/adr.md.tmpl"):
            self.assertTrue((self.root / t).exists(), t)
        cfg = json.loads(self.read(".claude/sdd.json"))
        self.assertIn("acceptance_cmd", cfg)
        self.assertEqual(cfg["adr_dir"], "adrs")
        self.assertNotIn("req_id_pattern", cfg)
        self.assertEqual(self.read("specs/index.md"), '---\nokf_version: "0.2"\n---\n')
        self.assertRegex(self.read("adrs/log.md"), r"# Update Log\n\n## \d{4}-\d{2}-\d{2}\n\* \*\*Creation\*\*")

    def test_init_is_idempotent(self):
        code, out = self.sdd("init")
        self.assertEqual(code, 0)
        self.assertIn("nothing, already initialised", out)

    def test_config_reflects_overrides(self):
        self.write(".claude/sdd.json", json.dumps({"unit_cmd": "make unit"}))
        code, out = self.sdd("config")
        self.assertEqual(code, 0)
        cfg = json.loads(out)
        self.assertEqual(cfg["unit_cmd"], "make unit")
        self.assertEqual(cfg["specs_dir"], "specs")

    def test_root_found_from_subdirectory(self):
        sub = self.root / "src" / "deep"
        sub.mkdir(parents=True)
        p = subprocess.run([sys.executable, str(SDD), "config"], cwd=sub,
                           capture_output=True, text=True)
        self.assertEqual(Path(json.loads(p.stdout)["root"]).resolve(), self.root.resolve())

    def test_new_scaffolds_from_templates(self):
        code, out = self.sdd("new", "add-tokens", "--title", "Add tokens")
        self.assertEqual(code, 0, out)
        intent = self.read("changes/add-tokens/intent.md")
        self.assertIn("id: add-tokens", intent)
        self.assertIn("title: Add tokens", intent)
        self.assertIn("status: draft", intent)
        self.assertNotIn("{{", intent)
        self.assertTrue((self.root / "changes/add-tokens/specs").is_dir())
        for f in ("plan.md", "tasks.md"):
            self.assertTrue((self.root / "changes/add-tokens" / f).exists())
        self.assertIn('okf_version: "0.2"', self.read("changes/add-tokens/index.md"))

    def test_new_rejects_bad_id_and_duplicates(self):
        self.assert_fails(self.sdd("new", "Bad_Name"), "kebab-case", code=2)
        self.new_change("c1")
        self.assert_fails(self.sdd("new", "c1"), "already exists", code=2)

    def test_unknown_command_is_usage_error(self):
        self.assertEqual(self.sdd("nope")[0], 2)
        self.assertEqual(self.sdd()[0], 2)

    def test_unknown_change_is_usage_error(self):
        self.assert_fails(self.sdd("check", "ghost"), "no change 'ghost'", code=2)


class TestInitBrownfield(unittest.TestCase):
    """init in a repo that already has code, ADRs and tests."""
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="sdd-test-"))
        (self.root / ".git").mkdir()
        put(self.root / "docs/adr/0001-use-postgres.md", "# Use Postgres\n")
        put(self.root / "tests/test_app.py", "def test_x():\n    pass\n")
        put(self.root / "pyproject.toml", "[project]\nname='x'\n")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def sdd(self, *args: str) -> tuple[int, str]:
        p = subprocess.run([sys.executable, str(SDD), *args], cwd=self.root,
                           capture_output=True, text=True, timeout=30)
        return p.returncode, p.stdout + p.stderr

    def test_survey_lists_existing_and_writes_nothing(self):
        code, out = self.sdd("init", "--survey")
        self.assertEqual(code, 0, out)
        self.assertIn("found: docs/adr/ (1 .md, ADR-like), tests/ (1 test file: test_*.py), pyproject.toml", out)
        self.assertIn("survey only", out)
        self.assertFalse((self.root / ".claude/sdd.json").exists())
        self.assertFalse((self.root / "specs").exists())

    def test_key_value_sets_first_config(self):
        code, out = self.sdd("init", "adr_dir=docs/sdd-adrs", "unit_cmd=make test")
        self.assertEqual(code, 0, out)
        cfg = json.loads((self.root / ".claude/sdd.json").read_text())
        self.assertEqual((cfg["adr_dir"], cfg["unit_cmd"], cfg["specs_dir"]), ("docs/sdd-adrs", "make test", "specs"))
        self.assertTrue((self.root / "docs/sdd-adrs/index.md").exists())
        self.assertTrue((self.root / "docs/sdd-adrs/.templates/adr.md.tmpl").exists())
        self.assertFalse((self.root / "adrs").exists())
        self.assertEqual((self.root / "docs/adr/0001-use-postgres.md").read_text(), "# Use Postgres\n")

    def test_key_value_refused_once_configured_or_unknown(self):
        self.assertEqual(self.sdd("init", "nope=1")[0], 2)
        self.assertFalse((self.root / ".claude/sdd.json").exists())
        self.assertEqual(self.sdd("init")[0], 0)
        code, out = self.sdd("init", "adr_dir=x")
        self.assertEqual(code, 2, out)
        self.assertIn("exists; edit it", out)

    def test_foreign_bundle_dir_stops_a_first_init(self):
        put(self.root / "adrs/0001-old.md", "# Old\n")
        code, out = self.sdd("init")
        self.assertEqual(code, 1, out)
        self.assertIn("WARN  adrs/ has 1 .md file(s) sdd did not create", out)
        self.assertIn("`init adr_dir=<dir>`", out)
        self.assertFalse((self.root / ".claude/sdd.json").exists())
        self.assertFalse((self.root / "specs").exists())
        code, out = self.sdd("init", "adr_dir=docs/sdd-adrs")
        self.assertEqual(code, 0, out)
        self.assertEqual(sorted(x.name for x in (self.root / "adrs").iterdir()), ["0001-old.md"])

    def test_foreign_bundle_dir_with_config_is_left_alone(self):
        put(self.root / ".claude/sdd.json", "{}")
        put(self.root / "adrs/0001-old.md", "# Old\n")
        code, out = self.sdd("init")
        self.assertEqual(code, 1, out)
        self.assertIn("edit adr_dir in .claude/sdd.json", out)
        self.assertFalse((self.root / "adrs/index.md").exists())
        self.assertFalse((self.root / "adrs/.templates").exists())
        self.assertTrue((self.root / "specs/index.md").exists())

    def test_key_value_with_foreign_dir_writes_nothing_and_can_be_retried(self):
        put(self.root / "adrs/0001-old.md", "# Old\n")
        code, out = self.sdd("init", "unit_cmd=make test")
        self.assertEqual(code, 1, out)
        self.assertIn("nothing written", out)
        self.assertFalse((self.root / ".claude/sdd.json").exists())
        self.assertFalse((self.root / "specs").exists())
        code, out = self.sdd("init", "unit_cmd=make test", "adr_dir=docs/sdd-adrs")
        self.assertEqual(code, 0, out)
        self.assertEqual(json.loads((self.root / ".claude/sdd.json").read_text())["unit_cmd"], "make test")

    def test_key_value_dirs_must_stay_inside_the_repo(self):
        for bad in ("specs_dir=", "specs_dir=.", "adr_dir=/abs", "adr_dir=../outside", "unit_cmd="):
            code, out = self.sdd("init", bad)
            self.assertEqual(code, 2, f"{bad}: {out}")
        self.assertFalse((self.root / ".claude/sdd.json").exists())
        self.assertFalse((self.root.parent / "outside").exists())

    def test_lost_index_of_an_sdd_bundle_is_repaired(self):
        self.assertEqual(self.sdd("init")[0], 0)
        put(self.root / "specs/capabilities/login.md", LOGIN)
        (self.root / "specs/index.md").unlink()
        code, out = self.sdd("init")
        self.assertEqual(code, 0, out)
        self.assertNotIn("WARN", out)
        self.assertTrue((self.root / "specs/index.md").exists())

    def test_survey_once_configured(self):
        shutil.rmtree(self.root / "tests")
        self.assertEqual(self.sdd("init")[0], 0)
        code, out = self.sdd("init", "--survey")
        self.assertEqual(code, 0, out)
        self.assertNotIn("tests/ (tests)", out)
        self.assertIn("then: edit .claude/sdd.json", out)

    def test_survey_finds_unusual_layouts_by_content(self):
        for f in ("architecture/records/0001-x.md", "architecture/records/0002-y.md"):
            put(self.root / f, "# x\n")
        for f in ("docs/decisions-log/a.md", "docs/decisions-log/b.md"):
            put(self.root / f, "# A\n\n## Status\n\nAccepted\n\n## Decision\n\nX\n")
        put(self.root / "notes/a.md", "# a\n")
        put(self.root / "notes/b.md", "# b\n")
        put(self.root / "web/src/__tests__/deep/x.test.ts", "")
        put(self.root / "node_modules/pkg/test_a.py", "")
        put(self.root / "pkg/a/a_test.go", "")
        code, out = self.sdd("init", "--survey")
        self.assertEqual(code, 0, out)
        for want in ("architecture/records/ (2 .md, ADR: numbered)", "docs/decisions-log/ (2 .md, ADR: headings)",
                     "web/src/__tests__/ (1 test file: *.test.js|ts)", "pkg/a/ (1 test file: *_test.go)"):
            self.assertIn(want, out)
        for absent in ("notes/", "node_modules", "__tests__/deep", "web/src/ "):
            self.assertNotIn(absent, out)

    def test_survey_takes_no_key_value(self):
        self.assertEqual(self.sdd("init", "--survey", "adr_dir=x")[0], 2)


class TestStatus(SddCase):
    def test_set_status_valid_and_invalid(self):
        self.new_change()
        code, out = self.sdd("set-status", "c1", "approved")
        self.assertEqual(code, 0, out)
        self.assertIn("draft -> approved", out)
        self.assertIn("status: approved", self.read("changes/c1/intent.md"))
        self.assert_fails(self.sdd("set-status", "c1", "done"), "usage", code=2)

    def test_status_json(self):
        self.added_change()
        code, out = self.sdd("status", "--json")
        self.assertEqual(code, 0, out)
        data = json.loads(out)
        self.assertEqual(data["archived"], 0)
        [c] = data["changes"]
        self.assertEqual((c["id"], c["status"], c["size"]), ("c1", "draft", "change"))
        self.assertEqual([t["id"] for t in c["tasks"]], ["T1", "T2"])
        self.assertEqual(c["tasks"][0]["refs"], ["capabilities/tokens#AC-01"])

    def test_task_template_comment_is_not_parsed(self):
        # the template's format comment contains task-shaped lines
        self.new_change()
        code, out = self.sdd("status", "--json")
        self.assertEqual(json.loads(out)["changes"][0]["tasks"], [])


# --------------------------------------------------------------- delta-new --
class TestDeltaNew(SddCase):
    def test_new_capability_from_template(self):
        self.new_change()
        code, out = self.sdd("delta-new", "c1", "capabilities/reports/export_report", "--title", "Export: CSV")
        self.assertEqual(code, 0, out)
        self.assertIn("created changes/c1/specs/capabilities/reports/export_report.md (new Capability)", out)
        text = self.read("changes/c1/specs/capabilities/reports/export_report.md")
        self.assertIn('type: Capability\ntitle: "Export: CSV"\n', text)
        self.assertIn("\n# Export: CSV\n", text)
        self.assertIn("by: human:tester", text)
        self.assertNotIn("<YYYY", text)
        for s in ("## Intent", "## Scope", "## Acceptance criteria", "### AC-01:"):
            self.assertIn(s, text)

    def test_new_invariant_and_default_title(self):
        self.new_change()
        self.assert_ok(self.sdd("delta-new", "c1", "invariants/no_secret_in_logs"))
        text = self.read("changes/c1/specs/invariants/no_secret_in_logs.md")
        self.assertIn('type: Invariant\ntitle: "No secret in logs"', text)
        self.assertIn("### Violation", text)

    def test_repo_template_wins_over_the_plugin_one(self):
        self.write("specs/.templates/capability.md.tmpl",
                   "---\ntype: Capability\ntitle: <Capability name>\n---\n\n# <Capability name>\n\nHOUSE STYLE\n")
        self.new_change()
        self.assert_ok(self.sdd("delta-new", "c1", "capabilities/x"))
        self.assertIn("HOUSE STYLE", self.read("changes/c1/specs/capabilities/x.md"))

    def test_existing_capability_gets_a_capability_delta(self):
        self.living()
        self.new_change()
        code, out = self.sdd("delta-new", "c1", LOGIN_REF)
        self.assertEqual(code, 0, out)
        self.assertIn("CapabilityDelta; next free AC-03", out)
        text = self.read(self.delta())
        self.assertIn(f"type: CapabilityDelta\ntitle: \"Delta: Login\"\ntarget: specs/{LOGIN_REF}.md\n", text)
        for s in ("## ADDED", "## MODIFIED", "## RETIRED", "## SECTIONS"):
            self.assertEqual(text.count(f"\n{s}\n"), 1, s)
        self.assertNotIn("{{", text)

    def test_template_guidance_is_not_parsed(self):
        # the CapabilityDelta comment holds an AC skeleton
        self.living()
        self.new_change()
        self.assert_ok(self.sdd("delta-new", "c1", LOGIN_REF))
        code, out = self.sdd("check", "c1")
        self.assertEqual(code, 0, out)
        self.assertIn("CapabilityDelta changes nothing", out)

    def test_rejects_bad_ids_existing_invariant_and_duplicate(self):
        self.new_change()
        for bad in ("auth", "capabilities/Auth", "capabilities/auth-x", "invariants", "specs/../x"):
            self.assert_fails(self.sdd("delta-new", "c1", bad), "not a concept id", code=2)
        self.assert_ok(self.sdd("delta-new", "c1", "capabilities/auth"))
        self.assert_fails(self.sdd("delta-new", "c1", "capabilities/auth"), "already exists", code=2)
        self.assert_fails(self.sdd("delta-new", "ghost", "capabilities/auth"), "no change 'ghost'", code=2)
        self.write("specs/invariants/no_secrets.md", NO_SECRETS)
        self.assert_fails(self.sdd("delta-new", "c1", "invariants/no_secrets"), "delta-stub", code=2)


# -------------------------------------------------------------- delta-stub --
class TestDeltaStub(SddCase):
    def setUp(self):
        super().setUp()
        self.living()
        self.new_change()

    def test_modified_copies_ac_with_base_hash(self):
        code, out = self.sdd("delta-stub", "c1", f"{LOGIN_REF}#AC-01")
        self.assertEqual(code, 0, out)
        base = re.search(r"base=([0-9a-f]{8})", out).group(1)
        delta = self.read(self.delta())
        self.assertIn("type: CapabilityDelta", delta)
        self.assertEqual(delta.count("## MODIFIED"), 1)
        mod = delta.split("## MODIFIED")[1].split("## RETIRED")[0]
        self.assertIn(f"### AC-01: Good password\n<!-- base: {base} -->", mod)
        self.assertIn("- **Then** the response is 200", mod)

    def test_retire_writes_reason_placeholder(self):
        self.assert_ok(self.sdd("delta-stub", "c1", f"{LOGIN_REF}#AC-02", "--retire"))
        ret = self.read(self.delta()).split("## RETIRED")[1].split("## SECTIONS")[0]
        self.assertIn("- **Retired**: <why it is retired>", ret)
        self.assertNotIn("423", ret)

    def test_section_copies_text_with_base(self):
        code, out = self.sdd("delta-stub", "c1", LOGIN_REF, "--section", "Scope")
        self.assertEqual(code, 0, out)
        sec = self.read(self.delta()).split("## SECTIONS")[1]
        self.assertRegex(sec, r"### Scope\n<!-- base: [0-9a-f]{8} -->\n\n- In: password login\n- Out: SSO")
        self.assert_ok(self.sdd("delta-stub", "c1", LOGIN_REF, "--section", "Title"))
        self.assertIn("### Title", self.read(self.delta()))
        self.assert_fails(self.sdd("delta-stub", "c1", LOGIN_REF, "--section", "Acceptance criteria"),
                          "--section takes one of", code=2)

    def test_deprecate_capability_and_invariant(self):
        self.assert_ok(self.sdd("delta-stub", "c1", LOGIN_REF, "--deprecate"))
        self.assertRegex(self.read(self.delta()), r"status: deprecated\nbase: [0-9a-f]{8}\n")
        self.write("specs/invariants/no_secrets.md", NO_SECRETS)
        self.assert_ok(self.sdd("delta-stub", "c1", "invariants/no_secrets", "--deprecate"))
        inv = self.read("changes/c1/specs/invariants/no_secrets.md")
        self.assertIn("type: Invariant", inv)
        self.assertIn("status: deprecated", inv)
        self.assertRegex(inv, r"\nbase: [0-9a-f]{8}\n")
        self.assertIn("## Statement", inv)

    def test_two_stubs_share_one_section(self):
        self.assert_ok(self.sdd("delta-stub", "c1", f"{LOGIN_REF}#AC-01"))
        self.assert_ok(self.sdd("delta-stub", "c1", f"{LOGIN_REF}#AC-02"))
        delta = self.read(self.delta())
        self.assertEqual(delta.count("## MODIFIED"), 1)
        self.assertLess(delta.index("### AC-02"), delta.index("### AC-01"))

    def test_rejects_unknown_duplicate_and_retired(self):
        self.assert_fails(self.sdd("delta-stub", "c1", f"{LOGIN_REF}#AC-09"), "not in living specs", "AC-03", code=2)
        self.assert_fails(self.sdd("delta-stub", "c1", "capabilities/ghost#AC-01"), "not in living specs", code=2)
        self.assert_ok(self.sdd("delta-stub", "c1", f"{LOGIN_REF}#AC-01"))
        self.assert_fails(self.sdd("delta-stub", "c1", f"{LOGIN_REF}#AC-01"), "already present", code=2)
        self.write(f"specs/{LOGIN_REF}.md", LOGIN.replace(
            "- **Given** 5 failed logins for alice\n- **When** she logs in again\n- **Then** the response is 423",
            "- **Retired**: lockout moved to the gateway"))
        self.assert_fails(self.sdd("delta-stub", "c1", f"{LOGIN_REF}#AC-02"), "is retired", code=2)


# ------------------------------------------------------------------- check --
class TestCheck(SddCase):
    def setUp(self):
        super().setUp()
        self.living()

    def modify_ac01(self):
        self.new_change()
        self.assert_ok(self.sdd("delta-stub", "c1", f"{LOGIN_REF}#AC-01"))
        self.set_tasks("c1", f"- [ ] T1 (test) x — {LOGIN_REF}#AC-01",
                       f"- [ ] T2 (impl) y — {LOGIN_REF}#AC-01 | blocked-by: T1")

    def test_clean_change_passes(self):
        self.added_change()
        code, out = self.sdd("check", "c1")
        self.assertEqual(code, 0, out)
        self.assertIn("OK c1: 1 unit(s), 2 tasks, 0 errors", out)

    def test_criterion_without_then(self):
        self.added_change()
        self.write("changes/c1/specs/capabilities/tokens.md",
                   NEW_CAP.replace("- **Then** the response is 401\n", ""))
        self.assert_fails(self.sdd("check", "c1"), "AC-01 has no **Then** line")

    def test_missing_sections_and_criteria(self):
        self.new_change()
        self.write("changes/c1/specs/capabilities/tokens.md", NEW_CAP.split("## Scope")[0])
        self.assert_fails(self.sdd("check", "c1"), "no '## Scope' section", "no acceptance criterion")

    def test_missing_test_and_impl_tasks(self):
        self.added_change()
        self.set_tasks("c1", "- [ ] T1 (chore) housekeeping")
        self.assert_fails(self.sdd("check", "c1"), "capabilities/tokens#AC-01: no (test) task",
                          "capabilities/tokens#AC-01: no (impl) task")

    def test_dangling_references(self):
        self.added_change()
        self.set_tasks("c1",
                       "- [ ] T1 (test) x — capabilities/tokens#AC-01 capabilities/tokens#AC-07",
                       "- [ ] T2 (impl) y — capabilities/tokens#AC-01 ADR-0042 | blocked-by: T9",
                       "- [ ] T3 (test) z — capabilities/tokens")
        self.assert_fails(self.sdd("check", "c1"), "references unknown capabilities/tokens#AC-07",
                          "blocked-by unknown T9", "ADR-0042 referenced but no file",
                          "names capability capabilities/tokens; reference its criteria")

    def test_duplicate_task_and_task_without_ref(self):
        self.added_change()
        self.set_tasks("c1",
                       "- [ ] T1 (test) x — capabilities/tokens#AC-01",
                       "- [ ] T1 (impl) y — capabilities/tokens#AC-01",
                       "- [ ] T3 (impl) z")
        self.assert_fails(self.sdd("check", "c1"), "duplicate T1", "T3 (impl) references no acceptance criterion")

    def test_new_concept_over_a_living_capability(self):
        self.new_change()
        self.write(self.delta(), LOGIN)
        self.assert_fails(self.sdd("check", "c1"), "exists; change it with a CapabilityDelta")

    def test_added_id_already_used(self):
        self.new_change()
        self.assert_ok(self.sdd("delta-new", "c1", LOGIN_REF))
        self.edit(self.delta(), "## ADDED\n", "## ADDED\n\n" + AC_03.replace("AC-03", "AC-02") + "\n")
        self.assert_fails(self.sdd("check", "c1"), "ADDED but the id exists", "next free AC-03")

    def test_modified_without_base(self):
        self.modify_ac01()
        text = re.sub(r"<!-- base: [0-9a-f]+ -->\n", "", self.read(self.delta()))
        self.write(self.delta(), text)
        self.assert_fails(self.sdd("check", "c1"), "missing <!-- base: -->")

    def test_conflict_when_living_spec_changed_after_stub(self):
        self.modify_ac01()
        self.assert_ok(self.sdd("check", "c1"))
        # another change lands first and edits AC-01
        self.edit(f"specs/{LOGIN_REF}.md", "the response is 200", "the response is 204")
        self.assert_fails(self.sdd("check", "c1"), "CONFLICT")

    def test_edit_of_another_ac_is_not_a_conflict(self):
        self.modify_ac01()
        self.edit(f"specs/{LOGIN_REF}.md", "the response is 423", "the response is 429")
        self.edit(f"specs/{LOGIN_REF}.md", "with `s3cret`\n", "with `s3cret`   \n")
        self.assert_ok(self.sdd("check", "c1"))

    def test_section_conflict(self):
        self.new_change()
        self.assert_ok(self.sdd("delta-stub", "c1", LOGIN_REF, "--section", "Scope"))
        self.assert_ok(self.sdd("check", "c1"))
        self.edit(f"specs/{LOGIN_REF}.md", "- Out: SSO", "- Out: SSO, passkeys")
        self.assert_fails(self.sdd("check", "c1"), "Scope: CONFLICT")

    def test_retired_needs_reason_and_no_test_task(self):
        self.new_change()
        self.assert_ok(self.sdd("delta-stub", "c1", f"{LOGIN_REF}#AC-02", "--retire"))
        self.set_tasks("c1", f"- [ ] T1 (test) x — {LOGIN_REF}#AC-02")
        self.assert_fails(self.sdd("check", "c1"), "RETIRED needs '- **Retired**: <reason>'",
                          f"tests retired {LOGIN_REF}#AC-02")

    def test_task_on_an_already_retired_criterion(self):
        self.write(f"specs/{LOGIN_REF}.md", LOGIN.replace(
            "- **Given** 5 failed logins for alice\n- **When** she logs in again\n- **Then** the response is 423",
            "- **Retired**: moved to the gateway"))
        self.new_change()
        self.set_tasks("c1", f"- [ ] T1 (chore) x — {LOGIN_REF}#AC-02")
        self.assert_fails(self.sdd("check", "c1"), f"references retired {LOGIN_REF}#AC-02")

    def test_impl_not_blocked_by_test_is_a_warning(self):
        self.added_change()
        self.set_tasks("c1", "- [ ] T1 (test) x — capabilities/tokens#AC-01",
                       "- [ ] T2 (impl) y — capabilities/tokens#AC-01")
        code, out = self.sdd("check", "c1")
        self.assertEqual(code, 0, out)
        self.assertIn("WARN  T2: impl not blocked-by", out)

    def test_plan_references_are_checked_outside_comments(self):
        self.added_change()
        self.write("changes/c1/plan.md",
                   "# Plan\n<!-- capabilities/tokens#AC-55 in a comment is ignored -->\n"
                   "## Approach\nServes capabilities/tokens#AC-01 and capabilities/tokens#AC-44 per ADR-0009.\n")
        code, out = self.sdd("check", "c1")
        self.assertEqual(code, 1, out)
        self.assertIn("plan.md references unknown capabilities/tokens#AC-44", out)
        self.assertIn("plan.md references unknown ADR-0009", out)
        self.assertNotIn("AC-55", out)

    def test_non_draft_without_tasks(self):
        self.new_change()
        self.write("changes/c1/specs/capabilities/tokens.md", NEW_CAP)
        self.assert_ok(self.sdd("set-status", "c1", "approved"))
        self.assert_fails(self.sdd("check", "c1"), "tasks.md has no tasks")

    def test_tests_flag_needs_acceptance_test_and_closed_tasks(self):
        self.added_change()
        self.assert_fails(self.sdd("check", "c1", "--tests"),
                          "capabilities/tokens#AC-01: no acceptance test", "open tasks: T1,T2")
        self.accept_test()
        self.set_tasks("c1", "- [x] T1 (test) x — capabilities/tokens#AC-01",
                       "- [x] T2 (impl) y — capabilities/tokens#AC-01 | blocked-by: T1")
        self.assert_ok(self.sdd("check", "c1", "--tests"))

    def test_test_citation_must_match_the_whole_id(self):
        self.added_change()
        self.set_tasks("c1", "- [x] T1 (test) x — capabilities/tokens#AC-01",
                       "- [x] T2 (impl) y — capabilities/tokens#AC-01 | blocked-by: T1")
        self.accept_test(ref="specs/capabilities/tokens#AC-01 capabilities/tokens#AC-010")
        self.assert_fails(self.sdd("check", "c1", "--tests"), "capabilities/tokens#AC-01: no acceptance test")

    def test_fix_path_test_task_on_existing_criterion_needs_acceptance_test(self):
        self.new_change()
        self.edit("changes/c1/intent.md", "size: change", "size: fix")
        self.set_tasks("c1", f"- [x] T1 (test) regression — {LOGIN_REF}#AC-02",
                       f"- [x] T2 (impl) fix — {LOGIN_REF}#AC-02 | blocked-by: T1")
        code, out = self.sdd("check", "c1")
        self.assertEqual(code, 0, out)
        self.assertNotIn("no spec delta", out)
        self.assert_fails(self.sdd("check", "c1", "--tests"), f"{LOGIN_REF}#AC-02: no acceptance test")
        self.accept_test(ref=f"{LOGIN_REF}#AC-02")
        self.assert_ok(self.sdd("check", "c1", "--tests"))


# ----------------------------------------------------------------- freeze ---
class TestBaseline(SddCase):
    """Criteria that record behavior the code already has (existing repos)."""
    def setUp(self):
        super().setUp()
        self.living()

    def baseline_cap(self, size: str = "change"):
        self.new_change()
        if size != "change":
            self.edit("changes/c1/intent.md", "size: change", f"size: {size}")
        self.write("changes/c1/specs/capabilities/tokens.md", NEW_CAP.replace(
            "- **Then** the response is 401\n", "- **Then** the response is 401\n- **Baseline**: src/auth/tokens.py\n"))

    def test_baseline_criterion_needs_no_impl_task(self):
        self.baseline_cap()
        self.set_tasks("c1", "- [ ] T1 (test) Expired token — capabilities/tokens#AC-01")
        code, out = self.sdd("check", "c1")
        self.assertEqual(code, 0, out)
        self.assertNotIn("no (impl) task", out)

    def test_baseline_criterion_still_needs_a_test_task(self):
        self.baseline_cap()
        self.set_tasks("c1", "- [ ] T1 (chore) x")
        self.assert_fails(self.sdd("check", "c1"), "capabilities/tokens#AC-01: no (test) task")

    def test_impl_task_on_baseline_only_warns(self):
        self.baseline_cap()
        self.set_tasks("c1", "- [ ] T1 (test) t — capabilities/tokens#AC-01",
                       "- [ ] T2 (impl) i — capabilities/tokens#AC-01 | blocked-by: T1")
        code, out = self.sdd("check", "c1")
        self.assertEqual(code, 0, out)
        self.assertIn("WARN  T2: cites only Baseline criteria", out)

    def test_baseline_needs_a_location(self):
        self.baseline_cap()
        self.edit("changes/c1/specs/capabilities/tokens.md", "- **Baseline**: src/auth/tokens.py",
                  "- **Baseline**: <where>")
        self.set_tasks("c1", "- [ ] T1 (test) t — capabilities/tokens#AC-01")
        self.assert_fails(self.sdd("check", "c1"), "Baseline needs")

    def test_baseline_on_added_delta_ok_on_modified_refused(self):
        self.new_change()
        self.assert_ok(self.sdd("delta-stub", "c1", f"{LOGIN_REF}#AC-01"))
        self.edit(self.delta(), "## ADDED\n", "## ADDED\n\n" + AC_03 + "- **Baseline**: src/session.py\n")
        self.set_tasks("c1", f"- [ ] T1 (test) x — {LOGIN_REF}#AC-01 {LOGIN_REF}#AC-03",
                       f"- [ ] T2 (impl) y — {LOGIN_REF}#AC-01 | blocked-by: T1")
        self.assert_ok(self.sdd("check", "c1"))
        self.edit(self.delta(), "the response is 200", "the response is 200\n- **Baseline**: src/login.py")
        self.assert_fails(self.sdd("check", "c1"), f"{LOGIN_REF}#AC-01: MODIFIED criteria cannot be Baseline")

    def test_size_baseline_rules(self):
        self.baseline_cap("baseline")
        self.set_tasks("c1", "- [ ] T1 (test) t — capabilities/tokens#AC-01")
        self.assert_ok(self.sdd("check", "c1"))
        self.set_tasks("c1", "- [ ] T1 (test) t — capabilities/tokens#AC-01",
                       "- [ ] T2 (impl) i — capabilities/tokens#AC-01 | blocked-by: T1")
        self.assert_fails(self.sdd("check", "c1"), "T2: a size: baseline change has no (impl) tasks")

    def test_size_baseline_refuses_new_behavior(self):
        self.added_change()
        self.edit("changes/c1/intent.md", "size: change", "size: baseline")
        self.assert_fails(self.sdd("check", "c1"), "capabilities/tokens#AC-01: not Baseline in a size: baseline change")

    def test_size_baseline_refuses_sections(self):
        self.new_change()
        self.edit("changes/c1/intent.md", "size: change", "size: baseline")
        self.assert_ok(self.sdd("delta-stub", "c1", LOGIN_REF, "--section", "Scope"))
        self.edit(self.delta(), "- Out: SSO", "- Out: SSO, tokens")
        self.edit(self.delta(), "## ADDED\n", "## ADDED\n\n" + AC_03 + "- **Baseline**: src/session.py\n")
        self.set_tasks("c1", f"- [ ] T1 (test) x — {LOGIN_REF}#AC-03")
        self.assert_fails(self.sdd("check", "c1"), f"{LOGIN_REF} Scope: SECTIONS in a size: baseline change")

    def test_baseline_in_a_comment_does_not_count(self):
        self.new_change()
        self.write("changes/c1/specs/capabilities/tokens.md", NEW_CAP.replace(
            "- **Then** the response is 401\n", "- **Then** the response is 401\n<!--\n- **Baseline**: src/x.py\n-->\n"))
        self.set_tasks("c1", "- [ ] T1 (test) t — capabilities/tokens#AC-01")
        self.assert_fails(self.sdd("check", "c1"), "capabilities/tokens#AC-01: no (impl) task")

    def test_freeze_without_git_warns_and_freezes(self):
        self.baseline_cap()
        self.set_tasks("c1", "- [x] T1 (test) t — capabilities/tokens#AC-01")
        self.accept_test()
        code, out = self.sdd("freeze", "c1")
        self.assertEqual(code, 0, out)
        self.assertIn("WARN  no git base: Baseline commit not recorded", out)
        self.assertTrue((self.root / "changes/c1/frozen.json").exists())

    def test_fix_may_add_criteria(self):
        self.added_change()
        self.edit("changes/c1/intent.md", "size: change", "size: fix")
        self.assert_ok(self.sdd("check", "c1"))
        code, out = self.sdd("status", "--json")
        self.assertEqual(json.loads(out)["changes"][0]["delta"], True)

    def test_fix_with_baseline_criterion_needs_no_impl(self):
        self.baseline_cap("fix")
        self.set_tasks("c1", "- [ ] T1 (test) t — capabilities/tokens#AC-01")
        self.assert_ok(self.sdd("check", "c1"))

    def test_fix_refuses_more_than_added_criteria(self):
        self.new_change()
        self.edit("changes/c1/intent.md", "size: change", "size: fix")
        self.assert_ok(self.sdd("delta-stub", "c1", f"{LOGIN_REF}#AC-01"))
        self.assert_ok(self.sdd("delta-stub", "c1", LOGIN_REF, "--section", "Scope"))
        self.edit(self.delta(), "- Out: SSO", "- Out: SSO, tokens")
        self.write("changes/c1/specs/invariants/no_secret_in_logs.md", NO_SECRETS.replace("status: stable", "status: draft"))
        self.edit("changes/c1/intent.md", "adrs: []", "adrs: [ADR-0001]")
        self.set_tasks("c1", f"- [ ] T1 (test) x — {LOGIN_REF}#AC-01 invariants/no_secret_in_logs",
                       f"- [ ] T2 (impl) y — {LOGIN_REF}#AC-01 | blocked-by: T1")
        self.assert_fails(self.sdd("check", "c1"), f"{LOGIN_REF}#AC-01: MODIFIED capability in a size: fix change",
                          "invariants/no_secret_in_logs: ADDED invariant in a size: fix change",
                          f"{LOGIN_REF} Scope: SECTIONS in a size: fix change",
                          "a fix records no decision")

    def test_unknown_size(self):
        self.added_change()
        self.edit("changes/c1/intent.md", "size: change", "size: huge")
        self.assert_fails(self.sdd("check", "c1"), "size 'huge' invalid")

    def test_context_marks_baseline(self):
        self.baseline_cap()
        self.set_tasks("c1", "- [ ] T1 (test) t — capabilities/tokens#AC-01")
        code, out = self.sdd("context", "c1", "T1")
        self.assertEqual(code, 0, out)
        self.assertIn("baseline: existing behavior, the test must pass on the current code", out)

    def test_sync_drops_the_marker(self):
        self.baseline_cap()
        self.set_tasks("c1", "- [x] T1 (test) t — capabilities/tokens#AC-01")
        self.sdd("set-status", "c1", "verified")
        self.assert_ok(self.sdd("sync", "c1"))
        spec = self.read("specs/capabilities/tokens.md")
        self.assertIn("- **Then** the response is 401\n", spec)
        self.assertNotIn("Baseline", spec)
        self.assert_ok(self.sdd("bundle", "specs"))


class TestFreeze(SddCase):
    def setUp(self):
        super().setUp()
        self.added_change()

    def test_freeze_without_tests_fails(self):
        self.assert_fails(self.sdd("freeze", "c1"), "nothing to freeze")
        self.assert_fails(self.sdd("verify-frozen", "c1"), "no frozen.json")

    def test_freeze_then_tamper(self):
        rel = self.accept_test()
        self.write("tests/acceptance/unrelated.py", "# nothing here\n")
        code, out = self.sdd("freeze", "c1")
        self.assertEqual(code, 0, out)
        frozen = json.loads(self.read("changes/c1/frozen.json"))
        self.assertEqual(list(frozen), [rel])
        self.assert_ok(self.sdd("verify-frozen", "c1"))

        self.write(rel, self.read(rel) + "    assert 1 == 1\n")
        self.assert_fails(self.sdd("verify-frozen", "c1"), f"{rel} modified after freeze")

        (self.root / rel).unlink()
        self.assert_fails(self.sdd("verify-frozen", "c1"), f"{rel} deleted after freeze")


# ------------------------------------------------------------------- ADRs ---
class TestAdr(SddCase):
    def test_new_numbers_and_supersede(self):
        code, out = self.sdd("adr-new", "Use", "JWT")
        self.assertEqual(code, 0, out)
        self.assertIn("ADR-0001 -> adrs/0001_use_jwt.md", out)
        adr1 = self.read("adrs/0001_use_jwt.md")
        self.assertIn('type: ADR\ntitle: "Use JWT"\n', adr1)
        self.assertIn("\n# Use JWT\n", adr1)
        self.assertIn("status: draft", adr1)
        self.assertIn("## Decision drivers", adr1)
        self.assertIn("[Use JWT](0001_use_jwt.md)", self.read("adrs/index.md"))

        self.assert_fails(self.sdd("adr-new", "X", "--supersedes", "ADR-0009"), "does not exist", code=2)

        self.assert_ok(self.sdd("adr-accept", "ADR-0001"))
        self.assertIn("status: stable", self.read("adrs/0001_use_jwt.md"))

        code, out = self.sdd("adr-new", "Use PASETO", "--supersedes", "ADR-0001")
        self.assertIn("ADR-0002 -> adrs/0002_use_paseto.md", out)
        self.assertIn("supersedes: [0001_use_jwt]", self.read("adrs/0002_use_paseto.md"))
        self.assert_ok(self.sdd("adr-accept", "ADR-0002"))
        old = self.read("adrs/0001_use_jwt.md")
        self.assertIn("status: deprecated", old)
        self.assertIn("superseded_by: 0002_use_paseto", old)
        self.assertIn("* **Update**: ADR-0002 accepted (supersedes ADR-0001)", self.read("adrs/log.md"))
        self.assert_ok(self.sdd("bundle", "adrs"))

    def test_accept_is_idempotent_and_checks_status(self):
        self.sdd("adr-new", "A")
        self.assert_ok(self.sdd("adr-accept", "ADR-0001"))
        self.assert_ok(self.sdd("adr-accept", "ADR-0001"))
        self.assert_fails(self.sdd("adr-accept", "ADR-0005"), "ADR-0005 does not exist")
        self.edit("adrs/0001_a.md", "status: stable", "status: deprecated")
        self.assert_fails(self.sdd("adr-accept", "ADR-0001"), "expected draft")

    def test_check_rejects_deprecated_reference(self):
        self.sdd("adr-new", "Old")
        self.sdd("adr-accept", "ADR-0001")
        self.sdd("adr-new", "New", "--supersedes", "ADR-0001")
        self.sdd("adr-accept", "ADR-0002")
        self.added_change()
        self.set_tasks("c1", "- [ ] T1 (test) x — capabilities/tokens#AC-01",
                       "- [ ] T2 (impl) y — capabilities/tokens#AC-01 ADR-0001 | blocked-by: T1")
        self.assert_fails(self.sdd("check", "c1"), "ADR-0001 is deprecated")

    def test_decision_link_outside_intent_warns(self):
        self.sdd("adr-new", "Token format")
        self.added_change()
        self.edit("changes/c1/specs/capabilities/tokens.md", "## Acceptance criteria",
                  "## Decisions\n\n- [Token format](../../adrs/0001_token_format.md)\n\n## Acceptance criteria")
        code, out = self.sdd("check", "c1")
        self.assertEqual(code, 0, out)
        self.assertIn("ADR-0001 is linked from a concept but not in intent.md adrs", out)
        self.assertNotIn("does not resolve", out)

    def test_bundle_adrs_flags_the_old_naming(self):
        self.write("adrs/ADR-0001-use-jwt.md", "---\nstatus: accepted\n---\n\n# ADR-0001: Use JWT\n")
        self.assert_fails(self.sdd("bundle", "adrs"), "old sdd ADR name: rename it 0001_use_jwt.md")


# ----------------------------------------------------------------- context --
class TestContext(SddCase):
    def setUp(self):
        super().setUp()
        self.living()
        self.sdd("adr-new", "Token", "format")
        self.edit("adrs/0001_token_format.md", "We choose <option>, because <reason tied to the drivers>.",
                  "Tokens are opaque 32-byte strings.")
        self.added_change()
        self.set_tasks("c1", "- [ ] T1 (test) x — capabilities/tokens#AC-01",
                       f"- [ ] T2 (impl) y — capabilities/tokens#AC-01 {LOGIN_REF}#AC-01 ADR-0001 | blocked-by: T1")
        self.write("changes/c1/plan.md", dedent("""
            ---
            type: plan
            change: c1
            ---

            # Plan

            ## Approach
            SECRET-APPROACH serves capabilities/tokens#AC-01.

            ## Contracts
            GET /v1/me -> 401 {"error": "token_expired"}

            ## Components
            src/mw.py -> capabilities/tokens#AC-01
            """))
        self.accept_test()

    def test_test_task_gets_criteria_and_contracts_only(self):
        code, out = self.sdd("context", "c1", "T1")
        self.assertEqual(code, 0, out)
        self.assertIn("### capabilities/tokens: Tokens", out)
        self.assertIn("Intent: As an API client", out)
        self.assertIn("<!-- ADDED in this change -->\n#### AC-01: Expired token", out)
        self.assertIn("## Contracts", out)
        self.assertIn("token_expired", out)
        self.assertNotIn("SECRET-APPROACH", out)
        self.assertNotIn("Frozen acceptance tests", out)

    def test_impl_task_gets_criteria_decision_and_frozen_paths(self):
        code, out = self.sdd("context", "c1", "T2")
        self.assertEqual(code, 0, out)
        self.assertIn("depends on: - [ ] T1", out)
        self.assertIn(f"<!-- unchanged, specs/{LOGIN_REF}.md -->\n#### AC-01: Good password", out)
        self.assertNotIn("AC-02", out)
        self.assertIn("ADR-0001: Token format [draft]\nTokens are opaque 32-byte strings.", out)
        self.assertNotIn("## Context", out)
        self.assertIn("tests/acceptance/test_tokens.py", out)
        self.assertNotIn("SECRET-APPROACH", out)
        self.assertNotIn("## Contracts", out)

    def test_plan_flag_adds_full_plan(self):
        code, out = self.sdd("context", "c1", "T2", "--plan")
        self.assertEqual(code, 0, out)
        self.assertIn("SECRET-APPROACH", out)

    def test_unknown_task(self):
        self.assert_fails(self.sdd("context", "c1", "T9"), "T9 not in tasks.md", code=2)


# -------------------------------------------------------------------- sync --
class TestSync(SddCase):
    def setUp(self):
        super().setUp()
        self.write("src/a.py", "x\n")
        self.write("src/b.py", "x\n")
        self.living()
        self.edit(f"specs/{LOGIN_REF}.md", "sources: []", "sources:\n  - resource: src/a.py")
        self.new_change()
        for args in ([f"{LOGIN_REF}#AC-01"], [f"{LOGIN_REF}#AC-02", "--retire"], [LOGIN_REF, "--section", "Scope"],
                     [LOGIN_REF, "--section", "Description"]):
            self.assert_ok(self.sdd("delta-stub", "c1", *args))
        self.edit(self.delta(), "the response is 200", "the response is 204")
        self.edit(self.delta(), "<why it is retired>", "the gateway locks accounts now")
        self.edit(self.delta(), "- Out: SSO", "- Out: SSO, lockout")
        self.edit(self.delta(), "A user can log in.", "A user can log in with a password.")
        self.edit(self.delta(), "## ADDED\n", "## ADDED\n\n" + AC_03)
        self.edit(self.delta(), "sources: []", "sources: [src/b.py]")
        self.set_tasks("c1",
                       f"- [x] T1 (test) x — {LOGIN_REF}#AC-01 {LOGIN_REF}#AC-03",
                       f"- [x] T2 (impl) y — {LOGIN_REF}#AC-01 {LOGIN_REF}#AC-03 | blocked-by: T1")
        self.archive = f"changes/archive/{_dt.date.today().isoformat()}-c1"

    def test_requires_verified(self):
        self.assert_fails(self.sdd("sync", "c1"), "sync requires verified")

    def test_dry_run_writes_nothing(self):
        self.sdd("set-status", "c1", "verified")
        before = self.read(f"specs/{LOGIN_REF}.md")
        code, out = self.sdd("sync", "c1", "--dry-run")
        self.assertEqual(code, 0, out)
        for line in (f"MODIFIED {LOGIN_REF}#AC-01", f"RETIRED  {LOGIN_REF}#AC-02", f"ADDED    {LOGIN_REF}#AC-03",
                     f"SECTION  {LOGIN_REF} Scope", "DRY-RUN ok, 5 change(s)"):
            self.assertIn(line, out)
        self.assertEqual(self.read(f"specs/{LOGIN_REF}.md"), before)
        self.assertTrue((self.root / "changes/c1").exists())

    def test_sync_merges_accepts_adrs_and_archives(self):
        self.sdd("adr-new", "Token", "format")
        self.edit("changes/c1/intent.md", "adrs: []", "adrs: [ADR-0001]")
        self.sdd("set-status", "c1", "verified")
        code, out = self.sdd("sync", "c1")
        self.assertEqual(code, 0, out)

        spec = self.read(f"specs/{LOGIN_REF}.md")
        self.assertIn("the response is 204", spec)
        self.assertNotIn("the response is 200", spec)
        self.assertIn("### AC-02: Lockout\n\n- **Retired**: the gateway locks accounts now\n\n### AC-03", spec)
        self.assertNotIn("423", spec)
        self.assertIn("- Out: SSO, lockout", spec)
        self.assertIn('description: "A user can log in with a password."', spec)
        self.assertNotIn("<!--", spec)
        self.assertEqual(re.findall(r"^### (AC-\d+)", spec, re.M), ["AC-01", "AC-02", "AC-03"])
        self.assertIn("status: stable", spec)
        self.assertIn("by: human:jdoe", spec)
        self.assertNotIn('at: "2026-01-01T00:00:00Z"', spec)
        self.assertIn("sources:\n  - resource: src/a.py\n  - resource: src/b.py\n", spec)

        self.assertIn("status: stable", self.read("adrs/0001_token_format.md"))
        self.assertFalse((self.root / "changes/c1").exists())
        self.assertIn("status: archived", self.read(f"{self.archive}/intent.md"))
        self.assertEqual(json.loads(self.sdd("status", "--json")[1])["archived"], 1)
        self.assertRegex(self.read("specs/log.md"), rf"## \d{{4}}-\d{{2}}-\d{{2}}\n\* \*\*Update\*\*: c1: "
                         rf"MODIFIED {LOGIN_REF}#AC-01; RETIRED {LOGIN_REF}#AC-02;")
        self.assert_ok(self.sdd("bundle", "specs"))

    def test_retired_id_is_never_reused(self):
        self.sdd("set-status", "c1", "verified")
        self.assert_ok(self.sdd("sync", "c1"))
        self.new_change("c2")
        code, out = self.sdd("delta-new", "c2", LOGIN_REF)
        self.assertIn("next free AC-04", out)
        self.edit(f"changes/c2/specs/{LOGIN_REF}.md", "## ADDED\n", "## ADDED\n\n" + AC_03.replace("AC-03", "AC-02"))
        self.assert_fails(self.sdd("check", "c2"), "ADDED but the id exists")

    def test_sync_twice_is_impossible(self):
        self.sdd("set-status", "c1", "verified")
        self.assert_ok(self.sdd("sync", "c1"))
        self.assert_fails(self.sdd("sync", "c1"), "no change 'c1'", code=2)

    def test_conflict_blocks_sync_and_writes_nothing(self):
        self.sdd("set-status", "c1", "verified")
        self.edit(f"specs/{LOGIN_REF}.md", "5 failed logins", "3 failed logins")
        changed = self.read(f"specs/{LOGIN_REF}.md")
        self.assert_fails(self.sdd("sync", "c1"), "CONFLICT", "fix errors before sync")
        self.assertEqual(self.read(f"specs/{LOGIN_REF}.md"), changed)
        self.assertTrue((self.root / "changes/c1/intent.md").exists())

    def test_force_skips_status_but_not_errors(self):
        self.edit(f"specs/{LOGIN_REF}.md", "5 failed logins", "3 failed logins")
        self.assert_fails(self.sdd("sync", "c1", "--force"), "CONFLICT")

    def test_bad_adr_blocks_sync_before_writing(self):
        self.edit("changes/c1/intent.md", "adrs: []", "adrs: [ADR-0007]")
        self.sdd("set-status", "c1", "verified")
        before = self.read(f"specs/{LOGIN_REF}.md")
        self.assert_fails(self.sdd("sync", "c1"), "ADR-0007")
        self.assertEqual(self.read(f"specs/{LOGIN_REF}.md"), before)

    def test_new_capability_and_invariant_create_concepts_and_indexes(self):
        self.new_change("c2")
        self.write("changes/c2/specs/capabilities/tokens.md", NEW_CAP)
        self.write("changes/c2/specs/invariants/no_secrets.md", NO_SECRETS.replace("status: stable", "status: draft"))
        self.set_tasks("c2", "- [x] T1 (test) x — capabilities/tokens#AC-01 invariants/no_secrets",
                       "- [x] T2 (impl) y — capabilities/tokens#AC-01 | blocked-by: T1")
        self.sdd("set-status", "c2", "verified")
        code, out = self.sdd("sync", "c2")
        self.assertEqual(code, 0, out)
        self.assertIn("ADDED capabilities/tokens (AC-01)", out)
        self.assertIn("ADDED invariants/no_secrets", out)
        self.assertIn("status: stable", self.read("specs/capabilities/tokens.md"))
        self.assertIn("status: stable", self.read("specs/invariants/no_secrets.md"))
        self.assertIn("* [Tokens](tokens.md) - Expired tokens are rejected.", self.read("specs/capabilities/index.md"))
        self.assertIn("* [invariants](invariants/index.md) - No password is logged.", self.read("specs/index.md"))
        self.assert_ok(self.sdd("bundle", "specs"))

    def test_invariant_replace_and_deprecate(self):
        self.write("specs/invariants/no_secrets.md", NO_SECRETS)
        self.assert_ok(self.sdd("bundle", "specs", "--fix"))
        self.new_change("c2")
        self.assert_ok(self.sdd("delta-stub", "c2", "invariants/no_secrets"))
        self.edit("changes/c2/specs/invariants/no_secrets.md", "password or token", "password, token or key")
        self.set_tasks("c2", "- [x] T1 (test) x — invariants/no_secrets")
        self.sdd("set-status", "c2", "verified")
        self.assert_ok(self.sdd("sync", "c2"))
        inv = self.read("specs/invariants/no_secrets.md")
        self.assertIn("password, token or key", inv)
        self.assertNotIn("base:", inv)
        self.new_change("c3")
        self.assert_ok(self.sdd("delta-stub", "c3", "invariants/no_secrets", "--deprecate"))
        self.set_tasks("c3", "- [x] T1 (test) x — invariants/no_secrets")
        self.assert_fails(self.sdd("check", "c3"), "tests deprecated invariants/no_secrets")
        self.set_tasks("c3", "- [x] T1 (chore) drop the log scrubber")
        self.sdd("set-status", "c3", "verified")
        self.assert_ok(self.sdd("sync", "c3"))
        self.assertIn("status: deprecated", self.read("specs/invariants/no_secrets.md"))

    def test_deprecated_invariant_still_listed_warns(self):
        self.write("specs/invariants/no_secrets.md", NO_SECRETS)
        self.edit(f"specs/{LOGIN_REF}.md", "## Invariants\n", "## Invariants\n\n- [No secrets](../../invariants/no_secrets.md)\n")
        self.assert_ok(self.sdd("bundle", "specs", "--fix"))
        self.new_change("c2")
        self.assert_ok(self.sdd("delta-stub", "c2", "invariants/no_secrets", "--deprecate"))
        code, out = self.sdd("check", "c2")
        self.assertIn(f"{LOGIN_REF} still lists invariants/no_secrets, deprecated by this change", out)

    def test_deprecate_capability_retires_its_criteria(self):
        self.new_change("c2")
        self.assert_ok(self.sdd("delta-stub", "c2", LOGIN_REF, "--deprecate"))
        self.set_tasks("c2", f"- [x] T1 (test) x — {LOGIN_REF}#AC-01")
        self.assert_fails(self.sdd("check", "c2"), f"tests retired {LOGIN_REF}#AC-01")
        self.set_tasks("c2", "- [x] T1 (chore) remove login")
        self.sdd("set-status", "c2", "verified")
        self.assert_ok(self.sdd("sync", "c2"))
        self.assertIn("status: deprecated", self.read(f"specs/{LOGIN_REF}.md"))

    @unittest.skipUnless(OKF, "okf not on PATH")
    def test_synced_bundles_are_okf_conformant(self):
        self.sdd("adr-new", "Token", "format")
        self.edit("changes/c1/intent.md", "adrs: []", "adrs: [ADR-0001]")
        self.sdd("set-status", "c1", "verified")
        self.assert_ok(self.sdd("sync", "c1"))
        for bundle in ("specs", "adrs"):
            p = subprocess.run([OKF, "validate", bundle], cwd=self.root, capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        copy = self.root / "okf-copy"
        shutil.copytree(self.root / "specs", copy, ignore=shutil.ignore_patterns(".templates"))
        subprocess.run([OKF, "index", str(copy)], capture_output=True, check=True)
        for p in copy.rglob("index.md"):
            self.assertEqual(p.read_text(), (self.root / "specs" / p.relative_to(copy)).read_text(), p)


# ------------------------------------------------ branch / PR / resume ------
FAKE_GH = """#!/bin/sh
echo "$@" >> "$GH_LOG"
case "$1 $2" in
  "pr create") [ -n "$GH_FAIL" ] && { echo "gh: not authenticated" >&2; exit 1; }
               echo "https://github.com/o/r/pull/7" ;;
  "pr view")   echo "sdd/c1" ;;
  "pr ready")  ;;
esac
"""


class GitCase(unittest.TestCase):
    """sdd.py against a real clone with a bare origin and a fake `gh` first on PATH."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sdd-git-")).resolve()
        self.origin = self.tmp / "origin.git"
        self.root = self.tmp / "work"
        bin_ = self.tmp / "bin"
        bin_.mkdir()
        (bin_ / "gh").write_text(FAKE_GH)
        (bin_ / "gh").chmod(0o755)
        self.log = self.tmp / "gh.log"
        self.env = {**os.environ, "PATH": f"{bin_}:{os.environ['PATH']}", "GH_LOG": str(self.log),
                    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                    "GIT_COMMITTER_EMAIL": "t@t"}
        self.env.pop("GH_FAIL", None)
        self.git("init", "-q", "--bare", "-b", "main", str(self.origin), cwd=self.tmp)
        self.git("clone", "-q", str(self.origin), str(self.root), cwd=self.tmp)
        self.git("checkout", "-q", "-b", "main", cwd=self.root)
        self.assertEqual(self.sdd("init")[0], 0)
        self.git("add", "-A", cwd=self.root)
        self.git("commit", "-qm", "init", cwd=self.root)
        self.git("push", "-q", "-u", "origin", "main", cwd=self.root)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def git(self, *args: str, cwd: Path | None = None) -> str:
        p = subprocess.run(["git", *args], cwd=cwd or self.root, capture_output=True, text=True, env=self.env)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout.strip()

    def sdd(self, *args: str, cwd: Path | None = None) -> tuple[int, str]:
        p = subprocess.run([sys.executable, str(SDD), *args], cwd=cwd or self.root,
                           capture_output=True, text=True, env=self.env, timeout=60)
        return p.returncode, p.stdout + p.stderr

    def start(self, name: str = "c1") -> Path:
        code, out = self.sdd("start", name, "--title", "Change one", "--pr-title", "feat: one")
        self.assertEqual(code, 0, out)
        return self.root / ".claude" / "worktrees" / f"sdd-{name}"

    def state(self, wt: Path, name: str = "c1") -> dict:
        return json.loads((wt / "changes" / name / "state.json").read_text())

    def remote_subjects(self, branch: str) -> list[str]:
        return self.git("log", "--format=%s", f"origin/{branch}", cwd=self.root).splitlines()


class TestStart(GitCase):
    def test_init_ignores_worktrees(self):
        self.assertIn("/.claude/worktrees/", (self.root / ".gitignore").read_text().splitlines())

    def test_start_makes_branch_worktree_state_and_draft_pr(self):
        wt = self.start()
        self.assertTrue((wt / "changes/c1/intent.md").exists())
        st = self.state(wt)
        self.assertEqual((st["phase"], st["branch"], st["base"], st["pr"]), ("spec", "sdd/c1", "main", 7))
        self.assertEqual(self.git("rev-parse", "--abbrev-ref", "HEAD", cwd=wt), "sdd/c1")
        self.git("fetch", "-q", "origin", "sdd/c1")
        self.assertEqual(self.remote_subjects("sdd/c1")[:2], ["chore(sdd): record PR #7", "chore(sdd): start c1"])
        self.assertIn("pr create --draft --base main --head sdd/c1 --title feat: one", self.log.read_text())
        self.assertFalse((self.root / "changes/c1").exists(), "main checkout stays clean")

    def test_start_without_gh_still_works_and_set_pr_records(self):
        self.env["GH_FAIL"] = "1"
        code, out = self.sdd("start", "c1", "--title", "One")
        self.assertEqual(code, 0, out)
        self.assertIn("PR missing", out)
        wt = self.root / ".claude/worktrees/sdd-c1"
        self.assertIsNone(self.state(wt)["pr"])
        code, out = self.sdd("set-pr", "c1", "12", "--url", "https://x/pull/12", cwd=wt)
        self.assertEqual(code, 0, out)
        self.assertEqual(self.state(wt)["pr"], 12)
        self.git("fetch", "-q", "origin", "sdd/c1")
        self.assertEqual(self.remote_subjects("sdd/c1")[0], "chore(sdd): record PR #12")

    def test_start_refuses_duplicates_and_uncommitted_config(self):
        self.start()
        self.assert_exit(self.sdd("start", "c1"), 1, "already exists")
        self.git("rm", "-q", ".claude/sdd.json", cwd=self.root)
        self.git("commit", "-qm", "drop cfg", cwd=self.root)
        self.git("push", "-q", cwd=self.root)
        self.assert_exit(self.sdd("start", "c2"), 1, "sdd.json")

    def test_failed_push_leaves_nothing_behind_so_start_can_be_retried(self):
        self.git("config", "remote.origin.pushurl", str(self.tmp / "nowhere.git"), cwd=self.root)
        self.assertEqual(self.sdd("start", "c1", "--title", "One")[0], 1)
        self.assertFalse((self.root / ".claude/worktrees/sdd-c1").exists())
        self.assertEqual(self.git("branch", "--list", "sdd/c1", cwd=self.root), "")
        self.git("config", "--unset", "remote.origin.pushurl", cwd=self.root)
        self.start()

    def assert_exit(self, res, code, needle):
        self.assertEqual(res[0], code, res[1])
        self.assertIn(needle, res[1])


class TestCheckpoint(GitCase):
    def test_checkpoint_sets_phase_commits_and_pushes(self):
        wt = self.start()
        (wt / "changes/c1/specs").mkdir(exist_ok=True)
        put(wt / "changes/c1/specs/capabilities/tokens.md", NEW_CAP)
        code, out = self.sdd("checkpoint", "c1", "--phase", "gate1", "-m", "docs(sdd): c1 spec", cwd=wt)
        self.assertEqual(code, 0, out)
        self.assertEqual(self.state(wt)["phase"], "gate1")
        self.git("fetch", "-q", "origin", "sdd/c1")
        self.assertEqual(self.remote_subjects("sdd/c1")[0], "docs(sdd): c1 spec")

    def test_checkpoint_nothing_to_commit_and_bad_phase(self):
        wt = self.start()
        code, out = self.sdd("checkpoint", "c1", cwd=wt)
        self.assertEqual(code, 0, out)
        self.assertIn("nothing to commit", out)
        self.assertEqual(self.sdd("checkpoint", "c1", "--phase", "nope", cwd=wt)[0], 2)

    def test_checkpoint_refuses_on_another_branch(self):
        wt = self.start()
        code, out = self.sdd("checkpoint", "c1", cwd=wt)  # sanity
        self.git("checkout", "-q", "-b", "other", cwd=wt)
        code, out = self.sdd("checkpoint", "c1", "-m", "x", cwd=wt)
        self.assertEqual(code, 1, out)
        self.assertIn("expected sdd/c1", out)


class TestResume(GitCase):
    def second_clone(self) -> Path:
        other = self.tmp / "other"
        self.git("clone", "-q", str(self.origin), str(other), cwd=self.tmp)
        return other

    def test_resume_from_a_fresh_clone_recreates_worktree_and_shows_phase(self):
        wt = self.start()
        self.assertEqual(self.sdd("checkpoint", "c1", "--phase", "plan", cwd=wt)[0], 0)
        other = self.second_clone()
        code, out = self.sdd("resume", "c1", cwd=other)
        self.assertEqual(code, 0, out)
        owt = other / ".claude/worktrees/sdd-c1"
        self.assertTrue((owt / "changes/c1/state.json").exists())
        self.assertIn(f"worktree {owt}", out)
        self.assertIn("phase plan:", out)
        self.assertIn("pr 7", out)
        self.assertEqual(self.git("rev-parse", "--abbrev-ref", "HEAD", cwd=owt), "sdd/c1")

    def test_resume_reuses_existing_worktree_and_pulls(self):
        wt = self.start()
        other = self.second_clone()
        self.assertEqual(self.sdd("resume", "c1", cwd=other)[0], 0)
        self.assertEqual(self.sdd("checkpoint", "c1", "--phase", "gate2", cwd=wt)[0], 0)
        code, out = self.sdd("resume", "c1", cwd=other)
        self.assertEqual(code, 0, out)
        self.assertIn("phase gate2:", out)

    def test_resume_by_pr_number(self):
        self.start()
        other = self.second_clone()
        code, out = self.sdd("resume", "c1", "--pr", "7", cwd=other)
        self.assertEqual(code, 0, out)
        self.assertIn("pr view 7", self.log.read_text())

    def test_resume_unknown_change_fails(self):
        code, out = self.sdd("resume", "ghost")
        self.assertEqual(code, 1, out)


class TestDeps(GitCase):
    def finish_change(self, name: str) -> Path:
        """Take a change through sync + finish on its branch (not merged into main yet)."""
        wt = self.start(name)
        self.assertEqual(self.sdd("set-status", name, "verified", cwd=wt)[0], 0)
        put(wt / f"changes/{name}/specs/capabilities/tokens.md", NEW_CAP)
        (wt / f"changes/{name}/tasks.md").write_text(
            TOKEN_TASKS)
        self.assertEqual(self.sdd("sync", name, "--force", cwd=wt)[0], 0)
        self.assertEqual(self.sdd("finish", name, cwd=wt)[0], 0)
        return wt

    def merge_into_main(self, name: str):
        self.git("fetch", "-q", "origin", f"sdd/{name}")
        self.git("merge", "-q", "--no-ff", "-m", f"merge {name}", f"origin/sdd/{name}", cwd=self.root)
        self.git("push", "-q", "origin", "main", cwd=self.root)

    def started_with(self, dep: str = "dep", name: str = "c1") -> Path:
        code, out = self.sdd("start", name, "--title", "C", "--requires", dep)
        self.assertEqual(code, 0, out)
        return self.root / ".claude/worktrees" / f"sdd-{name}"

    def test_start_stores_requires_and_warns(self):
        self.start("dep")
        code, out = self.sdd("start", "c1", "--title", "C", "--requires", "dep,dep")
        self.assertEqual(code, 0, out)
        self.assertIn("WARN requires open dep phase spec pr #7", out)
        wt = self.root / ".claude/worktrees/sdd-c1"
        self.assertEqual(self.state(wt)["requires"], ["dep"])
        code, out = self.sdd("status", "--json", cwd=wt)
        self.assertEqual(json.loads(out)["changes"][0]["requires"], ["dep"])

    def test_start_rejects_bad_or_self_requires(self):
        self.assertEqual(self.sdd("start", "c1", "--title", "C", "--requires", "c1")[0], 2)
        self.assertEqual(self.sdd("start", "c2", "--title", "C", "--requires", "Bad_Id")[0], 2)

    def test_deps_open_ready_unknown_then_merged(self):
        wt = self.started_with()
        code, out = self.sdd("deps", "c1", cwd=wt)
        self.assertEqual(code, 1, out)
        self.assertIn("unknown dep no branch sdd/dep", out)
        self.start("dep")
        code, out = self.sdd("deps", "c1", cwd=wt)
        self.assertEqual(code, 1, out)
        self.assertIn("open dep phase spec pr #7", out)
        self.assertIn("next: resume dep", out)
        self.sdd("checkpoint", "dep", "--phase", "plan", cwd=self.root / ".claude/worktrees/sdd-dep")
        self.assertIn("phase plan", self.sdd("deps", "c1", cwd=wt)[1])

    def test_deps_ready_then_missing_until_base_is_merged_in(self):
        wt = self.started_with()
        self.finish_change("dep")
        code, out = self.sdd("deps", "c1", cwd=wt)
        self.assertEqual(code, 1, out)
        self.assertIn("ready dep finished pr #7, awaits merge into main", out)
        self.assertIn("next: merge the PR of dep (#7)", out)
        self.merge_into_main("dep")
        code, out = self.sdd("deps", "c1", cwd=wt)
        self.assertEqual(code, 1, out)
        self.assertIn("missing dep merged into main, not in this branch", out)

    def test_transitive_deps_list_deepest_first(self):
        self.start("aa")
        self.started_with("aa", "bb")
        wt_c = self.started_with("bb", "cc")
        code, out = self.sdd("deps", "cc", cwd=wt_c)
        self.assertEqual(code, 1, out)
        lines = [l for l in out.splitlines() if l.startswith(("open", "unknown", "ready"))]
        self.assertEqual([l.split()[1] for l in lines], ["aa", "bb"])
        self.assertIn("next: resume aa", out)

    def test_cycle_is_an_error(self):
        wt_a = self.start("aa")
        self.started_with("aa", "bb")
        code, out = self.sdd("requires", "aa", "bb", cwd=wt_a)
        self.assertEqual(code, 1, out)
        self.assertIn("cycle aa -> bb -> aa", out)
        self.assertEqual(self.state(wt_a, "aa").get("requires"), [])
        self.assertEqual(self.sdd("start", "cc", "--title", "C", "--requires", "cc")[0], 2)

    def test_requires_command_sets_shows_and_clears(self):
        wt = self.start()
        self.assertEqual(self.sdd("requires", "c1", cwd=wt)[1].strip(), "-")
        code, out = self.sdd("requires", "c1", "xx,yy", "zz", cwd=wt)
        self.assertEqual(code, 0, out)
        self.assertEqual(self.state(wt)["requires"], ["xx", "yy", "zz"])
        self.git("fetch", "-q", "origin", "sdd/c1")
        self.assertEqual(self.remote_subjects("sdd/c1")[0], "chore(sdd): c1 requires xx,yy,zz")
        self.assertEqual(self.sdd("requires", "c1", cwd=wt)[1].strip(), "xx,yy,zz")
        self.sdd("requires", "c1", "--clear", cwd=wt)
        self.assertEqual(self.state(wt)["requires"], [])

    def test_checkpoint_gates_plan_and_later_but_not_earlier_phases(self):
        wt = self.started_with()
        self.start("dep")
        self.assertEqual(self.sdd("checkpoint", "c1", "--phase", "gate1", cwd=wt)[0], 0)
        code, out = self.sdd("checkpoint", "c1", "--phase", "plan", cwd=wt)
        self.assertEqual(code, 1, out)
        self.assertIn("required changes are not merged", out)
        self.assertIn("Next: resume dep", out)
        self.assertEqual(self.state(wt)["phase"], "gate1")

    def test_resume_refuses_while_dep_is_open_and_names_next_step(self):
        wt = self.started_with()
        self.start("dep")
        other = self.tmp / "other"
        self.git("clone", "-q", str(self.origin), str(other), cwd=self.tmp)
        code, out = self.sdd("resume", "c1", cwd=other)
        self.assertEqual(code, 1, out)
        self.assertIn("blocked: required changes are not merged into main", out)
        self.assertIn("next: resume dep, then `resume c1` again", out)
        self.assertNotIn("EnterWorktree", out)

    def test_resume_says_to_merge_a_finished_dep(self):
        self.started_with()
        self.finish_change("dep")
        code, out = self.sdd("resume", "c1")
        self.assertEqual(code, 1, out)
        self.assertIn("next: merge the PR of dep (#7), then `resume c1` again", out)

    def test_resume_and_checkpoint_merge_base_once_dep_is_merged(self):
        wt = self.started_with()
        self.finish_change("dep")
        self.merge_into_main("dep")
        code, out = self.sdd("resume", "c1")
        self.assertEqual(code, 0, out)
        self.assertIn("merged origin/main into the branch", out)
        self.assertTrue(list((wt / "changes/archive").glob("*-dep")))
        self.assertEqual(self.sdd("deps", "c1", cwd=wt)[0], 0)
        # a second change: the checkpoint itself brings the base in
        wt2 = self.started_with("dep", "c2")
        code, out = self.sdd("checkpoint", "c2", "--phase", "plan", cwd=wt2)
        self.assertEqual(code, 0, out)
        self.assertEqual(self.state(wt2, "c2")["phase"], "plan")

    def test_synced_but_not_finished_dep_is_still_open(self):
        wt = self.started_with()
        d = self.start("dep")
        self.assertEqual(self.sdd("set-status", "dep", "verified", cwd=d)[0], 0)
        put(d / "changes/dep/specs/capabilities/tokens.md", NEW_CAP)
        (d / "changes/dep/tasks.md").write_text(
            TOKEN_TASKS)
        self.assertEqual(self.sdd("sync", "dep", "--force", cwd=d)[0], 0)
        self.git("add", "-A", cwd=d)
        self.git("commit", "-qm", "sync", cwd=d)
        self.git("push", "-q", cwd=d)
        code, out = self.sdd("deps", "c1", cwd=wt)
        self.assertEqual(code, 1, out)
        self.assertIn("open dep phase spec pr #7 (synced, `finish` not run)", out)
        self.assertIn("next: resume dep", out)

    def test_start_does_not_warn_about_a_dep_merged_while_main_checkout_is_stale(self):
        self.finish_change("dep")
        self.merge_into_main("dep")
        self.git("reset", "-q", "--hard", "HEAD~1", cwd=self.root)  # local main behind origin
        code, out = self.sdd("start", "c1", "--title", "C", "--requires", "dep")
        self.assertEqual(code, 0, out)
        self.assertNotIn("WARN", out)

    def test_requires_command_warns_about_unmerged_and_unknown(self):
        wt = self.start()
        self.start("dep")
        code, out = self.sdd("requires", "c1", "dep", "lgoin", cwd=wt)
        self.assertEqual(code, 0, out)
        self.assertIn("WARN requires open dep phase spec", out)
        self.assertIn("WARN requires unknown lgoin no branch sdd/lgoin", out)

    def test_resume_refuses_to_merge_base_over_uncommitted_changes(self):
        wt = self.started_with()
        self.finish_change("dep")
        self.merge_into_main("dep")
        (wt / "scratch.txt").write_text("wip\n")
        code, out = self.sdd("resume", "c1")
        self.assertEqual(code, 1, out)
        self.assertIn("uncommitted changes", out)
        self.assertEqual((wt / "scratch.txt").read_text(), "wip\n")
        self.assertFalse(list((wt / "changes/archive").glob("*-dep")))

    def test_base_merge_conflict_is_aborted_cleanly(self):
        wt = self.started_with()
        (wt / "clash.txt").write_text("branch\n")
        self.sdd("checkpoint", "c1", cwd=wt)
        self.finish_change("dep")
        (self.root / "clash.txt").write_text("main\n")
        self.git("add", "-A", cwd=self.root)
        self.git("commit", "-qm", "clash", cwd=self.root)
        self.merge_into_main("dep")
        code, out = self.sdd("resume", "c1")
        self.assertEqual(code, 1, out)
        self.assertIn("clash.txt", out)
        self.assertEqual(self.git("status", "--porcelain", cwd=wt), "")


class TestPlanned(GitCase):
    """Changes planned on the base (intent.md committed before `start`), as a backlog."""

    def plan(self, name: str, title: str = "Planned", requires: str = ""):
        self.assertEqual(self.sdd("new", name, "--title", title)[0], 0)
        intent = self.root / f"changes/{name}/intent.md"
        text = intent.read_text().replace(f"title: {title}\n", f'title: "{title}"\nrequires: [{requires}]\n')
        intent.write_text(text.replace("## Why\n", "## Why\nWritten while planning.\n"))
        self.git("add", "-A", cwd=self.root)
        self.git("commit", "-qm", f"plan {name}", cwd=self.root)
        self.git("push", "-q", "origin", "main", cwd=self.root)

    def test_start_adopts_a_planned_change_and_keeps_its_intent(self):
        self.plan("010-dep", "The dependency")
        self.plan("020-c1", "Change one", "010-dep")
        code, out = self.sdd("start", "020-c1")
        self.assertEqual(code, 0, out)
        self.assertIn("adopted planned changes/020-c1/", out)
        self.assertIn("WARN requires planned 010-dep planned on main, not started", out)
        wt = self.root / ".claude/worktrees/sdd-020-c1"
        self.assertIn("Written while planning.", (wt / "changes/020-c1/intent.md").read_text())
        self.assertEqual(self.state(wt, "020-c1")["requires"], ["010-dep"])
        self.assertIn("--title Change one", self.log.read_text())
        code, out = self.sdd("deps", "020-c1", cwd=wt)
        self.assertEqual(code, 1, out)
        self.assertIn("next: start 010-dep", out)

    def test_start_refuses_flags_that_contradict_the_intent(self):
        self.plan("010-dep")
        self.plan("020-c1", "Change one", "010-dep")
        self.assertEqual(self.sdd("start", "020-c1", "--requires", "010-dep")[0], 0)
        self.plan("030-c2", "Change two", "010-dep")
        code, out = self.sdd("start", "030-c2", "--requires", "020-c1")
        self.assertEqual(code, 2, out)
        self.assertIn("differs from intent.md requires 010-dep", out)
        code, out = self.sdd("start", "030-c2", "--title", "Other")
        self.assertEqual(code, 2, out)
        self.assertFalse((self.root / ".claude/worktrees/sdd-030-c2").exists())

    def test_start_refuses_a_planned_change_already_started_on_the_base(self):
        self.plan("020-c1")
        (self.root / "changes/020-c1/state.json").write_text('{"phase": "spec", "branch": "sdd/020-c1"}')
        self.git("add", "-A", cwd=self.root)
        self.git("commit", "-qm", "stray state", cwd=self.root)
        self.git("push", "-q", "origin", "main", cwd=self.root)
        code, out = self.sdd("start", "020-c1")
        self.assertEqual(code, 1, out)
        self.assertIn("started already", out)

    def test_a_cycle_in_planned_requires_is_refused_before_any_side_effect(self):
        self.plan("010-a", "A", "020-b")
        self.plan("020-b", "B", "010-a")
        code, out = self.sdd("start", "010-a")
        self.assertEqual(code, 1, out)
        self.assertIn("cycle 010-a -> 020-b -> 010-a", out)
        self.assertEqual(self.git("branch", "--list", "sdd/010-a", cwd=self.root), "")

    def test_new_points_at_start_for_a_planned_change(self):
        self.plan("020-c1")
        code, out = self.sdd("new", "020-c1")
        self.assertNotEqual(code, 0)
        self.assertIn("a planned change, `start` adopts it", out)

    def test_requires_command_keeps_the_intent_in_step(self):
        self.plan("010-dep")
        self.plan("020-c1", "Change one", "010-dep")
        self.assertEqual(self.sdd("start", "020-c1")[0], 0)
        wt = self.root / ".claude/worktrees/sdd-020-c1"
        self.assertEqual(self.sdd("requires", "020-c1", "--clear", cwd=wt)[0], 0)
        self.assertIn("requires: []", (wt / "changes/020-c1/intent.md").read_text())

    def test_start_without_a_plan_is_unchanged(self):
        wt = self.start()
        self.assertNotIn("requires", (wt / "changes/c1/intent.md").read_text())


class TestBaselineProof(GitCase):
    """Baseline tests are frozen on unchanged code and re-run on the base commit."""
    def setUp(self):
        super().setUp()
        self.write("src/tokens.py", "TTL = 1\n")
        self.git("add", "-A")
        self.git("commit", "-qm", "code")
        self.git("push", "-q")
        self.wt = self.start()
        put(self.wt / "changes/c1/specs/capabilities/tokens.md", NEW_CAP.replace(
            "- **Then** the response is 401\n", "- **Then** the response is 401\n- **Baseline**: src/tokens.py\n"))
        put(self.wt / "changes/c1/tasks.md", "---\ntype: tasks\n---\n\n# Tasks\n\n"
            "- [x] T1 (test) t — capabilities/tokens#AC-01\n")
        self.test_file = self.wt / "tests/acceptance/test_tokens.py"
        put(self.test_file, "# capabilities/tokens#AC-01\ndef test_expired():\n    assert True\n")

    def write(self, rel: str, text: str):
        put(self.root / rel, text)

    def state(self) -> dict:
        return json.loads((self.wt / "changes/c1/state.json").read_text())

    def test_freeze_records_the_base_commit(self):
        code, out = self.sdd("freeze", "c1", cwd=self.wt)
        self.assertEqual(code, 0, out)
        base = self.git("merge-base", "HEAD", "origin/main", cwd=self.wt)
        self.assertEqual(self.state()["baseline"]["commit"], base)
        self.assertEqual(list(self.state()["baseline"]["files"]), ["tests/acceptance/test_tokens.py"])
        self.assertIn(f"baseline={base[:8]}", self.sdd("status", cwd=self.wt)[1])

    def test_new_baseline_test_after_code_changed_is_refused(self):
        put(self.wt / "src/tokens.py", "TTL = 2\n")
        code, out = self.sdd("freeze", "c1", cwd=self.wt)
        self.assertEqual(code, 1, out)
        self.assertIn("Baseline tests must be frozen before production code changes: src/tokens.py", out)
        self.assertFalse((self.wt / "changes/c1/frozen.json").exists())
        code, out = self.sdd("freeze", "c1", "--after-code", cwd=self.wt)
        self.assertEqual(code, 0, out)
        self.assertIn("WARN  production code already changed", out)

    def test_mixed_baseline_file_warns(self):
        put(self.wt / "changes/c1/specs/capabilities/tokens.md", NEW_CAP.replace(
            "- **Then** the response is 401\n", "- **Then** the response is 401\n- **Baseline**: src/tokens.py\n")
            + "\n### AC-02: Revoked token\n\n- **Given** a revoked token\n- **When** it calls GET /v1/me\n"
            "- **Then** the response is 401\n")
        put(self.wt / "changes/c1/tasks.md", "---\ntype: tasks\n---\n\n# Tasks\n\n"
            "- [x] T1 (test) t — capabilities/tokens#AC-01 capabilities/tokens#AC-02\n"
            "- [ ] T2 (impl) i — capabilities/tokens#AC-02 | blocked-by: T1\n")
        put(self.test_file, "# capabilities/tokens#AC-01\n# capabilities/tokens#AC-02\ndef test_x():\n    pass\n")
        code, out = self.sdd("freeze", "c1", cwd=self.wt)
        self.assertEqual(code, 0, out)
        self.assertIn("also tests capabilities/tokens#AC-02", out)

    def test_unchanged_baseline_test_refreezes_after_code(self):
        self.assertEqual(self.sdd("freeze", "c1", cwd=self.wt)[0], 0)
        put(self.wt / "src/tokens.py", "TTL = 2\n")
        self.assert_ok_(self.sdd("freeze", "c1", cwd=self.wt))

    def assert_ok_(self, res):
        self.assertEqual(res[0], 0, res[1])

    def test_baseline_tree_has_base_code_and_current_tests(self):
        self.assertEqual(self.sdd("baseline-tree", "c1", cwd=self.wt)[0], 1)
        self.assertEqual(self.sdd("freeze", "c1", cwd=self.wt)[0], 0)
        put(self.wt / "src/tokens.py", "TTL = 2\n")
        code, out = self.sdd("baseline-tree", "c1", cwd=self.wt)
        self.assertEqual(code, 0, out)
        tree = self.wt / ".claude/worktrees/sdd-c1-baseline"
        self.assertEqual((tree / "src/tokens.py").read_text(), "TTL = 1\n")
        self.assertTrue((tree / "tests/acceptance/test_tokens.py").exists())
        self.assertIn("run: pytest -q tests/acceptance/test_tokens.py", out)
        self.assertEqual(self.sdd("baseline-tree", "c1", "--link", "../x", cwd=self.wt)[0], 2)
        put(self.wt / "node_modules/dep/index.js", "")
        put(self.wt / "deps/lib.py", "")
        code, out = self.sdd("baseline-tree", "c1", "--link", "deps", cwd=self.wt)
        self.assertEqual(code, 0, out)
        self.assertIn("linked node_modules deps", out)
        self.assertTrue((tree / "node_modules/dep/index.js").exists())
        self.assertTrue((tree / "deps").is_symlink())
        code, out = self.sdd("baseline-tree", "c1", "--remove", cwd=self.wt)
        self.assertEqual(code, 0, out)
        self.assertFalse(tree.exists())


class TestFinishAndStatus(GitCase):
    def test_status_json_and_check_warn_expose_state(self):
        wt = self.start()
        code, out = self.sdd("status", "--json", cwd=wt)
        [c] = json.loads(out)["changes"]
        self.assertEqual((c["phase"], c["pr"], c["branch"]), ("spec", 7, "sdd/c1"))
        self.sdd("checkpoint", "c1", "--phase", "implement", cwd=wt)  # but status is draft
        code, out = self.sdd("check", "c1", cwd=wt)
        self.assertIn("WARN  state.json phase 'implement' does not fit status 'draft'", out)

    def test_finish_ignores_archived_changes_whose_name_only_ends_the_same(self):
        wt = self.start()
        other = wt / "changes/archive/2099-01-01-add-c1"
        other.mkdir(parents=True)
        (other / "state.json").write_text(json.dumps({"branch": "sdd/add-c1", "phase": "sync"}))
        code, out = self.sdd("finish", "c1", cwd=wt)
        self.assertEqual(code, 1, out)
        self.assertIn("no archived change 'c1'", out)

    def test_finish_marks_done_pushes_and_readies_pr(self):
        wt = self.start()
        self.assertEqual(self.sdd("set-status", "c1", "verified", cwd=wt)[0], 0)
        put(wt / "changes/c1/specs/capabilities/tokens.md", NEW_CAP)
        (wt / "changes/c1/tasks.md").write_text(
            TOKEN_TASKS)
        code, out = self.sdd("sync", "c1", "--force", cwd=wt)
        self.assertEqual(code, 0, out)
        code, out = self.sdd("finish", "c1", cwd=wt)
        self.assertEqual(code, 0, out)
        self.assertIn("pr 7 ready for review", out)
        self.assertIn("pr ready 7", self.log.read_text())
        [arch] = (wt / "changes/archive").glob("*-c1")
        self.assertEqual(json.loads((arch / "state.json").read_text())["phase"], "done")
        self.git("fetch", "-q", "origin", "sdd/c1")
        self.assertEqual(self.remote_subjects("sdd/c1")[0], "chore(sdd): sync c1")


OLD_REQ = """\
---
type: spec
title: auth
capability: auth
sources: []
---

# auth

### REQ-AUTH-001: Login with password
The API MUST accept a valid password.

#### Scenario: good password
- GIVEN user alice
- WHEN she logs in with the right password
- THEN the response is 200
"""


class TestBundle(SddCase):
    def test_fresh_init_is_a_valid_bundle(self):
        for b in ("specs", "adrs"):
            self.assert_ok(self.sdd("bundle", b))

    def test_old_req_format_is_an_error_without_migration(self):
        self.write("specs/auth/auth.md", OLD_REQ)
        self.write(f"specs/{CAP_INV_OLD}", OLD_REQ.replace("type: spec", "type: Capability"))
        code, out = self.sdd("bundle", "specs", "--fix")
        self.assertEqual(code, 1, out)
        self.assertEqual(out.count("old sdd format (REQ/INV blocks)"), 2, out)
        self.assertIn("REQ-AUTH-001", self.read("specs/auth/auth.md"))

    def test_misplaced_and_badly_named_concepts(self):
        self.write("specs/loose.md", LOGIN)
        self.write("specs/capabilities/Bad-Name.md", LOGIN)
        self.write("specs/invariants/x.md", LOGIN)
        code, out = self.sdd("bundle", "specs")
        self.assertEqual(code, 1, out)
        self.assertEqual(out.count("concepts live in specs/capabilities/ or specs/invariants/"), 2, out)
        self.assertIn("specs/invariants/x.md: type is 'Capability', expected Invariant", out)

    def test_dot_directories_are_ignored(self):
        self.write("specs/.templates/notes.md", "# not a concept\n")
        self.assert_ok(self.sdd("bundle", "specs"))
        self.assertNotIn(".templates", self.read("specs/index.md"))

    def test_stale_and_old_style_indexes_are_fixed(self):
        self.living()
        self.write("specs/capabilities/index.md", "---\ntype: index\ntitle: capabilities\n---\n\n# capabilities\n")
        self.write("specs/capabilities/auth/index.md", "stale\n")
        self.assert_fails(self.sdd("bundle", "specs"), "capabilities/index.md: stale", "auth/index.md: stale")
        self.assert_ok(self.sdd("bundle", "specs", "--fix"))
        self.assertEqual(self.read("specs/capabilities/auth/index.md"),
                         "# Capability\n\n* [Login](login.md) - A user can log in.\n")
        self.assertEqual(self.read("specs/capabilities/index.md"),
                         "# Subdirectories\n\n* [auth](auth/index.md) - A user can log in.\n")
        self.assert_ok(self.sdd("bundle", "specs"))

    def test_unsorted_criteria_are_fixed(self):
        self.living()
        ac1 = LOGIN.split("### AC-01")[1].split("### AC-02")[0]
        ac2 = LOGIN.split("### AC-02")[1].split("## Invariants")[0]
        self.write(f"specs/{LOGIN_REF}.md", LOGIN.split("### AC-01")[0] + "### AC-02" + ac2 + "### AC-01" + ac1
                   + "## Invariants" + LOGIN.split("## Invariants")[1])
        self.assert_fails(self.sdd("bundle", "specs"), "acceptance criteria not sorted")
        self.assert_ok(self.sdd("bundle", "specs", "--fix"))
        self.assertEqual(re.findall(r"^### (AC-\d+)", self.read(f"specs/{LOGIN_REF}.md"), re.M), ["AC-01", "AC-02"])
        self.assert_ok(self.sdd("bundle", "specs"))

    def test_sources_are_okf_entries_and_missing_ones_dropped(self):
        self.living()
        self.write("src/a.py", "x = 1\n")
        self.edit(f"specs/{LOGIN_REF}.md", "sources: []", "sources: [src/a.py, src/gone.py]")
        code, out = self.sdd("bundle", "specs")
        self.assertEqual(code, 0, out)
        self.assertIn("source 'src/gone.py' not found", out)
        self.assertIn("sources are plain strings", out)
        self.assert_ok(self.sdd("bundle", "specs", "--fix"))
        self.assertIn("sources:\n  - resource: src/a.py\n---", self.read(f"specs/{LOGIN_REF}.md"))
        code, out = self.sdd("bundle", "specs", "--fix")
        self.assertNotIn("FIXED", out)

    def test_missing_title_comes_from_the_heading(self):
        self.write(f"specs/{LOGIN_REF}.md", LOGIN.replace('title: "Login"\n', ""))
        self.assert_fails(self.sdd("bundle", "specs"), "no title in front matter")
        self.assert_ok(self.sdd("bundle", "specs", "--fix"))
        self.assertIn("title: Login\n", self.read(f"specs/{LOGIN_REF}.md"))

    def test_log_without_a_date_group_is_fixed(self):
        self.write("specs/log.md", "# Update Log\n")
        self.assert_fails(self.sdd("bundle", "specs"), "no `## YYYY-MM-DD` entry")
        self.assert_ok(self.sdd("bundle", "specs", "--fix"))
        self.assertIn("* **Creation**:", self.read("specs/log.md"))

    def test_invariant_structure(self):
        self.write("specs/invariants/no_secrets.md", NO_SECRETS.replace("- Check:", "- Note:")
                   .split("### Violation")[0])
        self.assert_fails(self.sdd("bundle", "specs", "--fix"), "needs a '- Check:' line",
                          "needs a '### Violation' case")

    def test_change_bundle_old_delta_misplaced_and_wrong_type(self):
        self.living()
        self.new_change()
        self.write("changes/c1/specs/auth/auth.md", OLD_REQ.replace("type: spec", "type: spec-delta"))
        self.write("changes/c1/specs/elsewhere/x.md", NEW_CAP)
        self.write("changes/c1/specs/invariants/x.md", NEW_CAP)
        code, out = self.sdd("bundle", "c1")
        self.assertEqual(code, 1, out)
        self.assertIn("changes/c1/specs/auth/auth.md: old sdd format", out)
        self.assertIn("changes/c1/specs/elsewhere/x.md: deltas live in specs/capabilities/", out)
        self.assertIn("type 'Capability' does not fit invariants/x (Invariant)", out)

    def test_change_bundle_front_matter_and_indexes_are_fixed(self):
        self.living()
        self.new_change()
        self.assert_ok(self.sdd("delta-new", "c1", LOGIN_REF))
        self.edit(self.delta(), f"target: specs/{LOGIN_REF}.md\n", "")
        self.write("changes/c1/specs/capabilities/tokens.md", NEW_CAP)
        code, out = self.sdd("bundle", "c1")
        self.assertEqual(code, 0, out)
        self.assertIn("front matter incomplete", out)
        self.assertIn("index.md: stale", out)
        self.assert_ok(self.sdd("bundle", "c1", "--fix"))
        self.assertIn(f"target: specs/{LOGIN_REF}.md", self.read(self.delta()))
        self.assertIn("* [Tokens](tokens.md) - Expired tokens are rejected.",
                      self.read("changes/c1/specs/capabilities/index.md"))
        code, out = self.sdd("bundle", "c1", "--fix")
        self.assertNotIn("FIXED", out)
        self.assertNotIn("WARN", out)

    def test_unknown_change(self):
        self.assert_fails(self.sdd("bundle", "nope"), "no change 'nope'", code=2)


class TestReviewFixes(SddCase):
    """Regressions from the code review of the concept format."""

    def test_block_scalar_description_reads_and_indexes_stably(self):
        self.write(f"specs/{LOGIN_REF}.md", LOGIN.replace('description: "A user can log in."',
                                                          "description: >\n  A user can\n  log in."))
        self.assert_ok(self.sdd("bundle", "specs", "--fix"))
        self.assertIn("* [Login](login.md) - A user can log in. ", self.read("specs/capabilities/auth/index.md"))
        code, out = self.sdd("bundle", "specs")
        self.assertEqual(code, 0, out)
        self.assertNotIn("stale", out)
        self.assertNotIn("description", out)

    def test_multi_line_quoted_description(self):
        self.write(f"specs/{LOGIN_REF}.md", LOGIN.replace('description: "A user can log in."',
                                                          'description: "A user can\n  log in."'))
        self.assert_ok(self.sdd("bundle", "specs", "--fix"))
        self.assertIn("* [Login](login.md) - A user can log in.\n", self.read("specs/capabilities/auth/index.md"))

    def test_nested_nulls_and_lists_survive_a_sync(self):
        self.write("src/a.py", "x\n")
        self.living()
        self.edit(f"specs/{LOGIN_REF}.md", "sources: []",
                  "sources:\n  - resource: src/a.py\n    note:\n    tags: [a, \"b,c\"]")
        self.new_change()
        self.assert_ok(self.sdd("delta-stub", "c1", f"{LOGIN_REF}#AC-01"))
        self.set_tasks("c1", f"- [x] T1 (test) x — {LOGIN_REF}#AC-01", f"- [x] T2 (impl) y — {LOGIN_REF}#AC-01 | blocked-by: T1")
        self.sdd("set-status", "c1", "verified")
        self.assert_ok(self.sdd("sync", "c1"))
        spec = self.read(f"specs/{LOGIN_REF}.md")
        self.assertIn("  - resource: src/a.py\n    note: null\n    tags: [a, \"b,c\"]\n", spec)

    def test_invariant_replace_conflicts_on_a_front_matter_change(self):
        self.write("specs/invariants/no_secrets.md", NO_SECRETS)
        self.assert_ok(self.sdd("bundle", "specs", "--fix"))
        self.new_change()
        self.assert_ok(self.sdd("delta-stub", "c1", "invariants/no_secrets"))
        self.set_tasks("c1", "- [ ] T1 (test) x — invariants/no_secrets")
        self.assert_ok(self.sdd("check", "c1"))
        self.edit("specs/invariants/no_secrets.md", "No password is logged.", "No password or key is logged.")
        self.assert_fails(self.sdd("check", "c1"), "invariants/no_secrets: CONFLICT")

    def test_section_with_sub_headings_is_one_unit(self):
        self.write(f"specs/{LOGIN_REF}.md", LOGIN.replace("- In: password login\n- Out: SSO",
                                                          "### In scope\n\n- password login\n\n### Out of scope\n\n- SSO"))
        self.assert_ok(self.sdd("bundle", "specs", "--fix"))
        self.new_change()
        self.assert_ok(self.sdd("delta-stub", "c1", LOGIN_REF, "--section", "Scope"))
        self.edit(self.delta(), "- SSO", "- SSO, passkeys")
        self.set_tasks("c1", "- [x] T1 (chore) scope wording")
        self.assert_ok(self.sdd("check", "c1"))
        self.sdd("set-status", "c1", "verified")
        self.assert_ok(self.sdd("sync", "c1"))
        spec = self.read(f"specs/{LOGIN_REF}.md")
        self.assertIn("## Scope\n\n### In scope\n\n- password login\n\n### Out of scope\n\n- SSO, passkeys\n", spec)

    def test_duplicate_section_and_unknown_delta_section_are_errors(self):
        self.living()
        self.new_change()
        self.assert_ok(self.sdd("delta-stub", "c1", LOGIN_REF, "--section", "Scope"))
        self.edit(self.delta(), "## SECTIONS\n", "## SECTIONS\n\n### Scope\n\n- In: x\n")
        self.edit(self.delta(), "## ADDED\n", "## Added\n\n" + AC_03 + "\n## ADDED\n")
        self.assert_fails(self.sdd("check", "c1"), "Scope: appears twice under SECTIONS",
                          "unknown section '## Added'")

    def test_stray_heading_under_criteria_is_an_error(self):
        self.write(f"specs/{LOGIN_REF}.md", LOGIN.replace("## Invariants", "### Notes\n\nSome notes.\n\n## Invariants"))
        self.assert_fails(self.sdd("bundle", "specs"), "'### Notes' under Acceptance criteria")
        self.living()
        self.new_change()
        self.assert_ok(self.sdd("delta-stub", "c1", f"{LOGIN_REF}#AC-02"))
        self.edit(self.delta(), "the response is 423", "the response is 423\n\n### Notes\n\nx")
        self.assert_fails(self.sdd("check", "c1"), "'### Notes' under ## MODIFIED is not a criterion")

    def test_fix_never_drops_a_stray_heading(self):
        ac1 = LOGIN.split("### AC-01")[1].split("### AC-02")[0]
        ac2 = LOGIN.split("### AC-02")[1].split("## Invariants")[0]
        self.write(f"specs/{LOGIN_REF}.md", LOGIN.split("### AC-01")[0] + "### AC-02" + ac2 + "### Notes\n\nKEEP ME\n\n"
                   + "### AC-01" + ac1 + "## Invariants" + LOGIN.split("## Invariants")[1])
        self.assert_fails(self.sdd("bundle", "specs", "--fix"), "not fixable while")
        self.assertIn("KEEP ME", self.read(f"specs/{LOGIN_REF}.md"))

    def test_stray_heading_does_not_change_the_criterion_hash(self):
        self.living()
        self.new_change()
        self.assert_ok(self.sdd("delta-stub", "c1", f"{LOGIN_REF}#AC-02"))
        self.edit(f"specs/{LOGIN_REF}.md", "## Invariants", "### Notes\n\nx\n\n## Invariants")
        code, out = self.sdd("check", "c1")
        self.assertNotIn("CONFLICT", out)

    def test_rationale_adr_link_is_resolved_and_counted(self):
        self.sdd("adr-new", "Redact logs")
        self.new_change()
        self.write("changes/c1/specs/invariants/no_secrets.md", NO_SECRETS.replace(
            "Logs are widely readable.", "Logs are widely readable.\n\n- Decided in: [Redact](../../adrs/0001_redact_logs.md)\n"
            "- Also: [gone](../../adrs/0009_gone.md)").replace("status: stable", "status: draft"))
        self.set_tasks("c1", "- [ ] T1 (test) x — invariants/no_secrets")
        code, out = self.sdd("check", "c1")
        self.assertIn("ADR-0001 is linked from a concept but not in intent.md adrs", out)
        self.assertIn("link '../../adrs/0009_gone.md' in '## Rationale' does not resolve", out)

    def test_directory_with_only_an_index_is_not_listed(self):
        self.living()
        self.write("specs/capabilities/empty/index.md", "# Capability\n")
        code, out = self.sdd("bundle", "specs", "--fix")
        self.assertEqual(code, 0, out)
        self.assertNotIn("empty", self.read("specs/capabilities/index.md"))
        self.assertFalse((self.root / "specs/capabilities/empty/index.md").exists())
        code, out = self.sdd("bundle", "specs", "--fix")
        self.assertNotIn("FIXED", out)

    def test_reserved_change_ids(self):
        for name in ("specs", "adrs", "archive"):
            self.assert_fails(self.sdd("new", name), "is reserved", code=2)


CAP_INV_OLD = "capabilities/auth/old.md"


if __name__ == "__main__":
    unittest.main()
