# Council brief: Agent Company 0.5.0: Review Council and 0.4.1 guard fixes

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

## Work under review (read these; the repo is /home/claude/agent-company)

The owner (Yen-Ching) asked: "carry on all the fix" (guard fail-closed and bypasses, branch-check rule, claim-word checker), then "install roast-room ... reorganise how all coworkers work ... possibly became one of self eval component". Her standing rules: real data never to a hosted model; agents never merge, only the owner; no words from the claims-check word list (`agent_company.py claims`; use "maps to") [reworded on 8 Nov before sealing; this council was not sealed]; no decision in the owner's name; cost conscious; anyone with zero technical knowledge must be able to deploy; original roles only, no simulations of real people in the product.

Changed files:
- `harness/guard.py`: fails closed; refuses git aliases, unknown subcommands, most git config keys, shortened push options, + refspecs, bare `git push`, HEAD on main, `$( )`, subshells, a lone `&`, wrappers, AGENT_COMPANY_OWNER set by an agent, writes into .git. Stated limit in README: text-only; server-side branch protection is the final stop.
- `agent_company.py`: `check` branch regex (line ~79); `claims` command (`claim_hits`, `cmd_claims`); `council` command (`cmd_council`); `verify_record` accepts kind "council" and record ids `council-<12 hex>`; VERSION 0.5.0.
- `council.py`: seats, `init`, `score` (weighted scores, bands, ruin cap, one-way-door cap, unanimity warning), agent-file template, protocol.
- `tests/test_guard_cases.py` (77 cases), `tests/test_council.py` (6 tests). Run: `cd /home/claude/agent-company && python3 -m pytest -q tests` (56 pass).
- `README.md` (harness section, Review Council section, Credits), `SKILL.md` (roles and loop), `templates/council.md`.
- The coworker org chart now puts a decision council at design, a quick self-eval council after tests and before the owner's merge, and a weekly retro council.

Options: A = ship 0.5.0 as it is (owner commits and pushes); B = fix the named issues first, then ship; C = send it back.
Do not modify any file in /home/claude/agent-company. Scratch work only in /tmp/claude-0/-home-claude/e58dcb52-2fc6-5698-a644-cd864e0aa16b/scratchpad/council-<seat>/.
