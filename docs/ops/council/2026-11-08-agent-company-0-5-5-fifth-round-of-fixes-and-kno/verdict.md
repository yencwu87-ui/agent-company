# Council verdict: Agent Company 0.5.5: fifth round of fixes and known limits

**GO** on option B: Fix the named issues first, then ship

## Option scores

- A (2x3 + 3x2 + 1x2 + 3x2) / 9 = 2.2
- B (2x8 + 3x8 + 1x8 + 3x8) / 9 = 8.0
- C (2x2 + 3x4 + 1x4 + 3x4) / 9 = 3.6

Spread on B: 0. Council confidence: 8/10. Scored from round 3.

## Seats

| Seat | Weight | A | B | C | Ruin risk | Stance |
|---|---|---|---|---|---|---|
| Owner's goal | 2 | 3 | 8 | 2 | none | B: every round-2 fix holds as named, but the wrapper fix is a fixed list: any leading program not on it (caffeinate and arch on macOS, flock |
| Breaker | 3 | 2 | 8 | 4 | possible | B: all 12 round-2 routes refused, but 30 of 40 new inputs got past and 26 did damage: env -C changes the folder without the guard following, |
| Claims officer | 1 | 2 | 8 | 4 | possible | B: my round-2 fixes hold, but unlisted wrappers hide git and gh (flock moved the remote's main in a scratch copy), and env with only a redir |
| Guardian | 3 | 2 | 8 | 4 | possible | B: every round-2 route refused, but an agent-made symlink lets grep -R print a .env and real data, unlisted wrappers skip every git and gh c |

## Weak pillars (4 or below: each needs a named fix)

- Breaker (Robustness under attack): 3

## Fixes the seats asked for

- BLOCKING: env -C / sudo -D folder
- BLOCKING: env > file
- BLOCKING: git grep --untracked
- BLOCKING: git pathspec magic
- BLOCKING: grep -d recurse with no folder
- BLOCKING: judge or refuse a command whose first word is unknown and a later word is git, gh, env or printenv
- BLOCKING: judge the command that actually runs behind any program
- BLOCKING: ps e / environ field
- BLOCKING: symlink targets resolved from the link's folder; follow links when checking folders
- BLOCKING: unlisted wrappers
- BLOCKING: xargs -a and xargs into movers or git
- LESSOPEN and MANPAGER (non-blocking)
- README on unknown wrappers (non-blocking)
- git mv wording (non-blocking)

The council is a self-evaluation. It does not replace the tests, the sealed evidence record, the owner's merge or the walkthrough with the customer. Seats are roles, not people.
