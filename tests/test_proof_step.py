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

    # A seal that holds, in the shape verify_record returns (quest from the hashed record, checkable signature)
    GOOD = {"sealed": True, "ok": True, "quest": "001", "verdict": "approve", "tests_passed": True, "checks": [{"check": "signature", "ok": True}]}

    def test_no_record_is_not_done(self):
        self.assertFalse(self.proof_done([])["done"])

    def test_one_sealed_record_that_verifies_is_done(self):
        self.assertTrue(self.proof_done([self.GOOD])["done"])

    def test_a_record_changed_after_sealing_is_not_done(self):
        s = self.proof_done([{"sealed": False, "ok": False}])
        self.assertFalse(s["done"])
        self.assertIn("verify", s["how"])

    def test_one_broken_record_reopens_the_step_even_beside_a_good_one(self):
        self.assertFalse(self.proof_done([self.GOOD, {"sealed": False, "ok": False}])["done"])


# ---- real bytes on disk: no mocked verifier (Codex r1 on PR #9: P1-1, P1-2, P1-3, P2-a, P2-b)
import json  # noqa: E402
from argparse import Namespace  # noqa: E402
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

    def seal(self, quest="001", cmd="python3 ok.py", verdict="approve", pr=""):
        # No pull request by default: a PR link whose head can't be looked up keeps step 6 open (Codex r3, P1-2)
        a = Namespace(quest=quest, pr=pr, verdict=verdict, test_cmd=cmd, workdir="", evaluator="Sera", builder="Brannoc",
                      challenger="", defects=0, verifier="", timeout=60)
        rc, _ = quiet(ac.cmd_seal, str(self.repo), a)
        return rc, json.loads(self.ledger().read_text(encoding="utf-8").splitlines()[-1])["id"]


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
        station, proof = self.vault()
        self.assertEqual(proof["broken"], 0)
        self.assertNotEqual(station["state"], "done")
        self.assertEqual(self.verify_all()[0], 1)       # Codex r3 P2: no records means step 6 is not done, so verify . fails too

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
            station, proof = self.assert_open()
            self.assertEqual(proof["open_quests"], 1)
            self.assertIn("Quest 001: the pull request moved after sealing", station["how"])
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
    """An older poll must never overwrite a newer one, even when the newer one failed (Codex r3 P2). world.html is not
    run here (Playwright is missing), so this only checks the page's text: refresh() numbers every request it sends and
    applies an answer, or a failure, only from the newest request sent; the timer sends no new poll while one is out."""
    def page(self):
        return (Path(__file__).resolve().parents[1] / "ui" / "world.html").read_text(encoding="utf-8")

    def test_refresh_applies_only_the_newest_request_sent(self):
        page = self.page()
        body = page[page.index("async function refresh()"):]
        body = body[:body.index("\n")]
        self.assertIn("const my=++pollSeq", body)
        self.assertEqual(body.count("if(my!==pollSeq)return"), 2, "both the answer path and the failure path must check the newest request")
        self.assertNotIn("applied", body)

    def test_the_timer_does_not_stack_polls(self):
        self.assertIn("setInterval(()=>{if(!inflight)refresh()},3000)", self.page())


# ---- Codex r3 on PR #9 (scope set by Cowork): the latest review per quest decides; fail closed; one snapshot of all files
class ProofStepRound3(DiskHelpers):
    def how(self):
        return self.step6()["how"]

    def bump(self, s):
        return ("1" if s[0] != "1" else "2") + s[1:]

    # 1. the latest review per quest decides
    def test_r3_1_a_later_changes_review_reopens_the_quest(self):
        self.seal("001")
        self.seal("001", verdict="changes")
        station, proof = self.assert_open()
        self.assertIn("Quest 001: latest review requested changes; seal again after an approving review.", station["how"])
        self.assertEqual(self.verify_all()[0], 1)

    def test_r3_1_a_later_reject_reopens_the_quest(self):
        self.seal("001")
        self.seal("001", verdict="reject")
        self.assert_open()
        self.assertIn("Quest 001: latest review rejected it", self.how())

    def test_r3_1_a_later_seal_with_failing_tests_reopens_the_quest(self):
        self.seal("001")
        self.seal("001", cmd="python3 -c 'import sys; sys.exit(3)'")
        self.assert_open()
        self.assertIn("Quest 001: the latest seal's tests failed", self.how())

    def test_r3_1_an_approving_seal_after_changes_closes_the_quest(self):
        self.seal("001", verdict="changes")
        self.seal("001")
        self.assertTrue(self.step6()["done"])
        self.assertEqual(self.verify_all()[0], 0)

    def test_r3_1_every_quest_needs_its_own_holding_seal(self):
        self.seal("001")
        self.seal("002", verdict="changes")
        self.assert_open()
        self.assertIn("Quest 002", self.how())
        self.assertNotIn("Quest 001", self.how())

    def test_r3_1_a_trust_snapshot_alone_cannot_close_step_6(self):
        ac.seal_doc(self.repo.resolve(), "trust", {"agents": [], "guild_sha256": ""})
        self.assertTrue(ac.verify_record(self.repo, self.lines_ids()[-1])["sealed"])
        self.assert_open()
        self.assertEqual(self.verify_all()[0], 1)

    def test_r3_1_the_quest_comes_from_the_hashed_record_not_the_ledger_line(self):
        self.seal("002", verdict="changes")
        self.seal("001")
        ls = [json.loads(l) for l in self.ledger().read_text(encoding="utf-8").splitlines()]
        ls[0]["quest"] = "001"                   # the ledger line says 001; the hashed record says 002
        self.ledger().write_text("".join(json.dumps(l) + "\n" for l in ls), encoding="utf-8")
        self.assert_open()
        self.assertIn("Quest 002", self.how())

    def lines_ids(self):
        return [json.loads(l)["id"] for l in self.ledger().read_text(encoding="utf-8").splitlines()]

    # 2. a PR lookup that fails is "not checked", never a pass
    def test_r3_2_a_pr_head_that_cannot_be_looked_up_keeps_step_6_open(self):
        with mock.patch.object(ac, "pr_head", return_value=(None, "couldn't reach the pull request")):
            self.seal("001", pr="https://github.com/o/r/pull/1")
            station, _ = self.assert_open()
            self.assertIn("PR head not checked: GitHub not reached", station["how"])
            rc, out = self.verify_all()
            self.assertEqual(rc, 1)
            self.assertIn("PR head not checked: GitHub not reached", out)

    def test_r3_2_a_pr_link_that_is_not_github_is_not_checked_either(self):
        self.seal("001", pr="https://example.test/pr/1")
        self.assert_open()
        self.assertIn("PR head not checked", self.how())

    def test_r3_2_a_pr_head_that_matches_closes_the_step(self):
        commit = subprocess.run(["git", "-C", str(self.repo), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
        with mock.patch.object(ac, "pr_head", return_value=(commit, "test")):
            self.seal("001", pr="https://github.com/o/r/pull/1")
            self.assertTrue(self.step6()["done"])
            self.assertEqual(self.verify_all()[0], 0)

    # 3. the ledger AND every record file are read once per refresh
    def test_r3_3_two_record_file_versions_in_one_refresh_cannot_add_up_to_done(self):
        _, a = self.seal("001")
        _, b = self.seal("002")
        good = {r: self.record(r).read_text(encoding="utf-8") for r in (a, b)}
        bad = {r: good[r].replace('"Sera"', '"Serb"') for r in (a, b)}
        self.record(b).write_text(bad[b], encoding="utf-8")        # version 1: A good, B changed
        real, calls = ac.verify_record, []

        def swap_after_first(*args, **kw):
            out = real(*args, **kw)
            calls.append(1)
            if len(calls) == 1:                                     # version 2: A changed, B good
                self.record(a).write_text(bad[a], encoding="utf-8")
                self.record(b).write_text(good[b], encoding="utf-8")
            return out
        with mock.patch.object(ac, "verify_record", side_effect=swap_after_first):
            w = ac.world_state(self.repo)
        self.assertEqual(w["proof"]["broken"], 1)                  # judged on version 1 alone: B is broken
        self.assertNotEqual({s["id"]: s for s in w["stations"]}["proof"]["state"], "done")

    def test_r3_3_each_record_file_is_read_once_per_refresh(self):
        for q in ("001", "002", "003"):
            self.seal(q)
        real, seen = ac.Path.read_bytes, []

        def counting(p):
            if p.name.endswith(".json") and p.parent.name == "evidence":
                seen.append(p.name)
            return real(p)
        with mock.patch.object(ac.Path, "read_bytes", counting):
            ac.world_state(self.repo)
        self.assertEqual(sorted(seen), sorted(set(seen)))
        self.assertEqual(len(seen), 3)

    def test_r3_3_a_record_file_renamed_to_another_valid_id_is_broken(self):
        _, a = self.seal("001")
        other = "001-" + self.bump(a[4:])
        self.record(a).rename(self.record(other))
        ls = self.ledger().read_text(encoding="utf-8").replace(a, other)
        self.ledger().write_text(ls, encoding="utf-8")
        _, proof = self.assert_open()
        self.assertEqual(proof["broken"], 1)

    # 4. an HMAC record this machine can't check names the fix
    def test_r3_4_an_hmac_record_not_checkable_here_names_cosign(self):
        self.seal("001")
        _, b = self.seal("002")
        f = self.record(b)
        rec = json.loads(f.read_text(encoding="utf-8"))
        rec.pop("sig_ed25519", None); rec.pop("signer", None)      # an older record: HMAC only
        f.write_text(json.dumps(rec), encoding="utf-8")
        ac.KEY_FILE = Path(self.tmp.name) / "not-this-machines.key"
        station, proof = self.assert_open()
        self.assertEqual(proof["unverified"], 1)
        self.assertIn("Run `agent_company.py cosign` on the machine that sealed it.", station["how"])
        self.assertEqual(self.verify_all()[0], 1)

    # 5. the CLI and the World agree
    def test_r3_5_an_empty_ledger_is_not_done_and_verify_fails(self):
        self.assert_open()
        rc, out = self.verify_all()
        self.assertEqual(rc, 1)
        self.assertIn("no evidence records yet", out)

    def test_r3_5_a_failing_rerun_reopens_the_world_until_a_passing_rerun(self):
        self.seal("001")
        self.assertTrue(self.step6()["done"])
        (self.repo / "ok.py").write_text("import sys\nsys.exit(4)\n")
        self.assertEqual(quiet(ac.cmd_verify, str(self.repo), None, True, False)[0], 1)
        station, _ = self.assert_open()
        self.assertIn("Quest 001: the tests failed when re-run", station["how"])
        (self.repo / "ok.py").write_text("print('ok')\n")
        self.assertEqual(quiet(ac.cmd_verify, str(self.repo), None, True, False)[0], 0)
        self.assertTrue(self.step6()["done"])


if __name__ == "__main__":
    unittest.main()
