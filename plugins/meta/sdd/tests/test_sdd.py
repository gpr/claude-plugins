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

LIVING_AUTH = """\
# auth

### REQ-AUTH-001: Login with password
The API MUST accept a valid password.

#### Scenario: good password
- GIVEN user alice
- WHEN she logs in with the right password
- THEN the response is 200

### REQ-AUTH-002: Lockout
The API MUST lock the account after 5 failures.

#### Scenario: five failures
- GIVEN 5 failed logins
- WHEN alice logs in again
- THEN the response is 423
"""

ADDED_003 = """\
### REQ-AUTH-003: Expired tokens are rejected
The API MUST reject an expired token with 401.

#### Scenario: expired token
- GIVEN a token expired 1 second ago
- WHEN it calls GET /v1/me
- THEN the response is 401
"""


def put(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def dedent(s: str) -> str:
    return textwrap.dedent(s).lstrip("\n")


class SddCase(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="sdd-test-"))
        (self.root / ".git").mkdir()
        self.assertEqual(self.sdd("init")[0], 0)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    # ---------------------------------------------------------------- helpers --
    def sdd(self, *args: str) -> tuple[int, str]:
        p = subprocess.run([sys.executable, str(SDD), *args], cwd=self.root,
                           capture_output=True, text=True, timeout=30)
        return p.returncode, p.stdout + p.stderr

    def write(self, rel: str, text: str):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def read(self, rel: str) -> str:
        return (self.root / rel).read_text()

    def set_tasks(self, change: str, *lines: str):
        self.write(f"changes/{change}/tasks.md", "# Tasks\n\n" + "\n".join(lines) + "\n")

    def living(self):
        self.write("specs/auth/auth.md", LIVING_AUTH)
        self.assert_ok(self.sdd("bundle", "specs", "--fix"))

    def new_change(self, name: str = "c1") -> str:
        code, out = self.sdd("new", name)
        self.assertEqual(code, 0, out)
        return name

    def added_change(self, name: str = "c1") -> str:
        """A clean change adding REQ-AUTH-003 with a test and an impl task."""
        self.new_change(name)
        self.write(f"changes/{name}/specs/auth/auth.md", "# Delta: auth\n\n## ADDED\n\n" + ADDED_003)
        self.set_tasks(name,
                       "- [ ] T1 (test) Expired token — REQ-AUTH-003",
                       "- [ ] T2 (impl) Reject expired — REQ-AUTH-003 | blocked-by: T1")
        return name

    def accept_test(self, rel: str = "tests/acceptance/test_tokens.py", req: str = "REQ-AUTH-003"):
        self.write(rel, f"# {req}\ndef test_expired():\n    assert True\n")
        return rel

    def assert_ok(self, res: tuple[int, str]):
        self.assertEqual(res[0], 0, res[1])

    def assert_fails(self, res: tuple[int, str], *needles: str, code: int = 1):
        self.assertEqual(res[0], code, res[1])
        for n in needles:
            self.assertIn(n, res[1])


# ------------------------------------------------------------------ setup ----
class TestInitConfigNew(SddCase):
    def test_init_creates_layout_and_config(self):
        for d in ("specs", "adr", "changes", "tests/acceptance"):
            self.assertTrue((self.root / d).is_dir(), d)
        cfg = json.loads(self.read(".claude/sdd.json"))
        self.assertIn("acceptance_cmd", cfg)
        self.assertNotIn("req_id_pattern", cfg)

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

    def test_new_rejects_bad_id_and_duplicates(self):
        self.assert_fails(self.sdd("new", "Bad_Name"), "kebab-case", code=2)
        self.new_change("c1")
        self.assert_fails(self.sdd("new", "c1"), "already exists", code=2)

    def test_unknown_command_is_usage_error(self):
        self.assertEqual(self.sdd("nope")[0], 2)
        self.assertEqual(self.sdd()[0], 2)

    def test_unknown_change_is_usage_error(self):
        self.assert_fails(self.sdd("check", "ghost"), "no change 'ghost'", code=2)


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
        self.assertEqual(c["tasks"][0]["reqs"], ["REQ-AUTH-003"])

    def test_task_template_comment_is_not_parsed(self):
        # the template's format comment contains task-shaped lines
        self.new_change()
        code, out = self.sdd("status", "--json")
        self.assertEqual(json.loads(out)["changes"][0]["tasks"], [])


# -------------------------------------------------------------- delta-stub --
class TestDeltaNew(SddCase):
    def test_scaffolds_delta_from_template(self):
        self.new_change()
        code, out = self.sdd("delta-new", "c1", "auth")
        self.assertEqual(code, 0, out)
        self.assertIn("created changes/c1/specs/auth/auth.md", out)
        delta = self.read("changes/c1/specs/auth/auth.md")
        self.assertIn("type: spec-delta\ntarget: specs/auth/auth.md\n", delta)
        self.assertIn("\n# Delta: auth\n", delta)
        for section in ("## ADDED", "## MODIFIED", "## REMOVED"):
            self.assertEqual(delta.count(f"\n{section}\n"), 1, section)
        self.assertIn("- GIVEN", delta)
        self.assertNotIn("{{", delta)

    def test_template_example_is_not_parsed(self):
        # the guidance comment holds a REQ/scenario skeleton
        self.new_change()
        self.assert_ok(self.sdd("delta-new", "c1", "auth"))
        code, out = self.sdd("check", "c1")
        self.assertEqual(code, 0, out)
        self.assertNotIn("ERROR", out)
        self.assertIn("no spec delta", out)

    def test_rejects_bad_capability_and_duplicate(self):
        self.new_change()
        self.assert_fails(self.sdd("delta-new", "c1", "Auth_X"), "kebab-case", code=2)
        self.assert_ok(self.sdd("delta-new", "c1", "auth"))
        self.assert_fails(self.sdd("delta-new", "c1", "auth"), "already exists", code=2)
        self.assert_fails(self.sdd("delta-new", "ghost", "auth"), "no change 'ghost'", code=2)

    def test_delta_stub_fills_template_sections(self):
        self.living()
        self.new_change()
        self.assert_ok(self.sdd("delta-new", "c1", "auth"))
        self.assert_ok(self.sdd("delta-stub", "c1", "REQ-AUTH-001"))
        delta = self.read("changes/c1/specs/auth/auth.md")
        self.assertEqual(delta.count("## MODIFIED"), 1)
        self.assertLess(delta.index("## MODIFIED"), delta.index("### REQ-AUTH-001"))
        self.assertLess(delta.index("### REQ-AUTH-001"), delta.index("## REMOVED"))


class TestDeltaStub(SddCase):
    def setUp(self):
        super().setUp()
        self.living()
        self.new_change()

    def test_missing_delta_starts_from_template(self):
        self.assert_ok(self.sdd("delta-stub", "c1", "REQ-AUTH-001"))
        delta = self.read("changes/c1/specs/auth/auth.md")
        self.assertIn("type: spec-delta\ntarget: specs/auth/auth.md\n", delta)
        self.assertIn("\n# Delta: auth\n", delta)
        self.assertIn("## ADDED", delta)
        self.assertEqual(delta.count("## MODIFIED"), 1)

    def test_modified_copies_block_with_base_hash(self):
        code, out = self.sdd("delta-stub", "c1", "REQ-AUTH-001")
        self.assertEqual(code, 0, out)
        base = re.search(r"base=([0-9a-f]{8})", out).group(1)
        delta = self.read("changes/c1/specs/auth/auth.md")
        self.assertIn("## MODIFIED", delta)
        self.assertIn(f"<!-- base: {base} -->", delta)
        self.assertIn("The API MUST accept a valid password.", delta)
        self.assertIn("#### Scenario: good password", delta)

    def test_remove_writes_reason_placeholder(self):
        self.assert_ok(self.sdd("delta-stub", "c1", "REQ-AUTH-002", "--remove"))
        delta = self.read("changes/c1/specs/auth/auth.md")
        self.assertIn("## REMOVED", delta)
        self.assertIn("Reason:", delta)
        self.assertNotIn("lock the account", delta)

    def test_two_stubs_share_one_section(self):
        self.assert_ok(self.sdd("delta-stub", "c1", "REQ-AUTH-001"))
        self.assert_ok(self.sdd("delta-stub", "c1", "REQ-AUTH-002"))
        delta = self.read("changes/c1/specs/auth/auth.md")
        self.assertEqual(delta.count("## MODIFIED"), 1)
        self.assertIn("REQ-AUTH-001", delta)
        self.assertIn("REQ-AUTH-002", delta)

    def test_rejects_unknown_and_duplicate(self):
        self.assert_fails(self.sdd("delta-stub", "c1", "REQ-AUTH-999"), "not in living specs", code=2)
        self.assert_ok(self.sdd("delta-stub", "c1", "REQ-AUTH-001"))
        self.assert_fails(self.sdd("delta-stub", "c1", "REQ-AUTH-001"), "already present", code=2)


# ------------------------------------------------------------------- check --
class TestCheck(SddCase):
    def setUp(self):
        super().setUp()
        self.living()

    def test_clean_change_passes(self):
        self.added_change()
        code, out = self.sdd("check", "c1")
        self.assertEqual(code, 0, out)
        self.assertIn("OK c1: 1 REQ, 2 tasks, 0 errors", out)

    def test_requirement_without_scenario(self):
        self.new_change()
        self.write("changes/c1/specs/auth/auth.md",
                   "## ADDED\n\n### REQ-AUTH-003: No scenario\nThe API MUST do X.\n")
        self.set_tasks("c1", "- [ ] T1 (test) x — REQ-AUTH-003",
                       "- [ ] T2 (impl) y — REQ-AUTH-003 | blocked-by: T1")
        self.assert_fails(self.sdd("check", "c1"), "no '#### Scenario:'")

    def test_missing_test_and_impl_tasks(self):
        self.added_change()
        self.set_tasks("c1", "- [ ] T1 (chore) housekeeping")
        self.assert_fails(self.sdd("check", "c1"), "REQ-AUTH-003: no (test) task",
                          "REQ-AUTH-003: no (impl) task")

    def test_dangling_references(self):
        self.added_change()
        self.set_tasks("c1",
                       "- [ ] T1 (test) x — REQ-AUTH-003 REQ-AUTH-777",
                       "- [ ] T2 (impl) y — REQ-AUTH-003 ADR-0042 | blocked-by: T9")
        self.assert_fails(self.sdd("check", "c1"), "references unknown REQ-AUTH-777",
                          "blocked-by unknown T9", "ADR-0042 referenced but no file")

    def test_duplicate_task_and_task_without_req(self):
        self.added_change()
        self.set_tasks("c1",
                       "- [ ] T1 (test) x — REQ-AUTH-003",
                       "- [ ] T1 (impl) y — REQ-AUTH-003",
                       "- [ ] T3 (impl) z")
        self.assert_fails(self.sdd("check", "c1"), "duplicate T1", "T3 (impl) references no REQ")

    def test_added_but_already_living(self):
        self.new_change()
        self.write("changes/c1/specs/auth/auth.md", "## ADDED\n\n" + LIVING_AUTH.split("\n\n", 1)[1])
        self.assert_fails(self.sdd("check", "c1"), "ADDED but already exists")

    def test_modified_without_base(self):
        self.new_change()
        block = LIVING_AUTH.split("### REQ-AUTH-002")[0].split("\n", 2)[2]
        self.write("changes/c1/specs/auth/auth.md", "## MODIFIED\n\n" + block)
        self.assert_fails(self.sdd("check", "c1"), "missing <!-- base: -->")

    def test_conflict_when_living_spec_changed_after_stub(self):
        self.new_change()
        self.assert_ok(self.sdd("delta-stub", "c1", "REQ-AUTH-001"))
        self.set_tasks("c1", "- [ ] T1 (test) x — REQ-AUTH-001",
                       "- [ ] T2 (impl) y — REQ-AUTH-001 | blocked-by: T1")
        self.assert_ok(self.sdd("check", "c1"))
        # another change lands first and edits REQ-AUTH-001
        self.write("specs/auth/auth.md", LIVING_AUTH.replace("a valid password", "a valid passphrase"))
        self.assert_fails(self.sdd("check", "c1"), "CONFLICT")

    def test_whitespace_only_edit_is_not_a_conflict(self):
        self.new_change()
        self.assert_ok(self.sdd("delta-stub", "c1", "REQ-AUTH-001"))
        self.set_tasks("c1", "- [ ] T1 (test) x — REQ-AUTH-001",
                       "- [ ] T2 (impl) y — REQ-AUTH-001 | blocked-by: T1")
        self.write("specs/auth/auth.md", LIVING_AUTH.replace("password.\n", "password.   \n", 1))
        self.assert_ok(self.sdd("check", "c1"))

    def test_test_task_on_removed_req(self):
        self.new_change()
        self.assert_ok(self.sdd("delta-stub", "c1", "REQ-AUTH-002", "--remove"))
        self.set_tasks("c1", "- [ ] T1 (test) x — REQ-AUTH-002")
        self.assert_fails(self.sdd("check", "c1"), "tests removed REQ-AUTH-002")

    def test_impl_not_blocked_by_test_is_a_warning(self):
        self.added_change()
        self.set_tasks("c1", "- [ ] T1 (test) x — REQ-AUTH-003", "- [ ] T2 (impl) y — REQ-AUTH-003")
        code, out = self.sdd("check", "c1")
        self.assertEqual(code, 0, out)
        self.assertIn("WARN  T2: impl not blocked-by", out)

    def test_plan_references_are_checked_outside_comments(self):
        self.added_change()
        self.write("changes/c1/plan.md",
                   "# Plan\n<!-- REQ-AUTH-555 in a comment is ignored -->\n"
                   "## Approach\nServes REQ-AUTH-003 and REQ-AUTH-444 per ADR-0009.\n")
        code, out = self.sdd("check", "c1")
        self.assertEqual(code, 1, out)
        self.assertIn("plan.md references unknown REQ-AUTH-444", out)
        self.assertIn("plan.md references unknown ADR-0009", out)
        self.assertNotIn("REQ-AUTH-555", out)

    def test_non_draft_without_tasks(self):
        self.new_change()
        self.write("changes/c1/specs/auth/auth.md", "## ADDED\n\n" + ADDED_003)
        self.assert_ok(self.sdd("set-status", "c1", "approved"))
        self.assert_fails(self.sdd("check", "c1"), "tasks.md has no tasks")

    def test_tests_flag_needs_acceptance_test_and_closed_tasks(self):
        self.added_change()
        self.assert_fails(self.sdd("check", "c1", "--tests"),
                          "REQ-AUTH-003: no acceptance test", "open tasks: T1,T2")
        self.accept_test()
        self.set_tasks("c1", "- [x] T1 (test) x — REQ-AUTH-003",
                       "- [x] T2 (impl) y — REQ-AUTH-003 | blocked-by: T1")
        self.assert_ok(self.sdd("check", "c1", "--tests"))

    def test_fix_path_test_task_on_existing_req_needs_acceptance_test(self):
        self.new_change()
        intent = self.read("changes/c1/intent.md").replace("size: change", "size: fix")
        self.write("changes/c1/intent.md", intent)
        self.set_tasks("c1", "- [x] T1 (test) regression — REQ-AUTH-002",
                       "- [x] T2 (impl) fix — REQ-AUTH-002 | blocked-by: T1")
        code, out = self.sdd("check", "c1")
        self.assertEqual(code, 0, out)
        self.assertNotIn("no spec delta", out)
        self.assert_fails(self.sdd("check", "c1", "--tests"), "REQ-AUTH-002: no acceptance test")
        self.accept_test(req="REQ-AUTH-002")
        self.assert_ok(self.sdd("check", "c1", "--tests"))


# ----------------------------------------------------------------- freeze ---
class TestFreeze(SddCase):
    def setUp(self):
        super().setUp()
        self.living()
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
        self.assertIn("ADR-0001 -> adr/ADR-0001-use-jwt.md", out)
        adr1 = self.read("adr/ADR-0001-use-jwt.md")
        self.assertIn("# ADR-0001: Use JWT", adr1)
        self.assertIn("status: proposed", adr1)

        self.assert_fails(self.sdd("adr-new", "X", "--supersedes", "ADR-0009"), "does not exist", code=2)

        self.assert_ok(self.sdd("adr-accept", "ADR-0001"))
        self.assertIn("status: accepted", self.read("adr/ADR-0001-use-jwt.md"))

        code, out = self.sdd("adr-new", "Use PASETO", "--supersedes", "ADR-0001")
        self.assertIn("ADR-0002", out)
        self.assert_ok(self.sdd("adr-accept", "ADR-0002"))
        old = self.read("adr/ADR-0001-use-jwt.md")
        self.assertIn("status: superseded", old)
        self.assertIn("superseded_by: ADR-0002", old)

    def test_accept_is_idempotent_and_checks_status(self):
        self.sdd("adr-new", "A")
        self.assert_ok(self.sdd("adr-accept", "ADR-0001"))
        self.assert_ok(self.sdd("adr-accept", "ADR-0001"))
        self.assert_fails(self.sdd("adr-accept", "ADR-0005"), "ADR-0005 does not exist")
        f = self.root / "adr/ADR-0001-a.md"
        f.write_text(f.read_text().replace("status: accepted", "status: deprecated"))
        self.assert_fails(self.sdd("adr-accept", "ADR-0001"), "expected proposed")

    def test_check_rejects_superseded_reference(self):
        self.living()
        self.sdd("adr-new", "Old")
        self.sdd("adr-accept", "ADR-0001")
        self.sdd("adr-new", "New", "--supersedes", "ADR-0001")
        self.sdd("adr-accept", "ADR-0002")
        self.added_change()
        self.set_tasks("c1", "- [ ] T1 (test) x — REQ-AUTH-003",
                       "- [ ] T2 (impl) y — REQ-AUTH-003 ADR-0001 | blocked-by: T1")
        self.assert_fails(self.sdd("check", "c1"), "ADR-0001 is superseded")


# ----------------------------------------------------------------- context --
class TestContext(SddCase):
    def setUp(self):
        super().setUp()
        self.living()
        self.sdd("adr-new", "Token", "format")
        f = self.root / "adr/ADR-0001-token-format.md"
        f.write_text(f.read_text().replace(
            "## Decision\n", "## Decision\nTokens are opaque 32-byte strings.\n"))
        self.added_change()
        self.set_tasks("c1", "- [ ] T1 (test) x — REQ-AUTH-003",
                       "- [ ] T2 (impl) y — REQ-AUTH-003 REQ-AUTH-001 ADR-0001 | blocked-by: T1")
        self.write("changes/c1/plan.md", dedent("""
            ---
            change: c1
            ---

            # Plan

            ## Approach
            SECRET-APPROACH serves REQ-AUTH-003.

            ## Contracts
            GET /v1/me -> 401 {"error": "token_expired"}

            ## Components
            src/mw.py -> REQ-AUTH-003
            """))
        self.accept_test()

    def test_test_task_gets_contracts_only(self):
        code, out = self.sdd("context", "c1", "T1")
        self.assertEqual(code, 0, out)
        self.assertIn("<!-- ADDED in this change -->", out)
        self.assertIn("### REQ-AUTH-003", out)
        self.assertIn("## Contracts", out)
        self.assertIn("token_expired", out)
        self.assertNotIn("SECRET-APPROACH", out)
        self.assertNotIn("Frozen acceptance tests", out)

    def test_impl_task_gets_reqs_decision_and_frozen_paths(self):
        code, out = self.sdd("context", "c1", "T2")
        self.assertEqual(code, 0, out)
        self.assertIn("depends on: - [ ] T1", out)
        self.assertIn("<!-- unchanged, specs/auth -->", out)
        self.assertIn("### REQ-AUTH-001", out)
        self.assertNotIn("REQ-AUTH-002", out)
        self.assertIn("Tokens are opaque 32-byte strings.", out)
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
        self.living()
        self.new_change()
        self.assert_ok(self.sdd("delta-stub", "c1", "REQ-AUTH-001"))
        self.assert_ok(self.sdd("delta-stub", "c1", "REQ-AUTH-002", "--remove"))
        f = self.root / "changes/c1/specs/auth/auth.md"
        text = f.read_text().replace("a valid password", "a valid passphrase")
        f.write_text(text.replace("## ADDED\n", "## ADDED\n\n" + ADDED_003, 1))
        self.set_tasks("c1",
                       "- [x] T1 (test) x — REQ-AUTH-001 REQ-AUTH-003",
                       "- [x] T2 (impl) y — REQ-AUTH-001 REQ-AUTH-003 | blocked-by: T1")
        self.archive = f"changes/archive/{_dt.date.today().isoformat()}-c1"

    def test_requires_verified(self):
        self.assert_fails(self.sdd("sync", "c1"), "sync requires verified")

    def test_dry_run_writes_nothing(self):
        self.sdd("set-status", "c1", "verified")
        before = self.read("specs/auth/auth.md")
        code, out = self.sdd("sync", "c1", "--dry-run")
        self.assertEqual(code, 0, out)
        for line in ("MODIFIED REQ-AUTH-001", "REMOVED  REQ-AUTH-002", "ADDED    REQ-AUTH-003",
                     "DRY-RUN ok, 3 change(s)"):
            self.assertIn(line, out)
        self.assertEqual(self.read("specs/auth/auth.md"), before)
        self.assertTrue((self.root / "changes/c1").exists())

    def test_sync_merges_accepts_adrs_and_archives(self):
        self.sdd("adr-new", "Token", "format")
        intent = self.read("changes/c1/intent.md").replace("adrs: []", "adrs: [ADR-0001]")
        self.write("changes/c1/intent.md", intent)
        self.sdd("set-status", "c1", "verified")
        code, out = self.sdd("sync", "c1")
        self.assertEqual(code, 0, out)

        spec = self.read("specs/auth/auth.md")
        self.assertIn("a valid passphrase", spec)
        self.assertNotIn("a valid password", spec)
        self.assertNotIn("REQ-AUTH-002", spec)
        self.assertNotIn("<!-- base:", spec)
        self.assertLess(spec.index("REQ-AUTH-001"), spec.index("REQ-AUTH-003"))
        self.assertIn("type: spec\ntitle: auth\ncapability: auth\n", spec)
        self.assertIn("\n# auth\n", spec)
        self.assertNotIn("GIVEN <", spec)  # delta template guidance stays out

        self.assertIn("status: accepted", self.read("adr/ADR-0001-token-format.md"))
        self.assertFalse((self.root / "changes/c1").exists())
        self.assertIn("status: archived", self.read(f"{self.archive}/intent.md"))
        self.assertEqual(json.loads(self.sdd("status", "--json")[1])["archived"], 1)

    def test_sync_twice_is_impossible(self):
        self.sdd("set-status", "c1", "verified")
        self.assert_ok(self.sdd("sync", "c1"))
        self.assert_fails(self.sdd("sync", "c1"), "no change 'c1'", code=2)

    def test_conflict_blocks_sync_and_writes_nothing(self):
        self.sdd("set-status", "c1", "verified")
        changed = LIVING_AUTH.replace("after 5 failures", "after 3 failures")
        self.write("specs/auth/auth.md", changed)
        self.assert_fails(self.sdd("sync", "c1"), "CONFLICT", "fix errors before sync")
        self.assertEqual(self.read("specs/auth/auth.md"), changed)
        self.assertTrue((self.root / "changes/c1/intent.md").exists())

    def test_force_skips_status_but_not_errors(self):
        self.write("specs/auth/auth.md", LIVING_AUTH.replace("after 5", "after 3"))
        self.assert_fails(self.sdd("sync", "c1", "--force"), "CONFLICT")

    def test_bad_adr_blocks_sync_before_writing(self):
        intent = self.read("changes/c1/intent.md").replace("adrs: []", "adrs: [ADR-0007]")
        self.write("changes/c1/intent.md", intent)
        self.sdd("set-status", "c1", "verified")
        before = self.read("specs/auth/auth.md")
        self.assert_fails(self.sdd("sync", "c1"), "ADR-0007")
        self.assertEqual(self.read("specs/auth/auth.md"), before)

    def test_living_spec_is_ordered_by_req_id(self):
        self.new_change("c2")
        self.write("changes/c2/specs/auth/auth.md", "## ADDED\n\n"
                   + ADDED_003.replace("REQ-AUTH-003", "REQ-AUTH-009") + "\n" + ADDED_003)
        self.set_tasks("c2", "- [x] T1 (test) x — REQ-AUTH-003 REQ-AUTH-009",
                       "- [x] T2 (impl) y — REQ-AUTH-003 REQ-AUTH-009 | blocked-by: T1")
        self.sdd("set-status", "c2", "verified")
        self.assert_ok(self.sdd("sync", "c2"))
        ids = re.findall(r"^### (REQ-AUTH-\d+)", self.read("specs/auth/auth.md"), re.M)
        self.assertEqual(ids, ["REQ-AUTH-001", "REQ-AUTH-002", "REQ-AUTH-003", "REQ-AUTH-009"])

    def test_new_capability_creates_spec(self):
        self.new_change("c2")
        self.write("changes/c2/specs/billing/billing.md",
                   "## ADDED\n\n### REQ-BILL-001: Invoice\nThe API MUST invoice.\n\n"
                   "#### Scenario: monthly\n- GIVEN a plan\n- WHEN month ends\n- THEN an invoice exists\n")
        self.set_tasks("c2", "- [x] T1 (test) x — REQ-BILL-001",
                       "- [x] T2 (impl) y — REQ-BILL-001 | blocked-by: T1")
        self.sdd("set-status", "c2", "verified")
        self.assert_ok(self.sdd("sync", "c2"))
        spec = self.read("specs/billing/billing.md")
        self.assertIn("type: spec\ntitle: Billing\ncapability: billing\n", spec)
        self.assertIn("\n# Billing\n", spec)
        self.assertIn("### REQ-BILL-001: Invoice", spec)


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
        put(wt / "changes/c1/specs/auth/auth.md", "# Delta: auth\n")
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
        put(wt / f"changes/{name}/specs/auth/auth.md", "# Delta: auth\n\n## ADDED\n\n" + ADDED_003)
        (wt / f"changes/{name}/tasks.md").write_text(
            "- [x] T1 (test) t — REQ-AUTH-003\n- [x] T2 (impl) i — REQ-AUTH-003 | blocked-by: T1\n")
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
        put(d / "changes/dep/specs/auth/auth.md", "# Delta: auth\n\n## ADDED\n\n" + ADDED_003)
        (d / "changes/dep/tasks.md").write_text(
            "- [x] T1 (test) t — REQ-AUTH-003\n- [x] T2 (impl) i — REQ-AUTH-003 | blocked-by: T1\n")
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
        put(wt / "changes/c1/specs/auth/auth.md", "# Delta: auth\n\n## ADDED\n\n" + ADDED_003)
        (wt / "changes/c1/tasks.md").write_text(
            "- [x] T1 (test) t — REQ-AUTH-003\n- [x] T2 (impl) i — REQ-AUTH-003 | blocked-by: T1\n")
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


INV_LOG = """\
### INV-SEC-001: Secrets are never logged
The system MUST NOT write a password or token to any log.

#### Check: test_no_secret_in_logs greps the captured log of the login flow
"""


class TestBundle(SddCase):
    def test_fresh_init_is_a_valid_bundle(self):
        self.assert_ok(self.sdd("bundle", "specs"))
        self.assertIn('okf_version: "0.2"', self.read("specs/index.md"))
        self.assertIn("type: log", self.read("specs/log.md"))

    def test_legacy_spec_md_is_migrated_and_second_run_is_clean(self):
        self.write("specs/auth/spec.md", LIVING_AUTH)
        self.assert_fails(self.sdd("bundle", "specs"), "legacy layout", "[fixable]")
        code, out = self.sdd("bundle", "specs", "--fix")
        self.assertEqual(code, 0, out)
        self.assertIn("FIXED", out)
        self.assertFalse((self.root / "specs/auth/spec.md").exists())
        concept = self.read("specs/auth/auth.md")
        self.assertIn("type: spec\ntitle: auth\ncapability: auth\nsources: []", concept)
        self.assertIn("REQ-AUTH-001, REQ-AUTH-002", self.read("specs/auth/index.md"))
        self.assertIn("[auth/](auth/index.md)", self.read("specs/index.md"))
        code, out = self.sdd("bundle", "specs", "--fix")
        self.assertEqual(code, 0, out)
        self.assertNotIn("FIXED", out)

    def test_stale_index_and_unsorted_blocks_are_fixed(self):
        self.living()
        a, b = LIVING_AUTH.split("\n\n### ")[1:]
        self.write("specs/auth/auth.md", self.read("specs/auth/auth.md").split("### ")[0]
                   + "### " + b + "\n### " + a)
        self.write("specs/auth/index.md", "stale\n")
        self.assert_fails(self.sdd("bundle", "specs"), "blocks not sorted", "index.md: stale")
        self.assert_ok(self.sdd("bundle", "specs", "--fix"))
        ids = re.findall(r"^### (REQ-AUTH-\d+)", self.read("specs/auth/auth.md"), re.M)
        self.assertEqual(ids, ["REQ-AUTH-001", "REQ-AUTH-002"])
        self.assert_ok(self.sdd("bundle", "specs"))

    def test_missing_source_is_a_warning_fix_drops_it(self):
        self.living()
        self.write("src/a.py", "x = 1\n")
        f = self.root / "specs/auth/auth.md"
        f.write_text(f.read_text().replace("sources: []", "sources: [src/a.py, src/gone.py]"))
        self.assert_ok(self.sdd("bundle", "specs"))
        code, out = self.sdd("bundle", "specs")
        self.assertIn("source 'src/gone.py' not found", out)
        self.assert_ok(self.sdd("bundle", "specs", "--fix"))
        self.assertIn("sources: [src/a.py]", f.read_text())

    def test_too_many_blocks_warns_and_is_not_fixed(self):
        self.living()
        self.write(".claude/sdd.json", json.dumps({"concept_max_blocks": 1}))
        code, out = self.sdd("bundle", "specs", "--fix")
        self.assertEqual(code, 0, out)
        self.assertIn("2 blocks > 1", out)

    def test_empty_concept_is_deleted(self):
        self.living()
        self.write("specs/auth/old.md", "# old\n")
        self.assert_fails(self.sdd("bundle", "specs"), "no requirement blocks")
        self.assert_ok(self.sdd("bundle", "specs", "--fix"))
        self.assertFalse((self.root / "specs/auth/old.md").exists())

    def test_unfixable_problems_stay_errors(self):
        self.living()
        self.write("specs/auth/dup.md", "### REQ-AUTH-001: Again\nx\n")
        self.write("specs/auth/inv.md", INV_LOG)
        self.write("specs/loose/deep/x.md", LIVING_AUTH.replace("AUTH", "LOOSE"))
        code, out = self.sdd("bundle", "specs", "--fix")
        self.assertEqual(code, 1, out)
        self.assertIn("defined in both", out)
        self.assertIn("INV in the spec tree", out)
        self.assertIn("concepts live in specs/<capability>/", out)

    def test_change_bundle_legacy_delta_front_matter_and_index(self):
        self.living()
        self.new_change()
        self.write("changes/c1/specs/auth.md", "# Delta: auth\n\n## ADDED\n\n" + ADDED_003)
        code, out = self.sdd("bundle", "c1")
        self.assertEqual(code, 0, out)
        self.assertIn("legacy layout", out)
        self.assert_ok(self.sdd("bundle", "c1", "--fix"))
        delta = self.read("changes/c1/specs/auth/auth.md")
        self.assertIn("type: spec-delta\ntarget: specs/auth/auth.md", delta)
        self.assertFalse((self.root / "changes/c1/specs/auth.md").exists())
        index = self.read("changes/c1/index.md")
        self.assertIn('okf_version: "0.2"', index)
        self.assertIn("## Spec delta", index)
        self.assertIn("ADDED REQ-AUTH-003", index)
        code, out = self.sdd("bundle", "c1", "--fix")
        self.assertNotIn("FIXED", out)
        self.assertNotIn("WARN", out)

    def test_change_bundle_rejects_misplaced_delta(self):
        self.new_change()
        self.write("changes/c1/specs/invariants/x.md", "## ADDED\n")
        self.assert_fails(self.sdd("bundle", "c1"), "deltas live in specs/<capability>/")

    def test_unknown_change(self):
        self.assert_fails(self.sdd("bundle", "nope"), "no change 'nope'", code=2)


class TestInvariants(SddCase):
    def inv_change(self, check: bool = True) -> str:
        self.new_change()
        self.assert_ok(self.sdd("delta-new", "c1", "invariants/security/logging"))
        f = self.root / "changes/c1/specs/invariants/security/logging.md"
        block = INV_LOG if check else INV_LOG.split("#### Check")[0]
        f.write_text(f.read_text().replace("## ADDED\n", "## ADDED\n\n" + block, 1))
        self.set_tasks("c1", "- [ ] T1 (test) No secret in logs — INV-SEC-001")
        return "c1"

    def test_delta_new_places_invariant_deltas_in_category_dirs(self):
        self.new_change()
        code, out = self.sdd("delta-new", "c1", "invariants/security")
        self.assertIn("created changes/c1/specs/invariants/security/security.md", out)
        self.assertIn("type: invariant-delta\ntarget: specs/invariants/security/security.md",
                      self.read("changes/c1/specs/invariants/security/security.md"))
        self.assert_ok(self.sdd("delta-new", "c1", "auth/tokens"))
        self.assertTrue((self.root / "changes/c1/specs/auth/tokens.md").exists())
        self.assert_fails(self.sdd("delta-new", "c1", "invariants"), "target must be", code=2)
        self.assert_fails(self.sdd("delta-new", "c1", "Bad Name"), "target must be", code=2)

    def test_invariant_needs_check_and_test_task_but_no_impl_task(self):
        self.inv_change()
        self.assert_ok(self.sdd("check", "c1"))
        self.set_tasks("c1", "- [ ] T1 (chore) nothing")
        self.assert_fails(self.sdd("check", "c1"), "INV-SEC-001: no (test) task")

    def test_invariant_without_check_fails(self):
        self.inv_change(check=False)
        self.assert_fails(self.sdd("check", "c1"), "no '#### Check:'")

    def test_inv_in_spec_tree_and_req_in_invariant_tree_fail(self):
        self.new_change()
        self.write("changes/c1/specs/auth/auth.md", "## ADDED\n\n" + INV_LOG)
        self.write("changes/c1/specs/invariants/security/s.md", "## ADDED\n\n" + ADDED_003)
        self.set_tasks("c1", "- [ ] T1 (test) t — INV-SEC-001 REQ-AUTH-003")
        self.assert_fails(self.sdd("check", "c1"), "INV in the wrong tree", "REQ in the wrong tree")

    def test_sync_writes_invariant_concept_indexes_and_log(self):
        self.inv_change()
        self.set_tasks("c1", "- [x] T1 (test) No secret in logs — INV-SEC-001")
        self.sdd("set-status", "c1", "verified")
        self.assert_ok(self.sdd("sync", "c1"))
        concept = self.read("specs/invariants/security/logging.md")
        self.assertIn("type: invariant\ntitle: Logging\ncategory: security", concept)
        self.assertIn("INV-SEC-001", self.read("specs/invariants/security/index.md"))
        self.assertIn("[security/](security/index.md)", self.read("specs/invariants/index.md"))
        self.assertIn("[invariants/](invariants/index.md)", self.read("specs/index.md"))
        self.assertRegex(self.read("specs/log.md"), r"- \d{4}-\d{2}-\d{2} c1: ADDED INV-SEC-001")
        self.assert_ok(self.sdd("bundle", "specs"))

    def test_impl_context_lists_invariants_in_force(self):
        self.write("specs/invariants/security/logging.md", INV_LOG)
        self.assert_ok(self.sdd("bundle", "specs", "--fix"))
        self.added_change()
        code, out = self.sdd("context", "c1", "T2")
        self.assertIn("## Invariants in force", out)
        self.assertIn("- INV-SEC-001: Secrets are never logged", out)
        code, out = self.sdd("context", "c1", "T1")
        self.assertNotIn("Invariants in force", out)


class TestConceptSync(SddCase):
    def test_modified_req_in_another_concept_is_moved(self):
        self.living()
        self.new_change()
        self.assert_ok(self.sdd("delta-new", "c1", "auth/lockout"))
        self.assert_ok(self.sdd("delta-stub", "c1", "REQ-AUTH-002"))
        self.assertTrue((self.root / "changes/c1/specs/auth/auth.md").exists())
        (self.root / "changes/c1/specs/auth/auth.md").rename(self.root / "changes/c1/specs/auth/lockout.md")
        self.set_tasks("c1", "- [x] T1 (test) x — REQ-AUTH-002", "- [x] T2 (impl) y — REQ-AUTH-002 | blocked-by: T1")
        self.sdd("set-status", "c1", "verified")
        code, out = self.sdd("sync", "c1")
        self.assertEqual(code, 0, out)
        self.assertIn("MOVED", out)
        self.assertNotIn("REQ-AUTH-002", self.read("specs/auth/auth.md"))
        self.assertIn("REQ-AUTH-002", self.read("specs/auth/lockout.md"))
        self.assertIn("REQ-AUTH-002", self.read("specs/auth/index.md"))
        self.assert_ok(self.sdd("bundle", "specs"))

    def test_removing_the_last_req_deletes_the_concept(self):
        self.write("specs/auth/auth.md", LIVING_AUTH.split("### REQ-AUTH-002")[0])
        self.assert_ok(self.sdd("bundle", "specs", "--fix"))
        self.new_change()
        self.assert_ok(self.sdd("delta-stub", "c1", "REQ-AUTH-001", "--remove"))
        self.set_tasks("c1", "- [x] T1 (chore) drop the endpoint")
        self.sdd("set-status", "c1", "verified")
        self.assert_ok(self.sdd("sync", "c1"))
        self.assertFalse((self.root / "specs/auth").exists())
        self.assertNotIn("auth", self.read("specs/index.md").split("# Specs")[1])
        self.assert_ok(self.sdd("bundle", "specs"))

    def test_sync_refuses_while_specs_bundle_is_invalid(self):
        self.added_change()
        self.write("specs/auth/spec.md", LIVING_AUTH)
        self.sdd("set-status", "c1", "verified")
        self.assert_fails(self.sdd("sync", "c1"), "specs bundle:", "bundle specs --fix")

    def test_delta_sources_are_merged_into_the_concept(self):
        self.write("src/a.py", "x\n")
        self.write("src/b.py", "x\n")
        self.living()
        f = self.root / "specs/auth/auth.md"
        f.write_text(f.read_text().replace("sources: []", "sources: [src/a.py]"))
        self.added_change()
        self.assert_ok(self.sdd("bundle", "c1", "--fix"))
        d = self.root / "changes/c1/specs/auth/auth.md"
        d.write_text(d.read_text().replace("sources: []", "sources: [src/b.py]"))
        self.sdd("set-status", "c1", "verified")
        self.assert_ok(self.sdd("sync", "c1"))
        self.assertIn("sources: [src/a.py, src/b.py]", f.read_text())


if __name__ == "__main__":
    unittest.main()
