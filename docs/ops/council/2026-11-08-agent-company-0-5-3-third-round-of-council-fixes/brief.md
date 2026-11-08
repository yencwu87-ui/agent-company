# Council brief: Agent Company 0.5.3: third round of council fixes

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

The owner (Yen-Ching) asked for Roast Room's council method to become a self-evaluation step for her coworkers, then: "rerun and seal a clean". Three quick councils came before this one, and none was sealed: 0.5.0, 0.5.1 and 0.5.2, in docs/ops/council/2026-11-08-agent-company-0-5-*/. Each has round-1.json with the cards and fixes. All three verdicts were GO WITH CONDITIONS on "fix, then ship".

Her standing rules: real data never to a hosted model; agents never merge, only the owner; no words from the claims-check word list (`agent_company.py claims`), use "maps to"; no decision in the owner's name; cost conscious; zero-knowledge deploy; original roles only.

What changed for 0.5.3, answering every BLOCKING fix in the 0.5.2 cards:
- **git commands that can remove the harness are refused:** `git clean`, `stash -u/--all`, `reset --hard`, checkout or restore over paths or from another commit, checkout of anything that isn't a local branch, and switching to a branch without the harness.
- **Places agents may read but not write:** `.gitignore`, `docs/ops/inbox/` and `docs/ops/evidence/` are refused for Write/Edit, shell redirects and writer commands. Moving a finished instruction out of the inbox with git mv is allowed.
- **Real data stays out of git:** `git add .`, `-A` and folder adds are refused while the project holds real data. The pre-push hook refuses a push whose commits touch a real-data path.
- **gh posts:** `--body-file`, `-F` and templates are refused. Wider approval wording ("ship it", "go ahead", "owner's decision", "accepted", look-alike spellings) is refused in posts, commit messages and tag messages.
- **Nothing in the owner's name:** `git commit -s`, `--trailer` and `--author` are refused, and so is setting user.name or user.email to the guild's owner name or "owner".
- **Push options:** `git push -o` and `--push-option` are refused.
- **Upload spellings:** every spelling the README names has a test case, and so do bisect run, archive --remote, find -delete, ~user and ~/.claude.
- **Tests:** a fail-closed test (a guard exception exits 2). The empty test overrides are gone.
- **Older set-ups:** `init` adds the council gates list, all off, to an older inbox README.
- **README:** states that Read may read harness files, and that seal checks claim words in its own folder only.
- **Guard record:** `guard-cases.md` in this folder holds all 202 hostile and normal cases from the earlier councils, run on an installed copy, with the guard's own line for each. 0 unexpected results.
- **Test runs:** `python3 -m pytest -q tests` gives 77 passed and 272 subtests. The browser checks give 45 passed. `agent_company.py claims` exits 0.

How to judge "clean" for this round. A fix is BLOCKING only if:
(1) something the README, SKILL.md or this brief states is false; or
(2) a route NOT in the README's open-routes list ("What the guard can't see": programs that run code once started, such as scripts, python -c, node -e, perl -e, ruby -e, sed e/w, make, test suites) lets an agent (a) read or send real data or secrets, (b) switch off or change the harness, (c) merge or push to a protected branch, or (d) record approval or a decision in the owner's name.
Routes the README already names as open are known limits and are not blocking.

Options: A = ship 0.5.3 as it is (the owner commits and pushes); B = fix the named issues first, then ship; C = send it back.
Do not modify any file in /home/claude/agent-company. Scratch work goes only in /tmp/claude-0/-home-claude/e58dcb52-2fc6-5698-a644-cd864e0aa16b/scratchpad/council4-<seat>/.
