# NNN: <short title>

Owner's words: "<exact quote>" (<date>)
Branch: `<type>/<plain-words>` from `<base>`, in its own worktree
Order: <before/after/alongside which instructions; any "start only when…">
Intent: <why this matters and what "good" looks like, in one or two sentences. If the plan breaks on contact, the agent acts on this within the rules: it never loosens a guard or merges, and when unsure it stops and reports>

## Steps
1. Failing tests first: <what must be shown to fail>.
2. The change: <what to build or fix; what must not be loosened>.
3. Tests to run: <named tests>. Expected: <counts or "0 wrong">.
4. Records: <defect register row, docs>.

## Stop point
Upload the branch, open a pull request into `<base>`, and write the evaluator brief in `<path>`. Don't merge. Report in docs/ops/outbox/.
