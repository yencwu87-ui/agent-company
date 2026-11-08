# Council brief: Agent Company 0.5.1: council fixes and guard hardening

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

The owner (Yen-Ching) asked for the guard fixes, then for Roast Room's council method to become a self-evaluation step for her coworkers. A first quick council on 0.5.0 (folder docs/ops/council/2026-11-08-agent-company-0-5-0-review-council-and-0-4-1-gua/, verdict.md and round-1.json) returned GO WITH CONDITIONS on "fix, then ship", with fixes from every seat. She said: "rerun and seal a clean". Her standing rules: real data never to a hosted model; agents never merge, only the owner; no words from the claims-check word list (`agent_company.py claims`), use "maps to"; no decision in the owner's name; cost conscious; zero-knowledge deploy; original roles only, no simulations of real people in the product.

What changed since that council (0.5.1):
- `harness/guard.py`: refuses writes to docs/ops/harness and .claude/settings*.json, and anything in .git after resolving paths (symlinks, case, `.git//`); refuses branch or folder changes chained with commits or pushes; reads the branch from `git -C`; refuses cherry-pick/reset/rebase/revert/am/pull on protected branches and worktrees on them; refuses `git remote add/set-url` and pushes to URLs; allows gh only for view/list/comment/create and read-only `gh api`; refuses shells, eval, source, pipes into a shell and `$VAR` commands; checks Grep/Glob/LS, shell globs, redirects, folders that contain real data, and every upload spelling; finds the owner override however it is quoted.
- `agent_company.py`: hook matcher now includes Grep, Glob and LS (an older install's matcher is updated on reinstall); the `check` branch rule catches quotes, bold, punctuation and origin/ prefixes; `council seal` refuses claim words and files changed after scoring; VERSION 0.5.1.
- `council.py`: one card per seat per round; mitigation_endorsed only in round 3; bool scores refused; the verdict reports claim words; cost and owner-switchable gates stated in the protocol.
- README harness section lists the new refusals and the routes still open (programs that run code: python -c, node -e, scripts, make). README and SKILL.md label the three council gates as proposals the owner switches on, with call counts.
- Tests: `cd <copy> && python3 -m pytest -q tests` gives 66 passed, 168 subtests; new cases in tests/test_guard_cases.py (class CouncilRoutes) and tests/test_council.py.

Options: A = ship 0.5.1 as it is (owner commits and pushes); B = fix named issues first, then ship; C = send it back.
Judge against your own question. Fixes you would still need go in your card; say whether each is blocking.
Do not modify any file in /home/claude/agent-company. Scratch work only in /tmp/claude-0/-home-claude/e58dcb52-2fc6-5698-a644-cd864e0aa16b/scratchpad/council2-<seat>/.
