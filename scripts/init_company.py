"""Create the agent-company structure in a repository. Standard library only; never overwrites an existing file."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
README = """# Instruction inbox

The chief of staff writes one file per instruction: `NNN_short-name.md`.
The coordinator (exactly one session):
1. Reads `inbox/` in number order, except this README, and follows each file's order notes.
2. For each instruction, works in its own worktree or branch, never in the main folder and never on a protected branch.
3. Has a builder do it: failing tests first, then the change, the named tests, upload, a pull request, an evaluator brief. Never merges.
4. Moves the instruction to `done/` only after its pull request is merged (check the remote), and writes `outbox/NNN_report.md`.
5. Rewrites `outbox/STATUS.md` after every step, checked against the remote, using the status template.
6. When blocked: writes the block into STATUS.md and stops. It never routes around a guard.
"""
ROLES = """# Roles (one agent per job)

| Role | Who | Never does |
|---|---|---|
| Owner | <name> | builds |
| Chief of staff | <session/tool> | builds, merges |
| Coordinator | <one session> | builds in the main folder, merges |
| Builder | <tool, one per branch> | reviews its own work, merges |
| Challenger | <session> | fixes |
| Independent evaluator | <different model/vendor> | edits the builder's branch |
| Claims officer | <session/check> | approves content |
| Watch | <scheduled task> | anything but reading and queueing builder steps |
"""

def write(p: Path, text: str):
    if p.exists():
        print("kept", p); return
    p.parent.mkdir(parents=True, exist_ok=True); p.write_text(text, encoding="utf-8"); print("created", p)

def main(repo: str):
    ops = Path(repo).resolve() / "docs" / "ops"
    for d in ("inbox", "done", "outbox", "templates"):
        (ops / d).mkdir(parents=True, exist_ok=True)
    write(ops / "inbox" / "README.md", README)
    write(ops / "ROLES.md", ROLES)
    for t in (HERE / "templates").glob("*.md"):
        write(ops / "templates" / t.name, t.read_text(encoding="utf-8"))
    write(ops / "outbox" / "STATUS.md", (HERE / "templates" / "status.md").read_text(encoding="utf-8"))

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python3 init_company.py <repo>")
    main(sys.argv[1])
