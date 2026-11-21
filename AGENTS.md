# AGENTS.md

Instructions for coding agents working in this repository.

## Setup

Python 3.9 or later and git; the code uses only the standard library, so a fresh checkout needs no install step. The browser tests in `tests/test_ui.mjs` additionally need Node and Playwright and are not part of the factory's checks.

## Validation

Run `python3 -m unittest discover -s tests` from the repository root. It must pass before any change is
handed over. `factory/checks.sh` runs the same command.

## Software factory

`/factory run` builds every open GitHub issue labeled `factory` through
intake → spec → build → gate → review → approve, one PR per issue. State is in
`factory/jobs/` (gitignored); `factory/bin/job` is its only writer. Checks:
`factory/checks.sh`. Dashboard: `cd factory && python3 -m http.server`, then
open http://localhost:8000/dashboard.html.

Each job works in its own git worktree, a full checkout of the repo at
`.worktrees/<job-id>` (gitignored). A tool run from the repo root that doesn't
read `.gitignore` sees those copies too; exclude `.worktrees/` in its config.

The owner merges every pull request herself: the approver always escalates.
The factory files are third-party GPLv3 code; see `factory/THIRD_PARTY.md`.
