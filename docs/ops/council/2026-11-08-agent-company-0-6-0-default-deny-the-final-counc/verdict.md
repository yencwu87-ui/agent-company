# Council verdict: Agent Company 0.6.0: default deny, the final council

**GO WITH CONDITIONS** on option B: Fix the named issues first, then ship

## Option scores

- A (2x2 + 1x3 + 3x8) / 6 = 5.2
- B (2x8 + 1x8 + 3x5) / 6 = 6.5
- C (2x4 + 1x3 + 3x2) / 6 = 2.8

Spread on B: 3. Council confidence: 8/10. Scored from round 1.

## Abstained

- Breaker: Abstained: a safety check stopped the seat's run before any probe ran, so it has no tested evidence. Not re-run, to keep the council inside the 450k-token budget the Roast Room verdict set. (left out of the weights)

## Seats

| Seat | Weight | A | B | C | Ruin risk | Stance |
|---|---|---|---|---|---|---|
| Owner's goal | 2 | 2 | 8 | 4 | possible | B: two allowed commands turned bash into 'git' through PATH and rewrote .claude/settings.json; git show HEAD:.env printed a committed secret |
| Claims officer | 1 | 3 | 8 | 3 | none | B: every count checks out, but 'env without -C or -S' is false: env -iCdocs and env --ch=docs deleted the guard; listed programs with option |
| Guardian | 3 | 8 | 5 | 2 | none | A: 26 of 30 hostile inputs refused; the 4 that got through were 1 list gap and 3 named known limits; none gets past both the separate agent  |

## Fixes the seats asked for

- BLOCKING: env option clusters and abbreviations
- BLOCKING: refuse PATH= and other lookup variables; test cp /bin/bash src/git + env PATH=./src git
- BLOCKING: secret check on bare rev:path (git show HEAD:.env)
- README script count wording (non-blocking)
- README: shells never allowed (non-blocking)
- README: the approval check doesn't read file contents (non-blocking)
- list gap: cp abbreviated link options
- list gap: git cat-file
- list gap: git show/cat-file rev:path secret check
- list gap: normalise node tests/ paths
- list gap: tar/sort/rg/zip options that run programs
- list gap: widen SHELLS
- node tests/../x.js (non-blocking)
- pytest -p as a known limit (non-blocking)

The council is a self-evaluation. It does not replace the tests, the sealed evidence record, the owner's merge or the walkthrough with the customer. Seats are roles, not people.
