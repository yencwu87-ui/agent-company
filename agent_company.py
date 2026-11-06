#!/usr/bin/env python3
"""Agent Company: run a company of AI agents as one orchestrated team.

Standard library only (Python 3.9+). Works with any agent tool that reads files.

    python3 agent_company.py init   [repo]             create docs/ops (inbox, done, outbox, templates, ROLES.md)
    python3 agent_company.py ui     [repo] [--port N]  open the drag-and-drop Command map; Deploy writes into the repo
    python3 agent_company.py guild  [repo] [--port N]  open Guild mode (the game): forge, fit the harness, deploy, prove, train
    python3 agent_company.py check  [repo]             refuse instructions missing the owner's words, a branch, tests or a stop point
    python3 agent_company.py status [repo]             what is pending, in progress, done, and what needs the owner
    python3 agent_company.py start  [repo] [--tool claude|codex|gemini|cursor|copilot] [--run]
                                                       print (or run) the command that starts the coordinator

Nothing here merges, pushes or deletes. Owner-only steps stay with a person.
"""
from __future__ import annotations

import argparse
import json
import re
import secrets
import shutil
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
VERSION = "0.2.0"

INBOX_README = """# Instruction inbox

The chief of staff writes one file per instruction: `NNN_short-name.md`.
The coordinator (exactly one session):
1. Reads inbox/ in number order, except this README, following each file's order notes.
2. Uses one worktree or branch per instruction, never the main folder and never a protected branch.
3. Has the named builder do it: failing tests first, then the change, the named tests, upload, a pull request, an evaluator brief. Never merges.
4. Sends the pull request to the named evaluator (and challenger, where named) and records their verdicts.
5. Moves the instruction to done/ only after its pull request is merged (check the remote), and writes outbox/NNN_report.md.
6. Rewrites outbox/STATUS.md after every step, checked against the remote.
7. When blocked: writes the block into STATUS.md and stops. Never routes around a guard.
"""

COORDINATOR_PROMPT = ("You are the coordinator. Follow docs/ops/inbox/README.md. Do every instruction in docs/ops/inbox/ "
                      "in number order. Update docs/ops/outbox/STATUS.md after each one. Never merge.")

NEEDED = {
    "the owner's words": re.compile(r"owner'?s? (words|decision|go)|^owner[, ]", re.I | re.M),
    "a branch": re.compile(r"^branch:|branch[: ]+`[^`]+`", re.I | re.M),
    "tests to run": re.compile(r"\btests?\b", re.I),
    "a stop point that says don't merge": re.compile(r"don'?t merge|do not merge", re.I),
}
PROTECTED = re.compile(r"^branch:\s*`?(main|master|develop/|release/)", re.I | re.M)


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
    if write_new(ops / "inbox" / "README.md", INBOX_README):
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
            if not self._ok_token():
                return self._send(403, '{"error":"bad token"}')
            if path == "/api/info":
                return self._send(200, json.dumps({"repo": str(ops.parent.parent), "ops": str(ops), "version": VERSION}))
            if path == "/api/plan":
                p = ops / "plan.json"
                return self._send(200, p.read_text(encoding="utf-8") if p.exists() else "null")
            if path == "/api/guild":
                g = ops / "guild" / "guild.json"
                return self._send(200, g.read_text(encoding="utf-8") if g.exists() else "null")
            return self._send(404, '{"error":"not found"}')

        def do_POST(self):
            if urlparse(self.path).path != "/api/deploy" or not self._ok_token():
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
            return self._send(200, json.dumps(deploy_files(ops, body.get("files", []), body.get("plan"), body.get("guild"))))

    return H


def cmd_ui(repo: str, port: int, open_browser: bool, page: str = "/") -> int:
    ops = ops_dir(repo)
    if not (ops / "inbox").is_dir():
        cmd_init(repo)
    token = secrets.token_urlsafe(18)
    srv = ThreadingHTTPServer(("127.0.0.1", port), make_handler(ops, token))
    url = f"http://127.0.0.1:{srv.server_address[1]}{page}?token={token}"
    print(f"Agent Company {'Guild' if page != '/' else 'Command'}: {url}\nWrites into {ops}. Press Ctrl+C to stop.")
    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="agent_company.py", description="Run a company of AI agents as one orchestrated team.")
    ap.add_argument("--version", action="version", version=VERSION)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("init", "check", "status"):
        s = sub.add_parser(name); s.add_argument("repo", nargs="?", default=".")
    s = sub.add_parser("ui"); s.add_argument("repo", nargs="?", default="."); s.add_argument("--port", type=int, default=8765); s.add_argument("--no-browser", action="store_true")
    s = sub.add_parser("guild"); s.add_argument("repo", nargs="?", default="."); s.add_argument("--port", type=int, default=8765); s.add_argument("--no-browser", action="store_true")
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
    if a.cmd == "guild":
        return cmd_ui(a.repo, a.port, not a.no_browser, "/guild")
    return cmd_start(a.repo, a.tool, a.run)


if __name__ == "__main__":
    sys.exit(main())
