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
        self.assertEqual(w["proof"], {"sealed": 0, "broken": 0, "unverified": 0})
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


class _KitRepo:
    """A scratch repo, and one scaffolded the way the kit's harness-init leaves it."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.repo)], check=True)
        quiet(ac.cmd_init, str(self.repo))

    def tearDown(self):
        self.tmp.cleanup()

    def kit(self):
        return ac.world_state(self.repo)["kit"]

    def scaffold(self):
        """A repo as harness-init leaves it, with an image built the way tools/golden.py builds one."""
        import hashlib
        r = self.repo
        locked = {"scripts/harness.py": b"# harness\n", "scripts/runtime.py": b"# runtime\n", "progress/clean-state.md": b"# clean\n"}
        for rel, data in locked.items():
            (r / rel).parent.mkdir(parents=True, exist_ok=True); (r / rel).write_bytes(data)
        for rel in ["progress/feature_list.json", "DECISIONS.md", "CLAUDE.md", ".harness/ledger.jsonl"]:
            (r / rel).parent.mkdir(parents=True, exist_ok=True); (r / rel).write_text("x\n", encoding="utf-8")
        deny = ["Bash(git push *)", "Read(./.env)"]
        gate = "python3 scripts/runtime.py gate"
        (r / ".claude").mkdir(exist_ok=True)
        (r / ".claude/settings.json").write_text(json.dumps({"permissions": {"deny": deny + ["Bash(rm -rf *)"]}, "hooks": {
            "PreToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": gate}]}]}}), encoding="utf-8")
        img = {"format": 1, "name": "harness-marketplace golden image", "version": "1.5.0",
               "locked": {k: hashlib.sha256(v).hexdigest() for k, v in sorted(locked.items())},
               "required": [["progress/feature_list.json"], ["DECISIONS.md"], ["CLAUDE.md", "AGENTS.md"], [".claude/settings.json"],
                            [".harness/ledger.jsonl"]],
               "deny": sorted(deny), "hooks": [gate]}
        img["image_sha"] = ac._golden_image_hash(img)
        (r / "scripts/golden-image.json").write_text(json.dumps(img, indent=2) + "\n", encoding="utf-8")
        return img


class WorldKit(_KitRepo, unittest.TestCase):
    """The World reads a Harness Marketplace kit (golden image, recovery drills) if the repo carries one. Read-only."""

    def test_a_repo_without_the_kit_says_so(self):
        k = self.kit()
        self.assertEqual(k["golden"], {"installed": False})
        self.assertEqual(k["recovery"], {"drills": 0, "last": None})

    def test_the_real_images_own_hash_is_reproduced(self):
        # an image built by the kit's own tools/golden.py (1.5.0): the World must hash it the same way, or it would cry ALTERED
        img = json.loads((Path(__file__).parent / "fixtures" / "golden-image-1.5.0.json").read_text(encoding="utf-8"))
        self.assertEqual(ac._golden_image_hash(img), img["image_sha"])

    def test_match_then_drift_names_what_drifted(self):
        img = self.scaffold()
        g = self.kit()["golden"]
        self.assertEqual((g["installed"], g["result"], g["version"], g["drift"]), (True, "MATCH", "1.5.0", []))
        self.assertEqual(g["sha"], img["image_sha"][:12])
        self.assertEqual(g["checked"], 3 + 5 + 2 + 1)                  # locked, required, deny rules, hooks
        (self.repo / "scripts/harness.py").write_text("# harness, loosened\n", encoding="utf-8")
        s = json.loads((self.repo / ".claude/settings.json").read_text(encoding="utf-8"))
        s["permissions"]["deny"].remove("Bash(git push *)"); s["hooks"] = {}
        (self.repo / ".claude/settings.json").write_text(json.dumps(s), encoding="utf-8")
        (self.repo / "DECISIONS.md").unlink(); (self.repo / "scripts/runtime.py").unlink()
        g = self.kit()["golden"]
        self.assertEqual(g["result"], "DRIFT")
        self.assertEqual(sorted(g["drift"]), sorted(["DRIFT scripts/harness.py", "MISSING scripts/runtime.py", "MISSING DECISIONS.md",
                                                     "DRIFT deny Bash(git push *)", "DRIFT hook python3 scripts/runtime.py gate"]))

    def test_an_edited_image_is_not_trusted(self):
        img = self.scaffold()
        img["deny"] = []                                               # someone loosens the standard and keeps the old hash
        (self.repo / "scripts/golden-image.json").write_text(json.dumps(img), encoding="utf-8")
        g = self.kit()["golden"]
        self.assertEqual((g["result"], g["checked"]), ("ALTERED", 0))
        (self.repo / "scripts/golden-image.json").write_text("{not json", encoding="utf-8")
        self.assertEqual(self.kit()["golden"]["result"], "ALTERED")
        img = self.scaffold(); img["locked"]["../outside.txt"] = "0" * 64; img["image_sha"] = ac._golden_image_hash(img)
        (self.repo / "scripts/golden-image.json").write_text(json.dumps(img), encoding="utf-8")
        self.assertIn("DRIFT ../outside.txt", self.kit()["golden"]["drift"])   # a path outside the repo is never read

    def chained(self, entries):
        """Ledger lines linked the way the kit's harness.py links them."""
        out, prev = [], "0" * 64
        for i, e in enumerate(entries, 1):
            e = {"seq": i, **e, "prev": prev}
            e["hash"] = ac._ledger_entry_hash(e); prev = e["hash"]; out.append(json.dumps(e, sort_keys=True, separators=(",", ":")))
        return "\n".join(out) + "\n"

    def test_recovery_shows_the_last_drill_in_the_kits_ledger(self):
        self.scaffold()
        lines = [{"ts": "2026-11-20T08:00:00Z", "type": "kill", "by": "Owner", "reason": "test"},
                 {"ts": "2026-11-20T08:05:00Z", "type": "drill", "by": "Owner", "result": "FAILED", "seconds": 9.5, "checks_run": 2},
                 {"ts": "2026-11-20T08:20:00Z", "type": "drill", "by": "Owner", "result": "RECOVERED", "seconds": 3.25, "checks_run": 2}]
        (self.repo / ".harness/ledger.jsonl").write_text(self.chained(lines), encoding="utf-8")
        self.assertEqual(self.kit()["recovery"], {"drills": 2, "last": {"result": "RECOVERED", "seconds": 3.25, "ts": "2026-11-20T08:20:00Z",
                                                                          "by": "Owner", "checks_run": 2}})


class WorldKitReview(_KitRepo, unittest.TestCase):
    """Found by an independent review on 20 Nov 2026: ways the readout said MATCH, or read outside the repo, when it must not."""

    def test_an_image_that_lists_nothing_is_not_a_match(self):
        self.scaffold()
        for img in ({}, {"locked": {}, "required": [], "deny": [], "hooks": []}, {"locked": [], "required": {}, "deny": "x", "hooks": 1}):
            img = dict(img, version="1.5.0"); img["image_sha"] = ac._golden_image_hash(img)
            (self.repo / "scripts/golden-image.json").write_text(json.dumps(img), encoding="utf-8")
            g = self.kit()["golden"]
            self.assertEqual((g["result"], g["checked"]), ("ALTERED", 0), img)

    def test_links_that_leave_the_repo_are_never_read(self):
        import os
        self.scaffold()
        outside = Path(tempfile.mkdtemp())
        (outside / "secret.json").write_text(json.dumps({"version": "PRIVATE-TOKEN-123", "image_sha": "SECRETSECRET", "type": "drill",
                                                         "result": "RECOVERED", "by": "PRIVATE-NAME", "ts": "2099"}), encoding="utf-8")
        for rel in ("scripts/golden-image.json", ".harness/ledger.jsonl"):
            (self.repo / rel).unlink(); os.symlink(outside / "secret.json", self.repo / rel)
        k = self.kit()
        self.assertNotIn("PRIVATE", json.dumps(k)); self.assertNotIn("SECRET", json.dumps(k))
        self.assertEqual(k["golden"]["result"], "ALTERED")
        self.assertEqual((k["recovery"]["drills"], k["recovery"]["last"]), (0, None))
        self.assertTrue(k["recovery"]["untrusted"])                     # and it says the ledger was not read, not "none on record"
        # settings linked outside the repo count as no settings at all
        (self.repo / "scripts/golden-image.json").unlink(); (self.repo / ".harness/ledger.jsonl").unlink(); self.scaffold()
        good = (self.repo / ".claude/settings.json").read_text(encoding="utf-8")
        (outside / "settings.json").write_text(good, encoding="utf-8")
        (self.repo / ".claude/settings.json").unlink(); os.symlink(outside / "settings.json", self.repo / ".claude/settings.json")
        g = self.kit()["golden"]
        self.assertEqual(g["result"], "DRIFT"); self.assertIn("DRIFT deny Bash(git push *)", g["drift"])

    def test_a_hook_that_cannot_stop_anything_is_drift(self):
        self.scaffold()
        sp = self.repo / ".claude/settings.json"
        good = json.loads(sp.read_text(encoding="utf-8"))
        gate = "python3 scripts/runtime.py gate"
        def result(settings, local=None):
            sp.write_text(json.dumps(settings), encoding="utf-8")
            lp = self.repo / ".claude/settings.local.json"
            lp.write_text(json.dumps(local), encoding="utf-8") if local is not None else (lp.unlink() if lp.exists() else None)
            return self.kit()["golden"]
        self.assertEqual(result(good)["result"], "MATCH")
        entry = {"type": "command", "command": gate}
        cases = {"under PostToolUse": {**good, "hooks": {"PostToolUse": [{"matcher": "*", "hooks": [entry]}]}},
                 "under a made-up event": {**good, "hooks": {"NoSuchEvent": [{"matcher": "*", "hooks": [entry]}]}},
                 "matcher narrowed": {**good, "hooks": {"PreToolUse": [{"matcher": "Read", "hooks": [entry]}]}},
                 "type is not command": {**good, "hooks": {"PreToolUse": [{"matcher": "*", "hooks": [{**entry, "type": "prompt"}]}]}},
                 "all hooks disabled": {**good, "disableAllHooks": True}}
        for name, s in cases.items():
            g = result(s)
            self.assertEqual(g["result"], "DRIFT", name); self.assertTrue(any("hook" in d for d in g["drift"]), name)
        g = result(good, local={"disableAllHooks": True})
        self.assertEqual(g["result"], "DRIFT", "disabled in settings.local.json")

    def test_odd_settings_never_crash_the_screen_or_pass(self):
        self.scaffold()
        sp = self.repo / ".claude/settings.json"
        good = json.loads(sp.read_text(encoding="utf-8"))
        for odd in ([1, 2], {**good, "permissions": {"deny": {r: True for r in good["permissions"]["deny"]}}},
                    {**good, "permissions": {"deny": good["permissions"]["deny"] + [{"a": 1}, ["b"]]}}, {**good, "hooks": {"PreToolUse": "x"}},
                    {**good, "hooks": {"PreToolUse": [1, {"hooks": "x"}, {"hooks": [1]}]}}):
            sp.write_text(json.dumps(odd), encoding="utf-8")
            g = self.kit()["golden"]                                  # must not raise
            if not (isinstance(odd, dict) and isinstance(odd.get("permissions", {}).get("deny"), list) and isinstance(odd.get("hooks"), dict)
                    and odd["hooks"].get("PreToolUse") and isinstance(odd["hooks"]["PreToolUse"], list) and isinstance(odd["hooks"]["PreToolUse"][0], dict)):
                self.assertEqual(g["result"], "DRIFT", odd)
        sp.write_bytes(b"\xff\xfe not utf-8")
        self.assertEqual(self.kit()["golden"]["result"], "DRIFT")

    def test_any_kill_file_counts_as_on(self):
        kp = self.repo / ".harness"; kp.mkdir(exist_ok=True)
        for make in (lambda p: p.write_text("{}", encoding="utf-8"), lambda p: p.write_text("[1]", encoding="utf-8"),
                     lambda p: p.write_bytes(b"\xff\xfe stop"), lambda p: p.mkdir()):
            k = kp / "KILL"
            make(k)
            self.assertTrue(ac.world_state(self.repo)["kill"]["on"])
            k.rmdir() if k.is_dir() else k.unlink()
        self.assertFalse(ac.world_state(self.repo)["kill"]["on"])

    def test_disabled_hooks_unfit_agent_companys_own_harness(self):
        ac.install_harness(self.repo)
        self.assertEqual(ac.world_state(self.repo)["harness"]["fitted"], 6)
        sp = self.repo / ".claude/settings.json"
        s = json.loads(sp.read_text(encoding="utf-8"))
        sp.write_text(json.dumps({**s, "disableAllHooks": True}), encoding="utf-8")
        h = ac.world_state(self.repo)["harness"]
        self.assertLess(h["fitted"], 6)                                # the guard file is there, but nothing runs it
        self.assertFalse(h["pieces"]["helm"] or h["pieces"]["hands"] or h["pieces"]["amulet"])
        sp.write_text(json.dumps(s), encoding="utf-8")
        (self.repo / ".claude/settings.local.json").write_text('{"disableAllHooks": true}', encoding="utf-8")
        self.assertLess(ac.world_state(self.repo)["harness"]["fitted"], 6)
        sp.write_text("[1, 2]", encoding="utf-8")                      # an odd settings file must not take the screen down
        self.assertEqual(ac.world_state(self.repo)["harness"]["fitted"], 0)

    def test_a_required_entry_must_be_a_file_as_the_kit_itself_requires(self):
        self.scaffold()
        (self.repo / "DECISIONS.md").unlink(); (self.repo / "DECISIONS.md").mkdir()
        g = self.kit()["golden"]
        self.assertEqual((g["result"], g["drift"]), ("DRIFT", ["MISSING DECISIONS.md"]))
        sp = self.repo / ".claude/settings.json"
        s = json.loads(sp.read_text(encoding="utf-8")); sp.write_text(json.dumps({**s, "disableAllHooks": True}), encoding="utf-8")
        self.assertIn("DRIFT hook python3 scripts/runtime.py gate", self.kit()["golden"]["drift"])   # worded as the kit words it


class WorldInterrogation(_KitRepo, unittest.TestCase):
    """Found by the interrogation on 20 Nov 2026: states where the screen showed better than the repository, or fell over."""
    chained = WorldKit.chained

    def worktree(self):
        subprocess.run(["git", "-C", str(self.repo), "-c", "user.name=t", "-c", "user.email=t@e", "commit", "-q", "--allow-empty", "-m", "x"], check=True)
        wt = Path(str(self.repo) + "-wt")
        subprocess.run(["git", "-C", str(self.repo), "worktree", "add", "-q", str(wt), "-b", "builder"], check=True)
        self.addCleanup(__import__("shutil").rmtree, wt, True)
        return wt

    def test_a_stop_in_the_main_checkout_shows_in_a_worktree_and_stops_the_runner_there(self):
        wt = self.worktree()
        (self.repo / ".harness").mkdir(exist_ok=True); (self.repo / ".harness/KILL").write_text('{"by": "Owner", "reason": "stop"}')
        k = ac.world_state(wt)["kill"]
        self.assertEqual((k["on"], k["by"]), (True, "Owner"))
        self.assertTrue(any("kill switch" in w for w in ac.runner_ready(wt)))
        (self.repo / ".harness/KILL").unlink()
        self.assertFalse(ac.world_state(wt)["kill"]["on"])
        (wt / ".git").write_text("not a gitdir line\n")                     # cannot tell where the main checkout is
        self.assertTrue(ac.world_state(wt)["kill"]["on"], "when it cannot check, the screen must not say off")

    def test_a_drill_line_is_shown_only_from_a_ledger_whose_chain_holds(self):
        self.scaffold()
        lp = self.repo / ".harness/ledger.jsonl"
        lp.write_text('{"type":"drill","result":"RECOVERED","by":"nobody","seconds":1,"checks_run":9}\n', encoding="utf-8")
        r = self.kit()["recovery"]
        self.assertIsNone(r["last"]); self.assertIn("chain", r["untrusted"])
        good = self.chained([{"ts": "t", "type": "drill", "by": "Owner", "result": "FAILED", "seconds": 2, "checks_run": 1}])
        lp.write_text(good, encoding="utf-8")
        self.assertEqual(self.kit()["recovery"]["last"]["result"], "FAILED")
        lp.write_bytes(good.encode() + b"\xe9 odd byte\n")                  # one odd byte must not turn FAILED into "none"
        r = self.kit()["recovery"]
        self.assertIsNone(r["last"]); self.assertTrue(r["untrusted"])
        lp.write_text(self.chained([{"ts": "t", "type": "drill", "by": "O", "result": "RECOVERED", "seconds": float("inf"), "checks_run": 1}]).replace("Infinity", "1e999"), encoding="utf-8")
        json.dumps(ac.world_state(self.repo), allow_nan=False)             # what the server sends must be real JSON

    def test_odd_files_never_take_the_screen_down(self):
        self.scaffold()
        (self.repo / ".harness/KILL").write_text("[" * 200000)
        self.assertTrue(ac.world_state(self.repo)["kill"]["on"])
        (self.repo / ".harness/KILL").unlink()
        (self.repo / ".claude/settings.json").write_text("[" * 200000)
        self.assertEqual(ac.world_state(self.repo)["kit"]["golden"]["result"], "DRIFT")
        (self.repo / "scripts/golden-image.json").write_text('{"version": "\\ud800", "image_sha": "x"}')
        self.assertEqual(ac.world_state(self.repo)["kit"]["golden"]["result"], "ALTERED")
        hooks = self.repo / ".git/hooks"; hooks.mkdir(exist_ok=True); (hooks / "pre-push").mkdir()
        self.assertFalse(ac.world_state(self.repo)["harness"]["pre_push"])
        rf = self.repo / "docs/ops/outbox/RUNNER.json"; rf.parent.mkdir(parents=True, exist_ok=True); rf.write_text("[]")
        self.assertEqual(ac.world_state(self.repo)["runner"]["state"], "never")

    def test_the_pre_push_hook_is_only_read_inside_the_repository(self):
        outside = Path(tempfile.mkdtemp()); (outside / "pre-push").write_text("#!/bin/sh\n# Agent Company harness\n")
        subprocess.run(["git", "-C", str(self.repo), "config", "core.hooksPath", str(outside)], check=True)
        self.assertFalse(ac.world_state(self.repo)["harness"]["pre_push"])

    def test_six_of_six_needs_the_real_guard_and_the_real_hook_commands(self):
        ac.install_harness(self.repo)
        self.assertEqual(ac.world_state(self.repo)["harness"]["fitted"], 6)
        g = self.repo / "docs/ops/harness/guard.py"; real = g.read_bytes()
        g.write_bytes(b"")
        self.assertEqual(ac.world_state(self.repo)["harness"]["fitted"], 0, "an empty guard.py still counted")
        g.write_bytes(real)
        sp = self.repo / ".claude/settings.json"; s = json.loads(sp.read_text(encoding="utf-8"))
        for e in s["hooks"]["PreToolUse"]:
            for h in e["hooks"]:
                h["command"] = "true # docs/ops/harness/guard.py"
        sp.write_text(json.dumps(s), encoding="utf-8")
        h = ac.world_state(self.repo)["harness"]
        self.assertFalse(h["pieces"]["helm"] or h["pieces"]["hands"], "a hook that only mentions the guard still counted")

    def test_the_golden_image_says_whether_it_is_pinned(self):
        img = self.scaffold()
        self.assertIs(self.kit()["golden"]["pinned"], False)
        wf = self.repo / ".github/workflows"; wf.mkdir(parents=True)
        (wf / "harness.yml").write_text(f"      run: python3 -I scripts/golden.py check --expect-sha {img['image_sha']}\n")
        g = self.kit()["golden"]
        self.assertEqual((g["result"], g["pinned"]), ("MATCH", True))
        img["deny"] = img["deny"][:1]; img["image_sha"] = ac._golden_image_hash(img)       # edited and hashed again
        (self.repo / "scripts/golden-image.json").write_text(json.dumps(img), encoding="utf-8")
        g = self.kit()["golden"]
        self.assertEqual(g["result"], "ALTERED"); self.assertIn("pinned", g["drift"][0])

    def test_only_a_plain_gate_hook_entry_counts_as_the_kit_counts_it(self):
        self.scaffold()
        sp = self.repo / ".claude/settings.json"; good = json.loads(sp.read_text(encoding="utf-8"))
        for change in (lambda h, g: h.pop("type"), lambda h, g: h.__setitem__("async", True), lambda h, g: g.__setitem__("if", "x")):
            s = json.loads(json.dumps(good)); g = s["hooks"]["PreToolUse"][0]; change(g["hooks"][0], g)
            sp.write_text(json.dumps(s), encoding="utf-8")
            self.assertEqual(self.kit()["golden"]["result"], "DRIFT")
