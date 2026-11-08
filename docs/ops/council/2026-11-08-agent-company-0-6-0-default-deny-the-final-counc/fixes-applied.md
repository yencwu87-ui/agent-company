# Fixes applied the same day (Roast Room verdict, condition 3)

The Roast Room verdict of 8 Nov (~/dev/roast-room/sessions/2026-11-08-agent-company-seal-or-060/verdict.md) set the rule for this final council. One final council runs. Gaps it finds are patched and sealed the same day. Only a way past BOTH the separate agent Git account AND branch protection reopens the decision. No seat found such a way.

Every finding below is patched in harness/guard.py, and each one has refused cases in tests/test_guard_cases.py, classes FinalRoutes and Round8Routes.

| Finding (seat) | Label | Fix | Test cases |
|---|---|---|---|
| `cp /bin/bash src/git` + `env PATH=./src git status` runs bash as git (Goal) | BLOCKING | PATH, PYTHONPATH, NODE_OPTIONS, PERL5LIB, RUBYLIB, NPM_CONFIG_*, PIP_*, SHELL, IFS, HOME and other lookup or loader variables are refused | env PATH=..., PATH=..., export PATH=..., PYTHONPATH, NODE_OPTIONS |
| `git show HEAD:.env` prints a committed secret (Goal, Guardian) | BLOCKING | git show/grep/log/diff/blame refuse a secret name, including in rev:path form; git cat-file is refused | git show HEAD:.env, git cat-file -p HEAD:.env, git cat-file blob |
| `env -iCdocs` and `env --ch=docs` change folder past the check (Claims) | BLOCKING | env takes only -i, -u NAME, --unset=NAME, -0 and --; any other option is refused | env -iCdocs, env --ch=, env -iS, env --sp= |
| tar --checkpoint-action / --to-command / -I, sort --compress-program, rg --pre, zip -TT run programs (Claims) | list gap | PROGRAM_RUN_OPTS refuses these options and their abbreviations | tar, sort, rg and zip cases |
| A shell the owner lists (mksh, rbash, busybox) runs (Claims) | list gap | SHELLS widened (mksh, rbash, yash, pwsh, nu, xonsh, elvish, busybox, toybox, ash and others); listed shells are still refused | test_owner_cannot_list_a_shell |
| cp --sym / --li / --deref (Claims) | list gap | abbreviations of --symbolic-link, --link and --dereference are refused | cp --sym, --li, --deref |
| node tests/../x.js runs a script outside tests/ (Goal, Guardian) | list gap | test commands that end in a folder run files inside that folder only | node tests/../x.js, node tests/../../x.js |
| README wording: shells, script count, pytest -p, approval in files (Goal, Claims, Guardian) | non-blocking | README reworded: shells are never allowed; the 6 refused commands are listed; pytest plugins and file contents are named as known limits | claims check passes |

The Breaker seat abstained: a safety check stopped its run before any probe ran. It was not re-run, to keep the council inside the 450k-token budget. Its weight is left out, and the verdict names the abstention.

After the fixes, `python3 -m pytest -q tests` gives 96 passed, 590 subtests. The browser checks give 45 passed, and `agent_company.py claims` exits 0.
