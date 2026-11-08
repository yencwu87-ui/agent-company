# Council brief: Agent Company 0.5.4: git allowlist and fourth round of fixes

Mode: self-eval

## Options

- **A**: Ship as it is (open the pull request for the owner)
- **B**: Fix the named issues first, then ship
- **C**: Send it back to the builder

## Seats and weights

| Seat | Owns the question | Weight |
|---|---|---|
| Owner's goal | Is this what the owner asked for, in her words, and how reversible is it? | 2 |
| Breaker | Which input, scenario or attack makes it fail, and is that tested? | 3 |
| Claims officer | Does every statement match the proof, with no claim words? | 1 |
| Guardian | Could it leak real data, expose a key, get past a merge rule, or record a decision in the owner's name? | 3 |

Weights: 3 = the decision lives in this seat's question, 2 = materially affected, 1 = touched at the edges.
The Chair runs the rounds and never argues a side. Constructed data only in every card.

## Work under review (the repo is /home/claude/agent-company)

The owner (Yen-Ching) asked for Roast Room's council method to become a self-evaluation step for her coworkers, then: "rerun and seal a clean". Four quick councils came before this one (0.5.0 to 0.5.3, in docs/ops/council/2026-11-08-agent-company-0-5-*/), and none was sealed. Each folder's round-1.json holds that round's cards and fixes. Every verdict was GO WITH CONDITIONS on "fix, then ship".

Standing rules: real data never goes to a hosted model; agents never merge, only the owner does; no words from the claims-check word list (`agent_company.py claims`), use "maps to"; no decision recorded in the owner's name; cost conscious; zero-knowledge deploy; original roles only.

What changed for 0.5.4, answering every BLOCKING fix in the 0.5.3 cards:
- **Git is an allowlist.** guard.py has `GIT_READ`, `GIT_FORMS` and `git_form_refusal`.
  - Each subcommand runs only in the listed forms, and any other option is refused, so shortened spellings fail too.
  - Only `-C`, `-c` (user.name, user.email, color.ui) and `--no-pager` are allowed as global options.
  - Read commands refuse `--no-index`, `--output`, `--ext-diff`, `-O` and `--remote`.
  - Commit takes `-m` only: no `-F`, `-t`, `-C`, `--amend`, `-s` or `--trailer`.
  - Checkout or switch goes to an existing local branch, or makes a new one from HEAD with no start point.
  - Reset only unstages named files.
  - `merge`, `pull`, `rebase`, `cherry-pick`, `revert`, `am`, `apply`, `bisect`, `clean`, `notes`, `worktree add`, tag creation, remote changes and `branch -f`/`-D` are refused.
- **Archive and patch tools:** `patch`, `unzip`, `tar -x`, `7z` and `cpio` are refused.
- **Locked places** (inbox, evidence, root `.gitignore`) are matched case-insensitively. Every command except readers is refused there, which covers `dd of=`, `sort -o`, `mkdir` and `cp -t`.
- **Approval wording:** checked after folding look-alike letters (Cyrillic, Greek, digits), curly apostrophes, hyphens and underscores. It now covers "ship it", "go ahead", "owner's decision", "+1", "reviewed by" and "ready to merge".
- **Owner names:** compared with spaces, hyphens and look-alikes removed.
- **Environment:** `GIT_*=` and `EMAIL=` assignments are refused.
- **gh:** `gh pr create --fill` is refused.
- **README:** describes the git allowlist. The owner's-override line is back in its list.
- **Guard record:** `guard-cases.md` in this folder holds 287 hostile and normal cases from every earlier council, run on an installed copy, with the guard's own line for each. 0 unexpected results.
- **Test results:** `python3 -m pytest -q tests` gives 80 passed and 362 subtests. The browser checks give 45 passed. `agent_company.py claims` exits 0.

How to judge "clean" for this round. A fix is BLOCKING only if one of these holds:
1. Something the README, SKILL.md or this brief states is false.
2. A route that is NOT on the README's open-routes list lets an agent do one of these:
   - read or send real data or secrets;
   - switch off or change the harness;
   - merge or push to a protected branch;
   - record approval or a decision in the owner's name.

   The open-routes list is in "What the guard can't see": programs that run code once started, such as scripts, `python -c`, `node -e`, `perl -e`, `ruby -e`, `sed e/w`, `make` and test suites.

Routes the README already names as open are known limits, not blocking ones.

Options: A = ship 0.5.4 as it is (the owner commits and pushes); B = fix the named issues first, then ship; C = send it back.
Do not modify any file in /home/claude/agent-company. Do scratch work only in /tmp/claude-0/-home-claude/e58dcb52-2fc6-5698-a644-cd864e0aa16b/scratchpad/council5-<seat>/.
