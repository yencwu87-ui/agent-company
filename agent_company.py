#!/usr/bin/env python3
"""Agent Company: run a company of AI agents as one orchestrated team.

Standard library only (Python 3.9+). Works with any agent tool that reads files.

    python3 agent_company.py launch [folder]           START HERE: makes the folder, git and setup, then opens the Guild
    python3 agent_company.py doctor [repo]             plain-language checks, each with the fix
    python3 agent_company.py smoke  [repo]             one PASS/FAIL gate: doctor, instructions, ledger, harness
    python3 agent_company.py import-agents <folder>    Claude Code subagents (.claude/agents/*.md) become Guild characters
    python3 agent_company.py init   [repo]             create docs/ops (inbox, done, outbox, templates, ROLES.md)
    python3 agent_company.py ui     [repo] [--port N]  open the drag-and-drop Command map; Deploy writes into the repo
    python3 agent_company.py guild  [repo] [--port N]  open Guild mode (the game): forge, fit the harness, deploy, prove, train
    python3 agent_company.py check  [repo]             refuse instructions missing the owner's words, a branch, tests or a stop point
    python3 agent_company.py status [repo]             what is pending, in progress, done, and what needs the owner
    python3 agent_company.py start  [repo] [--tool claude|codex|gemini|cursor|copilot] [--run]
                                                       print (or run) the command that starts the coordinator
    python3 agent_company.py seal   [repo] --quest 001 --pr URL --verdict approve --test-cmd "pytest -q" [...]
                                                       re-run the tests and write a chained, signed evidence record
    python3 agent_company.py verify [repo] [record-id] [--rerun] [--json]
                                                       check a record (or the whole ledger): hash, chain, signature, commit
    python3 agent_company.py harness [repo] [--check]  install (or check) the six-piece harness in a repo
    python3 agent_company.py card   [repo] [agent] [--seal]   write Declaration Cards (and seal them into the ledger)
    python3 agent_company.py trust  [repo] [--json] [--seal]  trust credits per agent (and seal the export into the ledger)

Nothing here merges, pushes or deletes. Owner-only steps stay with a person.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import hashlib
import hmac
import json
import os
import shlex
import tempfile
import time
import re
import secrets
import shutil
import stat
import math
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
TEMPLATES = HERE / "templates"
UI = HERE / "ui" / "command.html"
GUILD = HERE / "ui" / "guild.html"
WORLD = HERE / "ui" / "world.html"
VENDOR = {"three.module.min.js", "OrbitControls.js", "RoundedBoxGeometry.js"}   # served from ui/vendor/three, nothing else
VERSION = "0.6.1"
HARNESS_SRC = Path(os.environ["AGENT_COMPANY_KIT"]) if os.environ.get("AGENT_COMPANY_KIT") else HERE / "harness"   # OpenProof's kit, when set

INBOX_README = """# Instruction inbox

The chief of staff writes one file per instruction: `NNN_short-name.md`.
The coordinator (exactly one session):
1. Reads inbox/ in number order, except this README, following each file's order notes.
2. Uses one worktree or branch per instruction, never the main folder and never a protected branch.
3. Has the named builder do it: failing tests first, then the change, the named tests, upload, a pull request, an evaluator brief. Never merges.
4. Sends the pull request to the named evaluator (and challenger, where named) and records their verdicts.
5. After an approving review, the evaluator seals the evidence: `python3 <agent-company>/agent_company.py seal . --quest NNN --pr <url> --verdict approve --evaluator <name> --builder <name> --test-cmd "<the named tests>"`. Seal re-runs the tests itself; a record whose tests fail can't be used for full credit.
6. Moves the instruction to done/ only after its pull request is merged (check the remote), and writes outbox/NNN_report.md with the record id.
7. Rewrites outbox/STATUS.md after every step, checked against the remote.
8. When blocked: writes the block into STATUS.md and stops. Never routes around a guard (docs/ops/harness/guard.py).
9. Never writes into inbox/ or evidence/: instructions come from the owner or the chief of staff outside the agents' sessions (or from the Guild's deploy), and evidence comes from `seal`. The guard refuses agent writes there; moving a finished instruction to done/ with `git mv` is allowed.

## Review Council gates (the owner switches each one on by changing off to on; see templates/council.md)
- decision council before a plan, for costly or hard-to-undo work: off
- self-eval council after the tests pass, before the pull request goes to the owner (4 to 8 sub-agent calls): off
- weekly retro council on sent-back work and escaped defects: off
"""

COORDINATOR_PROMPT = ("You are the coordinator. Follow docs/ops/inbox/README.md. Do every instruction in docs/ops/inbox/ "
                      "in number order. Update docs/ops/outbox/STATUS.md after each one. Never merge.")

NEEDED = {
    "the owner's words": re.compile(r"owner'?s? (words|decision|go)|^owner[, ]", re.I | re.M),
    "a branch": re.compile(r"^branch:|branch[: ]+`[^`]+`", re.I | re.M),
    "tests to run": re.compile(r"\btests?\b", re.I),
    "a stop point that says don't merge": re.compile(r"don'?t merge|do not merge", re.I),
}
PROTECTED = re.compile(r"^\W*branch\W*:\W*(?:origin/|refs/heads/|heads/)?(main|master|develop|release)(?=[/`'\"*\s.,;:)]|$)", re.I | re.M)


def ops_dir(repo: str | Path) -> Path:
    return Path(repo).resolve() / "docs" / "ops"


def write_new(path: Path, text: str) -> bool:
    """Write only if the file doesn't exist. Returns True when written."""
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


# ---------------------------------------------------------------- init
def cmd_init(repo: str) -> int:
    root = Path(repo).resolve()
    if not root.is_dir():
        print(f"no such folder: {root}")
        return 1
    ops = ops_dir(root)
    for d in ("inbox", "done", "outbox", "templates"):
        (ops / d).mkdir(parents=True, exist_ok=True)
    made = []
    ir = ops / "inbox" / "README.md"
    if ir.exists() and "## Review Council gates" not in ir.read_text(encoding="utf-8", errors="replace"):
        with open(ir, "a", encoding="utf-8") as f:                       # an older set-up gets the gates list, all off
            f.write("\n" + INBOX_README[INBOX_README.index("## Review Council gates"):])
        made.append("inbox/README.md (added the Review Council gates, all off)")
    if write_new(ir, INBOX_README):
        made.append("inbox/README.md")
    for t in sorted(TEMPLATES.glob("*.md")):
        if write_new(ops / "templates" / t.name, t.read_text(encoding="utf-8")):
            made.append("templates/" + t.name)
    if write_new(ops / "outbox" / "STATUS.md", (TEMPLATES / "status.md").read_text(encoding="utf-8")):
        made.append("outbox/STATUS.md")
    if write_new(ops / "ROLES.md", "# Roles (one agent per job)\n\nOpen the Command map (`agent_company.py ui`) and press Deploy to fill this in.\n"):
        made.append("ROLES.md")
    print(f"Agent Company {VERSION}: {ops}")
    print("  created: " + (", ".join(made) if made else "nothing (already set up; nothing overwritten)"))
    print("  next:    python3 agent_company.py ui " + str(root))
    return 0


# ---------------------------------------------------------------- check
def check_text(name: str, text: str) -> list[str]:
    problems = []
    if not re.match(r"^\d{3}_[a-z0-9-]+\.md$", name):
        problems.append("name must be NNN_short-name.md")
    problems += [f"missing {k}" for k, rx in NEEDED.items() if not rx.search(text)]
    if PROTECTED.search(text):
        problems.append("builds straight on a protected branch")
    return problems


def cmd_check(repo: str) -> int:
    inbox = ops_dir(repo) / "inbox"
    files = sorted(p for p in inbox.glob("*.md") if p.name.lower() != "readme.md")
    if not files:
        print("inbox empty")
        return 0
    bad = 0
    for p in files:
        probs = check_text(p.name, p.read_text(encoding="utf-8"))
        print(f"{p.name}: " + ("ok" if not probs else "; ".join(probs)))
        bad += bool(probs)
    return 1 if bad else 0


# ---------------------------------------------------------------- status
def cmd_status(repo: str) -> int:
    ops = ops_dir(repo)
    pend = sorted(p.name for p in (ops / "inbox").glob("[0-9]*.md"))
    done = sorted(p.name for p in (ops / "done").glob("[0-9]*.md"))
    print(f"pending ({len(pend)}): " + (", ".join(pend) or "none"))
    print(f"done    ({len(done)}): " + (", ".join(done) or "none"))
    st = ops / "outbox" / "STATUS.md"
    if st.exists():
        text = st.read_text(encoding="utf-8")
        m = re.search(r"^Time:.*$", text, re.M)
        print("status  : " + (m.group(0) if m else "STATUS.md has no time line"))
        need = re.search(r"^## (Needs the owner|Blocked)[^\n]*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
        if need:
            print("\n" + need.group(0).strip())
    else:
        print("status  : no outbox/STATUS.md yet (start the coordinator)")
    return 0


# ---------------------------------------------------------------- start
TOOLS = {
    "claude": ["claude", COORDINATOR_PROMPT],
    "codex": ["codex", COORDINATOR_PROMPT],
    "gemini": ["gemini", "-i", COORDINATOR_PROMPT],
}


def cmd_start(repo: str, tool: str, run: bool) -> int:
    root = Path(repo).resolve()
    if tool in ("cursor", "copilot"):
        print(f"{tool}: open {root} in the editor's agent chat and paste:\n\n  {COORDINATOR_PROMPT}")
        return 0
    argv = TOOLS[tool]
    shown = " ".join(a if " " not in a else json.dumps(a) for a in argv)
    if not run:
        print(f"cd {root}\n{shown}\n\n(add --run to start it now; run exactly one coordinator)")
        return 0
    if not shutil.which(argv[0]):
        print(f"{argv[0]} is not installed or not on PATH")
        return 1
    return subprocess.call(argv, cwd=root)



# ---------------------------------------------------------------- OpenProof evidence: seal and verify
# A record is canonical JSON with a SHA-256 over its content, chained to the previous record in
# docs/ops/evidence/ledger.jsonl, and signed with HMAC-SHA256 using a key that stays on this machine
# (~/.agent-company/seal.key). Tampering with a record breaks its hash; removing or reordering one breaks the
# chain; a record made without the key can't carry a valid signature. If OPENPROOF_VERIFY_CMD is set (or --verifier is
# given), that command is run with the record's path appended, and its result goes into the record.
SCHEMA = "openproof.evidence/v1"
KEY_FILE = Path(os.environ.get("AGENT_COMPANY_KEY", Path.home() / ".agent-company" / "seal.key"))


def _key(create: bool) -> bytes | None:
    if KEY_FILE.exists():
        return KEY_FILE.read_bytes().strip()
    if not create:
        return None
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    k = secrets.token_hex(32).encode()
    fd = os.open(str(KEY_FILE), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(k)
    return k


def _canon(rec: dict) -> bytes:
    body = {k: v for k, v in rec.items() if k not in ("hash", "sig", "id", "sig_ed25519", "signer")}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


# Ed25519 seals (0.6.1): signed with ssh-keygen, which ships with macOS, Linux and Windows 10+. Anyone with the repo can
# check them against docs/ops/evidence/allowed_signers, on any machine. The HMAC signature stays for older records.
ED_KEY = Path(os.environ.get("AGENT_COMPANY_ED25519", KEY_FILE.parent / "seal_ed25519"))
ED_NS = "openproof-evidence"
SIGNERS = "allowed_signers"


def _ssh_keygen() -> str | None:
    return shutil.which("ssh-keygen")


def _user_signers() -> Path:
    """This user's own signer list, beside the keys and outside every checkout (~/.agent-company/allowed_signers).
    seal and cosign add this machine's key to it; verify --rerun trusts only a list like this, or --signers."""
    return ED_KEY.parent / SIGNERS


def _add_signer(al: Path, pub: str, header: str) -> None:
    lines = al.read_text(encoding="utf-8").splitlines() if al.exists() else [header]
    if not any(pub in l for l in lines):
        al.parent.mkdir(parents=True, exist_ok=True)
        al.write_text("\n".join(lines + [f'owner namespaces="{ED_NS}" {pub}']) + "\n", encoding="utf-8")


def _ed_key(create: bool) -> Path | None:
    if ED_KEY.exists() and ED_KEY.with_suffix(".pub").exists():
        return ED_KEY
    if not create or not _ssh_keygen():
        return None
    ED_KEY.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([_ssh_keygen(), "-q", "-t", "ed25519", "-N", "", "-C", "agent-company seal", "-f", str(ED_KEY)], capture_output=True, text=True)
    return ED_KEY if r.returncode == 0 else None


def _ed_fingerprint(pub: str) -> str:
    with tempfile.NamedTemporaryFile("w", suffix=".pub", delete=False) as f:
        f.write(pub + "\n")
    try:
        out = subprocess.run([_ssh_keygen(), "-lf", f.name], capture_output=True, text=True).stdout.split()
        return out[1] if len(out) > 1 else ""
    finally:
        os.unlink(f.name)


def _ed_sign(root: Path, digest: str) -> dict:
    """{sig_ed25519, signer} for a record hash, and the signer's public key added to allowed_signers. {} if not possible."""
    key = _ed_key(True)
    if not key:
        return {}
    with tempfile.TemporaryDirectory() as d:
        msg = Path(d) / "hash"
        msg.write_text(digest, encoding="utf-8")
        r = subprocess.run([_ssh_keygen(), "-Y", "sign", "-f", str(key), "-n", ED_NS, str(msg)], capture_output=True, text=True)
        sig = Path(str(msg) + ".sig")
        if r.returncode != 0 or not sig.exists():
            return {}
        signature = sig.read_text(encoding="utf-8")
    pub = " ".join(key.with_suffix(".pub").read_text(encoding="utf-8").split()[:2])
    _add_signer(_evdir(root) / SIGNERS, pub, "# Public keys that may seal evidence here (Agent Company). Check the fingerprint with the owner.")
    _add_signer(_user_signers(), pub, "# Keys this user trusts to seal evidence (Agent Company). verify --rerun runs a record's command only "
                                      "when its key is here or in a --signers file outside the repository.")
    return {"sig_ed25519": signature, "signer": _ed_fingerprint(pub)}


def _ed_match(rec: dict, al: Path) -> str | None:
    """The fingerprint of the key in `al` that the record's Ed25519 signature verifies against, or None."""
    if not _ssh_keygen() or not al.is_file():
        return None
    with tempfile.TemporaryDirectory() as d:
        sig = Path(d) / "s.sig"
        sig.write_text(rec.get("sig_ed25519", ""), encoding="utf-8")
        r = subprocess.run([_ssh_keygen(), "-Y", "verify", "-f", str(al), "-I", "owner", "-n", ED_NS, "-s", str(sig)],
                           input=rec.get("hash", ""), capture_output=True, text=True)
    if r.returncode != 0:
        return None
    m = re.search(r"\bkey (SHA256:\S+)", r.stdout + r.stderr)
    return m.group(1) if m else "a key in the list"


def _ed_verify(root: Path, rec: dict, signers: str = "") -> tuple:
    """(True/False/None, note) for a record's Ed25519 signature. The note names the key that matched in the list,
    never the record's own `signer` field, which is outside the hash."""
    if not _ssh_keygen():
        return None, "ssh-keygen isn't on this machine, so the Ed25519 signature can't be checked here"
    al = Path(signers) if signers else _evdir(root) / SIGNERS
    if not al.exists():
        return False, f"no {al.name} to check the signature against"
    fp = _ed_match(rec, al)
    if fp:
        return True, f"Ed25519, key {fp} (checkable on any machine)"
    return False, "the Ed25519 signature doesn't match this hash and these allowed signers: the record or the key list was changed"


RERUN_NO_TRUST = ("not re-run: no signer list outside this repository trusts this record's key; "
                  "pass --signers or cosign on the sealing machine.")
RERUN_DIRTY = ("not re-run: the working tree has uncommitted or untracked changes; commit or stash them, "
               "so the command runs on the sealed commit alone.")
RERUN_MOVED = "re-ran the sealed commit; its pull request has since moved."
REPO_SIGNERS_LIMIT = "signers read from this repository's own list; anyone who can edit the evidence can edit it."


def _inside(root: Path, p: Path) -> bool:
    return any(q == root or root in q.parents for q in (Path(os.path.abspath(p)), p.resolve()))


def _rerun_trust(root: Path, rec: dict, signers: str) -> tuple:
    """(who, refusal): who vouches for the record from outside the checkout, or why nothing does.
    The HMAC key is this machine's own, so a record it verifies is already trusted from outside."""
    if not rec.get("sig_ed25519"):
        return "signed with this machine's HMAC key", ""
    if signers:
        al = Path(signers)
        if _inside(root.resolve(), al):
            return "", f"not re-run: the --signers file {al.resolve()} is inside this repository; pass a signer list kept outside it."
    else:
        al = _user_signers()
        if _inside(root.resolve(), al):
            return "", RERUN_NO_TRUST
    fp = _ed_match(rec, al)
    return (f"key {fp} matched in {al}", "") if fp else ("", RERUN_NO_TRUST)


def _dirty(root: Path, ev: Path) -> bool:
    """Uncommitted or untracked changes, ignored files aside. The evidence folder is left out: it is what is being checked,
    and its records are written after the commit they seal."""
    rel = os.path.relpath(ev, root)
    r = subprocess.run(["git", "-C", str(root), "status", "--porcelain", "--untracked-files=all", "--", ".", f":(exclude){rel}"],
                       capture_output=True, text=True)
    return r.returncode != 0 or bool(r.stdout.strip())


def _git(cwd: Path, *args: str) -> str:
    try:
        r = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, timeout=20)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _evdir(repo: str | Path) -> Path:
    d = ops_dir(repo) / "evidence"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _ledger(repo) -> list[dict]:
    f = ops_dir(repo) / "evidence" / "ledger.jsonl"
    if not f.exists():
        return []
    out = []
    for line in f.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except ValueError:
                out.append({"broken": line[:80]})
    return out


def _run(cmd: str, cwd: Path, timeout: int) -> dict:
    t0 = time.time()
    try:
        r = subprocess.run(shlex.split(cmd), cwd=str(cwd), capture_output=True, text=True, timeout=timeout)
        out, code = (r.stdout + r.stderr), r.returncode
    except subprocess.TimeoutExpired:
        out, code = f"timed out after {timeout}s", 124
    except (OSError, ValueError) as e:
        out, code = f"could not run: {e}", 127
    return {"cmd": cmd, "exit": code, "passed": code == 0, "seconds": round(time.time() - t0, 2),
            "output_sha256": hashlib.sha256(out.encode("utf-8", "replace")).hexdigest(), "tail": out[-1500:]}


PR_URL = re.compile(r"^https?://(?:www\.)?github\.com/([^/]+)/([^/]+)/pull/(\d+)")


def pr_head(root: Path, pr: str) -> tuple[str | None, str]:
    """The pull request's current head commit: `gh api` when gh is signed in, else `git ls-remote` on the matching remote."""
    m = PR_URL.match(pr or "")
    if not m:
        return None, "not a GitHub pull request link"
    owner, name, num = m.groups()
    gh = os.environ.get("AGENT_COMPANY_GH", "gh")
    if shutil.which(gh):
        try:
            r = subprocess.run([gh, "api", f"repos/{owner}/{name}/pulls/{num}", "--jq", ".head.sha"], capture_output=True, text=True, timeout=15)
            sha = r.stdout.strip()
            if r.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", sha):
                return sha, "GitHub API (gh)"
        except (OSError, subprocess.SubprocessError):
            pass
    for remote in _git(root, "remote").split():
        url = _git(root, "remote", "get-url", remote).rstrip("/")
        base = re.sub(r"\.git$", "", url.split("/")[-1].split(":")[-1])
        if base.lower() != name.lower() or (("github.com" in url) and f"{owner}/".lower() not in url.lower()):
            continue
        try:
            r = subprocess.run(["git", "-C", str(root), "ls-remote", remote, f"refs/pull/{num}/head"], capture_output=True, text=True, timeout=20)
            sha = (r.stdout.split() or [""])[0]
            if re.fullmatch(r"[0-9a-f]{40}", sha):
                return sha, f"git ls-remote {remote}"
        except (OSError, subprocess.SubprocessError):
            pass
    return None, "couldn't reach the pull request (sign in with gh, or add the repo as a git remote)"


def cmd_seal(repo: str, a) -> int:
    root = Path(repo).resolve()
    work = Path(a.workdir).resolve() if a.workdir else root
    if not re.fullmatch(r"\d{3}", a.quest or ""):
        print("--quest must be three digits, for example 001"); return 2
    if a.verdict not in ("approve", "changes", "reject"):
        print("--verdict must be approve, changes or reject"); return 2
    if not a.test_cmd:
        print("--test-cmd is required: seal re-runs the tests itself instead of trusting a report"); return 2
    commit = _git(work, "rev-parse", "HEAD")
    if not commit:
        print(f"{work} isn't a git checkout with a commit"); return 2
    if a.pr:
        head, src = pr_head(root, a.pr)
        if head and head != commit:
            print(f"the pull request's head is {head[:12]} ({src}) but this checkout is {commit[:12]}: check out the PR's head and seal again"); return 2
    print(f"re-running: {a.test_cmd}  (in {work})")
    tests = _run(a.test_cmd, work, a.timeout)
    prev = (_ledger(root) or [{}])[-1].get("hash", "0" * 64)
    rec = {"schema": SCHEMA, "quest": a.quest, "pr": a.pr or "", "branch": _git(work, "rev-parse", "--abbrev-ref", "HEAD"),
           "commit": commit, "tree": _git(work, "rev-parse", "HEAD^{tree}"), "verdict": a.verdict, "evaluator": a.evaluator or "",
           "builder": a.builder or "", "challenger": a.challenger or "", "defects": int(a.defects or 0), "tests": tests,
           "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "tool": f"agent-company {VERSION}", "prev": prev}
    ext = a.verifier or os.environ.get("OPENPROOF_VERIFY_CMD", "")
    rec["hash"] = hashlib.sha256(_canon(rec)).hexdigest()
    rec["id"] = f"{a.quest}-{rec['hash'][:12]}"
    ev = _evdir(root)
    path = ev / f"{rec['id']}.json"
    if ext:   # the OpenProof verifier reads the record as written so far; its result is then sealed into the record
        path.write_text(json.dumps(rec, indent=1, ensure_ascii=False), encoding="utf-8")
        r = _run(f"{ext} {shlex.quote(str(path))}", root, a.timeout)
        rec["external"] = {"cmd": ext, "exit": r["exit"], "passed": r["passed"], "tail": r["tail"][-600:]}
        rec.pop("hash"); rec.pop("id")
        rec["hash"] = hashlib.sha256(_canon(rec)).hexdigest()
        rec["id"] = f"{a.quest}-{rec['hash'][:12]}"
        path.unlink(missing_ok=True)
        path = ev / f"{rec['id']}.json"
    rec["sig"] = hmac.new(_key(True), rec["hash"].encode(), hashlib.sha256).hexdigest()
    rec.update(_ed_sign(root, rec["hash"]))
    path.write_text(json.dumps(rec, indent=1, ensure_ascii=False), encoding="utf-8")
    with open(ev / "ledger.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({"id": rec["id"], "quest": rec["quest"], "hash": rec["hash"], "prev": prev, "created": rec["created"]}) + "\n")
    v = verify_record(root, rec["id"])
    print(f"record {rec['id']}  tests {'passed' if tests['passed'] else 'FAILED (exit ' + str(tests['exit']) + ')'}  verdict {a.verdict}")
    print(f"  {path.relative_to(root) if root in path.parents else path}")
    print("  sealed: full credit" if v["sealed"] else "  not sealable for full credit: " + "; ".join(v["why"]))
    return 0 if v["sealed"] else 1


def verify_record(repo, rid: str, rerun: bool = False, timeout: int = 1800, signers: str = "") -> dict:
    root = Path(repo).resolve()
    ev = ops_dir(root) / "evidence"
    checks, why = [], []
    def add(name, ok, note=""):
        checks.append({"check": name, "ok": ok, "note": note})
        if ok is False:
            why.append(f"{name}: {note}" if note else name)
    if not re.fullmatch(r"(\d{3}|trust|card|council)-[0-9a-f]{12}", rid or ""):
        add("record id", False, "expected NNN-, trust-, card- or council-<12 hex>")
        return {"id": rid, "ok": False, "sealed": False, "checks": checks, "why": why}
    f = ev / f"{rid}.json"
    if not f.exists():
        add("record file", False, f"{f.name} not found")
        return {"id": rid, "ok": False, "sealed": False, "checks": checks, "why": why}
    rec = json.loads(f.read_text(encoding="utf-8"))
    add("schema", rec.get("schema") == SCHEMA, rec.get("schema", ""))
    h = hashlib.sha256(_canon(rec)).hexdigest()
    add("hash", h == rec.get("hash") and rid == f"{rec.get('quest') or rec.get('kind')}-{h[:12]}", "content matches its hash" if h == rec.get("hash") else "record was changed after sealing")
    led = _ledger(root)
    idx = next((i for i, l in enumerate(led) if l.get("id") == rid), -1)
    chain_ok = idx >= 0 and led[idx].get("hash") == rec.get("hash") and led[idx].get("prev") == rec.get("prev") and \
        (rec.get("prev") == (led[idx - 1].get("hash") if idx > 0 else "0" * 64))
    add("chain", chain_ok, f"entry {idx + 1} of {len(led)} in ledger.jsonl" if chain_ok else "missing from the ledger, or the ledger was edited")
    if rec.get("sig_ed25519"):
        ok, note = _ed_verify(root, rec, signers)
        add("signature", ok, note)
    else:
        k = _key(False)
        if k is None:
            add("signature", None, "older record (HMAC): its key isn't on this machine, so only the signer's machine can check it. "
                                   "Hash and chain are checked. The signer can add an Ed25519 signature with: agent_company.py cosign")
        elif hmac.compare_digest(hmac.new(k, rec.get("hash", "").encode(), hashlib.sha256).hexdigest(), rec.get("sig", "")):
            add("signature", True, "signed on this machine (HMAC)")
        else:
            add("signature", None, "older record (HMAC) signed with a key that isn't this machine's: it can't be checked here, "
                                   "only on the signer's machine. The signer can add an Ed25519 signature with: agent_company.py cosign")
    if rec.get("kind") in ("trust", "card", "council"):
        if rec["kind"] in ("card", "council"):
            key = "cards" if rec["kind"] == "card" else "files"
            changed = [c["file"] for c in rec.get("content", {}).get(key, []) if not (root / c["file"]).exists() or
                       hashlib.sha256((root / c["file"]).read_bytes()).hexdigest() != c["sha256"]]
            add(key if key == "cards" else "council files", not changed, f"every {'card' if key == 'cards' else 'council file'} is unchanged since sealing" if not changed else "changed since sealing: " + ", ".join(changed))
        else:
            add("snapshot", True, f"{len(rec.get('content', {}).get('agents', []))} agents, guild.json {rec.get('content', {}).get('guild_sha256', '')[:12]}")
        ok = all(c["ok"] is not False for c in checks)
        return {"id": rid, "kind": rec["kind"], "created": rec.get("created"), "ok": ok, "sealed": ok and all(c["ok"] for c in checks if c["check"] in ("hash", "chain", "signature")),
                "checks": checks, "why": why}
    known = bool(_git(root, "cat-file", "-t", rec.get("commit", "")) == "commit")
    add("commit", known, rec.get("commit", "")[:12] + (" is in this repository" if known else " not found in this repository"))
    t = rec.get("tests", {})
    add("tests", bool(t.get("passed")), f"{t.get('cmd', '')} → exit {t.get('exit')}")
    add("verdict", rec.get("verdict") == "approve", rec.get("verdict", ""))
    if rec.get("pr"):
        head, src = pr_head(root, rec["pr"])
        if head is None:
            add("pull request", None, src)
        else:
            add("pull request", head == rec.get("commit"), f"head {head[:12]} matches the sealed commit ({src})" if head == rec.get("commit") else
                f"head is now {head[:12]}, sealed {rec.get('commit', '')[:12]}: the PR changed after sealing; seal it again")
    else:
        add("pull request", None, "no pull request given")
    if "external" in rec:
        add("OpenProof verifier", bool(rec["external"].get("passed")), f"{rec['external'].get('cmd')} → exit {rec['external'].get('exit')}")
    if rerun:
        head = _git(root, "rev-parse", "HEAD")
        # The command comes from the record itself: run it only when schema, hash, chain and signature all check out here.
        # A signature this machine can't check (an older HMAC record) is not enough, since a rewritten record can drop it.
        unproven = [c["check"] for c in checks if c["check"] in ("schema", "hash", "chain", "signature") and c["ok"] is not True]
        # The record's key must also be trusted from outside the checkout: anyone who can edit the evidence can edit the
        # repository's own allowed_signers, so that list alone never makes a command run.
        who, refusal = ("", "") if unproven else _rerun_trust(root, rec, signers)
        if unproven or not any(c["check"] == "signature" for c in checks):
            add("re-run", None, "not re-run: the record's " + (", ".join(unproven) or "signature") +
                " can't be confirmed here, so its test command isn't trusted to run")
        elif refusal:
            add("re-run", None, refusal)
        elif _dirty(root, ev):
            add("re-run", None, RERUN_DIRTY)
        elif head != rec.get("commit"):
            add("re-run", None, f"check out {rec.get('commit', '')[:12]} to re-run (HEAD is {head[:12]})")
        else:
            r = _run(t.get("cmd", ""), root, timeout)
            moved = any(c["check"] == "pull request" and c["ok"] is False for c in checks)
            add("re-run", r["passed"], f"exit {r['exit']} now; {who}" + (f". {RERUN_MOVED}" if moved else ""))
    integrity = all(c["ok"] is not False for c in checks if c["check"] in ("schema", "hash", "chain", "signature", "commit"))
    sealed = integrity and all(c["ok"] for c in checks if c["check"] in ("hash", "chain", "signature", "tests", "verdict")) and \
        all(c["ok"] is not False for c in checks if c["check"] in ("OpenProof verifier", "re-run", "pull request"))
    return {"id": rid, "quest": rec.get("quest"), "pr": rec.get("pr"), "verdict": rec.get("verdict"), "tests": t.get("cmd"),
            "tests_passed": t.get("passed"), "defects": rec.get("defects", 0), "evaluator": rec.get("evaluator"), "builder": rec.get("builder"),
            "commit": rec.get("commit"), "created": rec.get("created"), "ok": integrity, "sealed": sealed, "checks": checks, "why": why}


def seal_doc(root: Path, kind: str, content: dict) -> str:
    """Seal a trust export or a set of Declaration Cards into the same hashed, chained, signed ledger."""
    prev = (_ledger(root) or [{}])[-1].get("hash", "0" * 64)
    rec = {"schema": SCHEMA, "kind": kind, "content": content, "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "tool": f"agent-company {VERSION}", "prev": prev}
    rec["hash"] = hashlib.sha256(_canon(rec)).hexdigest()
    rec["id"] = f"{kind}-{rec['hash'][:12]}"
    rec["sig"] = hmac.new(_key(True), rec["hash"].encode(), hashlib.sha256).hexdigest()
    rec.update(_ed_sign(root, rec["hash"]))
    ev = _evdir(root)
    (ev / f"{rec['id']}.json").write_text(json.dumps(rec, indent=1, ensure_ascii=False), encoding="utf-8")
    with open(ev / "ledger.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({"id": rec["id"], "quest": kind, "hash": rec["hash"], "prev": prev, "created": rec["created"]}) + "\n")
    return rec["id"]


def cmd_verify(repo: str, rid: str | None, rerun: bool, as_json: bool, signers: str = "") -> int:
    root = Path(repo).resolve()
    ids = [rid] if rid else [l.get("id") for l in _ledger(root) if l.get("id")]
    if not ids:
        print("no evidence records yet (docs/ops/evidence/ledger.jsonl is empty)"); return 0
    results, seen = [], set()
    for i in ids:   # a record the ledger lists more than once is re-run at most once
        results.append(verify_record(root, i, rerun and i not in seen, signers=signers))
        if rerun and i in seen:
            results[-1]["checks"].append({"check": "re-run", "ok": None, "note": "not re-run again: the ledger lists this record more than once"})
        seen.add(i)
    if as_json:
        print(json.dumps(results if not rid else results[0], indent=1)); return 0 if all(r["ok"] for r in results) else 1
    if not signers:
        print(REPO_SIGNERS_LIMIT)
    for r in results:
        sig = next((c["ok"] for c in r["checks"] if c["check"] == "signature"), None)
        mark = "SEALED" if r["sealed"] else ("BROKEN" if not r["ok"] else
                                              "INTACT, SIGNATURE NOT CHECKABLE HERE" if sig is None else "INTACT, NOT SEALABLE")
        print(f"{r['id']}  {mark}")
        for c in r["checks"]:
            print(f"   {'✓' if c['ok'] else ('–' if c['ok'] is None else '✗')} {c['check']}: {c['note']}")
    return 0 if all(r["ok"] for r in results) else 1


# ---------------------------------------------------------------- harness: install and check
DENY = ["Bash(git merge:*)", "Bash(gh pr merge:*)", "Bash(git push --force:*)", "Bash(git push -f:*)", "Read(./.env)", "Read(./.env.*)",
        "Read(**/*.pem)", "Read(**/*.key)", "Read(**/id_rsa*)", "Edit(./.env)", "Edit(./.env.*)", "Edit(**/*.pem)", "Edit(**/*.key)"]
GUARD_CMD = 'python3 "$CLAUDE_PROJECT_DIR/docs/ops/harness/guard.py"'
TOOL_TO_MCP = {"GitHub: pull requests": "github", "GitHub: read": "github", "browser": "playwright", "issue tracker": "linear", "chat": "slack"}


def _allow_from_guild(ops: Path) -> dict:
    allow = {"mcp_servers": [], "web": False, "tools": [], "programs": [], "test_commands": []}
    g = ops / "guild" / "guild.json"
    try:
        heroes = json.loads(g.read_text(encoding="utf-8")).get("heroes", {}).values()
    except (OSError, ValueError, AttributeError):
        heroes = []
    for h in heroes:
        for t in h.get("allow", []):
            if t not in allow["tools"]:
                allow["tools"].append(t)
            if t in TOOL_TO_MCP and TOOL_TO_MCP[t] not in allow["mcp_servers"]:
                allow["mcp_servers"].append(TOOL_TO_MCP[t])
            if t == "web search":
                allow["web"] = True
    return allow


_READ_MAX = 5_000_000


def _read_inside(root: Path, rel: str, cap: int = _READ_MAX):
    """Text of a regular file at rel, only if it is really inside the repo (no link out of it) and not oversized. Else None."""
    try:
        base = Path(root).resolve()
        p = (base / rel).resolve()
        p.relative_to(base)
        if not p.is_file() or p.stat().st_size > cap:
            return None
        return p.read_text(encoding="utf-8")
    except (OSError, ValueError, RuntimeError):
        return None


def _json_inside(root: Path, rel: str):
    t = _read_inside(root, rel)
    if t is None:
        return None
    try:
        return json.loads(t)
    except (ValueError, RecursionError):            # deeply nested junk must not take the screen down
        return None


def _claude_settings(root: Path) -> dict:
    st = _json_inside(root, ".claude/settings.json")
    return st if isinstance(st, dict) else {}


def _hooks_disabled(root: Path) -> bool:
    """Claude Code runs no hook at all when disableAllHooks is set, in the project settings or the local ones."""
    for rel in (".claude/settings.json", ".claude/settings.local.json"):
        st = _json_inside(root, rel)
        if isinstance(st, dict) and st.get("disableAllHooks"):
            return True
    return False


def _hook_groups(settings: dict, event: str) -> list:
    """[(matcher, [command hooks])] for one event, whatever shape the file is in. A hook counts only as exactly
    {"type": "command", "command": ...} in a group with nothing but a matcher and hooks: any other key (async, timeout,
    a condition) could keep it from blocking a call."""
    hooks = settings.get("hooks") if isinstance(settings, dict) else None
    groups = hooks.get(event) if isinstance(hooks, dict) else None
    out = []
    for g in groups if isinstance(groups, list) else []:
        if not isinstance(g, dict) or set(g) - {"matcher", "hooks"}:
            continue
        inner = g.get("hooks")
        cmds = [h for h in (inner if isinstance(inner, list) else [])
                if isinstance(h, dict) and set(h) == {"type", "command"} and h["type"] == "command" and isinstance(h["command"], str)]
        m = g.get("matcher", "")
        out.append((m if isinstance(m, str) else "\x00", cmds))
    return out


def _deny_rules(settings: dict) -> list:
    perms = settings.get("permissions") if isinstance(settings, dict) else None
    deny = perms.get("deny") if isinstance(perms, dict) else None
    return [d for d in deny if isinstance(d, str)] if isinstance(deny, list) else []


def _main_checkout(root: Path) -> Path:
    """The main checkout `root` belongs to, read from .git without running git (the kit's runtime.py does the same).
    Raises when a worktree pointer cannot be followed, and callers treat that as "cannot tell"."""
    g = Path(root) / ".git"
    if g.is_dir() or not os.path.lexists(g):
        return Path(root)
    first = g.read_text(encoding="utf-8").splitlines()[0].strip() if g.stat().st_size < 10_000 else ""
    if not first.startswith("gitdir:"):
        raise ValueError(f"{g} is not a git folder or a worktree pointer")
    gitdir = Path(first[len("gitdir:"):].strip())
    gitdir = (gitdir if gitdir.is_absolute() else Path(root) / gitdir).resolve()
    cd = gitdir / "commondir"
    if not cd.is_file():
        return Path(root)
    common = (gitdir / cd.read_text(encoding="utf-8").splitlines()[0].strip()).resolve()
    return common.parent if common.name == ".git" else Path(root)


def kill_file(root: Path) -> Path | None:
    """The entry that stops the agents, or None. .harness/KILL in any form (a file with any content, a folder, a link)
    means stopped, in this checkout or in the main checkout it belongs to. If the main checkout cannot be worked out,
    the answer is the .git entry itself: unknown must never read as clear."""
    root = Path(root)
    try:
        places = [root, _main_checkout(root)]
    except (OSError, ValueError, IndexError):
        return root / ".git"
    for r in places:
        kp = r / ".harness" / "KILL"
        if os.path.lexists(kp):
            return kp
    return None


def _file_inside(path: Path, bases, cap: int = 1_000_000):
    """Bytes of a regular file (never a pipe or device) that sits inside one of `bases`. Else None."""
    try:
        rp = Path(path).resolve()
        if not any(rp == b or b in rp.parents for b in (Path(x).resolve() for x in bases)):
            return None
        st = rp.stat()
        if not stat.S_ISREG(st.st_mode) or st.st_size > cap:
            return None
        return rp.read_bytes()
    except (OSError, ValueError, RuntimeError):
        return None


def harness_status(repo) -> dict:
    root = Path(repo).resolve()
    hd = ops_dir(root) / "harness"
    st = _claude_settings(root)
    off = _hooks_disabled(root)                       # with all hooks disabled, nothing below is enforced
    is_guard = lambda h: h["command"] in (GUARD_CMD, GUARD_CMD + " --log")     # the exact commands the installer writes
    is_log = lambda h: h["command"] == GUARD_CMD + " --log"
    pre_groups = [] if off else _hook_groups(st, "PreToolUse")
    pre = [h for _, hs in pre_groups for h in hs if is_guard(h) and "--log" not in h["command"]]
    matchers = " ".join(m for m, hs in pre_groups if any(is_guard(h) for h in hs))
    post = [] if off else [h for _, hs in _hook_groups(st, "PostToolUse") for h in hs if is_log(h)]
    deny = _deny_rules(st)
    shipped = _file_inside(HARNESS_SRC / "guard.py", [HARNESS_SRC])
    guard = shipped is not None and _file_inside(hd / "guard.py", [root]) == shipped      # the guard itself, not a file of that name
    prepush = False
    try:
        hooks_dir = _git(root, "rev-parse", "--git-path", "hooks")
        if hooks_dir:
            hp = (Path(hooks_dir) if Path(hooks_dir).is_absolute() else root / hooks_dir) / "pre-push"
            body = _file_inside(hp, [root, _main_checkout(root)])                          # never a hook kept outside the repository
            prepush = body is not None and b"Agent Company harness" in body
    except (OSError, ValueError, IndexError):
        prepush = False
    pieces = {
        "helm": guard and bool(pre) and "Edit" in matchers,
        "chest": guard and all(d in deny for d in DENY[4:9]),
        "hands": guard and bool(pre) and "Bash" in matchers and "Bash(git merge:*)" in deny,
        "belt": guard and (hd / "allowlist.json").exists() and "mcp__" in matchers,
        "boots": guard and (hd / "real_data_paths.txt").exists() and "Read" in matchers,
        "amulet": guard and bool(post),
    }
    unc = _harness_uncommitted(root)
    return {"pieces": pieces, "fitted": sum(pieces.values()), "pre_push": prepush, "settings": str(root / ".claude" / "settings.json"),
            "committed": not unc, "uncommitted": unc}


# The harness only protects a builder in its own worktree if these files are in git: a worktree is made from a commit,
# and Claude Code loads the guard from "$CLAUDE_PROJECT_DIR/docs/ops/harness/guard.py", which is the worktree.
HARNESS_FILES = ["AGENTS.md", ".claude/settings.json", "docs/ops/harness/guard.py", "docs/ops/harness/allowlist.json", "docs/ops/harness/real_data_paths.txt"]


def _harness_uncommitted(root: Path) -> list[str]:
    out = []
    has_head = bool(_git(root, "rev-parse", "--verify", "-q", "HEAD"))
    for f in HARNESS_FILES:
        if not (root / f).exists() or not _git(root, "ls-files", "--", f) or not has_head:
            out.append(f); continue
        try:
            r = subprocess.run(["git", "-C", str(root), "diff", "--quiet", "HEAD", "--", f], capture_output=True, timeout=20)
            if r.returncode != 0:
                out.append(f)
        except (OSError, subprocess.SubprocessError):
            out.append(f)
    return out


def commit_harness(repo) -> dict:
    """Commit the harness files, and only those, on the current branch. This is the owner's step (a click in the World,
    or `harness --commit`): after it, every worktree made from this branch carries the guard."""
    root = Path(repo).resolve()
    st = harness_status(root)
    if st["fitted"] < 6:
        return {"error": f"only {st['fitted']} of 6 harness pieces are fitted; install the harness first", "status": st}
    files = [f for f in HARNESS_FILES if (root / f).exists()]
    ident = [] if _git(root, "config", "user.email") else ["-c", "user.name=Agent Company owner", "-c", "user.email=owner@localhost"]
    try:
        subprocess.run(["git", "-C", str(root), "add", "--", *files], capture_output=True, text=True, timeout=30, check=True)
        if st["uncommitted"]:
            r = subprocess.run(["git", "-C", str(root), *ident, "commit", "-q", "-m",
                                "Commit the Agent Company harness so every worktree carries the guard", "--", *files],
                               capture_output=True, text=True, timeout=30)
            if r.returncode != 0:
                return {"error": "git would not commit the harness files: " + (r.stderr or r.stdout).strip()[:300], "status": harness_status(root)}
    except (OSError, subprocess.SubprocessError) as e:
        return {"error": f"git failed: {e}", "status": harness_status(root)}
    return {"committed": files, "commit": _git(root, "rev-parse", "--short", "HEAD"), "status": harness_status(root)}


GUARD_MATCHER = "Bash|Edit|Write|MultiEdit|NotebookEdit|Read|Grep|Glob|LS|WebFetch|WebSearch|mcp__.*"


def install_harness(repo) -> dict:
    root = Path(repo).resolve()
    ops = ops_dir(root)
    hd = ops / "harness"
    hd.mkdir(parents=True, exist_ok=True)
    done = []
    shutil.copyfile(HARNESS_SRC / "guard.py", hd / "guard.py"); done.append("docs/ops/harness/guard.py")
    if not (hd / "allowlist.json").exists():
        (hd / "allowlist.json").write_text(json.dumps(_allow_from_guild(ops), indent=1), encoding="utf-8"); done.append("docs/ops/harness/allowlist.json")
    reals = [l.strip() for l in (hd / "real_data_paths.txt").read_text(encoding="utf-8").splitlines()
             if l.strip() and not l.strip().startswith("#")] if (hd / "real_data_paths.txt").exists() else []
    inside = [r for r in reals if not Path(os.path.expanduser(r)).is_absolute() or root in Path(os.path.expanduser(r)).resolve().parents]
    if inside:
        gi = root / ".gitignore"
        have = gi.read_text(encoding="utf-8").splitlines() if gi.exists() else []
        new = [r for r in inside if r not in have]
        if new:
            gi.write_text("\n".join(have + ["# real data: never committed (Agent Company harness)"] + new) + "\n", encoding="utf-8")
            done.append(".gitignore (real-data paths)")
    if not (hd / "real_data_paths.txt").exists():
        (hd / "real_data_paths.txt").write_text("# One path per line (relative to the repo, or absolute). Agents never read these, and never send them anywhere.\n# Example:\n# data/customers/\n", encoding="utf-8")
        done.append("docs/ops/harness/real_data_paths.txt")
    sp = root / ".claude" / "settings.json"
    sp.parent.mkdir(parents=True, exist_ok=True)
    try:
        st = json.loads(sp.read_text(encoding="utf-8")) if sp.exists() else {}
    except ValueError:
        return {"error": f"{sp} isn't valid JSON; fix it first, nothing was changed", "done": done}
    if sp.exists() and not (sp.parent / "settings.json.before-agent-company").exists():
        shutil.copyfile(sp, sp.parent / "settings.json.before-agent-company")
    perms = st.setdefault("permissions", {})
    perms["deny"] = perms.get("deny", []) + [d for d in DENY if d not in perms.get("deny", [])]
    hooks = st.setdefault("hooks", {})
    def ensure(event, matcher, cmd):
        lst = hooks.setdefault(event, [])
        mine = [e for e in lst if any(h.get("command") == cmd for h in e.get("hooks", []))]
        for e in mine:
            e["matcher"] = matcher                      # an older install's matcher is brought up to date
        if not mine:
            lst.append({"matcher": matcher, "hooks": [{"type": "command", "command": cmd}]})
    ensure("PreToolUse", GUARD_MATCHER, GUARD_CMD)
    ensure("PostToolUse", ".*", GUARD_CMD + " --log")
    sp.write_text(json.dumps(st, indent=2), encoding="utf-8"); done.append(".claude/settings.json (merged; original kept as settings.json.before-agent-company)")
    hooks_dir = _git(root, "rev-parse", "--git-path", "hooks")
    if hooks_dir:
        hdp = Path(hooks_dir) if Path(hooks_dir).is_absolute() else root / hooks_dir
        hdp.mkdir(parents=True, exist_ok=True)
        target = hdp / "pre-push"
        if target.exists() and "Agent Company harness" not in target.read_text(errors="replace"):
            target = hdp / "pre-push.agent-company"
        shutil.copyfile(HARNESS_SRC / "pre-push", target)
        target.chmod(0o755)
        done.append(str(target.relative_to(root)) if root in target.parents else str(target))
    agents = root / "AGENTS.md"
    block = ("\n<!-- agent-company harness -->\n## Harness (Agent Company)\nEvery agent works within the six-piece harness: its own worktree; never read or write secrets; never merge, "
             "force push, or push to main, master, develop/* or release/*; only the tools in docs/ops/harness/allowlist.json; never read the paths in "
             "docs/ops/harness/real_data_paths.txt or send data off this machine; every action is logged in docs/ops/evidence/. Claude Code enforces this "
             "with docs/ops/harness/guard.py; every tool is held by the git pre-push hook.\n")
    text = agents.read_text(encoding="utf-8") if agents.exists() else "# Agents\n"
    if "<!-- agent-company harness -->" not in text:
        agents.write_text(text.rstrip() + "\n" + block, encoding="utf-8"); done.append("AGENTS.md (harness section)")
    return {"done": done, "status": harness_status(root)}


def cmd_harness(repo: str, check: bool, commit: bool = False) -> int:
    names = {"helm": "Worktree helm", "chest": "Deny-rule plate", "hands": "No-merge gauntlets", "belt": "Allowlist belt", "boots": "Constructed-data boots", "amulet": "Evidence amulet"}
    if not check:
        r = install_harness(repo)
        if "error" in r:
            print(r["error"]); return 1
        print("installed:\n  " + "\n  ".join(r["done"]))
    if commit:
        c = commit_harness(repo)
        if "error" in c:
            print(c["error"]); return 1
        print(f"committed ({c['commit']}):\n  " + "\n  ".join(c["committed"]))
    s = harness_status(repo)
    print(f"harness {s['fitted']}/6 enforced in this repo · pre-push hook: {'yes' if s['pre_push'] else 'no'}")
    for k, v in s["pieces"].items():
        print(f"  {'✓' if v else '✗'} {names[k]}")
    if s["fitted"] == 6 and not s["committed"]:
        print("  ! not in git yet: " + ", ".join(s["uncommitted"]) + "\n    A builder in its own worktree would run without the guard. Run: python3 agent_company.py harness . --commit")
    return 0 if s["fitted"] == 6 else 1


# ---------------------------------------------------------------- Declaration Cards and trust credits from the Guild
CLASS_ROLE = {"master": "Owner", "herald": "Chief of staff", "leader": "Coordinator", "artificer": "Builder", "paladin": "Evaluator", "rogue": "Challenger", "scribe": "Claims officer", "ranger": "Watch"}
DELTA = {"clean": 3, "sealed": 8, "back": -10, "missed": -10, "escaped": -25, "breach": -60}


def _credits(h: dict) -> int:
    c = 100
    for x in h.get("history", []):
        c = x.get("set", 30) if x.get("o") == "restore" else max(0, min(100, c + (x.get("d") or 0)))
    return round(c)


def trust_table(repo) -> list[dict]:
    try:
        heroes = json.loads((ops_dir(repo) / "guild" / "guild.json").read_text(encoding="utf-8")).get("heroes", {}).values()
    except (OSError, ValueError):
        return []
    rows = []
    for h in heroes:
        if h.get("cls") == "master":
            continue
        win = [x for x in h.get("history", []) if x.get("o") in ("clean", "back", "missed", "escaped")][-10:]
        c = _credits(h)
        status = ("contained" if h.get("contained") or c < 15 else "probation" if c < 40 or h.get("probation", 0) > 0
                  else "watch" if c < 70 else "trusted")
        rows.append({"name": h.get("name"), "role": CLASS_ROLE.get(h.get("cls"), h.get("cls")), "origin": h.get("origin"), "level": h.get("lv", 1), "credits": c, "status": status,
                     "reliability": round(sum(x["o"] == "clean" for x in win) / len(win), 2) if win else None,
                     "credibility": round(sum(bool(x.get("sealed")) for x in win) / len(win), 2) if win else None})
    return rows


def cmd_trust(repo: str, as_json: bool, seal: bool = False) -> int:
    rows = trust_table(repo)
    if as_json:
        print(json.dumps(rows, indent=1)); return 0
    if not rows:
        print("no Guild saved in docs/ops/guild/guild.json yet (play Guild mode and press Write to my repo)"); return 0
    print(f"{'agent':24} {'role':16} {'lv':>2} {'credits':>7}  {'status':10} {'reliab.':>7} {'cred.':>6}")
    for r in rows:
        pct = lambda v: "–" if v is None else f"{round(v * 100)}%"
        print(f"{r['name'][:24]:24} {r['role'][:16]:16} {r['level']:>2} {r['credits']:>7}  {r['status']:10} {pct(r['reliability']):>7} {pct(r['credibility']):>6}")
    (ops_dir(repo) / "evidence").mkdir(parents=True, exist_ok=True)
    (ops_dir(repo) / "evidence" / "trust.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print("written: docs/ops/evidence/trust.json")
    if seal:
        g = ops_dir(repo) / "guild" / "guild.json"
        rid = seal_doc(Path(repo).resolve(), "trust", {"agents": rows, "guild_sha256": hashlib.sha256(g.read_bytes()).hexdigest()})
        print(f"sealed: {rid} (check it with: agent_company.py verify {repo} {rid})")
    return 0


def cmd_card(repo: str, agent: str | None, seal: bool = False) -> int:
    ops = ops_dir(repo)
    try:
        heroes = list(json.loads((ops / "guild" / "guild.json").read_text(encoding="utf-8")).get("heroes", {}).values())
    except (OSError, ValueError):
        print("no Guild saved in docs/ops/guild/guild.json yet"); return 1
    hs = harness_status(repo)
    owner = next((h.get("name") for h in heroes if h.get("cls") == "master"), "the owner")
    trust = {r["name"]: r for r in trust_table(repo)}
    out = ops / "guild" / "cards"
    out.mkdir(parents=True, exist_ok=True)
    made = []
    for h in heroes:
        if h.get("cls") == "master" or (agent and not h.get("name", "").lower().startswith(agent.lower())):
            continue
        t = trust.get(h.get("name"), {})
        slug = re.sub(r"[^a-z0-9]+", "-", h.get("name", "agent").lower()).strip("-")[:40] or "agent"
        role = CLASS_ROLE.get(h.get("cls"), h.get("cls"))
        text = (f"# Declaration Card: {h.get('name')} ({role})\n\n"
                f"- Purpose: {role} for this repository, run on {h.get('origin')}.\n"
                f"- May: work in its own worktree and branch; use {', '.join(h.get('allow', [])) or 'no extra tools'}.\n"
                f"- May never: merge; push to main, master, develop/* or release/*; read or write secrets; send real data to a hosted model; use tools outside its allowlist.\n"
                f"- Can reach: this repository's worktree; MCP servers in docs/ops/harness/allowlist.json; no credentials.\n"
                f"- Reviewed by: an independent evaluator on a different tool where possible; every approval is sealed with `agent_company.py seal`.\n"
                f"- Answers for it: {owner}.\n"
                f"- Stop and escalate when: a guard refuses an action, tests fail, or trust credits fall below 40.\n"
                f"- Harness: {hs['fitted']}/6 enforced in this repo (pre-push hook {'installed' if hs['pre_push'] else 'missing'}).\n"
                f"- Trust: level {h.get('lv', 1)}, {t.get('credits', 100)} credits, {t.get('status', 'trusted')}; credibility (sealed share) {'–' if t.get('credibility') is None else str(round(t['credibility'] * 100)) + '%'}.\n"
                f"- Signed: ________________ ({owner}), date ________\n")
        (out / f"{slug}.md").write_text(text, encoding="utf-8"); made.append(f"guild/cards/{slug}.md")
    print("written:\n  " + "\n  ".join(made) if made else "no matching agents")
    if seal and made:
        root = Path(repo).resolve()
        cards = [{"file": f"docs/ops/{m}", "sha256": hashlib.sha256((ops / m).read_bytes()).hexdigest()} for m in made]
        rid = seal_doc(root, "card", {"cards": cards})
        print(f"sealed: {rid} (edit a card and it stops verifying)")
    return 0


# ---------------------------------------------------------------- zero-knowledge start: launch, doctor, smoke, import-agents
DEFAULT_HOME = Path(os.environ.get("AGENT_COMPANY_HOME", Path.home() / "agent-company-projects"))


def _check(name: str, ok, detail: str, fix: str = "") -> dict:
    return {"check": name, "ok": ok, "detail": detail, "fix": fix}


def doctor(repo: str | Path | None = None) -> list[dict]:
    """Plain-language checks, each with the one thing to do when it fails. Nothing here changes anything."""
    out = []
    v = sys.version_info
    out.append(_check("Python", v >= (3, 9), f"{v.major}.{v.minor}.{v.micro}", "Install Python 3.9 or later from python.org, then run this again."))
    gv = ""
    try:
        gv = subprocess.run(["git", "--version"], capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    out.append(_check("git", bool(gv), gv or "not found", "Mac: run  xcode-select --install . Windows: install Git from git-scm.com."))
    out.append(_check("GitHub sign-in (optional)", bool(shutil.which("gh")) or None, "gh found" if shutil.which("gh") else "gh not installed: pull requests are checked with git instead",
                      "Optional: install the GitHub CLI (cli.github.com) and run  gh auth login ."))
    out.append(_check("Signing key", KEY_FILE.exists() or None, str(KEY_FILE) if KEY_FILE.exists() else "not made yet: the first seal makes it", ""))
    if repo is not None:
        root = Path(repo).resolve()
        out.append(_check("Project folder", root.is_dir(), str(root), f"Create the folder, or run: python3 agent_company.py launch"))
        if root.is_dir():
            top = _git(root, "rev-parse", "--show-toplevel")
            out.append(_check("Project is a git repository", bool(top), top or "no", "Run: python3 agent_company.py launch " + str(root) + "  (it sets git up for you)"))
            out.append(_check("Agent Company set up here", (ops_dir(root) / "inbox").is_dir(), str(ops_dir(root)), "Run: python3 agent_company.py init " + str(root)))
            hs = harness_status(root)
            out.append(_check("Harness enforced", hs["fitted"] == 6 and hs["pre_push"], f"{hs['fitted']}/6, pre-push hook {'yes' if hs['pre_push'] else 'no'}",
                              "Press 'Install the harness in this repo' in the Forge, or run: python3 agent_company.py harness " + str(root)))
            rp = ops_dir(root) / "harness" / "real_data_paths.txt"
            reals = [l.strip() for l in rp.read_text(encoding="utf-8").splitlines() if l.strip() and not l.strip().startswith("#")] if rp.exists() else []
            inside = [r for r in reals if (root / os.path.expanduser(r)).resolve().exists() and
                      (root in (root / os.path.expanduser(r)).resolve().parents)]
            out.append(_check("Real data kept outside the agents' folder", False if inside else None,
                              ("inside the project: " + ", ".join(inside)) if inside else "none inside the project",
                              "Move real data to a folder outside this project. The guard is a backstop; keeping real data out of the agents' folder is the control."))
            led = _ledger(root)
            out.append(_check("Evidence ledger", (all(verify_record(root, l["id"])["ok"] for l in led if l.get("id")) if led else None),
                              f"{len(led)} record(s)" if led else "no records yet: the evaluator seals after a review", "Run: python3 agent_company.py verify " + str(root)))
    return out


PLAN_ROLE = {"owner": "Owner", "chief": "Chief of staff", "coord": "Coordinator", "builder": "Builder", "evaluator": "Evaluator",
             "challenger": "Challenger", "claims": "Claims officer", "watch": "Watch"}


def team_of(ops: Path) -> list[dict]:
    """The team as the repo records it: the Guild's characters if there are any, otherwise the units placed on the Command map."""
    try:
        heroes = json.loads((ops / "guild" / "guild.json").read_text(encoding="utf-8")).get("heroes", {}).values()
        team = [{"name": str(h.get("name", ""))[:40], "role": CLASS_ROLE.get(h.get("cls"), str(h.get("cls", ""))[:30]),
                 "origin": str(h.get("origin", ""))[:30], "level": h.get("lv", 1)} for h in heroes if isinstance(h, dict)]
        if team:
            return team[:24]
    except (OSError, ValueError, AttributeError):
        pass
    try:
        plan = json.loads((ops / "plan.json").read_text(encoding="utf-8"))
        placed, units = plan.get("place", {}), plan.get("units", {})
        return [{"name": PLAN_ROLE.get(u.get("role"), str(u.get("role", ""))[:30]), "role": PLAN_ROLE.get(u.get("role"), str(u.get("role", ""))[:30]),
                 "origin": str(u.get("tool", ""))[:30], "level": 1} for uid, u in units.items() if uid in placed and isinstance(u, dict)][:24]
    except (OSError, ValueError, AttributeError):
        return []


def coordinator_started(ops: Path) -> bool:
    """True once STATUS.md carries a real time. The template's "Time: <date time zone>" placeholder is not a start."""
    p = ops / "outbox" / "STATUS.md"
    return p.exists() and bool(re.search(r"^Time:\s*\d", p.read_text(encoding="utf-8", errors="replace"), re.M))


def stage(repo: str | Path) -> dict:
    """Where this project is, and the one next step, for the first-run guide in the Guild."""
    root = Path(repo).resolve()
    ops = ops_dir(root)
    steps = [
        ("Set up", (ops / "inbox").is_dir(), "Agent Company is set up in this project."),
        ("Forge a team", (ops / "guild" / "guild.json").exists() or bool(team_of(ops)), "Forge characters, or load the demo guild, then press Write to my repo on the War map."),
        ("Install the harness", harness_status(root)["fitted"] == 6, "In the Forge's harness step, press Install the harness in this repo."),
        ("Write quests", any((ops / "inbox").glob("[0-9][0-9][0-9]_*.md")) if (ops / "inbox").is_dir() else False, "Add a quest on the War map and sound the horn."),
        ("Start the coordinator", coordinator_started(ops),
         "Run: python3 agent_company.py start . --tool claude --run  (or codex, gemini)"),
        ("Seal proof", bool(_ledger(root)), "After an approving review: python3 agent_company.py seal . --quest 001 --pr <link> --test-cmd \"<tests>\""),
    ]
    done = [s for s in steps if s[1]]
    nxt = next((s for s in steps if not s[1]), None)
    return {"steps": [{"name": n, "done": bool(d), "how": h} for n, d, h in steps], "done": len(done), "total": len(steps),
            "next": {"name": nxt[0], "how": nxt[2]} if nxt else None}


WORLD_STATIONS = [("setup", "Set up", "Project depot"), ("team", "Forge a team", "Team quarters"), ("harness", "Install the harness", "The Forge"),
                  ("orders", "Write quests", "Dispatch office"), ("run", "Start the coordinator", "Coordinator tower"), ("proof", "Seal proof", "Evidence vault")]
WORLD_LABEL = {"team": "Build the team", "orders": "Write the orders"}   # the World's words for stage() steps
WORLD_HOW = {"team": "Add your agents on the Command map (one coordinator, a builder and an independent evaluator), then press Deploy.",
             "harness": "Press Install the harness. It fits all six pieces in this repo and keeps your old settings as a backup.",
             "run": "In a terminal: python3 agent_company.py start . --tool claude --run (or codex, gemini). Or with no window, one instruction at a time: python3 agent_company.py run . --tool claude",
             "orders": "Write a mission on the Command map (the owner's words, a branch, tests, and a stop point that says Don't merge), then press Deploy."}


# ---- The Harness Marketplace kit, if this repo carries one (read-only). The golden image is one frozen version of the
# kit's harness; the check below mirrors `golden check` in that kit (tools/golden.py) and changes nothing. A MATCH means the
# standard files are in place, not that an agent behaves well. The image in the repo is what is compared against, so compare
# its version and hash with the kit's release when it matters. Recovery drills are read from the kit's ledger as written;
# `scripts/harness.py check` is what verifies that ledger's chain.
GOLDEN_IMAGES = ["scripts/golden-image.json", "golden/golden-image.json"]
_KIT_MAX = 5_000_000


def _golden_image_hash(img: dict) -> str:
    body = {k: v for k, v in img.items() if k != "image_sha"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def _inside(root: Path, rel: str):
    """The file at rel, only if it stays inside the repo. An image must never make the World read anything else."""
    try:
        p = (root / str(rel)).resolve()
        p.relative_to(root.resolve())
        return p
    except (OSError, ValueError, RuntimeError):
        return None


def _gate_hook_ok(settings: dict, cmd: str) -> bool:
    """The image's hook counts only where it can stop a tool call: a command hook under PreToolUse that matches every tool."""
    return any(m in ("", "*", ".*") and any(h["command"] == cmd for h in hs) for m, hs in _hook_groups(settings, "PreToolUse"))


def golden_status(repo: str | Path) -> dict:
    root = Path(repo)
    rel = next((p for p in GOLDEN_IMAGES if os.path.lexists(root / p)), None)
    if rel is None:
        return {"installed": False}
    base = {"installed": True, "image": rel, "version": "?", "sha": "", "checked": 0, "pinned": False}
    img = _json_inside(root, rel)
    if not isinstance(img, dict):
        return {**base, "result": "ALTERED", "drift": ["the golden image cannot be read as a JSON file inside this repository"]}
    base.update(version=str(img.get("version", "?"))[:20], sha=str(img.get("image_sha", ""))[:12])
    try:
        own = _golden_image_hash(img)
    except (ValueError, TypeError, RecursionError):                       # UnicodeEncodeError is a ValueError
        own = None
    if own is None or img.get("image_sha") != own:
        return {**base, "result": "ALTERED", "drift": ["the golden image no longer matches its own hash; restore it from the kit's release"]}
    pin = re.search(r"--expect-sha ([0-9a-f]{64})", _read_inside(root, ".github/workflows/harness.yml") or "")
    base["pinned"] = bool(pin)
    if pin and pin.group(1) != img["image_sha"]:
        return {**base, "result": "ALTERED", "drift": ["this is not the image pinned in .github/workflows/harness.yml; restore it from the kit's release"]}
    locked, required, deny, hooks = img.get("locked"), img.get("required"), img.get("deny"), img.get("hooks")
    if not (isinstance(locked, dict) and isinstance(required, list) and isinstance(deny, list) and isinstance(hooks, list)) \
            or not (locked and required and deny and hooks):
        return {**base, "result": "ALTERED", "drift": ["the golden image lists nothing to check in at least one section; restore it from the kit's release"]}
    drift, checked = [], 0
    for target, want in locked.items():
        checked += 1
        p = _inside(root, target)
        if p is None:
            drift.append(f"DRIFT {target}")
        elif not p.is_file():
            drift.append(f"MISSING {target}")
        else:
            try:
                same = p.stat().st_size <= _KIT_MAX and hashlib.sha256(p.read_bytes()).hexdigest() == want
            except OSError:
                same = False
            if not same:
                drift.append(f"DRIFT {target}")
    for options in required:
        checked += 1
        options = options if isinstance(options, list) else [options]
        if not any((q := _inside(root, o)) is not None and q.is_file() for o in options):
            drift.append("MISSING " + " or ".join(str(o) for o in options))
    settings = _claude_settings(root)
    have_deny = set(_deny_rules(settings))
    for rule in deny:
        checked += 1
        if not isinstance(rule, str) or rule not in have_deny:
            drift.append(f"DRIFT deny {rule}")
    off = _hooks_disabled(root)
    for cmd in hooks:
        checked += 1
        if off or not isinstance(cmd, str) or not _gate_hook_ok(settings, cmd):
            drift.append(f"DRIFT hook {cmd}")
    return {**base, "checked": checked, "result": "DRIFT" if drift else "MATCH", "drift": [str(d)[:160] for d in drift[:30]]}


def _ledger_entry_hash(e: dict) -> str:
    body = {k: v for k, v in e.items() if k != "hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def recovery_status(repo: str | Path) -> dict:
    """The last drill in the kit's ledger, shown only when every line reads and the hash chain holds, as the kit's own
    `runtime.py status` requires. Otherwise `untrusted` says why and no drill is shown: a failed or forged line must
    never turn into "none on record" or a green result."""
    lp = Path(repo) / ".harness" / "ledger.jsonl"
    none = {"drills": 0, "last": None}
    if not os.path.lexists(lp):
        return none
    text = _read_inside(Path(repo), ".harness/ledger.jsonl", _KIT_MAX)
    if text is None:
        return {**none, "untrusted": "the ledger cannot be read (not a file inside this repository, too large, or not UTF-8)"}
    drills, last, prev = 0, None, "0" * 64
    for i, line in enumerate((l for l in text.splitlines() if l.strip()), 1):
        try:
            e = json.loads(line)
            ok = isinstance(e, dict) and e.get("prev") == prev and e.get("seq") == i and e.get("hash") == _ledger_entry_hash(e)
        except (ValueError, TypeError, RecursionError):
            ok = False
        if not ok:
            return {**none, "untrusted": f"the ledger's chain is broken at line {i}"}
        prev = e["hash"]
        if e.get("type") == "drill":
            drills += 1
            sec = e.get("seconds")
            last = {"result": str(e.get("result", "?"))[:20],
                    "seconds": sec if isinstance(sec, (int, float)) and not isinstance(sec, bool) and math.isfinite(sec) else None,
                    "ts": str(e.get("ts", ""))[:30], "by": str(e.get("by", "?"))[:60],
                    "checks_run": e.get("checks_run") if isinstance(e.get("checks_run"), int) else None}
    return {"drills": drills, "last": last}


def world_state(repo: str | Path) -> dict:
    """Everything the 3D world draws, read from the repository at this moment. A station is 'done' only when every
    station before it is done, so the screen never shows a step as finished while an earlier one is still open."""
    root = Path(repo).resolve()
    ops = ops_dir(root)
    raw = {s["name"]: s for s in stage(root)["steps"]}
    stations, open_seen = [], False
    hs = harness_status(root)
    for sid, step, name in WORLD_STATIONS:
        ok = raw[step]["done"] and (sid != "harness" or hs["committed"])
        state = "locked" if open_seen else ("done" if ok else "next")
        open_seen = open_seen or not ok
        st = {"id": sid, "name": name, "step": WORLD_LABEL.get(sid, step), "state": state, "how": WORLD_HOW.get(sid, raw[step]["how"])}
        if sid == "harness":
            st["action"] = "install-harness"
            if hs["fitted"] == 6 and not hs["committed"]:
                st["action"] = "commit-harness"; st["step"] = "Commit the harness files"
                st["how"] = ("All six pieces are fitted, but their files are not in git yet, so a builder in its own worktree would run without "
                             "the guard. Press Commit the harness files.")
        stations.append(st)
    team = team_of(ops)
    recs = [verify_record(root, l["id"]) for l in _ledger(root) if l.get("id")][-50:]
    kill = {"on": False}
    kf = kill_file(root)
    if kf is not None:
        k = _json_inside(kf.parent.parent, ".harness/KILL") if kf.name == "KILL" else {"reason": "cannot tell: this checkout's .git cannot be followed to its repository"}
        k = k if isinstance(k, dict) else {}
        kill = {"on": True, "by": str(k.get("by", "?"))[:60], "reason": str(k.get("reason", "KILL file present"))[:200], "ts": str(k.get("ts", ""))[:30]}
    inbox, done = ops / "inbox", ops / "done"
    return {"version": VERSION, "repo": root.name, "stations": stations, "harness": hs, "team": team, "runner": runner_status(root),
            "orders": {"pending": len(list(inbox.glob("[0-9][0-9][0-9]_*.md"))) if inbox.is_dir() else 0,
                       "done": len(list(done.glob("[0-9][0-9][0-9]_*.md"))) if done.is_dir() else 0},
            "proof": {"sealed": sum(1 for r in recs if r.get("sealed")), "broken": sum(1 for r in recs if not r.get("ok"))},
            "kill": kill, "kit": {"golden": golden_status(root), "recovery": recovery_status(root)},
            "read_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}


# ---------------------------------------------------------------- the background runner
# One coordinator, with no window, on one instruction. It refuses to start unless the harness is fitted AND committed,
# the kill switch is off and nothing else is running. A supervisor process watches it: `run --stop` or the kill switch
# (.harness/KILL) ends the agent's whole process group. Nothing here skips a tool's own permission checks.
RUNNER_PROMPT = ("You are the coordinator. Follow docs/ops/inbox/README.md. Do only the lowest-numbered instruction in docs/ops/inbox/, "
                 "then update docs/ops/outbox/STATUS.md and stop. Never merge.")
HEADLESS = {"claude": ["claude", "-p", RUNNER_PROMPT], "codex": ["codex", "exec", RUNNER_PROMPT], "gemini": ["gemini", "-p", RUNNER_PROMPT]}


def _alive(pid) -> bool:
    try:
        os.kill(int(pid), 0)
    except (OSError, ValueError, TypeError):
        return False
    try:                                                   # a finished child that nobody has collected yet is not alive
        stat = Path(f"/proc/{int(pid)}/stat").read_text().rsplit(")", 1)[1].split()
        return stat[0] != "Z"
    except (OSError, IndexError):
        return True


def _runner_file(root: Path) -> Path:
    return ops_dir(root) / "outbox" / "RUNNER.json"


def runner_status(repo) -> dict:
    p = _runner_file(Path(repo).resolve())
    try:
        st = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError):
        return {"state": "never"}
    if not isinstance(st, dict):
        return {"state": "never"}
    if st.get("state") in ("running", "starting") and not _alive(st.get("supervisor")):
        st["state"] = "lost"                               # its supervisor is gone, so nothing is watching it
    return st


def runner_ready(repo) -> list[str]:
    root = Path(repo).resolve(); ops = ops_dir(root); hs = harness_status(root); why = []
    if hs["fitted"] < 6:
        why.append(f"the harness is not installed ({hs['fitted']} of 6 pieces): python3 agent_company.py harness .")
    elif not hs["committed"]:
        why.append("commit the harness files first, so every worktree carries the guard: python3 agent_company.py harness . --commit")
    if kill_file(root) is not None:
        why.append("the kill switch is on (.harness/KILL); only a named person lifts it")
    if not (ops / "inbox").is_dir() or not any((ops / "inbox").glob("[0-9][0-9][0-9]_*.md")):
        why.append("nothing in the inbox: write an instruction first")
    st = runner_status(root)
    if st.get("state") in ("running", "starting"):
        why.append(f"a runner is already running (pid {st.get('pid')}); exactly one coordinator at a time")
    return why


def start_runner(repo, tool: str, argv: list[str] | None = None, extra: list[str] | None = None) -> dict:
    root = Path(repo).resolve()
    if argv is None:
        if tool not in HEADLESS:
            return {"error": f"{tool} has no headless mode here; use: python3 agent_company.py start . --tool {tool}"}
        argv = HEADLESS[tool] + list(extra or [])
    why = runner_ready(root)
    if why:
        return {"error": "; ".join(why)}
    if not shutil.which(argv[0]):
        return {"error": f"{argv[0]} is not installed or not on PATH"}
    out = ops_dir(root) / "outbox"; out.mkdir(parents=True, exist_ok=True)
    (out / ".runner.stop").unlink(missing_ok=True)
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _runner_file(root).write_text(json.dumps({"state": "starting", "tool": tool, "started": started, "supervisor": os.getpid()}), encoding="utf-8")
    kw = {"start_new_session": True} if os.name != "nt" else {"creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)}
    sup = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "_supervise", str(root), tool, json.dumps(argv)],
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kw)
    end = time.time() + 5
    while time.time() < end:
        st = runner_status(root)
        if st.get("supervisor") == sup.pid and st.get("state") != "starting":
            break
        time.sleep(.05)
    return {**runner_status(root), "log": str(out / "runner.log")}


def stop_runner(repo) -> dict:
    root = Path(repo).resolve(); st = runner_status(root)
    if st.get("state") not in ("running", "starting"):
        return st
    (ops_dir(root) / "outbox" / ".runner.stop").write_text("stop", encoding="utf-8")
    return st


def _supervise(repo: str, tool: str, argv_json: str) -> int:
    root = Path(repo).resolve(); out = ops_dir(root) / "outbox"; rf = _runner_file(root)
    argv = json.loads(argv_json); started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    def write(**kv):
        rf.write_text(json.dumps({"tool": tool, "started": started, "supervisor": os.getpid(), "log": "docs/ops/outbox/runner.log", **kv}), encoding="utf-8")
    with open(out / "runner.log", "a", encoding="utf-8") as log:
        log.write(f"\n=== {started}  {tool}: one coordinator, one instruction ===\n"); log.flush()
        kw = {"start_new_session": True} if os.name != "nt" else {"creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)}
        try:
            child = subprocess.Popen(argv, cwd=root, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, **kw)
        except OSError as e:
            write(state="exited", exit=127, error=str(e), ended=started); return 1
        write(state="running", pid=child.pid)
        def end(state):
            try:
                os.killpg(child.pid, 15) if os.name != "nt" else child.terminate()
            except OSError:
                pass
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(child.pid, 9) if os.name != "nt" else child.kill()
                except OSError:
                    pass
                child.wait()
            log.write(f"=== {state} by the supervisor ===\n")
            write(state=state, pid=child.pid, exit=child.returncode, ended=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        while True:
            code = child.poll()
            if code is not None:
                write(state="exited", pid=child.pid, exit=code, ended=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())); break
            if kill_file(root) is not None:
                end("killed"); break
            if (out / ".runner.stop").exists():
                end("stopped"); break
            time.sleep(.2)
    (out / ".runner.stop").unlink(missing_ok=True)
    return 0


def cmd_run(repo: str, tool: str, status: bool, stop: bool, extra: list[str]) -> int:
    root = Path(repo).resolve()
    if status or stop:
        st = stop_runner(root) if stop else runner_status(root)
        if stop and st.get("state") in ("running", "starting"):
            end = time.time() + 8
            while time.time() < end and runner_status(root).get("state") in ("running", "starting"):
                time.sleep(.2)
            st = runner_status(root)
        print(f"runner: {st.get('state')}" + (f"  tool {st.get('tool')}  pid {st.get('pid')}  started {st.get('started')}" if st.get("tool") else "")
              + (f"  exit {st.get('exit')}" if "exit" in st else ""))
        return 0
    r = start_runner(root, tool, extra=extra)
    if r.get("error"):
        print("not started: " + r["error"]); return 1
    print(f"Coordinator running in the background ({tool}, pid {r.get('pid')}). It does the lowest-numbered instruction, then stops.\n"
          f"  log:    {r['log']}\n  status: python3 agent_company.py run . --status\n  stop:   python3 agent_company.py run . --stop\n"
          "A headless agent can use only the tools this project's settings allow. The World shows its state in the Coordinator tower.")
    return 0


def _print_checks(rows: list[dict]) -> bool:
    bad = False
    for r in rows:
        mark = "✓" if r["ok"] else ("–" if r["ok"] is None else "✗")
        print(f"  {mark} {r['check']}: {r['detail']}")
        if r["ok"] is False and r["fix"]:
            print(f"      → {r['fix']}")
            bad = True
    return not bad


def cmd_doctor(repo: str | None) -> int:
    print(f"Agent Company {VERSION}: doctor")
    ok = _print_checks(doctor(repo))
    print("\nAll set." if ok else "\nFix the ✗ lines above (each says how), then run the doctor again.")
    return 0 if ok else 1


def cmd_smoke(repo: str) -> int:
    """One gate before you trust a run: doctor, instruction check, ledger verification, harness. Writes a dated PASS/FAIL report."""
    root = Path(repo).resolve()
    rows = doctor(root)
    inbox = ops_dir(root) / "inbox"
    bad_inst = []
    for p in sorted(inbox.glob("[0-9][0-9][0-9]_*.md")) if inbox.is_dir() else []:
        probs = check_text(p.name, p.read_text(encoding="utf-8"))
        if probs:
            bad_inst.append(f"{p.name}: {'; '.join(probs)}")
    rows.append(_check("Instructions", not bad_inst if inbox.is_dir() else None, "all complete" if not bad_inst else "; ".join(bad_inst), "Fix each instruction, or let the Guild write it."))
    passed = all(r["ok"] is not False for r in rows)
    lines = [f"# Smoke check: {'PASS' if passed else 'FAIL'}", "", f"Project: {root}", f"Time: {time.strftime('%Y-%m-%d %H:%M %Z')}", f"Agent Company {VERSION}", ""]
    for r in rows:
        lines.append(f"- {'PASS' if r['ok'] else ('n/a' if r['ok'] is None else 'FAIL')} · {r['check']}: {r['detail']}" + (f" → {r['fix']}" if r['ok'] is False and r['fix'] else ""))
    lines += ["", "A check marked n/a had nothing to check yet. It is not counted as a pass or a fail."]
    out = ops_dir(root) / "outbox"
    if out.is_dir():
        f = out / f"smoke-{time.strftime('%Y-%m-%d')}.md"
        f.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0 if passed else 1


def _git_init(root: Path) -> None:
    if _git(root, "rev-parse", "--show-toplevel"):
        return
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "symbolic-ref", "HEAD", "refs/heads/main"], check=True)
    if not _git(root, "config", "user.name"):
        subprocess.run(["git", "-C", str(root), "config", "user.name", "Agent Company owner"], check=True)
    if not _git(root, "config", "user.email"):
        subprocess.run(["git", "-C", str(root), "config", "user.email", "owner@example.invalid"], check=True)
    readme = root / "README.md"
    if not readme.exists():
        readme.write_text("# My project\n\nRun by Agent Company: see docs/ops/.\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "Start the project"], check=True)


def cmd_launch(repo: str | None, port: int, open_browser: bool) -> int:
    """The zero-knowledge start: a project folder, git, the ops layout and the Guild, in one step."""
    root = Path(repo).expanduser().resolve() if repo else DEFAULT_HOME / "my-first-team"
    print(f"Agent Company {VERSION}: starting {root}")
    rows = doctor()
    if not _print_checks(rows[:2]):
        print("\nFix the line marked ✗, then start again."); return 1
    root.mkdir(parents=True, exist_ok=True)
    try:
        _git_init(root)
    except subprocess.CalledProcessError as e:
        print(f"  ✗ couldn't set up git in {root}: {e}"); return 1
    if not (ops_dir(root) / "inbox").is_dir():
        with contextlib.redirect_stdout(io.StringIO()):
            cmd_init(str(root))
        print("  ✓ Agent Company set up in docs/ops/")
    print(f"\nOpening the World. Your project lives in: {root}\nTo stop, close this window or press Ctrl+C.\n")
    return cmd_ui(str(root), port, open_browser, "/world")


AGENT_CLASS_HINTS = [("master", r"\b(owner|creative[- ]director|ceo|founder)\b"), ("leader", r"\b(producer|coordinator|project manager|scrum|release[- ]manager)\b"),
                     ("herald", r"\b(technical[- ]director|chief of staff|lead|director|planner|writer of orders)\b"), ("paladin", r"\b(qa|review|evaluator|auditor|tester|verif)"),
                     ("rogue", r"\b(security|red[- ]team|penetration|challenger|break|adversar)"), ("scribe", r"\b(writer|narrative|community|localization|documentation|claims)\b"),
                     ("ranger", r"\b(analytics|monitor|live[- ]ops|watch|performance)\b")]


NAME_HINTS = [("master", r"\b(owner|creative director|ceo|founder)\b"), ("leader", r"\b(producer|coordinator|release manager|scrum)\b"),
              ("paladin", r"\b(qa|tester|reviewer|evaluator|auditor)\b"), ("rogue", r"\b(security|red team|challenger)\b"),
              ("ranger", r"\b(analytics|monitor|live ops|watch)\b"), ("scribe", r"\b(writer|community|localization|docs?)\b"),
              ("herald", r"\b(director|lead|chief)\b"), ("artificer", r"\b(programmer|engineer|developer|builder|specialist|designer|artist|prototyper|world builder)\b")]


def cmd_import_agents(repo: str, source: str, origin: str) -> int:
    """Turn a folder of Claude Code subagents (.claude/agents/*.md, e.g. Claude Code Game Studios) into Guild characters."""
    src = Path(source).expanduser().resolve()
    files = sorted((src / ".claude" / "agents").glob("*.md")) if (src / ".claude" / "agents").is_dir() else sorted(src.glob("*.md"))
    if not files:
        print(f"no agent files found in {src}/.claude/agents/"); return 1
    ops = ops_dir(repo)
    g = ops / "guild" / "guild.json"
    try:
        guild = json.loads(g.read_text(encoding="utf-8")) if g.exists() else {}
    except ValueError:
        guild = {}
    guild.setdefault("heroes", {}); guild.setdefault("slots", {}); guild.setdefault("quests", []); guild.setdefault("chron", []); guild.setdefault("seq", 1); guild.setdefault("qseq", 1)
    have = {h.get("name") for h in guild["heroes"].values()}
    allow = {"master": [], "herald": ["GitHub: read"], "leader": ["git (local)", "GitHub: pull requests", "filesystem: worktree only"],
             "artificer": ["git (local)", "GitHub: pull requests", "filesystem: worktree only", "test runner"], "paladin": ["git (local)", "GitHub: read", "test runner"],
             "rogue": ["git (local)", "filesystem: worktree only", "test runner"], "scribe": ["GitHub: read"], "ranger": ["GitHub: read"]}
    added = []
    for f in files:
        text = f.read_text(encoding="utf-8", errors="replace")[:4000]
        m = re.search(r"^name:\s*(.+)$", text, re.M); d = re.search(r"^description:\s*\"?(.+?)\"?\s*$", text, re.M)
        name = (m.group(1).strip() if m else f.stem).replace("-", " ").title()
        if name in have:
            continue
        desc = (d.group(1) if d else "").lower()
        cls = next((c for c, rx in NAME_HINTS if re.search(rx, name.lower())), None) or \
            next((c for c, rx in AGENT_CLASS_HINTS if re.search(rx, desc)), "artificer")
        if cls == "master":
            cls = "herald"        # the owner is a person; an imported agent never takes the owner's seat
        hid = f"h{guild['seq']}"; guild["seq"] += 1
        guild["heroes"][hid] = {"id": hid, "name": name, "cls": cls, "origin": origin, "skin": len(added) % 5, "hair": len(added) % 6, "tunic": None,
                                "harness": ["helm", "chest", "hands", "belt", "boots", "amulet"], "allow": allow[cls], "xp": 0, "lv": 1, "probation": 0, "history": [],
                                "talents": [], "lessons": [], "record": {"won": 0, "back": 0, "defects": 0}, "source": str(f.relative_to(src)) if src in f.parents else f.name,
                                "brief": (d.group(1)[:200] if d else "")}
        added.append(f"{name} → {CLASS_ROLE.get(cls, cls)}")
    g.parent.mkdir(parents=True, exist_ok=True)
    g.write_text(json.dumps(guild, indent=1), encoding="utf-8")
    print(f"imported {len(added)} agent(s) into {g}:\n  " + "\n  ".join(added[:60]) + ("\n  …" if len(added) > 60 else ""))
    print("Open the World (agent_company.py world) to see them in the Team quarters. Every imported agent wears the full harness and starts at level 1; Guild mode (agent_company.py guild) places them on its map.")
    return 0

# ---------------------------------------------------------------- ui (local server, 127.0.0.1 only)
SAFE_NAME = re.compile(r"^(ROLES\.md|COORDINATOR_PROMPT\.txt|inbox/README\.md|inbox/\d{3}_[a-z0-9-]+\.md|guild/[a-z0-9-]{1,40}\.md)$")


def deploy_files(ops: Path, files: list, plan: dict | None, guild: dict | None = None) -> dict:
    written, kept, refused = [], [], []
    for item in files:
        if not (isinstance(item, list) and len(item) == 2 and all(isinstance(x, str) for x in item)):
            refused.append(str(item)[:40]); continue
        name, text = item
        if not SAFE_NAME.match(name) or len(text) > 100_000:
            refused.append(name); continue
        target = ops / name
        if name.startswith("inbox/") and name != "inbox/README.md":
            probs = check_text(Path(name).name, text)
            if probs:
                refused.append(f"{name} ({'; '.join(probs)})"); continue
            if write_new(target, text):
                written.append(name)
            else:
                kept.append(name)                 # never overwrite an instruction someone may be working on
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
            written.append(name)
    if isinstance(plan, dict):
        (ops / "plan.json").write_text(json.dumps(plan, indent=1), encoding="utf-8")
    if isinstance(guild, dict):
        (ops / "guild").mkdir(exist_ok=True)
        (ops / "guild" / "guild.json").write_text(json.dumps(guild, indent=1), encoding="utf-8")
    return {"written": written, "kept": kept, "refused": refused}


def make_handler(ops: Path, token: str):
    def wrap(page: str) -> str:
        if "<html" in page.lower():
            return page
        return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"></head><body>' + page + "</body></html>"
    page = wrap(UI.read_text(encoding="utf-8"))
    guild_page = wrap(GUILD.read_text(encoding="utf-8")) if GUILD.exists() else page
    world_page = wrap(WORLD.read_text(encoding="utf-8")) if WORLD.exists() else page

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):  # quiet
            pass

        def _ok_token(self) -> bool:
            q = parse_qs(urlparse(self.path).query)
            return secrets.compare_digest(q.get("token", [""])[0], token)

        def _send(self, code: int, body: str, ctype="application/json"):
            data = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype + "; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            path = urlparse(self.path).path
            if path in ("/", "/index.html"):
                return self._send(200, page, "text/html")
            if path in ("/guild", "/guild/"):
                return self._send(200, guild_page, "text/html")
            if path == "/favicon.ico":
                self.send_response(204); self.end_headers(); return
            if path in ("/world", "/world/"):
                return self._send(200, world_page, "text/html")
            if path.startswith("/vendor/"):
                name = path[len("/vendor/three/"):] if path.startswith("/vendor/three/") else ""
                f = HERE / "ui" / "vendor" / "three" / name
                if name not in VENDOR or not f.is_file():        # a fixed list of names: no path can climb out
                    return self._send(404, '{"error":"not found"}')
                return self._send(200, f.read_text(encoding="utf-8"), "text/javascript")
            if not self._ok_token():
                return self._send(403, '{"error":"bad token"}')
            if path == "/api/world":
                return self._send(200, json.dumps(world_state(ops.parent.parent)))
            if path == "/api/info":
                return self._send(200, json.dumps({"repo": str(ops.parent.parent), "ops": str(ops), "version": VERSION}))
            if path == "/api/plan":
                p = ops / "plan.json"
                return self._send(200, p.read_text(encoding="utf-8") if p.exists() else "null")
            q = parse_qs(urlparse(self.path).query)
            if path == "/api/records":
                quest = q.get("quest", [""])[0]
                led = [l for l in _ledger(ops.parent.parent) if l.get("id") and (not quest or l.get("quest") == quest)]
                return self._send(200, json.dumps([verify_record(ops.parent.parent, l["id"]) for l in led[-20:]][::-1]))
            if path == "/api/verify":
                return self._send(200, json.dumps(verify_record(ops.parent.parent, q.get("id", [""])[0])))
            if path == "/api/stage":
                return self._send(200, json.dumps({**stage(ops.parent.parent), "doctor": doctor(ops.parent.parent)}))
            if path == "/api/harness":
                return self._send(200, json.dumps(harness_status(ops.parent.parent)))
            if path == "/api/guild":
                g = ops / "guild" / "guild.json"
                return self._send(200, g.read_text(encoding="utf-8") if g.exists() else "null")
            return self._send(404, '{"error":"not found"}')

        def do_POST(self):
            path = urlparse(self.path).path
            if path not in ("/api/deploy", "/api/harness/install", "/api/harness/commit") or not self._ok_token():
                return self._send(403, '{"error":"refused"}')
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                return self._send(415, '{"error":"json only"}')
            n = int(self.headers.get("Content-Length", "0"))
            if n > 2_000_000:
                return self._send(413, '{"error":"too large"}')
            try:
                body = json.loads(self.rfile.read(n) or b"{}")
            except json.JSONDecodeError:
                return self._send(400, '{"error":"bad json"}')
            if path == "/api/harness/install":
                return self._send(200, json.dumps(install_harness(ops.parent.parent)))
            if path == "/api/harness/commit":
                return self._send(200, json.dumps(commit_harness(ops.parent.parent)))
            return self._send(200, json.dumps(deploy_files(ops, body.get("files", []), body.get("plan"), body.get("guild"))))

    return H


def cmd_ui(repo: str, port: int, open_browser: bool, page: str = "/") -> int:
    ops = ops_dir(repo)
    if not (ops / "inbox").is_dir():
        cmd_init(repo)
    token = secrets.token_urlsafe(18)
    srv = ThreadingHTTPServer(("127.0.0.1", port), make_handler(ops, token))
    url = f"http://127.0.0.1:{srv.server_address[1]}{page}?token={token}"
    print(f"Agent Company {({'/guild': 'Guild', '/world': 'World'}).get(page, 'Command')}: {url}\nWrites into {ops}. Press Ctrl+C to stop.")
    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


# Claim words never used in public text: say what was tested, and "maps to", instead.
CLAIM_WORDS = ("warranty", "warranties", "warranted", "certified", "certify", "compliant", "secure", "safe", "guarantee",
               "guaranteed", "guarantees", "best")
CLAIM_RE = re.compile(r"(?<![\w-])(" + "|".join(CLAIM_WORDS) + r")(?![\w-])", re.I)
CLAIM_EXT = (".md", ".html", ".htm", ".txt", ".srt")


def _visible_lines(path: Path):
    """(line number, visible text): for HTML, style and script blocks and tags (with their attributes) are blanked,
    so CSS such as safe-area-inset never counts. A line with the marker claims-ok is skipped."""
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() in (".html", ".htm"):
        keep = lambda m: "\n" * m.group(0).count("\n")
        text = re.sub(r"<(style|script)\b.*?</\1>", keep, text, flags=re.S | re.I)
        text = re.sub(r"<!--.*?-->", keep, text, flags=re.S)
        text = re.sub(r"<[^>]*>", lambda m: " " + keep(m), text, flags=re.S)
    for n, line in enumerate(text.splitlines(), 1):
        if "claims-ok" not in line:
            yield n, line


def claim_hits(paths) -> list:
    files = []
    for p in paths:
        p = Path(p)
        if p.is_dir():
            files += sorted(f for f in p.rglob("*") if f.suffix.lower() in CLAIM_EXT and f.is_file()
                            and not any(part in (".git", "node_modules", ".arena") for part in f.parts))
        elif p.is_file():
            files.append(p)
    hits = []
    for f in files:
        for n, line in _visible_lines(f):
            for m in CLAIM_RE.finditer(line):
                hits.append((str(f), n, m.group(0), line.strip()[:120]))
    return hits


def cmd_claims(paths) -> int:
    hits = claim_hits(paths or ["."])
    for f, n, w, line in hits:
        print(f"{f}:{n}: '{w}' · {line}")
    print(f"claims check: {'PASS, no claim words' if not hits else f'{len(hits)} claim word(s) to rewrite'}"
          " (warranty, certified, compliant, secure, safe, guaranteed, best; say what was tested, or \"maps to\")")
    return 1 if hits else 0


def cmd_council(a) -> int:
    import council as C
    root = Path(a.repo).resolve()
    if a.action == "seats":
        for s in C.SEATS:
            print(f"{s['key']:9} {s['name']:15} {'(on the default board) ' if s['key'] in C.DEFAULT_BOARD else ''}{s['question']}")
        return 0
    if a.action == "protocol":
        print(C.PROTOCOL); return 0
    if a.action == "agents":
        made = C.agent_files(root, a.seats.split(",") if a.seats else None)
        print("written:\n  " + "\n  ".join(made) + "\nOpen a new Claude Code session so the seats load as agents."); return 0
    try:
        if a.action == "init":
            if not a.arg:
                print('give the decision: council init "<decision>" --options "A=...,B=..." (or --self-eval)'); return 1
            opts = dict(o.split("=", 1) for o in re.split(r",(?=\s*[A-Z]=)", a.options)) if a.options else None
            opts = {k.strip(): v.strip() for k, v in opts.items()} if opts else None
            board = a.seats.split(",") if a.seats else (C.QUICK_BOARD if a.quick else None)
            weights = dict(w.split("=") for w in a.weights.split(",")) if a.weights else None
            f = C.init(ops_dir(a.repo), a.arg, opts, board, weights, "self-eval" if a.self_eval else "decision")
            print(f"council ready: {f.relative_to(root)}\nnext: the Chair runs the rounds (agent_company.py council protocol)")
            return 0
        folder = Path(a.arg) if a.arg else None
        if not folder or not (folder / "brief.json").exists():
            folder = root / a.arg if a.arg else None
        if not folder or not (folder / "brief.json").exists():
            print("give the council folder (docs/ops/council/<date>-<slug>)"); return 1
        folder = folder.resolve()
        if a.action == "score":
            v = C.score(folder)
            print(f"{v['label']} on {v['recommended']}: {v['recommended_text']}")
            for o in v["math"].values():
                print("  " + o)
            print(f"spread {v['spread']:g}, confidence {v['confidence']}/10" + "".join(f"\n  override: {o}" for o in v["overrides"]))
            print(f"written: {(folder / 'verdict.md').relative_to(root)}")
            return 0
        if a.action == "seal":
            if not (folder / "verdict.json").exists():
                print("score it first: agent_company.py council score <folder>"); return 1
            import council as C2
            words = C2.claim_words(folder, include_verdict=True)
            if words:
                print("not sealed: claim words in this council's files (rewrite them, score again, then seal):\n  " + "\n  ".join(words)); return 1
            changed = C2.unchanged_since_scoring(folder)
            if changed:
                print("not sealed: changed after scoring: " + ", ".join(changed) + ". Score again, then seal."); return 1
            files = [{"file": str(p.relative_to(root)), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                     for p in sorted(folder.glob("*")) if p.is_file()]
            v = json.loads((folder / "verdict.json").read_text(encoding="utf-8"))
            rid = seal_doc(root, "council", {"session": str(folder.relative_to(root)), "label": v["label"],
                                             "recommended": v["recommended"], "option_scores": v["option_scores"], "files": files})
            print(f"sealed: {rid} (check it with: agent_company.py verify {a.repo} {rid})")
            return 0
    except ValueError as e:
        print(f"council: {e}"); return 1
    print("unknown council action"); return 1


def cmd_cosign(repo: str, rid: str | None) -> int:
    """Add an Ed25519 signature to records this machine signed with HMAC, so they can be checked anywhere."""
    root = Path(repo).resolve()
    k = _key(False)
    if k is None:
        print("no HMAC key on this machine: only the machine that sealed a record can cosign it"); return 1
    if not _ed_key(True):
        print("ssh-keygen isn't available, so no Ed25519 key can be made here"); return 1
    done, skipped = [], []
    for l in _ledger(root):
        i = l.get("id")
        if not i or (rid and i != rid):
            continue
        p = _evdir(root) / f"{i}.json"
        rec = json.loads(p.read_text(encoding="utf-8"))
        if rec.get("sig_ed25519"):
            continue
        v = verify_record(root, i)
        own = hmac.compare_digest(hmac.new(k, rec.get("hash", "").encode(), hashlib.sha256).hexdigest(), rec.get("sig", ""))
        if not own or not v["ok"] or hashlib.sha256(_canon(rec)).hexdigest() != rec.get("hash"):
            skipped.append(i); continue
        rec.update(_ed_sign(root, rec["hash"]))
        p.write_text(json.dumps(rec, indent=1, ensure_ascii=False), encoding="utf-8"); done.append(i)
    print(("cosigned (Ed25519): " + ", ".join(done)) if done else "nothing to cosign")
    if skipped:
        print("skipped (not signed on this machine, or not intact): " + ", ".join(skipped))
    if done:
        print("commit docs/ops/evidence/ (the records and allowed_signers) so others can check them")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="agent_company.py", description="Run a company of AI agents as one orchestrated team.")
    ap.add_argument("--version", action="version", version=VERSION)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("init", "check", "status"):
        s = sub.add_parser(name); s.add_argument("repo", nargs="?", default=".")
    s = sub.add_parser("ui"); s.add_argument("repo", nargs="?", default="."); s.add_argument("--port", type=int, default=8765); s.add_argument("--no-browser", action="store_true")
    s = sub.add_parser("guild"); s.add_argument("repo", nargs="?", default="."); s.add_argument("--port", type=int, default=8765); s.add_argument("--no-browser", action="store_true")
    s = sub.add_parser("world", help="the live 3D world: see the real state of this repo and deploy step by step"); s.add_argument("repo", nargs="?", default="."); s.add_argument("--port", type=int, default=8765); s.add_argument("--no-browser", action="store_true")
    s = sub.add_parser("seal", help="re-run the tests and write a chained, signed evidence record")
    s.add_argument("repo", nargs="?", default="."); s.add_argument("--quest", required=True); s.add_argument("--pr", default="")
    s.add_argument("--verdict", default="approve"); s.add_argument("--test-cmd", dest="test_cmd", required=True); s.add_argument("--workdir", default="")
    s.add_argument("--evaluator", default=""); s.add_argument("--builder", default=""); s.add_argument("--challenger", default=""); s.add_argument("--defects", type=int, default=0)
    s.add_argument("--verifier", default="", help="an OpenProof verifier command; the record's path is appended"); s.add_argument("--timeout", type=int, default=1800)
    s = sub.add_parser("verify"); s.add_argument("repo", nargs="?", default="."); s.add_argument("id", nargs="?"); s.add_argument("--rerun", action="store_true"); s.add_argument("--json", action="store_true")
    s.add_argument("--signers", default="", help="an allowed_signers file you trust, instead of the one in the repo; with --rerun it must be outside the repo")
    s = sub.add_parser("cosign", help="add an Ed25519 signature to records this machine sealed, so anyone can check them"); s.add_argument("repo", nargs="?", default="."); s.add_argument("id", nargs="?")
    s = sub.add_parser("harness"); s.add_argument("repo", nargs="?", default="."); s.add_argument("--check", action="store_true"); s.add_argument("--commit", action="store_true", help="commit the harness files so every worktree carries the guard")
    s = sub.add_parser("run", help="one coordinator in the background, with no window, on one instruction"); s.add_argument("repo", nargs="?", default="."); s.add_argument("--tool", choices=sorted(HEADLESS), default="claude"); s.add_argument("--status", action="store_true"); s.add_argument("--stop", action="store_true"); s.add_argument("--tool-arg", action="append", default=[], help="an extra argument for the tool, added on your own judgement")
    s = sub.add_parser("_supervise"); s.add_argument("repo"); s.add_argument("tool"); s.add_argument("argv")
    s = sub.add_parser("card"); s.add_argument("repo", nargs="?", default="."); s.add_argument("agent", nargs="?"); s.add_argument("--seal", action="store_true")
    s = sub.add_parser("trust"); s.add_argument("repo", nargs="?", default="."); s.add_argument("--json", action="store_true"); s.add_argument("--seal", action="store_true")
    s = sub.add_parser("launch", help="the zero-knowledge start: folder, git, setup and the World in one step"); s.add_argument("repo", nargs="?"); s.add_argument("--port", type=int, default=8765); s.add_argument("--no-browser", action="store_true")
    s = sub.add_parser("doctor"); s.add_argument("repo", nargs="?")
    s = sub.add_parser("smoke"); s.add_argument("repo", nargs="?", default=".")
    s = sub.add_parser("import-agents", help="turn .claude/agents/*.md (e.g. Claude Code Game Studios) into team members")
    s.add_argument("source"); s.add_argument("--repo", default="."); s.add_argument("--origin", default="Claude Code")
    s = sub.add_parser("council", help="Review Council: a board of role seats that self-evaluates a decision or finished work")
    s.add_argument("action", choices=["seats", "protocol", "agents", "init", "score", "seal"]); s.add_argument("arg", nargs="?")
    s.add_argument("--repo", default="."); s.add_argument("--options", default=""); s.add_argument("--seats", default="")
    s.add_argument("--weights", default=""); s.add_argument("--quick", action="store_true"); s.add_argument("--self-eval", dest="self_eval", action="store_true")
    s = sub.add_parser("claims", help="check public text for claim words (warranty, certified, compliant, secure, safe, guaranteed, best)"); s.add_argument("paths", nargs="*")
    s = sub.add_parser("start"); s.add_argument("repo", nargs="?", default="."); s.add_argument("--tool", choices=["claude", "codex", "gemini", "cursor", "copilot"], default="claude"); s.add_argument("--run", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "init":
        return cmd_init(a.repo)
    if a.cmd == "check":
        return cmd_check(a.repo)
    if a.cmd == "status":
        return cmd_status(a.repo)
    if a.cmd == "ui":
        return cmd_ui(a.repo, a.port, not a.no_browser)
    if a.cmd == "launch":
        return cmd_launch(a.repo, a.port, not a.no_browser)
    if a.cmd == "doctor":
        return cmd_doctor(a.repo)
    if a.cmd == "smoke":
        return cmd_smoke(a.repo)
    if a.cmd == "import-agents":
        return cmd_import_agents(a.repo, a.source, a.origin)
    if a.cmd == "council":
        return cmd_council(a)
    if a.cmd == "claims":
        return cmd_claims(a.paths)
    if a.cmd == "seal":
        return cmd_seal(a.repo, a)
    if a.cmd == "verify":
        return cmd_verify(a.repo, a.id, a.rerun, a.json, a.signers)
    if a.cmd == "cosign":
        return cmd_cosign(a.repo, a.id)
    if a.cmd == "harness":
        return cmd_harness(a.repo, a.check and not a.commit, a.commit)
    if a.cmd == "run":
        return cmd_run(a.repo, a.tool, a.status, a.stop, a.tool_arg)
    if a.cmd == "_supervise":
        return _supervise(a.repo, a.tool, a.argv)
    if a.cmd == "card":
        return cmd_card(a.repo, a.agent, a.seal)
    if a.cmd == "trust":
        return cmd_trust(a.repo, a.json, a.seal)
    if a.cmd == "world":
        return cmd_ui(a.repo, a.port, not a.no_browser, "/world")
    if a.cmd == "guild":
        return cmd_ui(a.repo, a.port, not a.no_browser, "/guild")
    return cmd_start(a.repo, a.tool, a.run)


if __name__ == "__main__":
    sys.exit(main())
