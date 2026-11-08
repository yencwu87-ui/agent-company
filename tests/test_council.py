"""Review Council: brief, scoring bands, ruin and one-way-door caps, unanimity warning, agent files, sealing."""
import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from test_proof import Base, quiet, ac  # noqa: E402
import council as C  # noqa: E402


def card(seat, a, b, c, **kw):
    return {"seat": seat, "scores": {"A": a, "B": b, "C": c}, "stance": f"{seat} view", "confidence": kw.pop("confidence", 4), **kw}


class Council(Base):
    def make(self, cards_by_round, weights=None, board=None, options=None):
        f = C.init(ac.ops_dir(str(self.repo)), "Ship drop 54?", options or {"A": "Ship it now", "B": "Fix F1 and F2, then ship", "C": "Don't do it"},
                   board or ["goal", "breaker", "claims", "guardian"], weights or {"goal": 3, "breaker": 2})
        for n, cards in cards_by_round.items():
            (f / f"round-{n}.json").write_text(json.dumps(cards))
        return f

    def test_brief_keeps_the_guardian_and_checks_weights(self):
        f = C.init(ac.ops_dir(str(self.repo)), "x", {"A": "go", "B": "don't do it"}, ["goal", "buyer"], None)
        self.assertIn("guardian", json.loads((f / "brief.json").read_text())["board"])
        with self.assertRaises(ValueError):
            C.init(ac.ops_dir(str(self.repo)), "y", {"A": "go"}, None, None)
        with self.assertRaises(ValueError):
            C.init(ac.ops_dir(str(self.repo)), "z", {"A": "go", "B": "no"}, ["goal"], {"goal": 5})
        g = C.init(ac.ops_dir(str(self.repo)), "self", None, None, None, "self-eval")
        self.assertEqual(json.loads((g / "brief.json").read_text())["options"], C.SELF_EVAL_OPTIONS)

    def test_weighted_score_and_band(self):
        f = self.make({1: [card("goal", 5, 8, 2), card("breaker", 3, 7, 4), card("claims", 6, 8, 2), card("guardian", 4, 8, 3)]})
        v = C.score(f)
        self.assertEqual(v["recommended"], "B")
        self.assertEqual(v["option_scores"]["B"], round((3 * 8 + 2 * 7 + 8 + 8) / 7, 1))   # 7.7
        self.assertEqual(v["label"], "GO")
        self.assertTrue((f / "verdict.md").exists())

    def test_ruin_cap_until_mitigation_endorsed(self):
        cards = [card("goal", 9, 6, 1), card("breaker", 9, 6, 1), card("claims", 9, 6, 1), card("guardian", 6, 6, 1, ruin="likely")]
        f = self.make({1: cards})
        v = C.score(f)
        self.assertEqual((v["recommended"], v["label"]), ("A", "RESHAPE"))
        self.assertTrue(any("ruin cap" in o for o in v["overrides"]))
        cards[-1]["mitigation_endorsed"] = True
        (f / "round-3.json").write_text(json.dumps(cards))
        self.assertEqual(C.score(f)["label"], "GO")

    def test_one_way_door_cap_and_dont_do_it(self):
        f = self.make({1: [card("goal", 10, 1, 1, one_way=True), card("breaker", 6, 1, 1, one_way=True),
                           card("claims", 10, 1, 1, one_way=True), card("guardian", 9, 1, 1)]})
        self.assertEqual(C.score(f)["label"], "GO WITH CONDITIONS")
        g = self.make({1: [card("goal", 2, 3, 8), card("breaker", 2, 3, 9), card("claims", 1, 2, 8), card("guardian", 1, 1, 9)]})
        self.assertEqual(C.score(g)["label"], "DON'T DO IT")

    def test_unanimity_warning_and_bad_cards(self):
        f = self.make({1: [card("goal", 8, 5, 1), card("breaker", 8, 4, 1), card("claims", 9, 5, 1), card("guardian", 8, 5, 1)]})
        self.assertTrue(C.score(f)["unanimity_warning"])
        g = self.make({1: [card("goal", 11, 5, 1), card("breaker", 8, 4, 1)]})
        with self.assertRaises(ValueError):
            C.score(g)

    def test_cli_agents_score_seal_verify(self):
        made = C.agent_files(self.repo)
        self.assertEqual(len(made), len(C.SEATS))
        text = (self.repo / ".claude/agents/council-guardian.md").read_text()
        self.assertIn("tools: Read, Grep, Glob", text)
        self.assertEqual(ac.claim_hits([self.repo / ".claude/agents"]), [])
        f = self.make({1: [card("goal", 5, 8, 2), card("breaker", 3, 7, 4), card("claims", 6, 8, 2), card("guardian", 4, 8, 3)]})
        self.assertEqual(quiet(ac.main, ["council", "score", str(f), "--repo", str(self.repo)])[0], 0)
        self.assertEqual(quiet(ac.main, ["council", "seal", str(f), "--repo", str(self.repo)])[0], 0)
        rid = [l["id"] for l in ac._ledger(self.repo) if l["id"].startswith("council-")][0]
        r = ac.verify_record(self.repo, rid)
        self.assertTrue(r["sealed"])
        (f / "verdict.md").write_text("edited")
        self.assertFalse(ac.verify_record(self.repo, rid)["ok"])

    def test_council_fixes_from_its_own_review(self):
        ok = [card("goal", 5, 8, 2), card("breaker", 3, 7, 4), card("claims", 6, 8, 2), card("guardian", 4, 8, 3)]
        with self.assertRaises(ValueError):                       # one seat stuffing extra cards
            C.score(self.make({1: ok + [card("goal", 10, 1, 1)] * 5}))
        with self.assertRaises(ValueError):                       # ruin cleared before round 3
            C.score(self.make({1: ok[:3] + [card("guardian", 9, 1, 1, ruin="likely", mitigation_endorsed=True)]}))
        with self.assertRaises(ValueError):                       # a bool is not a score
            C.score(self.make({1: ok[:3] + [card("guardian", True, 1, 1)]}))
        f = self.make({1: ok})
        (f / "brief.md").write_text((f / "brief.md").read_text() + "\nThis is the best plan.\n")
        C.score(f)
        self.assertNotEqual(quiet(ac.main, ["council", "seal", str(f), "--repo", str(self.repo)])[0], 0)
        (f / "brief.md").write_text((f / "brief.md").read_text().replace("best", "chosen"))
        C.score(f)
        self.assertEqual(quiet(ac.main, ["council", "seal", str(f), "--repo", str(self.repo)])[0], 0)
        rid = [l["id"] for l in ac._ledger(self.repo) if l["id"].startswith("council-")][-1]
        (f / "round-1.json").write_text("[]")
        self.assertFalse(ac.verify_record(self.repo, rid)["ok"])

    def test_seal_refuses_a_hand_edited_verdict_and_claims_pass_repo_wide(self):
        f = self.make({1: [card("goal", 5, 8, 2), card("breaker", 3, 7, 4), card("claims", 6, 8, 2), card("guardian", 4, 8, 3)]})
        C.score(f)
        (f / "verdict.md").write_text("GO on A\n")
        self.assertNotEqual(quiet(ac.main, ["council", "seal", str(f), "--repo", str(self.repo)])[0], 0)
        C.score(f)
        (f / "round-1.json").write_text((f / "round-1.json").read_text() + " ")    # same second, different bytes
        self.assertNotEqual(quiet(ac.main, ["council", "seal", str(f), "--repo", str(self.repo)])[0], 0)
        self.assertEqual(ac.claim_hits([self.repo]), [])

    def test_harness_ignores_real_data_and_doctor_flags_it(self):
        hd = self.repo / "docs/ops/harness"; quiet(ac.cmd_harness, str(self.repo), False)
        (hd / "real_data_paths.txt").write_text("data/real\n"); (self.repo / "data/real").mkdir(parents=True)
        quiet(ac.cmd_harness, str(self.repo), False)
        self.assertIn("data/real", (self.repo / ".gitignore").read_text())
        row = next(c for c in ac.doctor(self.repo) if c["check"].startswith("Real data"))
        self.assertIs(row["ok"], False)

    def test_init_adds_the_gates_to_an_older_inbox_readme(self):
        ir = ac.ops_dir(str(self.repo)) / "inbox" / "README.md"
        ir.write_text("# Instruction inbox\n(older set-up)\n")
        quiet(ac.cmd_init, str(self.repo))
        text = ir.read_text()
        self.assertIn("## Review Council gates", text); self.assertIn("(older set-up)", text)
        self.assertEqual(text.count(": off"), 3)

    def test_an_abstaining_seat_is_left_out_and_named(self):
        f = self.make({1: [card("goal", 5, 8, 2), {"seat": "breaker", "abstain": True, "stance": "run halted before any probe"},
                           card("claims", 6, 8, 2), card("guardian", 4, 8, 3)]})
        v = C.score(f)
        self.assertEqual(v["option_scores"]["B"], round((2 * 8 + 8 + 8) / 4, 1))
        self.assertEqual(v["abstained"][0]["seat"], "breaker")
        self.assertIn("Abstained", (f / "verdict.md").read_text())
        g = self.make({1: [card("goal", 5, 8, 2)] + [{"seat": k, "abstain": True} for k in ("breaker", "claims", "guardian")]})
        with self.assertRaises(ValueError):
            C.score(g)


if __name__ == "__main__":
    unittest.main()
