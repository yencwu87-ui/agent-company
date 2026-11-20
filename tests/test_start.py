"""Zero-knowledge start: launch sets everything up, doctor and smoke explain, import-agents reads Claude Code subagents."""
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import agent_company as ac  # noqa: E402


def quiet(fn, *a):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = fn(*a)
    return rc, buf.getvalue()


class Start(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_launch_sets_up_a_new_folder_without_any_knowledge(self):
        proj = self.home / "team"
        with mock.patch.object(ac, "cmd_ui", return_value=0) as ui:
            rc, out = quiet(ac.cmd_launch, str(proj), 8765, False)
        self.assertEqual(rc, 0)
        self.assertTrue((proj / ".git").exists()); self.assertTrue((proj / "docs/ops/inbox/README.md").exists())
        self.assertEqual(ac._git(proj, "rev-parse", "--abbrev-ref", "HEAD"), "main")
        ui.assert_called_once(); self.assertEqual(ui.call_args[0][3], "/world")  # the 3D world is the start screen (owner, 20 Nov 2026)
        with mock.patch.object(ac, "cmd_ui", return_value=0):
            rc2, _ = quiet(ac.cmd_launch, str(proj), 8765, False)      # running it again is harmless
        self.assertEqual(rc2, 0)

    def test_doctor_names_the_fix(self):
        proj = self.home / "plain"; proj.mkdir()
        rows = {r["check"]: r for r in ac.doctor(proj)}
        self.assertFalse(rows["Project is a git repository"]["ok"]); self.assertIn("launch", rows["Project is a git repository"]["fix"])
        rc, out = quiet(ac.cmd_doctor, str(proj))
        self.assertEqual(rc, 1); self.assertIn("→", out)

    def test_stage_moves_forward(self):
        proj = self.home / "team"
        with mock.patch.object(ac, "cmd_ui", return_value=0):
            quiet(ac.cmd_launch, str(proj), 8765, False)
        st = ac.stage(proj)
        self.assertEqual(st["steps"][0]["done"], True); self.assertEqual(st["next"]["name"], "Forge a team")
        quiet(ac.cmd_harness, str(proj), False)
        self.assertTrue(ac.stage(proj)["steps"][2]["done"])

    def test_smoke_writes_a_dated_report(self):
        proj = self.home / "team"
        with mock.patch.object(ac, "cmd_ui", return_value=0):
            quiet(ac.cmd_launch, str(proj), 8765, False)
        rc, out = quiet(ac.cmd_smoke, str(proj))
        self.assertEqual(rc, 1); self.assertIn("FAIL", out)            # harness not installed yet
        quiet(ac.cmd_harness, str(proj), False)
        rc, out = quiet(ac.cmd_smoke, str(proj))
        self.assertEqual(rc, 0, out); self.assertIn("# Smoke check: PASS", out)
        self.assertTrue(list((proj / "docs/ops/outbox").glob("smoke-*.md")))

    def test_import_agents_maps_roles_and_never_takes_the_owner_seat(self):
        src = self.home / "studio" / ".claude" / "agents"; src.mkdir(parents=True)
        for name, desc in [("creative-director", "Guards the vision"), ("qa-tester", "Writes test cases"), ("security-engineer", "Finds vulnerabilities"),
                           ("producer", "Sprint planning"), ("gameplay-programmer", "Implements mechanics"), ("analytics-engineer", "Telemetry")]:
            (src / f"{name}.md").write_text(f"---\nname: {name}\ndescription: \"{desc}\"\n---\nbody\n")
        proj = self.home / "team"; (proj / "docs/ops").mkdir(parents=True)
        rc, _ = quiet(ac.cmd_import_agents, str(proj), str(self.home / "studio"), "Claude Code")
        heroes = {h["name"]: h for h in json.loads((proj / "docs/ops/guild/guild.json").read_text())["heroes"].values()}
        self.assertEqual(rc, 0)
        self.assertEqual({k: v["cls"] for k, v in heroes.items()}, {"Creative Director": "herald", "Qa Tester": "paladin", "Security Engineer": "rogue",
                                                                    "Producer": "leader", "Gameplay Programmer": "artificer", "Analytics Engineer": "ranger"})
        self.assertTrue(all(len(h["harness"]) == 6 for h in heroes.values()))
        quiet(ac.cmd_import_agents, str(proj), str(self.home / "studio"), "Claude Code")   # no duplicates on a second import
        self.assertEqual(len(json.loads((proj / "docs/ops/guild/guild.json").read_text())["heroes"]), 6)


if __name__ == "__main__":
    unittest.main()
