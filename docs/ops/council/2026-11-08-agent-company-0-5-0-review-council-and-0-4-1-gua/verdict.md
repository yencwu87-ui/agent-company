# Council verdict: Agent Company 0.5.0: Review Council and 0.4.1 guard fixes

**GO WITH CONDITIONS** on option B: Fix the named issues first, then ship

## Option scores

- A (2x6 + 3x2 + 1x6 + 3x2) / 9 = 3.3
- B (2x8 + 3x6 + 1x8 + 3x7) / 9 = 7.0
- C (2x3 + 3x4 + 1x3 + 3x4) / 9 = 3.7

Spread on B: 2. Council confidence: 8/10. Scored from round 1.

## Seats

| Seat | Weight | A | B | C | Ruin risk | Stance |
|---|---|---|---|---|---|---|
| Owner's goal | 2 | 6 | 8 | 3 | none | B: covers each item asked for and is easy to undo; but the claims check fails on the council's own brief, and the self-eval gate's cost is u |
| Breaker | 3 | 2 | 6 | 4 | possible | B: about 45 of 55 hostile inputs got past the guard; worst, an agent can rewrite guard.py, settings.json or real_data_paths.txt with a plain |
| Claims officer | 1 | 6 | 8 | 3 | none | B: the counts and statements match the tests; the one gap is that the repo's own claims check exits 1 because of the council brief, which mu |
| Guardian | 3 | 2 | 7 | 4 | possible | B: the guard still lets an agent read real data through Grep, switch itself off by editing settings.json or real_data_paths.txt, and approve |

## Fixes the seats asked for

- Add Grep and Glob to the hook matcher; refuse unknown tools
- Add every route as a test; list the remaining open routes in README
- Check AGENT_COMPANY_OWNER after quote removal; refuse writing gh api calls and gh pr merge anywhere
- Grep and Glob in the matcher and decide(), with secret and real-data checks
- Guard tests for pushes to master and develop/*
- Label the design and retro councils as proposals for the owner
- Make `claims` pass with council folders in the repo, with a test
- Make claims pass on the whole repo before sealing this council
- One wording for XP
- Put Purse on the quick board or say why not
- Refuse checkout/switch/worktree/cd chained with push or commit; read branch from -C; refuse cherry-pick/reset/rebase/am/revert on protected branches
- Refuse curl -d@, -T<file>, -F=@ and wget --post-file; check after @ or =
- Refuse gh api merge/PUT/POST on pulls, gh alias, gh pr review --approve (or allowlist gh)
- Refuse git remote add/set-url
- Refuse sh/bash/zsh/eval/source and pipes into a shell; unquoted globs and redirects near secret or real-data names
- Refuse writes to .claude/settings*.json and docs/ops/harness/*
- Refuse writes to docs/ops/harness/*, .claude/settings*.json, .git/hooks; resolve paths (symlinks, case) first
- Resolve .git paths in Bash args; refuse cd .git
- State the self-eval gate's cost and how the owner switches it off
- Test that editing a round file after sealing fails verify
- Tests for each route; list remaining open routes in README
- Widen the check branch regex (quotes, bold, punctuation, origin/)
- council init/score refuse claim words, or claims skips docs/ops/council, with a test
- council.py: one card per seat, mitigation_endorsed only in round 3, no bool scores
- mitigation_endorsed only in round 3

The council is a self-evaluation. It does not replace the tests, the sealed evidence record, the owner's merge or the walkthrough with the customer. Seats are roles, not people.
