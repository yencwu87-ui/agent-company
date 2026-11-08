# Council verdict: Agent Company 0.5.2: second round of council fixes

**GO WITH CONDITIONS** on option B: Fix the named issues first, then ship

## Option scores

- A (2x7 + 3x3 + 1x4 + 3x2) / 9 = 3.7
- B (2x8 + 3x6 + 1x8 + 3x7) / 9 = 7.0
- C (2x2 + 3x4 + 1x3 + 3x4) / 9 = 3.4

Spread on B: 2. Council confidence: 7/10. Scored from round 1.

## Seats

| Seat | Weight | A | B | C | Ruin risk | Stance |
|---|---|---|---|---|---|---|
| Owner's goal | 2 | 7 | 8 | 2 | none | B: answers all three 0.5.1 goal fixes and keeps every gate off and owner-switched; an older set-up never gets the gates list. |
| Breaker | 3 | 3 | 6 | 4 | possible | B with low confidence: the 0.5.1 list maps to code, but this round's hostile testing was cut short. |
| Claims officer | 1 | 4 | 8 | 3 | none | B: counts and behaviour match, but gh approval text via --body-file gets through, and the README calls upload spellings tested that no test  |
| Guardian | 3 | 2 | 7 | 4 | possible | B: six routes outside the README's open list: git clean/stash/reset remove the harness, .gitignore edits let real data into commits, approva |

## Fixes the seats asked for

- BLOCKING: agent writes to the inbox
- BLOCKING: commit -s, --trailer, owner user.name
- BLOCKING: cover gh --body-file/-F
- BLOCKING: gh --body-file and wider approval wording
- BLOCKING: git clean, stash -u, reset --hard, checkout/restore of other commits
- BLOCKING: protect .gitignore; refuse git add . / -A with real data; pre-push refuses real-data paths
- BLOCKING: push -o
- BLOCKING: re-run the 0.5.1 hostile cases on an installed copy and record each refusal line in the council folder
- BLOCKING: tests for every upload spelling the README names
- README states the Read tool may read harness files
- evidence append-only for agents
- init or doctor adds the gates list to an older inbox README (non-blocking)
- no empty test overrides
- seal states it checks only its own folder (non-blocking)
- test that a guard exception exits 2
- tests for bisect run, archive --remote, find -delete, --url-query @, ~user, ~/.claude

The council is a self-evaluation. It does not replace the tests, the sealed evidence record, the owner's merge or the walkthrough with the customer. Seats are roles, not people.
