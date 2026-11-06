"""Refuse instructions that would leave an agent guessing. Standard library only. Exit 1 on any problem."""
import re, sys
from pathlib import Path

NEEDED = {
    "owner's words (a quote)": re.compile(r"owner'?s? (words|decision|go)|^owner[, ]", re.I | re.M),
    "a branch": re.compile(r"^branch:|branch[: ]+`[^`]+`", re.I | re.M),
    "tests to run": re.compile(r"\btests?\b", re.I),
    "a stop point (don't merge)": re.compile(r"don'?t merge|do not merge|stop there|stop point", re.I),
}

def check(repo: str) -> int:
    inbox = Path(repo) / "docs" / "ops" / "inbox"
    bad = 0
    files = sorted(p for p in inbox.glob("*.md") if p.name.lower() != "readme.md")
    if not files:
        print("inbox empty"); return 0
    for p in files:
        text = p.read_text(encoding="utf-8")
        if not re.match(r"^\d{3}_[a-z0-9-]+\.md$", p.name):
            print(f"{p.name}: name must be NNN_short-name.md"); bad += 1
        missing = [k for k, rx in NEEDED.items() if not rx.search(text)]
        if re.search(r"--force|-f\b.*push|push.*\b-f\b", text) and "never" not in text.lower():
            missing.append("no force-push")
        for m in missing:
            print(f"{p.name}: missing {m}"); bad += 1
        if not missing:
            print(f"{p.name}: ok")
    return 1 if bad else 0

if __name__ == "__main__":
    sys.exit(check(sys.argv[1] if len(sys.argv) > 1 else "."))
