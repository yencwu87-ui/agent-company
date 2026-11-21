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
             mock.patch.object(ac, "_read_ledger", return_value=lines, create=True), \
             mock.patch.object(ac, "verify_record", side_effect=lambda root, rid, *a, **kw: by_id[rid]):
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


class DiskHelpers(Base):
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


class ProofStepOnDisk(DiskHelpers):
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


# ---- Codex r2 on PR #9: real bytes on disk again; only the network (pr_head) is ever stubbed
from argparse import Namespace  # noqa: E402


class ProofStepRound2(DiskHelpers):
    def unsign(self, rid):
        f = self.record(rid)
        rec = json.loads(f.read_text(encoding="utf-8"))
        for k in ("sig", "sig_ed25519", "signer"):
            rec.pop(k, None)
        f.write_text(json.dumps(rec), encoding="utf-8")

    def seal_pr(self, pr):
        a = Namespace(quest="001", pr=pr, verdict="approve", test_cmd="python3 ok.py", workdir="", evaluator="Sera", builder="Brannoc",
                      challenger="", defects=0, verifier="", timeout=60)
        quiet(ac.cmd_seal, str(self.repo), a)
        return json.loads(self.ledger().read_text(encoding="utf-8").splitlines()[-1])["id"]

    def lines(self):
        return self.ledger().read_text(encoding="utf-8").splitlines()

    def write_lines(self, lines):
        self.ledger().write_text("".join(l + "\n" for l in lines), encoding="utf-8")

    # P1-1: an unreadable ledger
    def test_r2_p1_1_an_undecodable_byte_in_the_ledger_opens_the_step(self):
        self.seal()
        with open(self.ledger(), "ab") as fh:
            fh.write(b"\xff\n")
        _, proof = self.assert_open()
        self.assertGreaterEqual(proof["broken"], 1)
        rc, out = self.verify_all()
        self.assertEqual(rc, 1)
        self.assertIn("ledger unreadable", out)

    def test_r2_p1_1_a_ledger_that_is_a_directory_opens_the_step(self):
        self.seal()
        self.ledger().unlink()
        self.ledger().mkdir()
        _, proof = self.assert_open()
        self.assertGreaterEqual(proof["broken"], 1)
        rc, out = self.verify_all()
        self.assertEqual(rc, 1)
        self.assertIn("ledger unreadable", out)

    # P1-2: a record file whose ledger line is gone
    def test_r2_p1_2_a_tail_line_blanked_to_spaces_does_not_hide_its_record(self):
        self.seal()
        _, b = self.seal()
        self.unsign(b)
        ls = self.lines()
        self.write_lines(ls[:-1] + ["   "])
        _, proof = self.assert_open()
        self.assertGreaterEqual(proof["broken"], 1)
        rc, out = self.verify_all()
        self.assertEqual(rc, 1)
        self.assertIn(f"record file not in the ledger: {b}.json", out)

    def test_r2_p1_2_a_deleted_tail_line_does_not_hide_its_record(self):
        self.seal()
        _, b = self.seal()
        self.unsign(b)
        self.write_lines(self.lines()[:-1])
        _, proof = self.assert_open()
        self.assertEqual(proof["broken"], 1)
        rc, out = self.verify_all()
        self.assertEqual(rc, 1)
        self.assertIn(f"record file not in the ledger: {b}.json", out)

    def test_r2_p1_2_a_blank_line_inside_the_ledger_is_broken(self):
        self.seal()
        self.append("  ")
        _, proof = self.assert_open()
        self.assertEqual(proof["broken"], 1)
        self.assertEqual(self.verify_all()[0], 1)

    def test_r2_p1_2_a_ledger_of_only_blank_lines_with_no_records_is_empty(self):
        (self.repo / "docs/ops/evidence").mkdir(parents=True, exist_ok=True)
        self.ledger().write_text("\n  \n", encoding="utf-8")
        _, proof = self.vault()
        self.assertEqual(proof["broken"], 0)
        self.assertEqual(self.verify_all()[0], 0)

    # P1-3: one snapshot per refresh
    def test_r2_p1_3_world_state_reads_the_ledger_once(self):
        for _ in range(3):
            self.seal()
        with mock.patch.object(ac, "_read_ledger", wraps=ac._read_ledger) as r:
            ac.world_state(self.repo)
        self.assertEqual(r.call_count, 1)

    def test_r2_p1_3_two_ledger_versions_in_one_refresh_cannot_add_up_to_done(self):
        self.seal()
        self.seal()
        a, b = [json.loads(l) for l in self.lines()]
        v1 = [json.dumps(a), json.dumps(dict(b, prev="1" + b["prev"][1:] if b["prev"][0] != "1" else "2" + b["prev"][1:]))]   # B broken
        v2 = [json.dumps(dict(a, prev="1" + a["prev"][1:])), json.dumps(b)]                                                     # A broken
        self.write_lines(v1)
        real, calls = ac.verify_record, []

        def swap_after_first(*args, **kw):
            out = real(*args, **kw)
            calls.append(1)
            if len(calls) == 1:
                self.write_lines(v2)
            return out
        with mock.patch.object(ac, "verify_record", side_effect=swap_after_first):
            w = ac.world_state(self.repo)
        self.assertEqual(w["proof"]["sealed"] + w["proof"]["broken"], 2)
        self.assertGreaterEqual(w["proof"]["broken"], 1)        # judged against v1 alone: B is broken
        self.assertNotEqual({s["id"]: s for s in w["stations"]}["proof"]["state"], "done")

    # P1-4 and P2-a: the CLI and the World agree
    def moved(self, root, pr):
        return ("f" * 40, "test") if pr.endswith("/2") else (None, "unreachable in this test")

    def test_r2_p1_4_a_pr_that_moved_after_sealing_keeps_the_step_open(self):
        self.seal()
        self.seal_pr("https://example.test/pr/2")
        with mock.patch.object(ac, "pr_head", side_effect=self.moved):
            _, proof = self.assert_open()
            self.assertEqual(proof["not_sealable"], 1)
            rc, out = self.verify_all()
            self.assertEqual(rc, 1)
            self.assertIn("INTACT, NOT SEALABLE", out)
            rc, _ = quiet(ac.cmd_verify, str(self.repo), None, False, True)
            self.assertEqual(rc, 1)

    def test_r2_p2_a_verify_exits_1_beside_an_unsigned_record_in_text_and_json(self):
        self.seal()
        _, b = self.seal()
        self.unsign(b)
        self.assertEqual(self.verify_all()[0], 1)
        self.assertEqual(quiet(ac.cmd_verify, str(self.repo), None, False, True)[0], 1)

    def test_r2_verify_exits_0_when_step_6_is_done(self):
        self.seal()
        self.assertEqual(self.verify_all()[0], 0)
        self.assertEqual(quiet(ac.cmd_verify, str(self.repo), None, False, True)[0], 0)

    # P3: the whole World goes from DONE to open after one byte
    def test_r2_p3_the_world_shows_done_then_open_after_a_byte_edit(self):
        from test_cli import GOOD
        ops = self.repo / "docs" / "ops"
        ac.deploy_files(ops, [["inbox/001_add-rate-limiting.md", GOOD]], None,
                        {"heroes": {"h1": {"name": "Brannoc", "cls": "artificer", "origin": "Claude Code", "lv": 2},
                                    "h2": {"name": "Ysolde", "cls": "paladin", "origin": "Codex", "lv": 1}}})
        ac.install_harness(self.repo)
        self.assertNotIn("error", ac.commit_harness(self.repo))
        (ops / "outbox" / "STATUS.md").write_text("# Status\n\nTime: 2026-11-21 10:00 SGT\n", encoding="utf-8")
        _, rid = self.seal()
        states = {s["id"]: s["state"] for s in ac.world_state(self.repo)["stations"]}
        self.assertEqual(states, {k: "done" for k in states})
        f = self.record(rid)
        f.write_text(f.read_text(encoding="utf-8").replace('"Sera"', '"Serb"'), encoding="utf-8")
        states = {s["id"]: s["state"] for s in ac.world_state(self.repo)["stations"]}
        self.assertEqual(states["proof"], "next")
        self.assertEqual({states[k] for k in ("setup", "team", "harness", "orders", "run")}, {"done"})


class WorldPagePolls(unittest.TestCase):
    """P2-b: an older poll must never overwrite a newer one. world.html is not run here (Playwright is missing), so this
    only checks that refresh() numbers its polls and drops a response older than the newest one applied."""
    def test_refresh_numbers_its_polls_and_drops_stale_answers(self):
        page = (Path(__file__).resolve().parents[1] / "ui" / "world.html").read_text(encoding="utf-8")
        body = page[page.index("async function refresh()"):]
        body = body[:body.index("\n")]
        self.assertIn("const my=++pollSeq", body)
        self.assertEqual(body.count("if(my<=applied)return"), 2, "both the answer path and the connection-lost path must drop stale polls")
        self.assertIn("applied=my", body)


if __name__ == "__main__":
    unittest.main()
