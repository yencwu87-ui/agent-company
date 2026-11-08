#!/usr/bin/env python3
"""Agent Company harness guard: the six harness pieces, enforced as a Claude Code hook.

Installed by `agent_company.py harness <repo>` into docs/ops/harness/guard.py and wired in .claude/settings.json:
    PreToolUse  (Bash, Edit, Write, NotebookEdit, Read, WebFetch, WebSearch, mcp__*)  → python3 guard.py
    PostToolUse (*)                                                                  → python3 guard.py --log

Reads the tool call as JSON on stdin (Claude Code's hook input). Exit 2 blocks the call and tells the agent why.
Standard library only. Settings live next to this file:
    allowlist.json        the tools and MCP servers agents may use (the allowlist belt)
    real_data_paths.txt   paths that hold real data (constructed-data boots): never read, never sent anywhere

  Worktree helm          edits and writes stay inside the project folder
  Deny-rule plate        secrets and keys are never read or written (.env, *.pem, *.key, id_rsa, .ssh, credentials)
  No-merge gauntlets     no merge, no force push, no push or commit to main, master, develop/* or release/*
  Allowlist belt         MCP servers and web tools only when allowlisted
  Constructed-data boots no reading real-data paths; no uploading files with curl, scp or rsync
  Evidence amulet        every tool call is appended to docs/ops/evidence/actions.jsonl (PostToolUse)
"""
from __future__ import annotations

import fnmatch
import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or HERE.parent.parent.parent).resolve()
PROTECTED = re.compile(r"^(main|master|develop(/.*)?|release(/.*)?)$", re.I)
SECRET_GLOBS = [".env", ".env.*", "*.pem", "*.key", "*.p12", "*.pfx", "id_rsa*", "id_ed25519*", "*credentials*", "*.keychain*", "*secret*",
                ".netrc", "_netrc", ".npmrc", ".pypirc", ".git-credentials", ".pgpass", ".boto", "*.tfvars", "hosts.yml", "environ", ".credentials.json"]
SECRET_DIRS = [".ssh", ".aws", ".gnupg", ".config/gcloud", ".docker", ".kube", ".azure", ".config/gh", ".agent-company"]


def load_allow() -> dict:
    try:
        return json.loads((HERE / "allowlist.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"mcp_servers": [], "web": False}


def real_paths() -> list[str]:
    try:
        lines = (HERE / "real_data_paths.txt").read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    return [l.strip() for l in lines if l.strip() and not l.lstrip().startswith("#")]


def is_secret(p: str) -> bool:
    path = Path(os.path.expanduser(p))
    name = path.name.lower()
    if any(fnmatch.fnmatch(name, g) for g in SECRET_GLOBS):
        return True
    parts = [x.lower() for x in path.parts]
    return any(d.split("/")[0] in parts for d in SECRET_DIRS)


CWD = [PROJECT]   # the tool call's working folder; decide() sets it, so relative paths resolve the way the shell will


def is_real(p: str) -> bool:
    if not p:
        return False
    full = Path(os.path.expanduser(p))
    full = (CWD[0] / full).resolve() if not full.is_absolute() else full.resolve()
    for r in real_paths():
        rp = Path(os.path.expanduser(r))
        rp = (PROJECT / rp).resolve() if not rp.is_absolute() else rp.resolve()
        if full == rp or rp in full.parents:
            return True
    return False


def inside_project(p: str, cwd: Path) -> bool:
    full = Path(os.path.expanduser(p))
    full = (cwd / full).resolve() if not full.is_absolute() else full.resolve()
    return full == PROJECT or PROJECT in full.parents


# Files that hold the harness itself. An agent that could rewrite them could switch every piece off at once.
HARNESS_FILES = ("docs/ops/harness/", ".claude/settings.json", ".claude/settings.local.json")
SHELLS = {"sh", "bash", "zsh", "dash", "ksh", "fish", "csh", "tcsh", "eval", "source", ".", "exec", "mksh", "rbash", "yash", "pwsh",
          "powershell", "nu", "xonsh", "elvish", "busybox", "toybox", "ash", "oksh", "pdksh", "rc", "es", "osh", "ion", "script", "expect"}
SECRET_SAMPLES = [".env", ".env.local", "id_rsa", "id_ed25519", "server.pem", "server.key", "cert.p12", "credentials", "my_secret.txt"]
GLOB_CHARS = set("*?[")


def norm(p: str, cwd: Path) -> Path:
    """The path as the file system will see it: ~ expanded, relative to cwd, symlinks resolved, . and .. folded."""
    full = Path(os.path.expanduser(p))
    full = full if full.is_absolute() else cwd / full
    try:
        return full.resolve()
    except (OSError, RuntimeError):
        return Path(os.path.normpath(str(full)))


def touches_git(p: str, cwd: Path) -> bool:
    """True for anything inside a .git folder (any case: macOS disks fold case), after resolving links."""
    parts = [x.lower() for x in Path(os.path.normpath(os.path.expanduser(p))).parts] + [x.lower() for x in norm(p, cwd).parts]
    return ".git" in parts or ".gitconfig" in parts


def protected_parent(p: str, cwd: Path) -> str | None:
    """A folder that holds the harness, git's folder, or real data (moving or deleting it switches a piece off)."""
    base = norm(p, cwd)
    if not base.is_dir():
        return None
    for t in [PROJECT / h.rstrip("/") for h in HARNESS_FILES] + [PROJECT / ".git"] + [norm(r, PROJECT) for r in real_paths()]:
        if base == t or base in t.parents:
            return str(t.relative_to(PROJECT)) if PROJECT in t.parents else str(t)
    return None


def harness_file(p: str, cwd: Path) -> bool:
    home_claude = Path(os.path.expanduser("~/.claude")).resolve()
    if norm(p, cwd) == home_claude or home_claude in norm(p, cwd).parents:
        return True                                   # user-level settings can switch every hook off (disableAllHooks)
    try:
        rel = norm(p, cwd).relative_to(PROJECT).as_posix().lower() + ("/" if norm(p, cwd).is_dir() else "")
    except ValueError:
        rel = os.path.normpath(p).replace("\\", "/").lower()
    return any(rel == h.rstrip("/") or rel.startswith(h) for h in HARNESS_FILES)


def glob_reaches(pattern: str, cwd: Path) -> str | None:
    """For an argument with * ? or [, say whether it could reach a secret or a real-data path."""
    import glob as _glob
    base = os.path.expanduser(pattern)
    hits = _glob.glob(base if os.path.isabs(base) else str(cwd / base), recursive=True)
    for h in hits:
        if is_secret(h) or is_real(h) or harness_file(h, cwd) or touches_git(h, cwd):
            return h
    low = norm(base, cwd).as_posix().lower()
    for t in [PROJECT / h.rstrip("/") for h in HARNESS_FILES] + [PROJECT / ".git" / "hooks" / "x", PROJECT / ".git" / "config"]:
        if fnmatch.fnmatch(t.as_posix().lower(), low) or fnmatch.fnmatch(t.as_posix().lower() + "/x", low):
            return str(t)
    name = os.path.basename(base) or base
    if any(fnmatch.fnmatch(s, name) for s in SECRET_SAMPLES) and not name.startswith("*."):
        return name
    for r in real_paths():
        rp = str(norm(r, PROJECT))
        if fnmatch.fnmatch(rp, str(norm(base, cwd))) or fnmatch.fnmatch(rp + "/x", str(norm(base, cwd))):
            return r
    return None


def path_pieces(arg: str) -> list:
    """An argument and the file names hidden inside it: after @ or =, and either side of < or > (cat<.env, -d@file)."""
    out = [arg]
    for piece in re.split(r"[<>]", arg):
        out += [piece, piece.split("=")[-1], piece.split("@")[-1]]
    return [x for x in dict.fromkeys(out) if x and not x.startswith("-")] + \
           [x for x in (arg.split("=", 1)[-1] if arg.startswith("-") and "=" in arg else "", arg.split("@", 1)[-1] if "@" in arg else "") if x]


READERS = {"grep", "egrep", "fgrep", "rg", "ag", "find", "cat", "tar", "zip", "cp", "rsync", "scp", "less", "more", "head", "tail", "du", "tree", "xxd", "od", "strings"}


def holds_real(p: str, cwd: Path) -> bool:
    """True when p is a folder that contains a real-data path (grep -r x data/ reads data/real)."""
    base = norm(p, cwd)
    if not base.is_dir():
        return False
    return any(base in norm(r, PROJECT).parents or base == norm(r, PROJECT) for r in real_paths())


# Wrapper words that run the next word, and the options of each that take a value. unwrap() strips them so the guard
# judges the command that actually runs (env -u X git push, time printenv, timeout 5 env, /usr/bin/env).
WRAPPER_OPTS = {"env": {"-u", "--unset", "-C", "--chdir", "-S", "--split-string"}, "time": {"-f", "--format", "-o", "--output"},
                "command": set(), "builtin": set(), "exec": {"-a"}, "nohup": set(), "nice": {"-n", "--adjustment"},
                "timeout": {"-s", "--signal", "-k", "--kill-after"}, "stdbuf": {"-i", "-o", "-e"}, "sudo": {"-u", "-g", "-C", "-D", "-h", "-p", "-U"},
                "doas": {"-u", "-C"}, "xargs": {"-a", "-d", "-E", "-I", "-L", "-n", "-P", "-s", "--arg-file", "--delimiter", "--max-args"},
                "{": set(), "}": set(), "!": set(), "chronic": set(), "ionice": {"-c", "-n", "-p"}, "taskset": set(), "setsid": set(), "unbuffer": set()}


def unwrap(w: list):
    """(the words of the command that actually runs, whether env was one of the wrappers)."""
    saw_env = False
    while w:
        head = os.path.basename(w[0])
        if re.match(r"^\w+=", w[0]) or w[0].isdigit():
            w = w[1:]; continue
        if head not in WRAPPER_OPTS:
            break
        saw_env = saw_env or head == "env"
        opts, w = WRAPPER_OPTS[head], w[1:]
        while w and (w[0].startswith("-") or (head == "env" and re.match(r"^\w+=", w[0]))):
            if w[0] == "--":
                w = w[1:]; break
            w = w[2:] if w[0] in opts else w[1:]
        if head == "timeout" and w:
            w = w[1:]                                   # the duration
        if head == "taskset" and w:
            w = w[1:]
    return w, saw_env


def env_dump(w: list, wrapped_env: bool) -> str | None:
    msg = "Deny-rule plate: printing the environment can show API keys and tokens. Ask for the one variable you need by name."
    if not w:
        return msg if wrapped_env else None
    exe, rest = os.path.basename(w[0]), w[1:]
    if exe in ("printenv", "compgen"):
        return msg
    if exe == "set" and not (rest and all(re.fullmatch(r"[-+][euxo]+|pipefail|errexit|nounset|xtrace", x) for x in rest)):
        return msg
    if exe in ("export", "declare", "typeset", "local", "readonly") and not any("=" in x for x in rest) and \
            all(x.startswith("-") for x in rest):
        return msg
    if exe in ("export", "declare", "typeset", "local", "readonly") and any(x.startswith("-") and "p" in x for x in rest):
        return msg
    return None


def holds_secret(p: str, cwd: Path, limit: int = 20000) -> str | None:
    """A secret-named file inside folder p (grep -r KEY src reads src/.env)."""
    base = norm(p, cwd)
    if not base.is_dir():
        return None
    n = 0
    for root, dirs, files in os.walk(base, followlinks=True):
        dirs[:] = [d for d in dirs if d != ".git"]
        for f in files + dirs:
            n += 1
            if is_secret(os.path.join(root, f)):
                return os.path.join(root, f)
            if n > limit:
                return f"{base} (too large to check)"
    return None


# 0.6.0: default deny. The Bash tool runs only the programs on this list (plus the owner's additions in allowlist.json
# under "programs"). Anything else is refused, so a program the guard has never heard of (a wrapper such as caffeinate,
# flock or strace, an interpreter, a shell) can't carry a command past it. No general shell or interpreter is listed:
# python3 and node run only as the owner's named test commands ("test_commands") or as agent_company.py.
PROGRAMS = {
    "git", "gh", "ls", "cat", "head", "tail", "wc", "grep", "egrep", "fgrep", "rg", "find", "diff", "cmp", "sort", "uniq", "cut",
    "tr", "echo", "printf", "pwd", "mkdir", "touch", "cp", "mv", "rm", "rmdir", "jq", "date", "true", "false", "test", "[",
    "basename", "dirname", "realpath", "stat", "file", "tree", "du", "sha256sum", "md5sum", "shasum", "nl", "column", "tee",
    "tar", "zip", "gzip", "gunzip", "which", "whoami", "uname", "sleep", "seq", "fold", "fmt", "paste", "comm", "rev", "expand",
    "cd", "set", "export", "unset",
}
SAFE_WRAPPERS = {"env", "time", "nice", "timeout", "nohup", "stdbuf", "ionice", "{", "}", "!"}
DEFAULT_TEST_COMMANDS = ["python3 -m pytest", "python3 -m unittest", "npm test", "npm run test", "node tests/"]


def allowed_programs() -> set:
    return PROGRAMS | {str(x) for x in load_allow().get("programs", []) if str(x) not in SHELLS}


def test_commands() -> list:
    return DEFAULT_TEST_COMMANDS + [str(x) for x in load_allow().get("test_commands", [])]


def wrapper_refusal(w: list) -> str | None:
    """Only the wrappers the guard can see through: env (without -C), time, nice, timeout, nohup, stdbuf, ionice."""
    i = 0
    while i < len(w):
        head = os.path.basename(w[i])
        if re.match(r"^\w+=", w[i]) or w[i].isdigit():
            i += 1; continue
        if head in WRAPPER_OPTS and head not in SAFE_WRAPPERS:
            return f"No-merge gauntlets: {head} runs another command in a way the guard can't follow. Run the command itself."
        if head not in WRAPPER_OPTS:
            return None
        if head == "env":
            j = i + 1
            while j < len(w) and w[j].startswith("-"):
                x = w[j]
                if x in ("-i", "--ignore-environment", "-0", "--null", "--"):
                    j += 1
                    if x == "--":
                        break
                    continue
                if x in ("-u", "--unset"):
                    j += 2; continue
                if x.startswith("--unset=") or re.fullmatch(r"-u\w+", x):
                    j += 1; continue
                return f"No-merge gauntlets: env {x} isn't one of the env options the guard follows (-i, -u NAME). Refused."

        i += 1
        while i < len(w) and w[i].startswith("-"):
            i += 2 if w[i] in WRAPPER_OPTS.get(head, set()) else 1
        if head == "timeout" and i < len(w):
            i += 1
    return None


def program_refusal(w: list) -> str | None:
    """Default deny: the first word of what actually runs must be a listed program, a named test command or agent_company.py."""
    exe = w[0]
    base = os.path.basename(exe)
    if "/" in exe and base not in ("agent_company.py",):
        if not (exe.startswith(("./", "../")) and False):
            return f"No-merge gauntlets: run programs by name, not by path ({exe}). The guard checks the name against its list."
    line = " ".join(w)
    if base in ("python3", "python") and len(w) > 1 and os.path.basename(w[1]) == "agent_company.py":
        sub = w[2] if len(w) > 2 else ""
        if sub in ("harness", "launch", "ui", "guild", "start", "import-agents", "init"):
            return f"Harness: agent_company.py {sub} changes the set-up or starts things. The owner runs it."
        return None
    for t in test_commands():
        if t.endswith("/") and line.startswith(t):
            target = line[len(t.split()[0]) + 1:].split()[0] if len(line.split()) > 1 else ""
            folder = t.split()[-1]
            if ".." in Path(target).parts or not os.path.normpath(target).startswith(os.path.normpath(folder) + os.sep):
                return f"No-merge gauntlets: the test command runs files inside {folder} only."
    if any(line == t or line.startswith(t + " ") or (t.endswith("/") and line.startswith(t)) for t in test_commands()):
        if re.search(r"\s-(c|e|m\s+(?!pytest|unittest))", " " + line[len(line.split()[0]):]) and not line.startswith(("python3 -m pytest", "python3 -m unittest")):
            return "No-merge gauntlets: a test command can't carry -c or -e code. Run the test command as the owner listed it."
        return None
    if base not in allowed_programs():
        return (f"No-merge gauntlets: {base} isn't on this repo's program list, so it is refused (default deny). "
                f"The owner can add it to \"programs\" in docs/ops/harness/allowlist.json, or add a test command to \"test_commands\".")
    return None


# Options of listed programs that start another program. Refused with their abbreviations.
PROGRAM_RUN_OPTS = {
    "tar": ("--checkpoint-action", "--to-command", "--use-compress-program", "-I", "--info-script", "--new-volume-script", "-F",
            "--rsh-command", "--rmt-command", "-x", "--extract", "--get"),
    "sort": ("--compress-program",),
    "rg": ("--pre", "--pre-glob", "--search-zip", "-z"),
    "zip": ("-TT", "--unzip-command", "-T", "--test"),
    "find": ("-exec", "-execdir", "-ok", "-okdir", "-delete", "-fprint", "-fprintf", "-fls"),
    "diff": ("--diff-program",),
    "git": (),
    "gzip": (), "gunzip": (),
    "tree": (), "jq": ("--rawfile", "--slurpfile"),
}


READ_OK = {"cat", "head", "tail", "less", "more", "wc", "grep", "egrep", "fgrep", "rg", "ls", "file", "stat", "git", "diff", "jq", "python3", "python", "nl", "md5sum", "sha256sum", "shasum"}
NETWORK = {"nc", "ncat", "netcat", "socat", "telnet", "ftp", "sftp", "tftp", "ssh"}
MOVERS = {"mv", "rm", "rmdir", "cp", "rsync", "ln", "unlink", "shred", "truncate", "chmod", "chown", "tar", "zip", "diff"}


def real_present() -> bool:
    return any(norm(r, PROJECT).exists() and PROJECT in norm(r, PROJECT).parents for r in real_paths())


def real_tracked(repo: Path) -> bool:
    """True when git already tracks a real-data path (then git show, grep, log -p and archive could print it)."""
    paths = real_paths()
    if not paths:
        return False
    try:
        out = subprocess.run(["git", "-C", str(repo), "ls-files", "--"] + paths, capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return True
    return bool(out.strip())


# Places agents may read but never write: the owner's instruction channel, the evidence trail, and .gitignore
# (its real-data lines keep real data out of commits).
WRITE_LOCKED = ("docs/ops/inbox/", "docs/ops/evidence/", ".gitignore")
WRITERS = {"cp", "mv", "tee", "touch", "sed", "truncate", "dd", "install", "ln", "rm", "rmdir", "unlink", "shred", "chmod", "chown", "rsync", "tar", "unzip"}
APPROVAL = re.compile(r"\b(appro?v\w*|sign(ed|s|ing)?[- ]?off|lgtm|merge it|ok to merge|ship it|go ahead|owner('s)? (decision|approval|sign)|decided|accepted|green[- ]?light)", re.I)


CONFUSABLE = str.maketrans({"а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x", "і": "i", "ј": "j", "ѕ": "s", "һ": "h",
                            "ԁ": "d", "ɡ": "g", "ο": "o", "α": "a", "ε": "e", "ρ": "p", "ι": "i", "κ": "k", "ν": "v", "τ": "t", "υ": "u",
                            "Α": "A", "Β": "B", "Ε": "E", "Ο": "O", "Ρ": "P", "Τ": "T", "Χ": "X", "А": "A", "В": "B", "Е": "E", "О": "O",
                            "Р": "P", "С": "C", "Т": "T", "Х": "X", "’": "'", "‘": "'", "ʼ": "'", "`": "'", "‐": "-", "‑": "-", "–": "-", "—": "-",
                            "0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"})


def fold(text: str) -> str:
    """Lower case, look-alike letters mapped to Latin, accents dropped, hyphens and underscores as spaces."""
    import unicodedata
    t = unicodedata.normalize("NFKD", text).translate(CONFUSABLE)
    t = "".join(ch for ch in t if not unicodedata.combining(ch)).lower()
    return re.sub(r"[-_]+", " ", t)


APPROVAL2 = re.compile(r"\b(appro?v\w*|sign(ed|s|ing)? ?off|lgtm|merge it|ok to merge|ready to merge|ship it|go ahead|green ?light|"
                       r"owners?'?s? (decision|approval|sign|call|go)|decided|accepted|reviewed by|acked by|\+1)", re.I)


SQUASHED = ("approv", "lgtm", "signedoff", "signoff", "shipit", "goahead", "oktomerge", "okaytomerge", "readytomerge", "goodtomerge",
            "finetomerge", "oktoship", "greenlight", "mergewhengreen", "goodtogo")
OWNER_SPEAKS = re.compile(r"\b(owner|owners)\b\W+(?:\w+\W+){0,3}?(says?|said|ok|okay|reviewed|agreed|agrees|wants|asked|decided|call|final|"
                          r"signed|accepts?|yes|go|approves?|blessed)\b|\bper (the )?owner\b", re.I)


def squash(text: str) -> str:
    import unicodedata
    t = "".join(ch for ch in text if unicodedata.category(ch) != "Cf")    # zero-width spaces, soft hyphens, joiners
    return re.sub(r"[^a-z+]", "", fold(t))


def approval_words(text: str) -> bool:
    import unicodedata
    clean = "".join(ch for ch in text if unicodedata.category(ch) != "Cf")
    sq = squash(text)
    owner_said = OWNER_SPEAKS.search(fold(clean)) or any(n and n != "owner" and n in sq for n in owner_names())
    return bool(APPROVAL.search(clean) or APPROVAL2.search(fold(clean)) or "+1" in clean or any(k in sq for k in SQUASHED) or owner_said)


def write_locked(p: str, cwd: Path) -> str | None:
    try:
        rel = norm(p, cwd).relative_to(PROJECT).as_posix()
    except ValueError:
        return None
    rel_dir = (rel + ("/" if norm(p, cwd).is_dir() else "")).lower()      # macOS disks fold case: Inbox is inbox
    for z in WRITE_LOCKED:
        if rel_dir == z or rel_dir.startswith(z) or (z.endswith("/") and z.startswith(rel_dir) and rel_dir.endswith("/")):
            return z.rstrip("/")
    return None


def owner_names() -> list:
    try:
        g = json.loads((PROJECT / "docs/ops/guild/guild.json").read_text(encoding="utf-8"))
        names = [h.get("name", "") for h in g.get("heroes", {}).values() if h.get("cls") == "master"]
    except (OSError, ValueError, AttributeError):
        names = []
    return [re.sub(r"[^a-z]", "", fold(n)) for n in names if n] + ["owner"]


def is_toplevel(d: Path) -> bool:
    try:
        top = subprocess.run(["git", "-C", str(d), "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return False
    return bool(top) and Path(top).resolve() == d.resolve()


def is_branch(repo: Path, name: str) -> bool:
    try:
        return subprocess.run(["git", "-C", str(repo), "show-ref", "--verify", "--quiet", f"refs/heads/{name}"], timeout=5).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def tracked_at(repo: Path, rev: str, path: str) -> bool:
    try:
        return subprocess.run(["git", "-C", str(repo), "cat-file", "-e", f"{rev}:{path}"], capture_output=True, timeout=5).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def branch_of(cwd: Path) -> str:
    try:
        return subprocess.run(["git", "-C", str(cwd), "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


# Git subcommands an agent may run. Anything else (an alias, a git-<name> program on PATH, plumbing such as
# send-pack) is refused, because the guard cannot see what it would do.
GIT_SUBCOMMANDS = {
    "add", "am", "apply", "archive", "bisect", "blame", "branch", "cat-file", "check-ignore", "checkout", "cherry",
    "cherry-pick", "clean", "clone", "commit", "config", "count-objects", "describe", "diff", "fetch", "for-each-ref",
    "format-patch", "fsck", "gc", "grep", "help", "init", "log", "ls-files", "ls-remote", "ls-tree", "merge",
    "merge-base", "mv", "name-rev", "notes", "pull", "push", "range-diff", "rebase", "reflog", "remote", "reset",
    "restore", "rev-list", "rev-parse", "revert", "rm", "shortlog", "show", "show-ref", "stash", "status", "switch",
    "tag", "version", "worktree",
}
GIT_OPTS_WITH_VALUE = ("-C", "-c", "--git-dir", "--work-tree", "--namespace", "--super-prefix", "--config-env", "--exec-path")
# Config keys an agent may set with -c or git config, matched exactly. Everything else is refused: alias.*, include.*, core.*,
# remote.*, push.* re-route a push or switch a hook off, and diff.external, diff.*.textconv, pager.* and core.pager run a command.
CONFIG_OK = ("user.name", "user.email", "color.ui")
CONFIG_READ = ("--get", "--get-all", "--get-regexp", "-l", "--list", "--show-origin", "--show-scope", "--name-only")
# Long options git also accepts in any unambiguous shortened form (git push --no-verif works), so prefixes are refused too.
PUSH_REFUSED_LONG = ("--force", "--force-with-lease", "--force-if-includes", "--no-verify", "--all", "--mirror",
                     "--branches", "--delete", "--prune", "--receive-pack", "--exec")
PUSH_REFUSED_SHORT = set("fd")


def long_hit(arg: str, names) -> str:
    """The refused long option that arg spells, in full or shortened (git accepts any unambiguous prefix)."""
    if not arg.startswith("--") or len(arg) < 4:
        return ""
    head = arg.split("=")[0]
    return next((n for n in names if n == head or n.startswith(head) or head.startswith(n)), "")


def config_refusal(key: str) -> str:
    if key.lower() in ("user.name", "user.email"):
        return f"No-merge gauntlets: that {key} names the owner. An agent commits under its own name, never the owner's."
    return f"No-merge gauntlets: git config {key} is refused. Agents may set only user.name, user.email and color.ui."


def config_key_ok(key: str, value: str = "") -> bool:
    k = key.lower()
    if k in ("user.name", "user.email") and value and any(ord(ch) > 127 for ch in value):
        return False                                  # look-alike letters outside any table: plain ASCII names only
    v = re.sub(r"[^a-z]", "", fold(value)) if value else ""
    if k in ("user.name", "user.email") and v and any(n and (n in v or (len(v) >= 4 and v in n)) for n in owner_names()):
        return False                                  # an agent never commits as the owner
    return k in CONFIG_OK


def git_subcommand(args: list):
    """(subcommand, its arguments, refusal or None), skipping git's global options (-C dir, -c key=value, ...)."""
    i = 0
    while i < len(args):
        a = args[i]
        val = None
        if a in ("--git-dir", "--work-tree", "--namespace", "--super-prefix") or a.startswith(("--git-dir=", "--work-tree=", "--namespace=", "--super-prefix=")):
            return "", [], f"No-merge gauntlets: git {a.split('=')[0]} points git somewhere else. Agents use -C, -c user.name/user.email/color.ui and --no-pager (or -P) only."
        if a in GIT_OPTS_WITH_VALUE:
            val = args[i + 1] if i + 1 < len(args) else ""
            name, i = a, i + 2
        elif a.startswith("-c") and len(a) > 2:
            name, val, i = "-c", a[2:], i + 1
        elif a.startswith("--config-env=") or a.startswith("--exec-path="):
            name, val, i = a.split("=")[0], a.split("=", 1)[1], i + 1
        elif a in ("--no-pager", "-P"):
            i += 1
            continue
        elif a.startswith("-"):
            return "", [], f"No-merge gauntlets: git {a} is not on the guard's list of git options. Agents use -C, -c user.name/user.email/color.ui and --no-pager only."
        else:
            return a, args[i + 1:], None
        if name == "--exec-path":
            return "", [], "No-merge gauntlets: --exec-path is refused (it changes which programs git runs)."
        if name in ("-c", "--config-env") and not config_key_ok(val.split("=")[0], val.split("=", 1)[1] if "=" in val else ""):
            return "", [], config_refusal(val.split("=")[0])
    return "", [], None


# The git allowlist: a subcommand runs only in the forms listed here; any other option is refused. Git accepts
# shortened long options (--har for --hard), so an allowlist, not a blocklist, is what keeps up with it.
GIT_READ = {"status", "log", "diff", "show", "blame", "rev-parse", "ls-files", "ls-tree", "describe", "shortlog", "rev-list",
            "cat-file", "for-each-ref", "show-ref", "name-rev", "merge-base", "version", "help", "count-objects", "check-ignore",
            "grep", "cherry", "range-diff"}
READ_REFUSED = ("--no-index", "--output", "--ext-diff", "--textconv", "--open-files-in-pager", "--exec", "--upload-pack", "--remote",
                "--untracked", "--no-exclude-standard",
                "--paginate", "--output-directory")
GIT_FORMS = {   # subcommand: (options allowed exactly, options that take a value)
    "add": ({"-u", "--update", "-N", "--intent-to-add", "-v", "--verbose", "--"}, set()),
    "commit": ({"-q", "--quiet", "-a", "--allow-empty", "-v", "--verbose"}, {"-m", "--message"}),
    "push": ({"-u", "--set-upstream", "-q", "--quiet", "-v", "--verbose", "--follow-tags"}, set()),
    "fetch": ({"-q", "--quiet", "-p", "--prune", "-v", "--verbose"}, set()),
    "checkout": ({"-b", "-q", "--quiet"}, set()),
    "switch": ({"-c", "--create", "-q", "--quiet"}, set()),
    "restore": ({"--staged", "-S", "--worktree", "-W", "-q", "--quiet", "--"}, set()),
    "reset": ({"-q", "--quiet", "--"}, set()),
    "stash": ({"-q", "--quiet"}, {"-m", "--message"}),
    "branch": ({"-a", "--all", "-r", "--remotes", "-v", "-vv", "--verbose", "--list", "--show-current", "--merged", "--no-merged"}, set()),
    "rm": ({"--cached", "-q", "--quiet", "-r", "--"}, set()),
    "mv": ({"-k", "-v", "--verbose", "-n", "--dry-run"}, set()),
    "tag": ({"-l", "--list", "-n"}, set()),
    "remote": (set(), set()),
    "worktree": (set(), set()),
    "reflog": (set(), set()),
    "config": (set(), set()),     # judged by the config rules below
}


def git_form_refusal(sub: str, rest: list, gdir: Path) -> str | None:
    if sub in GIT_READ:
        hit = next((long_hit(a, READ_REFUSED) or a for a in rest if long_hit(a, READ_REFUSED) or a.startswith("-O")), "")
        return f"No-merge gauntlets: git {sub} {hit} reaches outside the repository or runs a program. Refused." if hit else None
    if sub not in GIT_FORMS:
        return (f"No-merge gauntlets: git {sub} isn't one of the git commands agents use (it can merge, rewrite history, "
                f"apply patches or remove the harness). Ask the owner.")
    if sub == "config":
        if any(a in ("-e", "--edit") or a.startswith("--ed") for a in rest):
            return "No-merge gauntlets: git config --edit runs an editor on git's config. Refused."
        if any(a in ("-l", "--show-origin") or a.startswith(("--li", "--get-r", "--get-u")) for a in rest):
            return "Deny-rule plate: listing git config can print remote URLs with tokens in them. Refused."
        if any(re.search(r"(^|\.)(url|pushurl|insteadof|pushinsteadof|extraheader|helper|token|password)$", a.lower()) or a.lower().startswith(("url.", "credential", "http.")) for a in rest if not a.startswith("-")):
            return "Deny-rule plate: remote URLs, credential helpers and http headers can hold tokens. Agents don't read them."
        if any(a in ("--global", "--system", "--file", "-f") or a.startswith(("--file=", "--glo", "--sys")) for a in rest):
            return "No-merge gauntlets: agents change this repository's git config only, never the owner's global or system config."
        return None
    ok, valued = GIT_FORMS[sub]
    pos, i = [], 0
    while i < len(rest):
        a = rest[i]
        if a in valued:
            if sub in ("commit", "stash") and approval_words(rest[i + 1] if i + 1 < len(rest) else ""):
                return "No-merge gauntlets: a message may not say it is approved, signed off or decided. Describe the change; the owner decides."
            i += 2; continue
        if any(a.startswith(v + "=") for v in valued if v.startswith("--")):
            if approval_words(a.split("=", 1)[1]):
                return "No-merge gauntlets: a message may not say it is approved, signed off or decided."
            i += 1; continue
        if sub in ("commit", "stash") and re.fullmatch(r"-[aqv]*m", a):          # -am "msg"
            if approval_words(rest[i + 1] if i + 1 < len(rest) else ""):
                return "No-merge gauntlets: a message may not say it is approved, signed off or decided."
            i += 2; continue
        if a.startswith("-") and a not in ok:
            return f"No-merge gauntlets: git {sub} {a} isn't on the guard's list of git options for agents. Refused."
        if not a.startswith("-"):
            pos.append(a)
        i += 1
    if sub == "commit" and not any(a in valued or re.fullmatch(r"-[aqv]*m", a) or a.startswith("--message=") for a in rest):
        return "No-merge gauntlets: write the commit message on the command line with -m, where the guard can read it."
    if sub == "add":
        if not pos and not any(a in ("-u", "--update") for a in rest):
            return None
        for a in pos:
            if a in (".", ":/", ":", "*") or any(ch in a for ch in "*?[:") or (norm(a, gdir).is_dir() and real_present()):
                return "Constructed-data boots: add the files you changed by name (no folders, dots or patterns while the project holds real data)."
    if sub == "checkout":
        if "-b" in rest:
            return None if len(pos) == 1 else "Harness: git checkout -b takes a new branch name only, made from where you are."
        if len(pos) != 1 or not is_branch(gdir, pos[0]):
            return "Harness: git checkout switches to an existing local branch only (or makes one with -b). Paths, commits and '-' are refused."
    if sub == "switch":
        if any(a in ("-c", "--create") for a in rest):
            return None if len(pos) == 1 else "Harness: git switch -c takes a new branch name only, made from where you are."
        if len(pos) != 1 or not is_branch(gdir, pos[0]):
            return "Harness: git switch goes to an existing local branch only."
    if sub == "restore" and any(norm(a, gdir).is_dir() or a in (".",) for a in pos):
        return "Harness: git restore takes named files only."
    before = rest[:rest.index("--")] if "--" in rest else rest
    revs = [a for a in before if not a.startswith("-") and not (gdir / a).exists()]
    if sub == "reset" and any(r != "HEAD" for r in revs):
        return "Harness: git reset only unstages named files (git reset HEAD <file>). Moving the branch is refused."
    if sub == "fetch" and (len(pos) > 1 or (pos and (pos[0] in (".", "..") or re.search(r"[:/@\\.]", pos[0])))):
        return "No-merge gauntlets: git fetch takes a remote name only (git fetch origin). Refspecs and local paths can move your branches."
    if sub == "config" and any(a in ("-l", "--show-origin") or a.startswith(("--li", "--get-r", "--get-u")) for a in rest):
        return "Deny-rule plate: listing all git config can print remote URLs with tokens in them. Ask for one key with --get."
    if sub == "stash" and pos and pos[0] not in ("push", "list", "show", "pop", "apply"):
        return "Harness: git stash push, list, show, pop or apply only."
    if sub == "branch" and pos and (len(pos) > 1 or PROTECTED.match(pos[0])):
        return "No-merge gauntlets: git branch makes one new branch from where you are; start points and protected names are refused."
    if sub == "tag" and pos and not any(a in ("-l", "--list") for a in rest):
        return "No-merge gauntlets: agents list tags; making tags is the owner's."
    if sub == "remote" and (pos[:1] in (["show"], ["get-url"]) or any(a in ("-v", "--verbose") for a in rest)):
        return "Deny-rule plate: remote URLs can hold tokens, so agents list remote names only (git remote)."
    if sub == "remote" and pos:
        return "Constructed-data boots: agents don't add or change git remotes."
    if sub == "worktree" and pos[:1] not in (["list"],) and not (pos[:1] == ["add"] and len(pos) == 2 and "-b" not in rest):
        return "No-merge gauntlets: git worktree list, or git worktree add <folder> for the current branch only."
    if sub == "worktree" and pos[:1] == ["add"]:
        return "No-merge gauntlets: make worktrees with agent_company.py start, not by hand."
    if sub == "reflog" and pos[:1] not in ([], ["show"]):
        return "Harness: git reflog show only."
    return None


GIT_WRITES = {"push", "commit", "cherry-pick", "am", "revert", "reset", "rebase", "merge", "pull"}


def git_dir_of(args: list, cwd: Path) -> Path:
    """The folder git will act in: the last -C <dir> before the subcommand, else cwd."""
    d = cwd
    for i, a in enumerate(args):
        if a == "-C" and i + 1 < len(args):
            d = norm(args[i + 1], d)
        elif not a.startswith("-") and (i == 0 or args[i - 1] not in GIT_OPTS_WITH_VALUE):
            break
    return d


GH_READ = {("pr", "view"), ("pr", "list"), ("pr", "diff"), ("pr", "checks"), ("pr", "status"), ("pr", "create"), ("pr", "comment"),
           ("issue", "view"), ("issue", "list"), ("issue", "create"), ("issue", "comment"), ("run", "view"), ("run", "list"),
           ("repo", "view"), ("auth", "status"), ("release", "view"), ("release", "list"), ("search", "*"), ("status", "*")}


def gh_refusal(args: list) -> str | None:
    """gh runs with the owner's own sign-in, so only reading and opening PRs and issues are allowed."""
    pos, i = [], 0
    while i < len(args):
        a = args[i]
        if a in ("-R", "--repo"):
            i += 2; continue
        if not a.startswith("-"):
            pos.append(a)
        i += 1
    if not pos:
        return None
    if pos[0] == "api":
        method = next((args[j + 1] for j, a in enumerate(args) if a in ("-X", "--method") and j + 1 < len(args)), "")
        method = method or next((a.split("=", 1)[1] if a.startswith("--method=") else a[2:] for a in args
                                 if a.startswith("--method=") or (a.startswith("-X") and len(a) > 2)), "GET")
        writes = any(a in ("-f", "-F", "--field", "--raw-field", "--input") or a.startswith(("-f", "-F", "--field=", "--raw-field=", "--input=")) for a in args)
        if method.upper() != "GET" or writes or any("/merge" in a for a in args):
            return "No-merge gauntlets: gh api calls that change anything run as the owner, so they are refused. Agents only read."
        return None
    pair = (pos[0], pos[1] if len(pos) > 1 else "")
    text = " ".join(args)
    posts = pair in (("pr", "comment"), ("pr", "create"), ("issue", "comment"), ("issue", "create"), ("pr", "edit"), ("issue", "edit"))
    if pair == ("auth", "status") and len(args) > 2:
        return "Deny-rule plate: gh auth status with options can print the owner's token. Run it bare."
    if posts and any(a in ("-f", "-F", "--body-file", "-T", "--template") or a.startswith(("--body-file=", "-F", "--fill", "--template")) for a in args):
        return "No-merge gauntlets: gh posts run under the owner's sign-in, so the text must be on the command line (--body), where the guard can read it. --body-file is refused."
    if posts and approval_words(text):
        return "No-merge gauntlets: a gh post runs under the owner's sign-in, so it may not say it is approved, signed off or accepted. Describe the work; the owner decides."
    if pair in GH_READ or (pos[0], "*") in GH_READ:
        return None
    return f"No-merge gauntlets: 'gh {' '.join(pos[:2])}' acts with the owner's own GitHub sign-in (merge, approve, alias, settings...), so it is refused. Agents may view, list, comment and open pull requests."


def push_refusal(rest: list, cwd: Path, check_remote: bool = False):
    for a in rest:
        hit = long_hit(a, PUSH_REFUSED_LONG)
        if hit:
            return f"No-merge gauntlets: {a} ({hit}) is refused. Push one named branch of your own, with the pre-push hook on."
        if a.startswith("-") and not a.startswith("--") and PUSH_REFUSED_SHORT & set(a[1:]):
            return f"No-merge gauntlets: {a} is refused (force or delete). Push one named branch of your own."
    pos = [a for a in rest if not a.startswith("-")]
    if len(pos) < 2:
        return "No-merge gauntlets: name the remote and your branch (git push origin <your-branch>). A bare push follows config that can route it anywhere."
    if check_remote and re.search(r"[:/@\\]", pos[0]):
        return f"Constructed-data boots: push to a named remote such as origin, not to {pos[0]}."
    here = branch_of(cwd)
    for a in pos[1:]:
        if any(ch in a for ch in "*?["):
            return "No-merge gauntlets: wildcard refspecs are refused. Push one named branch of your own."
        if a.startswith("+"):
            return "No-merge gauntlets: a + refspec is a force push, refused."
        src, _, dst = a.partition(":")
        target = dst or src
        for pre in ("refs/heads/", "heads/"):  # git resolves heads/main to refs/heads/main
            if target.startswith(pre):
                target = target[len(pre):]
        if target.startswith("refs/"):
            return f"No-merge gauntlets: {target} is refused. Push to a branch named plainly (git push origin <your-branch>)."
        if target in ("HEAD", "@", ""):
            target = here
        if not target or PROTECTED.match(target):
            return f"No-merge gauntlets: no push to the protected branch {target or '(unknown)'}. Push your own branch and open a pull request."
    return None


# Words that run the next word as a command. The guard skips them so it sees the real command (env git push ...).
WRAPPERS = {"env", "time", "command", "builtin", "exec", "nohup", "nice", "sudo", "doas", "xargs", "timeout", "stdbuf", "{", "}", "!"}


def hidden_command(cmd: str) -> str | None:
    """Refuse shell forms that hide a command from a guard that reads text: $( ), backticks, ( ) subshells, a lone &."""
    if "`" in cmd or "$(" in cmd or "<(" in cmd or ">(" in cmd:
        return "No-merge gauntlets: $( ), backticks and <( ) hide a command from the guard, so they are refused. Run one plain command."
    try:
        lex = shlex.shlex(cmd, posix=True, punctuation_chars="();<>|&")
        lex.whitespace_split = True
        toks = list(lex)
    except ValueError:
        return "No-merge gauntlets: the guard could not read this command's quoting, so it is refused."
    for t in toks:
        if t and set(t) <= set("();<>|&") and ("(" in t or ")" in t or t == "&"):
            return "No-merge gauntlets: a ( ) subshell or a lone & hides a command from the guard, so it is refused. Run one plain command."
    return None


def split_commands(cmd: str) -> list:
    """The commands in a line, split at ; && || | and newlines outside quotes (a ; inside a message is not a command)."""
    try:
        lex = shlex.shlex(cmd.replace("\n", " ; "), posix=True, punctuation_chars=";&|<>")
        lex.whitespace_split = True
        toks = list(lex)
    except ValueError:
        return re.split(r"&&|\|\||;|\||\n", cmd)
    parts, cur = [], []
    for t in toks:
        if t and set(t) <= set(";&|"):
            parts.append(" ".join(x if re.fullmatch(r"[<>&]+", x) else shlex.quote(x) for x in cur)); cur = []
        else:
            cur.append(t)
    parts.append(" ".join(x if re.fullmatch(r"[<>&]+", x) else shlex.quote(x) for x in cur))
    return [p for p in parts if p.strip()]


def check_bash(cmd: str, cwd: Path) -> str | None:
    why = hidden_command(cmd)
    if why:
        return why
    if re.search(r"\$[\w{(]|\$'|~[A-Za-z_]", cmd):
        return "No-merge gauntlets: shell variables ($NAME, ${...}, $PWD) and ~user hide which file a command touches, so they are refused. Write the path out."
    if re.search(r"\{[^{}\s]*,[^{}\s]*\}|\{[^{}\s]*\.\.[^{}\s]*\}", cmd):
        return "No-merge gauntlets: brace lists ({a,b}) hide which files a command touches, so they are refused. Name each file."
    if "AGENT_COMPANY_OWNER" in re.sub(r"[\'\"\\\s]", "", cmd):
        return "No-merge gauntlets: AGENT_COMPANY_OWNER is the owner's own override. Agents never set it."
    if re.search(r"\bGIT_[A-Z_]+=|\bEMAIL=", cmd):
        return "No-merge gauntlets: GIT_* variables (author, committer, config, directories) change who or what git acts as. Refused."
    if re.search(r"core\.hookspath|\.git/hooks|\.git/config|\.gitconfig|\bGIT_CONFIG|\bGIT_EXEC_PATH|\bGIT_DIR\b", cmd, re.I):
        return "No-merge gauntlets: agents never change git hooks, git config files or git's environment."
    parts = split_commands(cmd)
    moves, writes = False, False
    for part in parts:
        try:
            w0 = shlex.split(part)
        except ValueError:
            w0 = part.split()
        while w0 and (re.match(r"^\w+=", w0[0]) or w0[0] in WRAPPERS):
            w0 = w0[1:]
        if not w0:
            continue
        if w0[0] in ("cd", "pushd", "popd") or (os.path.basename(w0[0]) == "git" and set(w0[1:]) & {"checkout", "switch", "worktree"}):
            moves = True
        if os.path.basename(w0[0]) in ("git", "gh") and set(w0[1:]) & GIT_WRITES:
            writes = True
    if moves and len([x for x in parts if x.strip()]) > 1:
        return "No-merge gauntlets: cd or a branch change chained with another command is refused, because the guard checks paths and branches before the command runs. Run the cd or checkout on its own first."
    if moves and writes:
        return "No-merge gauntlets: changing branch or folder and then committing or pushing in one command is refused. Do it in two steps, so the guard can see which branch you are on."
    for part in parts:
        CWD[0] = cwd.resolve()
        part = re.sub(r"[<>]+", lambda m: f" {m.group(0)} ", part)    # cat<.env reads .env: split redirects off
        try:
            w = shlex.split(part)
        except ValueError:
            w = part.split()
        for v in [x.split("=", 1)[1] for x in w if re.match(r"^\w+=", x)]:
            if v and (is_secret(v) or is_real(v) or harness_file(v, cwd) or touches_git(v, cwd)):
                return f"Deny-rule plate: a variable is set to {v}, a protected path. Refused."
        if any(re.match(r"^(EDITOR|VISUAL|PAGER|GIT_\w+|EMAIL|LD_PRELOAD|LD_LIBRARY_PATH|DYLD_\w+|BASH_ENV|ENV|PROMPT_COMMAND|PATH|"
                        r"PYTHONPATH|PYTHONSTARTUP|PYTHONHOME|PYTHONUSERBASE|NODE_OPTIONS|NODE_PATH|PERL5LIB|PERL5OPT|RUBYLIB|RUBYOPT|"
                        r"NPM_CONFIG_\w+|npm_config_\w+|PIP_\w+|LESSOPEN|LESSCLOSE|MANPAGER|BROWSER|SHELL|IFS|CDPATH|HOME)=", x) for x in w):
            return "No-merge gauntlets: PATH, EDITOR, PAGER, GIT_*, loader and interpreter variables change which program runs or what it loads. Refused."
        if any("/environ" in x for x in w):
            return "Deny-rule plate: a process environment can hold API keys and tokens. Refused."
        bad_wrap = wrapper_refusal(w)
        if bad_wrap:
            return bad_wrap
        w, wrapped_env = unwrap(w)
        dump = env_dump(w, wrapped_env)
        if dump:
            return dump
        if not w:
            continue
        why = program_refusal(w)
        if why:
            return why
        exe = os.path.basename(w[0])
        args = w[1:]
        pcwd, gsub, grest = cwd, "", []
        if exe == "git" and args:
            gsub, grest, gwhy = git_subcommand(args)
            if gwhy:
                return gwhy
            pcwd = git_dir_of(args, cwd)
            if pcwd != cwd.resolve() and not is_toplevel(pcwd):
                return "No-merge gauntlets: git -C must name a worktree's top folder, so paths mean the same to the guard and to git. Use paths from the top instead."
            CWD[0] = pcwd
            args_for_paths = grest
        else:
            args_for_paths = args
        if exe in ("patch", "unzip", "7z", "7za", "cpio", "bsdtar", "ar") or (exe in ("tar", "gtar") and any(
                a.startswith("-") and "x" in a.lstrip("-")[:4] or a in ("--extract", "--get") or (not a.startswith("-") and re.fullmatch(r"[a-z]*x[a-z]*", a) and args.index(a) == 0)
                for a in args)):
            return f"Harness: {exe} writes the files named inside a patch or archive, which the guard can't see. Use the Edit tool for changes."
        if exe not in READ_OK:
            for a in args:
                for x in path_pieces(a):
                    z = write_locked(x, pcwd)
                    if z:
                        return f"Harness: {z} is written only by the owner or by Agent Company itself. Agents may read it (cat, grep, head), not change it."
        runner = PROGRAM_RUN_OPTS.get(exe)
        if runner and any(a == o or a.startswith(o + "=") or (o.startswith("--") and len(a) >= 4 and a.split("=")[0] != "--" and o.startswith(a.split("=")[0]))
                          or (len(o) == 2 and a.startswith(o) and len(a) > 2) for a in args for o in runner):
            return f"No-merge gauntlets: that {exe} option runs another program, which the guard can't see. Refused."
        if exe == "cp" and any(a.startswith("--") and len(a) >= 4 and any(o.startswith(a.split("=")[0]) for o in ("--symbolic-link", "--link", "--dereference"))
                               for a in args):
            return "Harness: cp that makes or follows links can reach past the guard's path checks. Copy plain files."
        if exe == "cp" and any(a in ("-s", "-l", "--symbolic-link", "--link", "-L", "-H", "--dereference") or
                               (a.startswith("-") and not a.startswith("--") and set(a[1:]) & set("slLH")) for a in args):
            return "Harness: cp that makes or follows links can reach past the guard's path checks. Copy plain files."
        if exe == "git" and any(a.startswith(":") and not a.startswith("::") for a in grest):
            return "No-merge gauntlets: git pathspec magic (:/, :(top), :(icase)) changes which paths git touches. Use plain paths."
        if exe in ("grep", "egrep", "fgrep") and any(a in ("-d", "--directories", "--directories=recurse", "-drecurse") or a.startswith("--directories")
                                                    for a in args) and holds_secret(".", cwd):
            return "Deny-rule plate: grep reading folders here would reach a secret file. Name a narrower folder."
        if exe in NETWORK:
            return f"Constructed-data boots: {exe} opens a raw network connection, so it is refused."
        if exe == "find" and any(a in ("-exec", "-execdir", "-ok", "-okdir", "-delete", "-fprint", "-fprintf", "-fls") for a in args):
            return "No-merge gauntlets: find with -exec, -ok or -delete runs or deletes things the guard can't see, so it is refused."
        if exe in ("awk", "gawk", "nawk", "mawk") and any("system" in a or "|" in a or "getline" in a for a in args):
            return "No-merge gauntlets: awk that runs commands (system, |, getline) is refused."
        if exe in MOVERS or (exe == "git" and gsub in ("rm", "mv", "clean")):
            for a in args_for_paths:
                hit = protected_parent(a, pcwd)
                if hit and not a.startswith("-"):
                    return f"Harness: {exe} on {a} would move or delete {hit} (the harness, git's folder or real data). Refused."
        targets = [w[i + 1] for i, t in enumerate(w[:-1]) if set(t) <= set("<>&|0123456789") and ">" in t]
        if exe in WRITERS or exe == "git" and gsub in ("mv", "rm", "checkout", "restore"):
            pos_args = [a for a in args_for_paths if not a.startswith("-")]
            srcs = pos_args[:-1] if exe in ("mv", "cp") or gsub == "mv" else []
            for a in pos_args:
                z = write_locked(a, pcwd)
                dest = pos_args[-1] if pos_args else ""
                inbox_out = (exe == "git" and z == "docs/ops/inbox" and a in srcs and norm(a, pcwd).is_file() and
                             norm(dest, pcwd).as_posix().startswith((PROJECT / "docs/ops/done").as_posix() + "/"))
                if z and not inbox_out:
                    targets.append(a)
        for t in targets:
            z = write_locked(t, pcwd) or (harness_file(t, pcwd) and "the harness") or (touches_git(t, pcwd) and ".git")
            if z:
                return f"Harness: {z} is written only by the owner or by Agent Company itself (seal, the Guild's deploy). Agents may read it, not change it."
        if exe in SHELLS or w[0].startswith("$"):
            return f"No-merge gauntlets: '{w[0]}' runs commands the guard can't read, so it is refused. Run the command itself."
        for a in args_for_paths:
            for x in path_pieces(a):
                if touches_git(x, pcwd):
                    return f"No-merge gauntlets: {a} is inside git's own folder. Agents never touch .git."
                if is_secret(x):
                    return f"Deny-rule plate: {a} looks like a secret or key. Agents don't read or write secrets."
                if harness_file(x, pcwd):
                    return f"Harness: {a} is part of the harness itself (docs/ops/harness, .claude/settings.json). Agents don't change or read it from the shell."
                if any(ch in x for ch in GLOB_CHARS):
                    hit = glob_reaches(x, pcwd)
                    if hit:
                        return f"Deny-rule plate: {a} could reach {hit}, a secret or real-data path. Name the file you mean."
                if is_secret(x):
                    return f"Deny-rule plate: {a} looks like a secret or key. Agents don't read or write secrets."
                if is_real(x):
                    return f"Constructed-data boots: {a} is listed as real data. Use constructed cases only."
                if exe in READERS and holds_real(x, pcwd):
                    return f"Constructed-data boots: {exe} on {a} would reach a real-data folder inside it. Name a narrower folder."
                if exe in READERS | MOVERS and norm(x, pcwd).is_dir():
                    hid = holds_secret(x, pcwd)
                    if hid:
                        return f"Deny-rule plate: {exe} on {a} would reach {hid}, a secret. Name the files you mean."
        if exe in READERS and exe in ("grep", "rg", "ag", "find") and not [a for a in args if not a.startswith("-")][1 if exe != "find" else 0:]:
            if holds_real(".", pcwd):
                return f"Constructed-data boots: {exe} with no folder searches here, which holds real data. Name a narrower folder."
            if any(a.startswith("-") and ("r" in a.lstrip("-")[:3] or a.startswith("--recursive")) for a in args) or exe in ("rg", "ag", "find"):
                if holds_secret(".", pcwd):
                    return f"Deny-rule plate: {exe} here would reach a secret file. Name a narrower folder."
        if exe == "git" and args:
            sub, rest, why = git_subcommand(args)
            if why:
                return why
            gdir = git_dir_of(args, cwd)
            if gdir != cwd.resolve() and not is_toplevel(gdir):
                return "No-merge gauntlets: git -C must name a worktree's top folder, so paths mean the same to the guard and to git. Use paths from the top instead."
            if sub and sub not in GIT_SUBCOMMANDS:
                return f"No-merge gauntlets: 'git {sub}' is not a git command the guard knows (an alias or an outside program). Use the full git command."
            if sub:
                why = git_form_refusal(sub, rest, git_dir_of(args, cwd))
                if why:
                    return why
            if any(long_hit(a, ("--no-verify",)) for a in rest):
                return "No-merge gauntlets: --no-verify is refused. Git hooks stay on."
            if sub == "merge":
                return "No-merge gauntlets: agents never merge. Open a pull request; the owner merges."
            if sub == "config":
                keys = [a for a in rest if not a.startswith("-")]
                if not any(a in CONFIG_READ for a in rest) and keys and not config_key_ok(keys[0], keys[1] if len(keys) > 1 else ""):
                    return config_refusal(keys[0])
            if any(a in ("-x", "--exec", "--upload-pack", "--receive-pack", "-O", "--open-files-in-pager", "--remote") or (a == "-u" and sub != "push") or
                   a.startswith(("--exec=", "--upload-pack=", "--receive-pack=", "-O", "--open-files-in-pager=", "--remote=")) for a in rest) \
                    and sub in ("rebase", "fetch", "clone", "ls-remote", "pull", "grep", "archive", "push"):
                return f"No-merge gauntlets: git {sub} with an option that runs a command or reaches another machine is refused."
            if sub == "clean":
                return "Harness: git clean deletes untracked files, which can include the harness. Refused; remove named files yourself."
            if sub == "stash" and any(a in ("-u", "--include-untracked", "-a", "--all") for a in rest):
                return "Harness: git stash with untracked files can remove the harness. Refused."
            if sub == "reset" and "--hard" in rest:
                return "Harness: git reset --hard is refused (it can drop the harness and other work). Ask the owner."
            if sub in ("checkout", "switch", "restore"):
                gdir = git_dir_of(args, cwd)
                if any(a in (".", "--", "--source") or a.startswith("--source=") or a in ("-s", "--detach") for a in rest) or \
                        any(protected_parent(a, gdir) or harness_file(a, gdir) for a in rest if not a.startswith("-")):
                    return f"Harness: git {sub} over paths, another commit's files or a detached commit is refused, because it can replace the harness."
                target = "" if sub == "restore" or any(a in ("-b", "-B", "-c", "-C", "--orphan") for a in rest) else next((a for a in rest if not a.startswith("-")), "")
                if target and sub in ("checkout", "switch") and not is_branch(gdir, target):
                    return f"Harness: {target} is not a local branch; checking out a commit or a remote ref is refused (it can drop the harness). Make a branch with -b."
                if target and tracked_at(gdir, "HEAD", "docs/ops/harness/guard.py") and not tracked_at(gdir, target, "docs/ops/harness/guard.py"):
                    return f"Harness: {target} has no harness, so switching to it would remove the guard. Refused."
            if sub == "add" and (any(a in ("-A", "--all", ".", ":/", "*") for a in rest) or
                                 any(holds_real(a, git_dir_of(args, cwd)) for a in rest if not a.startswith("-"))) and real_present():
                return "Constructed-data boots: this project holds real data, so git add -A, git add . and adding its folder are refused. Add the files you changed by name."
            if sub == "commit" and any(a in ("-s", "--signoff") or a.startswith("--trailer") or a == "--author" or a.startswith("--author=") for a in rest):
                return "No-merge gauntlets: sign-offs, trailers and --author put words or a name on the commit that aren't the agent's. Refused."
            if sub in ("commit", "tag") and approval_words(" ".join(rest)):
                return "No-merge gauntlets: a commit or tag message may not say it is approved, signed off or decided. Describe the change; the owner decides."
            if sub == "push" and any(a in ("-o",) or a.startswith(("-o", "--push-option", "--push-o")) for a in rest):
                return "No-merge gauntlets: push options (-o) can set auto-merge on the host. Refused."
            if sub == "bisect" and rest[:1] == ["run"]:
                return "No-merge gauntlets: git bisect run runs a command the guard can't see, so it is refused."
            if sub == "add" and any(a in ("-f", "--force") for a in rest):
                return "Constructed-data boots: git add --force adds ignored files, which can include real data. Refused."
            if sub in ("show", "grep", "archive", "log", "diff", "blame", "cat-file") and real_tracked(git_dir_of(args, cwd)):
                return "Constructed-data boots: real data is tracked in this repository, so git commands that print file contents are refused. The owner removes it from history first."
            if sub in ("show", "cat-file") and any(is_real(a.split(":", 1)[-1]) for a in rest if ":" in a):
                return "Constructed-data boots: that file is listed as real data."
            if sub in ("show", "cat-file", "grep", "log", "diff", "blame") and any(
                    is_secret(a.split(":", 1)[-1]) or is_secret(a) for a in rest if not a.startswith("-")):
                return "Deny-rule plate: that names a secret file, as it is in git's history. Agents don't read secrets."
            if sub == "cat-file":
                return "Deny-rule plate: git cat-file reads any object in the repository, including secrets in history. Use git show <commit> for commits."
            if sub == "branch" and any(a in ("-f", "--force", "-M", "-m", "-D", "-C", "-c") for a in rest) and any(PROTECTED.match(a) for a in rest if not a.startswith("-")):
                return "No-merge gauntlets: moving, renaming or deleting a protected branch is refused."
            here = branch_of(git_dir_of(args, cwd))
            if sub in ("commit", "cherry-pick", "am", "revert", "reset", "rebase", "pull") and PROTECTED.match(here):
                return f"No-merge gauntlets: no {sub} on the protected branch {here}. Use your quest's branch and worktree."
            if sub == "push":
                why = push_refusal(rest, git_dir_of(args, cwd), check_remote=True)
                if why:
                    return why
            if sub == "remote" and rest[:1] and rest[0] in ("add", "set-url", "rename", "remove", "rm"):
                return "Constructed-data boots: agents don't add or change git remotes (a new remote can send the repository anywhere)."
            if sub == "worktree" and rest[:1] == ["add"] and any(PROTECTED.match(a) for a in rest[1:] if not a.startswith("-")):
                return "No-merge gauntlets: a worktree on a protected branch is refused. Make a worktree on your own branch."
        if exe == "gh":
            why = gh_refusal(args)
            if why:
                return why
        if exe in ("curl", "wget"):
            for a in args:
                if a in ("-K", "--config", "--data-urlencode", "--url-query", "--json") or a.startswith(("-K", "--config=")) or \
                        (a.startswith("--data-urlencode") or a.startswith("--url-query") or a.startswith("--json")) and "@" in a:
                    return "Constructed-data boots: curl options that read a file or a config file are refused."
                if a in ("-T", "--upload-file", "-F", "--form", "--post-file", "--body-file") or re.match(r"^(-T.|-F.|--upload-file=|--post-file=|--body-file=)", a) \
                        or a.startswith("@") or "=@" in a or re.match(r"^-(d|-data[\w-]*)=?@", a) or (a.startswith("-d") and "@" in a):
                    return "Constructed-data boots: uploading files from this machine is blocked."
                if "@" in a and not re.match(r"^[a-z]+://", a):
                    return "Constructed-data boots: a curl or wget argument with @ can read a file, so it is refused."
        if exe in ("scp", "rsync", "sftp") and any(":" in a and not a.startswith("-") for a in args):
            return "Constructed-data boots: copying files to another machine is blocked."
    return None


def decide(data: dict) -> str | None:
    tool = data.get("tool_name", "")
    ti = data.get("tool_input") or {}
    cwd = Path(data.get("cwd") or os.getcwd())
    CWD[0] = cwd.resolve()
    allow = load_allow()
    if tool == "Bash":
        return check_bash(ti.get("command", ""), cwd)
    if tool in ("Edit", "Write", "MultiEdit", "NotebookEdit", "Read"):
        p = ti.get("file_path") or ti.get("notebook_path") or ""
        if p and is_secret(p):
            return f"Deny-rule plate: {p} looks like a secret or key."
        if p and is_real(p):
            return f"Constructed-data boots: {p} is listed as real data."
        if p and touches_git(p, cwd):
            return f"No-merge gauntlets: {p} is git's own configuration or hooks. Agents never change it."
        if tool != "Read" and p and write_locked(p, cwd):
            return f"Harness: {write_locked(p, cwd)} is written only by the owner or by Agent Company itself. Agents may read it."
        if tool != "Read" and p and harness_file(p, cwd):
            return f"Harness: {p} is part of the harness itself. Agents never change it; the owner reinstalls it with agent_company.py harness."
        if tool != "Read" and p and not inside_project(p, cwd):
            return f"Worktree helm: {p} is outside this project folder. Agents only change files in their own worktree."
        return None
    if tool in ("Grep", "Glob", "LS"):
        where = ti.get("path") or "."
        if touches_git(str(where), cwd) or touches_git(str(ti.get("glob") or ""), cwd) or ".git/" in str(ti.get("pattern") if tool == "Glob" else ""):
            return "No-merge gauntlets: git's own folder holds config and remote URLs that can carry tokens. Agents don't search it."
        hid = holds_secret(str(where), cwd)
        if hid:
            return f"Deny-rule plate: searching {where} would reach {hid}, a secret. Search a narrower folder."
        for x in [where, ti.get("glob") or "", ti.get("pattern") if tool == "Glob" else ""]:
            if not x:
                continue
            if is_secret(x) or is_real(x):
                return f"Deny-rule plate / constructed-data boots: {x} is a secret or real-data path."
            if any(ch in x for ch in GLOB_CHARS):
                hit = glob_reaches(x if tool != "Glob" or x == where else os.path.join(where, x), cwd)
                if hit:
                    return f"Deny-rule plate: {x} could reach {hit}, a secret or real-data path. Narrow the search."
        base = norm(where, cwd)
        for r in real_paths():
            rp = norm(r, PROJECT)
            if rp == base or base in rp.parents:
                return f"Constructed-data boots: searching {where} would read {r}, which is listed as real data. Search a narrower folder."
        return None
    if tool in ("WebFetch", "WebSearch"):
        return None if allow.get("web") else "Allowlist belt: web tools aren't on this repo's allowlist (docs/ops/harness/allowlist.json)."
    if tool.startswith("mcp__"):
        server = tool.split("__")[1] if tool.count("__") >= 2 else tool[5:]
        servers = [s.lower() for s in allow.get("mcp_servers", [])]
        return None if server.lower() in servers else f"Allowlist belt: the MCP server '{server}' isn't on this repo's allowlist."
    return None


def log(data: dict) -> None:
    ev = PROJECT / "docs" / "ops" / "evidence"
    ev.mkdir(parents=True, exist_ok=True)
    ti = data.get("tool_input") or {}
    summary = ti.get("command") or ti.get("file_path") or ti.get("url") or ti.get("query") or ""
    line = {"t": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "session": data.get("session_id", ""), "tool": data.get("tool_name", ""), "what": str(summary)[:300]}
    with open(ev / "actions.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(line) + "\n")


def main() -> int:
    try:
        data = json.loads(sys.stdin.read() or "{}")
        if not isinstance(data, dict) or not isinstance(data.get("tool_input") or {}, dict):
            raise ValueError("not a tool call")
    except ValueError:
        if "--log" in sys.argv:
            return 0
        print("Agent Company harness: the guard could not read this tool call, so it is refused.", file=sys.stderr)
        return 2
    if "--log" in sys.argv:
        try:
            log(data)
        except OSError:
            pass
        return 0
    try:
        why = decide(data)
    except Exception as e:  # fail closed: exit 1 would let the call through
        why = f"Agent Company harness: the guard failed ({type(e).__name__}), so it cannot check this call; refused."
    if why:
        print(why, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
