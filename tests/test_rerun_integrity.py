"""verify --rerun runs a record's test command only while the record is intact (hash, chain, signature, schema)."""
import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from test_proof import Base, git  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import agent_company as ac  # noqa: E402


class RerunIntegrity(Base):
    def setUp(self):
        super().setUp()
        (self.repo / "mark.py").write_text("open('runs.txt', 'a').write('x')\n")
        git(self.repo, "add", "mark.py"); git(self.repo, "commit", "-qm", "mark")

    def runs(self):
        p = self.repo / "runs.txt"
        return len(p.read_text()) if p.exists() else 0

    def rerun_check(self, v):
        return next(c for c in v["checks"] if c["check"] == "re-run")

    def test_an_intact_record_is_re_run(self):
        _, rid = self.seal(cmd="python3 mark.py")
        self.assertEqual(self.runs(), 1)
        v = ac.verify_record(self.repo, rid, rerun=True)
        self.assertEqual(self.runs(), 2)
        self.assertTrue(self.rerun_check(v)["ok"])
        self.assertTrue(v["sealed"])

    def test_a_record_whose_command_was_edited_is_not_run(self):
        _, rid = self.seal(cmd="python3 mark.py")
        f = self.repo / "docs/ops/evidence" / f"{rid}.json"
        rec = json.loads(f.read_text()); rec["tests"]["cmd"] = "python3 -c \"open('edited.txt','w').write('ran')\""; f.write_text(json.dumps(rec))
        v = ac.verify_record(self.repo, rid, rerun=True)
        self.assertFalse((self.repo / "edited.txt").exists(), "the edited command ran")
        self.assertEqual(self.runs(), 1)
        c = self.rerun_check(v)
        self.assertIsNot(c["ok"], True)
        self.assertIn("not re-run", c["note"])
        self.assertFalse(v["ok"])

    def test_a_record_missing_from_the_ledger_is_not_run(self):
        _, rid = self.seal(cmd="python3 mark.py")
        (self.repo / "docs/ops/evidence/ledger.jsonl").write_text("")
        v = ac.verify_record(self.repo, rid, rerun=True)
        self.assertEqual(self.runs(), 1)
        self.assertIsNot(self.rerun_check(v)["ok"], True)

    def test_a_forged_unsigned_record_is_not_run(self):
        """Rewrite the record and its ledger line consistently, but drop the signatures: hash and chain hold, the signature
        can't be checked, so the command must not run."""
        import hashlib
        _, rid = self.seal(cmd="python3 mark.py")
        ev = self.repo / "docs/ops/evidence"
        rec = json.loads((ev / f"{rid}.json").read_text())
        rec["tests"]["cmd"] = "python3 -c \"open('forged.txt','w').write('ran')\""
        for k in ("sig", "sig_ed25519", "signer"):
            rec.pop(k, None)
        h = hashlib.sha256(ac._canon(rec)).hexdigest()
        new = f"{rec['quest']}-{h[:12]}"
        rec["hash"], rec["id"] = h, new
        (ev / f"{rid}.json").unlink(); (ev / f"{new}.json").write_text(json.dumps(rec))
        led = [json.loads(l) for l in (ev / "ledger.jsonl").read_text().splitlines() if l.strip()]
        led[-1]["id"], led[-1]["hash"] = new, h
        (ev / "ledger.jsonl").write_text("".join(json.dumps(l) + "\n" for l in led))
        v = ac.verify_record(self.repo, new, rerun=True)
        self.assertTrue(next(c for c in v["checks"] if c["check"] == "hash")["ok"])
        self.assertFalse((self.repo / "forged.txt").exists(), "the forged command ran")
        self.assertIsNot(self.rerun_check(v)["ok"], True)


if __name__ == "__main__":
    unittest.main()
