# Council verdict: Agent Company 0.5.4: git allowlist and fourth round of fixes

**GO WITH CONDITIONS** on option B: Fix the named issues first, then ship

## Option scores

- A (2x4 + 3x3 + 1x3 + 3x2) / 9 = 2.9
- B (2x7 + 3x8 + 1x8 + 3x7) / 9 = 7.4
- C (2x3 + 3x4 + 1x5 + 3x5) / 9 = 4.2

Spread on B: 1. Council confidence: 8/10. Scored from round 1.

## Warning

Round 1 was unanimous within 1 point. The strongest unargued alternative should have been a crux in round 2.

## Seats

| Seat | Weight | A | B | C | Ruin risk | Stance |
|---|---|---|---|---|---|---|
| Owner's goal | 2 | 4 | 7 | 3 | none | B: two README statements about the owner's name and approval wording fail on an installed guard; small fixes. |
| Breaker | 3 | 3 | 8 | 4 | possible | B: 69 of 75 hostile inputs refused, all data, harness and push routes held; the 6 that got through record approval in text, the worst with a |
| Claims officer | 1 | 3 | 8 | 5 | none | B: counts match; four statements are false on an installed copy: global options, restore with the harness committed, mv out of the inbox, re |
| Guardian | 3 | 2 | 7 | 5 | possible | B: gh auth status -t prints the owner's token, git fetch . feat:main moves main, reset <rev> -- moves HEAD, other credential files and envir |

## Weak pillars (4 or below: each needs a named fix)

- Guardian (Downside and standing rules): 4

## Fixes the seats asked for

- BLOCKING: .netrc, .npmrc, .pypirc, .docker, .kube, gh hosts
- BLOCKING: decision in the owner's name without a listed word, or name free-worded approval as a known limit
- BLOCKING: drop Unicode format characters before the approval check
- BLOCKING: environment dumps
- BLOCKING: fetch refspecs and fetch .
- BLOCKING: gh auth status -t
- BLOCKING: global options
- BLOCKING: join letters split by dots, hyphens or spaces
- BLOCKING: owner name in message text
- BLOCKING: plain mv out of the inbox
- BLOCKING: reordered owner name and partial name in email
- BLOCKING: reset <rev> --
- BLOCKING: reset to HEAD only
- BLOCKING: restore with the harness committed; rerun the record with the harness committed
- BLOCKING: zero-width, hyphenated and spaced approval words
- clearer refusal line for owner-name user.name
- gh pr create -f
- git config --list
- record the passing approval phrases
- shipit and okay to merge; say the word list covers common forms only

The council is a self-evaluation. It does not replace the tests, the sealed evidence record, the owner's merge or the walkthrough with the customer. Seats are roles, not people.
