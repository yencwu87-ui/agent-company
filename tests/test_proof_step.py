"""Step 6 (Seal proof) counts as done only while the evidence holds: a ledger line alone is not proof."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import agent_company as ac  # noqa: E402
from test_cli import quiet  # noqa: E402


class ProofStep(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.repo)], check=True)
        quiet(ac.cmd_init, str(self.repo))

    def tearDown(self):
        self.tmp.cleanup()

    def proof_done(self, records):
        lines = [{"id": f"r{i}"} for i in range(len(records))]
        by_id = {f"r{i}": r for i, r in enumerate(records)}
        with mock.patch.object(ac, "_ledger", return_value=lines), \
             mock.patch.object(ac, "verify_record", side_effect=lambda root, rid: by_id[rid]):
            step = {s["name"]: s for s in ac.stage(self.repo)["steps"]}["Seal proof"]
        return step

    def test_no_record_is_not_done(self):
        self.assertFalse(self.proof_done([])["done"])

    def test_one_sealed_record_that_verifies_is_done(self):
        self.assertTrue(self.proof_done([{"sealed": True, "ok": True}])["done"])

    def test_a_record_changed_after_sealing_is_not_done(self):
        s = self.proof_done([{"sealed": False, "ok": False}])
        self.assertFalse(s["done"])
        self.assertIn("verify", s["how"])

    def test_one_broken_record_reopens_the_step_even_beside_a_good_one(self):
        self.assertFalse(self.proof_done([{"sealed": True, "ok": True}, {"sealed": False, "ok": False}])["done"])


if __name__ == "__main__":
    unittest.main()
