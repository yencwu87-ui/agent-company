# Council verdict: Agent Company 0.5.1: council fixes and guard hardening

**GO WITH CONDITIONS** on option B: Fix the named issues first, then ship

## Option scores

- A (2x5 + 3x1 + 1x3 + 3x2) / 9 = 2.4
- B (2x8 + 3x6 + 1x8 + 3x7) / 9 = 7.0
- C (2x3 + 3x4 + 1x4 + 3x4) / 9 = 3.8

Spread on B: 2. Council confidence: 8/10. Scored from round 1.

## Seats

| Seat | Weight | A | B | C | Ruin risk | Stance |
|---|---|---|---|---|---|---|
| Owner's goal | 2 | 5 | 8 | 3 | none | B: covers the 0.5.0 fix list, but the repo-wide claims check still exits 1 on the 0.5.0 brief, and the owner asked for a clean seal. |
| Breaker | 3 | 1 | 6 | 4 | possible | B: 24 of 27 hostile commands got past the 0.5.1 guard, including a settings rewrite through a glob and real data read through variables, bra |
| Claims officer | 1 | 3 | 8 | 4 | none | B: counts match, but four statements are not backed: the repo-wide claims check, 'every spelling' of uploads, seal accepting edits after sco |
| Guardian | 3 | 2 | 7 | 4 | possible | B: 'cd data && cat real/r.csv' still reaches real data because relative paths resolve from the project root; real data can be committed and  |

## Fixes the seats asked for

- BLOCKING: a test for claims over a repo with a council folder
- BLOCKING: claims exits 0 on the whole repo
- BLOCKING: claims exits 0 repo-wide, with a test
- BLOCKING: curl --data-urlencode @ and -K
- BLOCKING: git rebase -x, bisect run, --upload-pack, grep -O; find -exec, awk system
- BLOCKING: globs checked against harness and .git
- BLOCKING: keep real data out of git (.gitignore, add -f, show/grep/archive)
- BLOCKING: list tested upload spellings instead of 'every spelling'
- BLOCKING: no git exemption for harness paths
- BLOCKING: protect parent folders of the harness and ~/.claude settings
- BLOCKING: refuse moving or deleting parents of harness or real data
- BLOCKING: refuse shell expansion in paths; check VAR=value
- BLOCKING: resolve paths from the call's folder; refuse cd chained with reads
- BLOCKING: seal refuses a hand-edited verdict.md
- council gate switches in the inbox README
- curl -K, mv and diff on real-data folders
- gh api -XGET crash
- gh posts that claim approval
- git branch -f on protected names; case-insensitive protected names
- hash-based change check
- seal states or runs the repo-wide check
- tests for all 24

The council is a self-evaluation. It does not replace the tests, the sealed evidence record, the owner's merge or the walkthrough with the customer. Seats are roles, not people.
