"""Tests for agent_company.py. Standard library only: python3 -m unittest discover -s tests"""
import io
import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from contextlib import redirect_stdout
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import agent_company as ac  # noqa: E402

GOOD = """# 001: Add rate limiting

Owner's words: "Protect the API before launch"
Branch: `feat/rate-limit`, in its own worktree

## Steps
1. Failing tests first.
3. Tests to run: rate-limit unit tests.

## Stop point
Upload, open a pull request. Don't merge.
"""


def quiet(fn, *a):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = fn(*a)
    return rc, buf.getvalue()


class InitCheckStatus(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_init_creates_layout_and_never_overwrites(self):
        rc, out = quiet(ac.cmd_init, str(self.repo))
        self.assertEqual(rc, 0)
        ops = self.repo / "docs" / "ops"
        for d in ("inbox", "done", "outbox", "templates"):
            self.assertTrue((ops / d).is_dir(), d)
        (ops / "ROLES.md").write_text("mine", encoding="utf-8")
        rc, out = quiet(ac.cmd_init, str(self.repo))
        self.assertIn("nothing overwritten", out)
        self.assertEqual((ops / "ROLES.md").read_text(encoding="utf-8"), "mine")

    def test_init_refuses_missing_folder(self):
        rc, _ = quiet(ac.cmd_init, str(self.repo / "nope"))
        self.assertEqual(rc, 1)

    def test_check_accepts_a_complete_instruction(self):
        self.assertEqual(ac.check_text("001_add-rate-limiting.md", GOOD), [])

    def test_check_refusals(self):
        cases = {
            "missing the owner's words": GOOD.replace("Owner's words", "Note"),
            "missing a branch": GOOD.replace("Branch: `feat/rate-limit`", "Somewhere"),
            "missing a stop point that says don't merge": GOOD.replace("Don't merge.", "Done."),
            "builds straight on a protected branch": GOOD.replace("feat/rate-limit", "main"),
        }
        for want, text in cases.items():
            with self.subTest(want=want):
                self.assertIn(want, ac.check_text("001_x.md", text))
        self.assertIn("name must be NNN_short-name.md", ac.check_text("Rate Limit.md", GOOD))

    def test_check_command_exit_codes(self):
        quiet(ac.cmd_init, str(self.repo))
        inbox = self.repo / "docs" / "ops" / "inbox"
        (inbox / "001_good.md").write_text(GOOD, encoding="utf-8")
        self.assertEqual(quiet(ac.cmd_check, str(self.repo))[0], 0)
        (inbox / "002_bad.md").write_text("no rules here", encoding="utf-8")
        rc, out = quiet(ac.cmd_check, str(self.repo))
        self.assertEqual(rc, 1)
        self.assertIn("002_bad.md: ", out)

    def test_status_lists_pending_and_done(self):
        quiet(ac.cmd_init, str(self.repo))
        ops = self.repo / "docs" / "ops"
        (ops / "inbox" / "001_a.md").write_text(GOOD, encoding="utf-8")
        (ops / "done" / "000_b.md").write_text(GOOD, encoding="utf-8")
        rc, out = quiet(ac.cmd_status, str(self.repo))
        self.assertIn("pending (1): 001_a.md", out)
        self.assertIn("done    (1): 000_b.md", out)

    def test_start_prints_without_running(self):
        rc, out = quiet(ac.cmd_start, str(self.repo), "claude", False)
        self.assertEqual(rc, 0)
        self.assertIn("run exactly one coordinator", out)
        rc, out = quiet(ac.cmd_start, str(self.repo), "cursor", False)
        self.assertIn("paste", out)


class Deploy(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        quiet(ac.cmd_init, str(self.repo))
        self.ops = self.repo / "docs" / "ops"

    def tearDown(self):
        self.tmp.cleanup()

    def test_writes_allowed_names_only(self):
        r = ac.deploy_files(self.ops, [
            ["ROLES.md", "roles"], ["inbox/001_add-rate-limiting.md", GOOD], ["guild/brannoc-forgehand.md", "# sheet"],
            ["../escape.md", "x"], ["inbox/../../x.md", "x"], ["/etc/passwd", "x"], ["guild/Bad Name.md", "x"], ["notes.txt", "x"],
        ], None)
        self.assertEqual(sorted(r["written"]), ["ROLES.md", "guild/brannoc-forgehand.md", "inbox/001_add-rate-limiting.md"])
        self.assertEqual(len(r["refused"]), 5)
        self.assertFalse((self.repo / "docs" / "escape.md").exists())

    def test_never_overwrites_an_instruction(self):
        ac.deploy_files(self.ops, [["inbox/001_add-rate-limiting.md", GOOD]], None)
        r = ac.deploy_files(self.ops, [["inbox/001_add-rate-limiting.md", GOOD + "\nchanged"]], None)
        self.assertEqual(r["kept"], ["inbox/001_add-rate-limiting.md"])
        self.assertNotIn("changed", (self.ops / "inbox" / "001_add-rate-limiting.md").read_text(encoding="utf-8"))

    def test_refuses_an_incomplete_instruction(self):
        r = ac.deploy_files(self.ops, [["inbox/002_bad.md", "Branch: `main`"]], None)
        self.assertEqual(r["written"], [])
        self.assertTrue(r["refused"][0].startswith("inbox/002_bad.md"))

    def test_guild_sheets_update_and_guild_saved(self):
        ac.deploy_files(self.ops, [["guild/nyx.md", "level 1"]], None, {"heroes": {}})
        ac.deploy_files(self.ops, [["guild/nyx.md", "level 2"]], None, {"heroes": {"h1": {}}})
        self.assertEqual((self.ops / "guild" / "nyx.md").read_text(encoding="utf-8"), "level 2")
        self.assertEqual(json.loads((self.ops / "guild" / "guild.json").read_text(encoding="utf-8")), {"heroes": {"h1": {}}})

    def test_rejects_malformed_items_and_huge_files(self):
        r = ac.deploy_files(self.ops, [["ROLES.md"], "x", ["ROLES.md", "a" * 100_001]], None)
        self.assertEqual(r["written"], [])
        self.assertEqual(len(r["refused"]), 3)


class Server(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        repo = Path(cls.tmp.name)
        quiet(ac.cmd_init, str(repo))
        cls.ops = repo / "docs" / "ops"
        cls.token = "t0ken"
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), ac.make_handler(cls.ops, cls.token))
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.tmp.cleanup()

    def get(self, path):
        with urllib.request.urlopen(self.base + path) as r:
            return r.status, r.read().decode()

    def post(self, path, body, ctype="application/json"):
        req = urllib.request.Request(self.base + path, data=json.dumps(body).encode(), method="POST", headers={"Content-Type": ctype})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, None

    def test_pages_are_served(self):
        self.assertIn("Agent Company Command", self.get("/")[1])
        page = self.get("/guild")[1]
        self.assertIn("Agent Company Guild", page)
        self.assertTrue(page.lstrip().lower().startswith("<!doctype html>"))

    def test_api_needs_the_token(self):
        with self.assertRaises(urllib.error.HTTPError) as e:
            self.get("/api/info")
        self.assertEqual(e.exception.code, 403)
        self.assertEqual(self.post("/api/deploy", {"files": []})[0], 403)
        self.assertEqual(self.get(f"/api/info?token={self.token}")[0], 200)

    def test_deploy_over_http_and_json_only(self):
        st, r = self.post(f"/api/deploy?token={self.token}", {"files": [["guild/ollo.md", "# Ollo"]], "guild": {"heroes": {}}})
        self.assertEqual(st, 200)
        self.assertEqual(r["written"], ["guild/ollo.md"])
        self.assertEqual(self.get(f"/api/guild?token={self.token}")[1].strip()[:1], "{")
        self.assertEqual(self.post(f"/api/deploy?token={self.token}", {}, "text/plain")[0], 415)


if __name__ == "__main__":
    unittest.main()
