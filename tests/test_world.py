"""The live 3D world: the page, its offline three.js files, and the state it draws (read from the real repo)."""
import json
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import agent_company as ac  # noqa: E402
from test_cli import GOOD, quiet  # noqa: E402

ORDER = ["setup", "team", "harness", "orders", "run", "proof"]


class WorldState(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.repo)], check=True)
        quiet(ac.cmd_init, str(self.repo))
        self.ops = self.repo / "docs" / "ops"

    def tearDown(self):
        self.tmp.cleanup()

    def stations(self):
        return {s["id"]: s for s in ac.world_state(self.repo)["stations"]}

    def test_fresh_repo_has_one_next_step_and_everything_after_it_locked(self):
        w = ac.world_state(self.repo)
        self.assertEqual([s["id"] for s in w["stations"]], ORDER)
        self.assertEqual([s["state"] for s in w["stations"]], ["done", "next", "locked", "locked", "locked", "locked"])
        self.assertEqual(w["version"], ac.VERSION)
        self.assertEqual(w["harness"]["fitted"], 0)
        self.assertEqual(w["orders"], {"pending": 0, "done": 0})
        self.assertEqual(w["proof"], {"sealed": 0, "broken": 0})
        self.assertFalse(w["kill"]["on"])

    def test_a_later_step_cannot_show_done_while_an_earlier_one_is_open(self):
        # STATUS.md from init already has a "Time:" line, so the raw check for "run" is true on day one
        self.assertEqual(self.stations()["run"]["state"], "locked")

    def test_team_then_harness_then_orders_unlock_in_order(self):
        ac.deploy_files(self.ops, [], None, {"heroes": {"h1": {"name": "Brannoc", "cls": "artificer", "origin": "Claude Code", "lv": 2},
                                                         "h2": {"name": "Ysolde", "cls": "paladin", "origin": "Codex", "lv": 1}}})
        w = ac.world_state(self.repo)
        self.assertEqual({s["id"]: s["state"] for s in w["stations"]}["harness"], "next")
        self.assertEqual([(t["name"], t["role"]) for t in w["team"]], [("Brannoc", "Builder"), ("Ysolde", "Evaluator")])
        ac.install_harness(self.repo)
        subprocess.run(["git", "-C", str(self.repo), "-c", "user.name=Owner", "-c", "user.email=o@example.test", "commit", "-q", "--allow-empty", "-m", "start"], check=True)
        self.assertNotIn("error", ac.commit_harness(self.repo))      # the harness step closes only once its files are committed
        w = ac.world_state(self.repo)
        self.assertEqual(w["harness"]["fitted"], 6)
        self.assertEqual({s["id"]: s["state"] for s in w["stations"]}["orders"], "next")
        ac.deploy_files(self.ops, [["inbox/001_add-rate-limiting.md", GOOD]], None, None)
        w = ac.world_state(self.repo)
        self.assertEqual(w["orders"]["pending"], 1)
        self.assertEqual({s["id"]: s["state"] for s in w["stations"]}["orders"], "done")

    def test_coordinator_counts_as_started_only_when_status_has_a_real_time(self):
        ac.deploy_files(self.ops, [["inbox/001_add-rate-limiting.md", GOOD]], None, {"heroes": {"h1": {"name": "Mara", "cls": "leader"}}})
        ac.install_harness(self.repo)
        subprocess.run(["git", "-C", str(self.repo), "-c", "user.name=Owner", "-c", "user.email=o@example.test", "commit", "-q", "--allow-empty", "-m", "start"], check=True)
        ac.commit_harness(self.repo)
        self.assertEqual(self.stations()["run"]["state"], "next", "the untouched STATUS.md template must not read as a running coordinator")
        (self.ops / "outbox" / "STATUS.md").write_text("# Status\n\nTime: 2026-11-20 12:10 SGT (checked against the remote)\n", encoding="utf-8")
        self.assertEqual(self.stations()["run"]["state"], "done")

    def test_first_run_guide_does_not_call_the_template_status_a_started_coordinator(self):
        steps = {s["name"]: s["done"] for s in ac.stage(self.repo)["steps"]}
        self.assertFalse(steps["Start the coordinator"], "a new project has no coordinator yet")
        (self.ops / "outbox" / "STATUS.md").write_text("# Status\n\nTime: 2026-11-20 12:10 SGT\n", encoding="utf-8")
        self.assertTrue({s["name"]: s["done"] for s in ac.stage(self.repo)["steps"]}["Start the coordinator"])

    def test_a_team_placed_on_the_command_map_counts_as_a_team(self):
        plan = {"units": {"u1": {"id": "u1", "role": "coord", "tool": "Claude Code"}, "u2": {"id": "u2", "role": "builder", "tool": "Claude Code"},
                          "u3": {"id": "u3", "role": "evaluator", "tool": "Codex"}, "u9": {"id": "u9", "role": "watch", "tool": "Scheduled task"}},
                "place": {"u1": "cp:coord", "u2": "m001:builder", "u3": "m001:evaluator"}, "missions": []}
        ac.deploy_files(self.ops, [], plan, None)
        w = ac.world_state(self.repo)
        self.assertEqual({s["id"]: s["state"] for s in w["stations"]}["team"], "done")
        self.assertEqual([(t["role"], t["origin"]) for t in w["team"]], [("Coordinator", "Claude Code"), ("Builder", "Claude Code"), ("Evaluator", "Codex")],
                         "only units placed on the field are on the team")

    def test_an_empty_command_map_is_not_a_team(self):
        ac.deploy_files(self.ops, [], {"units": {"u1": {"id": "u1", "role": "coord", "tool": "Claude Code"}}, "place": {}, "missions": []}, None)
        self.assertEqual(self.stations()["team"]["state"], "next")

    def test_kill_switch_file_is_reported_and_stops_the_line(self):
        (self.repo / ".harness").mkdir()
        (self.repo / ".harness" / "KILL").write_text(json.dumps({"by": "Owner", "reason": "drill", "ts": "2026-11-20T04:00:00Z"}))
        w = ac.world_state(self.repo)
        self.assertEqual(w["kill"], {"on": True, "by": "Owner", "reason": "drill", "ts": "2026-11-20T04:00:00Z"})

    def test_every_station_says_how_and_only_the_harness_has_a_button(self):
        for s in ac.world_state(self.repo)["stations"]:
            self.assertTrue(s["name"] and s["how"])
        self.assertEqual([s["id"] for s in ac.world_state(self.repo)["stations"] if s.get("action")], ["harness"])


class WorldServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        repo = Path(cls.tmp.name)
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        quiet(ac.cmd_init, str(repo))
        cls.token = "t0ken"
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), ac.make_handler(repo / "docs" / "ops", cls.token))
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.srv.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.tmp.cleanup()

    def get(self, path):
        with urllib.request.urlopen(self.base + path) as r:
            return r.status, r.headers.get("Content-Type", ""), r.read().decode()

    def code(self, path):
        try:
            return self.get(path)[0]
        except urllib.error.HTTPError as e:
            return e.code

    def test_world_page_is_served_and_loads_nothing_from_the_internet(self):
        st, ctype, page = self.get("/world")
        self.assertEqual(st, 200)
        self.assertIn("text/html", ctype)
        self.assertIn("Agent Company World", page)
        self.assertTrue(page.lstrip().lower().startswith("<!doctype html>"))
        for outside in ("https://", "http://", "//cdn", "fonts.googleapis"):
            self.assertNotIn(outside, page.replace("http://www.w3.org/", ""), outside)

    def test_three_js_is_served_from_the_kit_itself(self):
        for f in ("three.module.min.js", "OrbitControls.js", "RoundedBoxGeometry.js"):
            st, ctype, body = self.get(f"/vendor/three/{f}")
            self.assertEqual(st, 200, f)
            self.assertIn("javascript", ctype)
            self.assertGreater(len(body), 1000)

    def test_vendor_route_serves_only_its_own_files(self):
        for bad in ("/vendor/three/../../agent_company.py", "/vendor/three/%2e%2e/%2e%2e/agent_company.py",
                    "/vendor/../agent_company.py", "/vendor/three/nope.js", "/vendor/three/", "/vendor/three/LICENSE/../../../SKILL.md"):
            self.assertEqual(self.code(bad), 404, bad)

    def test_browser_icon_request_is_answered_quietly(self):
        self.assertEqual(self.code("/favicon.ico"), 204)

    def post_code(self, path):
        req = urllib.request.Request(self.base + path, data=b"{}", method="POST", headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status
        except urllib.error.HTTPError as e:
            return e.code

    def test_the_screen_cannot_approve_merge_seal_or_lift_the_kill_switch(self):
        for path in ("/api/approve", "/api/merge", "/api/seal", "/api/kill", "/api/revive", "/api/world", "/api/start", "/api/verify"):
            self.assertEqual(self.post_code(f"{path}?token={self.token}"), 403, path)

    def test_command_map_links_back_to_the_world(self):
        self.assertIn('id="btn-world"', self.get("/")[2])

    def test_world_state_needs_the_token(self):
        self.assertEqual(self.code("/api/world"), 403)
        st, _, body = self.get(f"/api/world?token={self.token}")
        self.assertEqual(st, 200)
        self.assertEqual([s["id"] for s in json.loads(body)["stations"]], ORDER)


class WorldCommand(unittest.TestCase):
    def test_world_command_opens_the_world(self):
        from unittest import mock
        with mock.patch.object(ac, "cmd_ui", return_value=0) as ui, mock.patch.object(sys, "argv", ["agent_company.py", "world", ".", "--no-browser"]):
            ac.main()
        self.assertEqual(ui.call_args[0][3], "/world")


if __name__ == "__main__":
    unittest.main()
