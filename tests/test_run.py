"""The harness must travel with the repo, and the background runner must refuse to start without it."""
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import agent_company as ac  # noqa: E402
from test_cli import GOOD, quiet  # noqa: E402

TEAM = {"units": {"u1": {"id": "u1", "role": "coord", "tool": "Claude Code"}}, "place": {"u1": "cp:coord"}, "missions": []}
PY = sys.executable


def git(repo, *a):
    return subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True, check=True).stdout.strip()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "proj"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.repo)], check=True)
        git(self.repo, "config", "user.name", "Owner"); git(self.repo, "config", "user.email", "owner@example.test")
        (self.repo / "README.md").write_text("x\n"); git(self.repo, "add", "-A"); git(self.repo, "commit", "-qm", "start")
        quiet(ac.cmd_init, str(self.repo))
        self.ops = self.repo / "docs" / "ops"

    def tearDown(self):
        try:
            ac.stop_runner(self.repo)
            self.wait(lambda: ac.runner_status(self.repo)["state"] != "running", 5)
        except Exception:
            pass
        self.tmp.cleanup()

    def wait(self, cond, secs=8):
        end = time.time() + secs
        while time.time() < end:
            if cond():
                return True
            time.sleep(.1)
        return cond()

    def ready(self):
        ac.deploy_files(self.ops, [["inbox/001_add-rate-limiting.md", GOOD]], TEAM, None)
        ac.install_harness(self.repo)
        return ac.commit_harness(self.repo)


class HarnessTravels(Base):
    def test_a_fresh_install_is_fitted_but_not_committed(self):
        ac.install_harness(self.repo)
        st = ac.harness_status(self.repo)
        self.assertEqual(st["fitted"], 6)
        self.assertFalse(st["committed"])
        self.assertIn("docs/ops/harness/guard.py", st["uncommitted"])
        self.assertIn(".claude/settings.json", st["uncommitted"])

    def test_the_world_keeps_the_harness_step_open_until_it_is_committed(self):
        ac.deploy_files(self.ops, [], TEAM, None)
        ac.install_harness(self.repo)
        s = {x["id"]: x for x in ac.world_state(self.repo)["stations"]}["harness"]
        self.assertEqual(s["state"], "next")
        self.assertEqual(s["action"], "commit-harness")
        self.assertIn("commit", s["how"].lower())
        ac.commit_harness(self.repo)
        s = {x["id"]: x for x in ac.world_state(self.repo)["stations"]}["harness"]
        self.assertEqual(s["state"], "done")

    def test_commit_takes_only_the_harness_files(self):
        ac.install_harness(self.repo)
        (self.repo / "notes.txt").write_text("mine\n")
        (self.repo / ".claude" / "settings.json.before-agent-company").write_text("{}")
        r = ac.commit_harness(self.repo)
        self.assertNotIn("error", r)
        tracked = git(self.repo, "ls-files").splitlines()
        for f in ("AGENTS.md", ".claude/settings.json", "docs/ops/harness/guard.py", "docs/ops/harness/allowlist.json", "docs/ops/harness/real_data_paths.txt"):
            self.assertIn(f, tracked)
        self.assertNotIn("notes.txt", tracked)
        self.assertNotIn(".claude/settings.json.before-agent-company", tracked)
        self.assertTrue(ac.harness_status(self.repo)["committed"])
        self.assertIn("harness", git(self.repo, "log", "-1", "--format=%s").lower())

    def test_a_new_worktree_carries_the_guard(self):
        ac.install_harness(self.repo); ac.commit_harness(self.repo)
        wt = Path(self.tmp.name) / "wt"
        git(self.repo, "worktree", "add", "-q", str(wt), "-b", "feat/x")
        self.assertTrue((wt / "docs/ops/harness/guard.py").exists())
        hooks = json.loads((wt / ".claude/settings.json").read_text())["hooks"]["PreToolUse"]
        self.assertTrue(any("guard.py" in h["command"] for e in hooks for h in e["hooks"]))

    def test_editing_the_guard_after_the_commit_shows_as_not_committed(self):
        ac.install_harness(self.repo); ac.commit_harness(self.repo)
        p = self.repo / "docs/ops/harness/guard.py"; p.write_text(p.read_text() + "\n# loosened\n")
        st = ac.harness_status(self.repo)
        self.assertFalse(st["committed"]); self.assertEqual(st["uncommitted"], ["docs/ops/harness/guard.py"])

    def test_commit_is_refused_until_all_six_pieces_are_fitted(self):
        self.assertIn("error", ac.commit_harness(self.repo))

    def test_commit_over_http_needs_the_token(self):
        ac.install_harness(self.repo)
        srv = ThreadingHTTPServer(("127.0.0.1", 0), ac.make_handler(self.ops, "t0ken"))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        def post(path):
            req = urllib.request.Request(base + path, data=b"{}", method="POST", headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req) as r:
                    return r.status, json.loads(r.read())
            except urllib.error.HTTPError as e:
                return e.code, None
        try:
            self.assertEqual(post("/api/harness/commit")[0], 403)
            st, body = post("/api/harness/commit?token=t0ken")
            self.assertEqual(st, 200); self.assertTrue(body["status"]["committed"])
        finally:
            srv.shutdown()


class Runner(Base):
    def test_headless_commands_never_skip_permissions(self):
        self.assertEqual(ac.HEADLESS["claude"][:2], ["claude", "-p"])
        self.assertEqual(ac.HEADLESS["codex"][:2], ["codex", "exec"])
        for argv in ac.HEADLESS.values():
            flat = " ".join(argv).lower()
            for bad in ("skip-permissions", "bypass", "yolo", "full-auto", "--no-verify"):
                self.assertNotIn(bad, flat)
            self.assertIn("lowest-numbered", flat)
            self.assertIn("never merge", flat)
        self.assertNotIn("cursor", ac.HEADLESS); self.assertNotIn("copilot", ac.HEADLESS)

    def test_refuses_without_a_committed_harness(self):
        ac.deploy_files(self.ops, [["inbox/001_add-rate-limiting.md", GOOD]], TEAM, None)
        r = ac.start_runner(self.repo, "claude", argv=[PY, "-c", "print('hi')"])
        self.assertIn("harness", r["error"]); self.assertEqual(ac.runner_status(self.repo)["state"], "never")
        ac.install_harness(self.repo)
        self.assertIn("commit", ac.start_runner(self.repo, "claude", argv=[PY, "-c", "print('hi')"])["error"])

    def test_refuses_with_nothing_in_the_inbox(self):
        ac.deploy_files(self.ops, [], TEAM, None); ac.install_harness(self.repo); ac.commit_harness(self.repo)
        self.assertIn("inbox", ac.start_runner(self.repo, "claude", argv=[PY, "-c", "print('hi')"])["error"])

    def test_refuses_while_the_kill_switch_is_on(self):
        self.ready()
        (self.repo / ".harness").mkdir(); (self.repo / ".harness" / "KILL").write_text('{"by":"Owner","reason":"drill"}')
        self.assertIn("kill switch", ac.start_runner(self.repo, "claude", argv=[PY, "-c", "print('hi')"])["error"])

    def test_refuses_a_tool_with_no_headless_mode(self):
        self.ready()
        self.assertIn("error", ac.start_runner(self.repo, "cursor"))

    def test_runs_in_the_background_logs_and_records_the_exit(self):
        self.ready()
        t0 = time.time()
        r = ac.start_runner(self.repo, "claude", argv=[PY, "-c", "import time; print('coordinator says hello'); time.sleep(1.2)"])
        self.assertNotIn("error", r); self.assertLess(time.time() - t0, 3, "start must return at once")
        self.assertTrue(self.wait(lambda: ac.runner_status(self.repo)["state"] == "running"))
        self.assertEqual(ac.world_state(self.repo)["runner"]["state"], "running")
        self.assertTrue(self.wait(lambda: ac.runner_status(self.repo)["state"] == "exited"))
        st = ac.runner_status(self.repo)
        self.assertEqual(st["exit"], 0); self.assertEqual(st["tool"], "claude")
        self.assertIn("coordinator says hello", (self.ops / "outbox" / "runner.log").read_text())

    def test_exactly_one_runner(self):
        self.ready()
        ac.start_runner(self.repo, "claude", argv=[PY, "-c", "import time; time.sleep(30)"])
        self.assertTrue(self.wait(lambda: ac.runner_status(self.repo)["state"] == "running"))
        self.assertIn("already", ac.start_runner(self.repo, "claude", argv=[PY, "-c", "print(1)"])["error"])

    def test_stop_ends_it(self):
        self.ready()
        ac.start_runner(self.repo, "claude", argv=[PY, "-c", "import time; time.sleep(30)"])
        self.assertTrue(self.wait(lambda: ac.runner_status(self.repo)["state"] == "running"))
        pid = ac.runner_status(self.repo)["pid"]
        ac.stop_runner(self.repo)
        self.assertTrue(self.wait(lambda: ac.runner_status(self.repo)["state"] == "stopped"))
        self.assertTrue(self.wait(lambda: not ac._alive(pid)))

    def test_the_kill_switch_ends_a_running_agent(self):
        self.ready()
        ac.start_runner(self.repo, "claude", argv=[PY, "-c", "import time; time.sleep(30)"])
        self.assertTrue(self.wait(lambda: ac.runner_status(self.repo)["state"] == "running"))
        pid = ac.runner_status(self.repo)["pid"]
        (self.repo / ".harness").mkdir(exist_ok=True); (self.repo / ".harness" / "KILL").write_text('{"by":"Owner","reason":"drill"}')
        self.assertTrue(self.wait(lambda: ac.runner_status(self.repo)["state"] == "killed"))
        self.assertTrue(self.wait(lambda: not ac._alive(pid)))

    def test_the_agent_runs_in_the_project_folder(self):
        self.ready()
        ac.start_runner(self.repo, "claude", argv=[PY, "-c", "import os; print('cwd=' + os.getcwd())"])
        self.assertTrue(self.wait(lambda: ac.runner_status(self.repo)["state"] == "exited"))
        self.assertIn(f"cwd={self.repo.resolve()}", (self.ops / "outbox" / "runner.log").read_text())


if __name__ == "__main__":
    unittest.main()
