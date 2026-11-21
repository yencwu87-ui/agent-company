"""verify --rerun runs a record's test command only while the record is intact (hash, chain, signature, schema)."""
import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from test_proof import Base, git, quiet  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import agent_company as ac  # noqa: E402


class Marked(Base):
    """A repo whose test command, `python3 mark.py`, leaves one mark in runs.txt each time it runs."""
    def setUp(self):
        super().setUp()
        (self.repo / "mark.py").write_text("open('runs.txt', 'a').write('x')\n")
        (self.repo / ".gitignore").write_text("runs.txt\n")
        git(self.repo, "add", "-A"); git(self.repo, "commit", "-qm", "mark")   # a clean tree at the sealed commit

    def runs(self):
        p = self.repo / "runs.txt"
        return len(p.read_text()) if p.exists() else 0

    def rerun_check(self, v):
        return next(c for c in v["checks"] if c["check"] == "re-run")


class RerunIntegrity(Marked):

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


NO_TRUST = "not re-run: no signer list outside this repository trusts this record's key; pass --signers or cosign on the sealing machine."
LIMIT = "signers read from this repository's own list; anyone who can edit the evidence can edit it."
MOVED = "re-ran the sealed commit; its pull request has since moved."
DIRTY = ("not re-run: the working tree has uncommitted or untracked changes; commit or stash them, "
         "so the command runs on the sealed commit alone.")


def in_repo(p):
    return f"not re-run: the --signers file {p} is inside this repository; pass a signer list kept outside it."


class RerunTrustAnchor(Marked):
    """Cowork's second opinion on PR #10: --rerun executes code, so the record's key must be trusted from outside the checkout.
    Every key here lives in the test's temporary folder (Base moves KEY_FILE and ED_KEY there), never in the real home."""

    def user_list(self):
        return ac._user_signers()

    def pub(self):
        return " ".join(ac.ED_KEY.with_suffix(".pub").read_text().split()[:2])

    def fingerprint(self):
        return ac._ed_fingerprint(self.pub())

    def reseal(self, rid, change):
        """Change a record, then rehash, rechain and re-sign it with the current keys, so only `change` differs."""
        import hashlib
        import hmac
        ev = self.repo / "docs/ops/evidence"
        rec = json.loads((ev / f"{rid}.json").read_text())
        change(rec)
        for k in ("sig", "sig_ed25519", "signer"):
            rec.pop(k, None)
        h = hashlib.sha256(ac._canon(rec)).hexdigest()
        new = f"{rec['quest']}-{h[:12]}"
        rec["hash"], rec["id"] = h, new
        rec["sig"] = hmac.new(ac._key(True), h.encode(), hashlib.sha256).hexdigest()
        rec.update(ac._ed_sign(self.repo, h))
        (ev / f"{rid}.json").unlink(); (ev / f"{new}.json").write_text(json.dumps(rec))
        led = [json.loads(l) for l in (ev / "ledger.jsonl").read_text().splitlines() if l.strip()]
        led[-1]["id"], led[-1]["hash"] = new, h
        (ev / "ledger.jsonl").write_text("".join(json.dumps(l) + "\n" for l in led))
        return new

    # P1: the trust anchor
    def test_the_per_user_list_sits_beside_the_keys_not_in_the_real_home(self):
        self.assertEqual(self.user_list(), Path(self.tmp.name) / "allowed_signers")

    def test_seal_adds_its_own_key_to_the_per_user_list(self):
        self.seal(cmd="python3 mark.py")
        text = self.user_list().read_text()
        self.assertIn(self.pub(), text)
        self.assertIn('namespaces="openproof-evidence"', text)

    def test_cosign_adds_its_own_key_to_the_per_user_list(self):
        real = ac._ssh_keygen
        ac._ssh_keygen = lambda: None                      # seal with HMAC only, as before 0.6.1
        try:
            _, rid = self.seal(cmd="python3 mark.py")
        finally:
            ac._ssh_keygen = real
        self.assertFalse(self.user_list().exists())
        quiet(ac.cmd_cosign, str(self.repo), rid)
        self.assertIn(self.pub(), self.user_list().read_text())

    def test_no_outside_list_means_no_rerun(self):
        _, rid = self.seal(cmd="python3 mark.py")
        self.user_list().unlink()                          # only the repository's own list holds the key
        v = ac.verify_record(self.repo, rid, rerun=True)
        self.assertEqual(self.runs(), 1)
        self.assertEqual(self.rerun_check(v)["note"], NO_TRUST)
        self.assertIsNone(self.rerun_check(v)["ok"])
        self.assertTrue(ac.verify_record(self.repo, rid)["sealed"], "plain verify still uses the repository's list")

    def test_a_key_only_the_repository_list_trusts_is_not_run(self):
        """An editor adds their own key to docs/ops/evidence/allowed_signers and signs a rewritten record with it."""
        _, rid = self.seal(cmd="python3 mark.py")
        owner_key = ac.ED_KEY
        ac.ED_KEY = Path(self.tmp.name) / "intruder" / "seal_ed25519"; ac.ED_KEY.parent.mkdir()
        new = self.reseal(rid, lambda r: r["tests"].update(cmd="python3 -c \"open('intruder.txt','w').write('ran')\""))
        ac.ED_KEY = owner_key                              # back on the owner's machine: her own list doesn't hold that key
        v = ac.verify_record(self.repo, new, rerun=True)
        self.assertTrue(next(c for c in v["checks"] if c["check"] == "signature")["ok"])
        self.assertFalse((self.repo / "intruder.txt").exists(), "a key only the repository trusts ran its command")
        self.assertEqual(self.rerun_check(v)["note"], NO_TRUST)

    def test_signers_inside_the_repository_are_refused(self):
        _, rid = self.seal(cmd="python3 mark.py")
        inside = self.repo / "docs/ops/evidence/allowed_signers"
        v = ac.verify_record(self.repo, rid, rerun=True, signers=str(inside))
        self.assertEqual(self.runs(), 1)
        self.assertEqual(self.rerun_check(v)["note"], in_repo(inside.resolve()))

    def test_signers_outside_the_repository_are_accepted(self):
        _, rid = self.seal(cmd="python3 mark.py")
        outside = Path(self.tmp.name) / "trusted_signers"
        outside.write_text(self.user_list().read_text()); self.user_list().unlink()
        v = ac.verify_record(self.repo, rid, rerun=True, signers=str(outside))
        self.assertEqual(self.runs(), 2)
        self.assertTrue(self.rerun_check(v)["ok"])

    def test_plain_verify_prints_the_repository_list_limit_once(self):
        self.seal(cmd="python3 mark.py"); self.seal(quest="002", cmd="python3 mark.py")
        _, out = quiet(ac.cmd_verify, str(self.repo), None, False, False)
        self.assertEqual(out.count(LIMIT), 1)
        outside = Path(self.tmp.name) / "trusted_signers"; outside.write_text(self.user_list().read_text())
        _, out = quiet(ac.cmd_verify, str(self.repo), None, False, False, str(outside))
        self.assertNotIn(LIMIT, out)

    # P2: identical ledger rows
    def test_identical_ledger_rows_run_once(self):
        self.seal(cmd="python3 mark.py")
        led = self.repo / "docs/ops/evidence/ledger.jsonl"
        row = led.read_text().splitlines()[-1]
        led.write_text(led.read_text() + row + "\n" + row + "\n")
        quiet(ac.cmd_verify, str(self.repo), None, True, False)
        self.assertEqual(self.runs(), 2, "the same record was re-run more than once")

    # P2: the pull request moved after sealing
    def test_a_moved_pull_request_still_reruns_with_a_note(self):
        _, rid = self.seal(cmd="python3 mark.py")
        real = ac.pr_head
        ac.pr_head = lambda root, pr: ("f" + "0" * 39, "test")
        try:
            v = ac.verify_record(self.repo, rid, rerun=True)
        finally:
            ac.pr_head = real
        self.assertEqual(self.runs(), 2)
        self.assertIn(MOVED, self.rerun_check(v)["note"])

    # P2: the success message names the key that matched, never the record's own claim
    def test_success_names_the_matched_key_not_the_records_signer_field(self):
        _, rid = self.seal(cmd="python3 mark.py")
        f = self.repo / "docs/ops/evidence" / f"{rid}.json"
        rec = json.loads(f.read_text()); rec["signer"] = "SHA256:claimed-by-the-record"; f.write_text(json.dumps(rec))
        v = ac.verify_record(self.repo, rid, rerun=True)
        self.assertEqual(self.runs(), 2)
        note = self.rerun_check(v)["note"]
        self.assertEqual(note, f"exit 0 now; key {self.fingerprint()} matched in {self.user_list()}")
        sig = next(c for c in v["checks"] if c["check"] == "signature")["note"]
        self.assertNotIn("claimed-by-the-record", sig + note)
        self.assertIn(self.fingerprint(), sig)

    # P3: the working tree
    def test_a_changed_tracked_file_means_no_rerun(self):
        _, rid = self.seal(cmd="python3 mark.py")
        (self.repo / "mark.py").write_text("open('dirty.txt', 'w').write('ran')\n")
        v = ac.verify_record(self.repo, rid, rerun=True)
        self.assertFalse((self.repo / "dirty.txt").exists(), "a changed working tree ran")
        self.assertEqual(self.rerun_check(v)["note"], DIRTY)

    def test_an_untracked_file_means_no_rerun(self):
        _, rid = self.seal(cmd="python3 mark.py")
        (self.repo / "conftest.py").write_text("x = 1\n")
        v = ac.verify_record(self.repo, rid, rerun=True)
        self.assertEqual(self.runs(), 1)
        self.assertEqual(self.rerun_check(v)["note"], DIRTY)

    # P3: the checks that had no isolated test
    def test_a_wrong_schema_version_is_not_run(self):
        _, rid = self.seal(cmd="python3 mark.py")
        new = self.reseal(rid, lambda r: r.update(schema="openproof.evidence/v0"))
        v = ac.verify_record(self.repo, new, rerun=True)
        by = {c["check"]: c["ok"] for c in v["checks"]}
        self.assertEqual((by["schema"], by["hash"], by["chain"], by["signature"]), (False, True, True, True))
        self.assertEqual(self.runs(), 1)
        self.assertIn("not re-run", self.rerun_check(v)["note"])

    def test_a_key_outside_the_selected_list_is_not_run(self):
        _, rid = self.seal(cmd="python3 mark.py")
        owner_key = ac.ED_KEY
        ac.ED_KEY = Path(self.tmp.name) / "other" / "seal_ed25519"; ac.ED_KEY.parent.mkdir(); ac._ed_key(True)
        other = Path(self.tmp.name) / "other_signers"
        other.write_text(f'owner namespaces="openproof-evidence" {self.pub()}\n')
        ac.ED_KEY = owner_key
        v = ac.verify_record(self.repo, rid, rerun=True, signers=str(other))
        self.assertIs(next(c for c in v["checks"] if c["check"] == "signature")["ok"], False)
        self.assertEqual(self.runs(), 1)
        self.assertIn("not re-run", self.rerun_check(v)["note"])


if __name__ == "__main__":
    unittest.main()
