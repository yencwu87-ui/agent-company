# Council verdict: Agent Company 0.5.3: third round of council fixes

**GO WITH CONDITIONS** on option B: Fix the named issues first, then ship

## Option scores

- A (2x8 + 3x4 + 1x1 + 3x2) / 9 = 3.9
- B (2x7 + 3x5 + 1x6 + 3x7) / 9 = 6.2
- C (2x2 + 3x3 + 1x5 + 3x5) / 9 = 3.7

Spread on B: 2. Council confidence: 6/10. Scored from round 1.

## Seats

| Seat | Weight | A | B | C | Ruin risk | Stance |
|---|---|---|---|---|---|---|
| Owner's goal | 2 | 8 | 7 | 2 | none | A: both goal fixes from 0.5.2 are in the code and tested; reversible; every gate starts off. |
| Breaker | 3 | 4 | 5 | 3 | possible | No robustness call: the session stopped before any hostile input was run. |
| Claims officer | 1 | 1 | 6 | 5 | none | B: counts hold, but at least seven README statements are false on the installed guard: shortened git options, -B/-C and '-', commit -F, dd/s |
| Guardian | 3 | 2 | 7 | 5 | possible | B: git grep/diff --no-index read real data; git apply, patch, tar and unzip rewrite the guard; checkout -b from an old commit, reset --keep  |

## Weak pillars (4 or below: each needs a named fix)

- Breaker (Robustness under attack): 4

## Fixes the seats asked for

- BLOCKING: --no-index reads
- BLOCKING: -s on cherry-pick, revert, rebase, am
- BLOCKING: GIT_AUTHOR_*/GIT_COMMITTER_*, prefix matching of --author/--signoff/--trailer, -sm, commit -C/-c
- BLOCKING: apply, am, patch, tar -x, unzip in the project
- BLOCKING: checkout -B/-C/'-', reset --keep, revert, rebase, cherry-pick, am, apply, bisect start
- BLOCKING: commit -F/-t/-C/-c, tag -F, git notes
- BLOCKING: dd of=, sort -o, patch, mkdir, cp -t
- BLOCKING: every prefix of --push-option
- BLOCKING: git add --pathspec-from-file
- BLOCKING: locked places case-insensitive
- BLOCKING: message files, notes, gh pr create --fill, look-alike letters
- BLOCKING: owner names without spaces, hyphens, look-alikes
- BLOCKING: shortened long options for reset/stash/add/commit
- BLOCKING: start points of checkout -b/switch -c, reset --keep/--merge, revert/cherry-pick of harness commits
- BLOCKING: test for --data-binary @ and the -F/scp cases in the upload group
- BLOCKING: wider approval wording and look-alike letters
- move the owner's-override README line back into its list (non-blocking)
- run the Breaker seat again so the installed-copy hostile run happens (non-blocking)
- seal as clean only with no BLOCKING fix left from any seat (non-blocking, for the Chair)

The council is a self-evaluation. It does not replace the tests, the sealed evidence record, the owner's merge or the walkthrough with the customer. Seats are roles, not people.
