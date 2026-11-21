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


# ---- real bytes on disk: no mocked verifier (Codex r1 on PR #9: P1-1, P1-2, P1-3, P2-a, P2-b)
import json  # noqa: E402
from test_proof import Base  # noqa: E402


class ProofStepOnDisk(Base):
    def ledger(self):
        return self.repo / "docs/ops/evidence" / "ledger.jsonl"

    def record(self, rid):
        return self.repo / "docs/ops/evidence" / f"{rid}.json"

    def append(self, line):
        with open(self.ledger(), "a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def step6(self):
        return {s["name"]: s for s in ac.stage(self.repo)["steps"]}["Seal proof"]

    def vault(self):
        w = ac.world_state(self.repo)      # must return, never raise, whatever the ledger holds
        return {s["id"]: s for s in w["stations"]}["proof"], w["proof"]

    def assert_open(self):
        self.assertFalse(self.step6()["done"])
        station, proof = self.vault()
        self.assertNotEqual(station["state"], "done")
        return station, proof

    def verify_all(self):
        return quiet(ac.cmd_verify, str(self.repo), None, False, False)

    def test_baseline_one_good_seal_is_done(self):
        rc, _ = self.seal()
        self.assertEqual(rc, 0)
        self.assertTrue(self.step6()["done"])
        self.assertEqual(self.vault()[1]["broken"], 0)

    def test_p1_1_a_changed_first_record_of_51_reopens_the_step(self):
        rids = [self.seal()[1] for _ in range(51)]
        self.assertTrue(self.step6()["done"])
        f = self.record(rids[0])
        f.write_text(f.read_text(encoding="utf-8").replace('"Sera"', '"Serb"'), encoding="utf-8")   # one byte, still JSON
        json.loads(f.read_text(encoding="utf-8"))
        _, proof = self.assert_open()
        self.assertEqual(proof["broken"], 1)
        self.assertEqual(proof["sealed"], 50)

    def test_p1_2_a_malformed_ledger_line_is_broken(self):
        self.seal()
        self.append("{")
        _, proof = self.assert_open()
        self.assertEqual(proof["broken"], 1)
        rc, out = self.verify_all()
        self.assertEqual(rc, 1)
        self.assertIn("BROKEN", out)

    def test_p1_2_a_line_without_an_id_is_broken(self):
        self.seal()
        self.append('{"quest": "001"}')
        self.assert_open()
        self.assertEqual(self.verify_all()[0], 1)

    def test_p1_2_a_trailing_duplicate_id_with_a_changed_hash_is_broken(self):
        _, rid = self.seal()
        first = json.loads(self.ledger().read_text(encoding="utf-8").splitlines()[0])
        self.append(json.dumps(dict(first, hash="0" + first["hash"][1:] if first["hash"][0] != "0" else "1" + first["hash"][1:])))
        _, proof = self.assert_open()
        self.assertGreaterEqual(proof["broken"], 1)
        self.assertFalse(ac.verify_record(self.repo, rid)["ok"])
        self.assertEqual(self.verify_all()[0], 1)

    def test_p1_3_a_record_that_is_no_longer_an_object_does_not_raise(self):
        _, rid = self.seal()
        self.assertTrue(self.step6()["done"])
        f = self.record(rid)
        f.write_text("[" + f.read_text(encoding="utf-8")[1:], encoding="utf-8")
        self.assertFalse(ac.verify_record(self.repo, rid)["ok"])
        _, proof = self.assert_open()
        self.assertEqual(proof["broken"], 1)

    def test_p1_3_a_record_that_is_json_but_not_an_object_does_not_raise(self):
        _, rid = self.seal()
        self.record(rid).write_text("[1, 2]", encoding="utf-8")
        self.assertFalse(ac.verify_record(self.repo, rid)["ok"])
        self.assert_open()

    def test_p1_3_a_null_ledger_line_does_not_raise(self):
        self.seal()
        self.append("null")
        _, proof = self.assert_open()
        self.assertEqual(proof["broken"], 1)
        self.assertEqual(self.verify_all()[0], 1)

    def test_p2_a_an_unsigned_record_beside_a_good_seal_is_not_done(self):
        self.seal()
        _, rid = self.seal()
        f = self.record(rid)
        rec = json.loads(f.read_text(encoding="utf-8"))
        for k in ("sig", "sig_ed25519", "signer"):
            rec.pop(k, None)
        f.write_text(json.dumps(rec), encoding="utf-8")
        self.assertTrue(ac.verify_record(self.repo, rid)["ok"])     # intact content, but nothing proves who sealed it
        _, proof = self.assert_open()
        self.assertEqual(proof["unverified"], 1)

    def test_p2_b_world_state_verifies_each_record_once(self):
        for _ in range(3):
            self.seal()
        with mock.patch.object(ac, "verify_record", wraps=ac.verify_record) as v:
            ac.world_state(self.repo)
        self.assertEqual(v.call_count, 3)


if __name__ == "__main__":
    unittest.main()
