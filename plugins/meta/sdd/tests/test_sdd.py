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
        self.write("specs/auth/spec.md", LIVING_AUTH)

    def new_change(self, name: str = "c1") -> str:
        code, out = self.sdd("new", name)
        self.assertEqual(code, 0, out)
        return name

    def added_change(self, name: str = "c1") -> str:
        """A clean change adding REQ-AUTH-003 with a test and an impl task."""
        self.new_change(name)
        self.write(f"changes/{name}/specs/auth.md", "# Delta: auth\n\n## ADDED\n\n" + ADDED_003)
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
        self.assertIn("created changes/c1/specs/auth.md", out)
        delta = self.read("changes/c1/specs/auth.md")
        self.assertTrue(delta.startswith("# Delta: auth\n"))
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
        delta = self.read("changes/c1/specs/auth.md")
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
        delta = self.read("changes/c1/specs/auth.md")
        self.assertTrue(delta.startswith("# Delta: auth\n"))
        self.assertIn("## ADDED", delta)
        self.assertEqual(delta.count("## MODIFIED"), 1)

    def test_modified_copies_block_with_base_hash(self):
        code, out = self.sdd("delta-stub", "c1", "REQ-AUTH-001")
        self.assertEqual(code, 0, out)
        base = re.search(r"base=([0-9a-f]{8})", out).group(1)
        delta = self.read("changes/c1/specs/auth.md")
        self.assertIn("## MODIFIED", delta)
        self.assertIn(f"<!-- base: {base} -->", delta)
        self.assertIn("The API MUST accept a valid password.", delta)
        self.assertIn("#### Scenario: good password", delta)

    def test_remove_writes_reason_placeholder(self):
        self.assert_ok(self.sdd("delta-stub", "c1", "REQ-AUTH-002", "--remove"))
        delta = self.read("changes/c1/specs/auth.md")
        self.assertIn("## REMOVED", delta)
        self.assertIn("Reason:", delta)
        self.assertNotIn("lock the account", delta)

    def test_two_stubs_share_one_section(self):
        self.assert_ok(self.sdd("delta-stub", "c1", "REQ-AUTH-001"))
        self.assert_ok(self.sdd("delta-stub", "c1", "REQ-AUTH-002"))
        delta = self.read("changes/c1/specs/auth.md")
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
        self.write("changes/c1/specs/auth.md",
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
        self.write("changes/c1/specs/auth.md", "## ADDED\n\n" + LIVING_AUTH.split("\n\n", 1)[1])
        self.assert_fails(self.sdd("check", "c1"), "ADDED but already exists")

    def test_modified_without_base(self):
        self.new_change()
        block = LIVING_AUTH.split("### REQ-AUTH-002")[0].split("\n", 2)[2]
        self.write("changes/c1/specs/auth.md", "## MODIFIED\n\n" + block)
        self.assert_fails(self.sdd("check", "c1"), "missing <!-- base: -->")

    def test_conflict_when_living_spec_changed_after_stub(self):
        self.new_change()
        self.assert_ok(self.sdd("delta-stub", "c1", "REQ-AUTH-001"))
        self.set_tasks("c1", "- [ ] T1 (test) x — REQ-AUTH-001",
                       "- [ ] T2 (impl) y — REQ-AUTH-001 | blocked-by: T1")
        self.assert_ok(self.sdd("check", "c1"))
        # another change lands first and edits REQ-AUTH-001
        self.write("specs/auth/spec.md", LIVING_AUTH.replace("a valid password", "a valid passphrase"))
        self.assert_fails(self.sdd("check", "c1"), "CONFLICT")

    def test_whitespace_only_edit_is_not_a_conflict(self):
        self.new_change()
        self.assert_ok(self.sdd("delta-stub", "c1", "REQ-AUTH-001"))
        self.set_tasks("c1", "- [ ] T1 (test) x — REQ-AUTH-001",
                       "- [ ] T2 (impl) y — REQ-AUTH-001 | blocked-by: T1")
        self.write("specs/auth/spec.md", LIVING_AUTH.replace("password.\n", "password.   \n", 1))
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
        self.write("changes/c1/specs/auth.md", "## ADDED\n\n" + ADDED_003)
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
        f = self.root / "changes/c1/specs/auth.md"
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
        before = self.read("specs/auth/spec.md")
        code, out = self.sdd("sync", "c1", "--dry-run")
        self.assertEqual(code, 0, out)
        for line in ("MODIFIED REQ-AUTH-001", "REMOVED  REQ-AUTH-002", "ADDED    REQ-AUTH-003",
                     "DRY-RUN ok, 3 change(s)"):
            self.assertIn(line, out)
        self.assertEqual(self.read("specs/auth/spec.md"), before)
        self.assertTrue((self.root / "changes/c1").exists())

    def test_sync_merges_accepts_adrs_and_archives(self):
        self.sdd("adr-new", "Token", "format")
        intent = self.read("changes/c1/intent.md").replace("adrs: []", "adrs: [ADR-0001]")
        self.write("changes/c1/intent.md", intent)
        self.sdd("set-status", "c1", "verified")
        code, out = self.sdd("sync", "c1")
        self.assertEqual(code, 0, out)

        spec = self.read("specs/auth/spec.md")
        self.assertIn("a valid passphrase", spec)
        self.assertNotIn("a valid password", spec)
        self.assertNotIn("REQ-AUTH-002", spec)
        self.assertNotIn("<!-- base:", spec)
        self.assertLess(spec.index("REQ-AUTH-001"), spec.index("REQ-AUTH-003"))
        self.assertTrue(spec.startswith("# auth\n"))
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
        self.write("specs/auth/spec.md", changed)
        self.assert_fails(self.sdd("sync", "c1"), "CONFLICT", "fix errors before sync")
        self.assertEqual(self.read("specs/auth/spec.md"), changed)
        self.assertTrue((self.root / "changes/c1/intent.md").exists())

    def test_force_skips_status_but_not_errors(self):
        self.write("specs/auth/spec.md", LIVING_AUTH.replace("after 5", "after 3"))
        self.assert_fails(self.sdd("sync", "c1", "--force"), "CONFLICT")

    def test_bad_adr_blocks_sync_before_writing(self):
        intent = self.read("changes/c1/intent.md").replace("adrs: []", "adrs: [ADR-0007]")
        self.write("changes/c1/intent.md", intent)
        self.sdd("set-status", "c1", "verified")
        before = self.read("specs/auth/spec.md")
        self.assert_fails(self.sdd("sync", "c1"), "ADR-0007")
        self.assertEqual(self.read("specs/auth/spec.md"), before)

    def test_living_spec_is_ordered_by_req_id(self):
        self.new_change("c2")
        self.write("changes/c2/specs/auth.md", "## ADDED\n\n"
                   + ADDED_003.replace("REQ-AUTH-003", "REQ-AUTH-009") + "\n" + ADDED_003)
        self.set_tasks("c2", "- [x] T1 (test) x — REQ-AUTH-003 REQ-AUTH-009",
                       "- [x] T2 (impl) y — REQ-AUTH-003 REQ-AUTH-009 | blocked-by: T1")
        self.sdd("set-status", "c2", "verified")
        self.assert_ok(self.sdd("sync", "c2"))
        ids = re.findall(r"^### (REQ-AUTH-\d+)", self.read("specs/auth/spec.md"), re.M)
        self.assertEqual(ids, ["REQ-AUTH-001", "REQ-AUTH-002", "REQ-AUTH-003", "REQ-AUTH-009"])

    def test_new_capability_creates_spec(self):
        self.new_change("c2")
        self.write("changes/c2/specs/billing.md",
                   "## ADDED\n\n### REQ-BILL-001: Invoice\nThe API MUST invoice.\n\n"
                   "#### Scenario: monthly\n- GIVEN a plan\n- WHEN month ends\n- THEN an invoice exists\n")
        self.set_tasks("c2", "- [x] T1 (test) x — REQ-BILL-001",
                       "- [x] T2 (impl) y — REQ-BILL-001 | blocked-by: T1")
        self.sdd("set-status", "c2", "verified")
        self.assert_ok(self.sdd("sync", "c2"))
        spec = self.read("specs/billing/spec.md")
        self.assertTrue(spec.startswith("# billing\n"))
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
        (wt / "changes/c1/specs/auth.md").write_text("# Delta: auth\n")
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
        (wt / f"changes/{name}/specs/auth.md").write_text("# Delta: auth\n\n## ADDED\n\n" + ADDED_003)
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
        self.assertIn("-", self.sdd("requires", "c1", cwd=wt)[1])
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
        (wt / "changes/c1/specs/auth.md").write_text("# Delta: auth\n\n## ADDED\n\n" + ADDED_003)
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


if __name__ == "__main__":
    unittest.main()
