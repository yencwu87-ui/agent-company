---
name: agent-company
description: Run a company of AI agents as one orchestrated team, with a human owner, a coordinator, builders, reviewers and an evidence trail. Use when setting up, running or fixing multi-agent work across sessions, tools or machines.
---

# Agent company: run AI agents like a well-run team

People manage, and agents do the work. The owner sets direction, judges the results and fixes what breaks. Everything else is delegated to agents with one job each, written instructions, independent review and evidence. This skill works with any agent tool that reads files: Claude Code, Codex, Cursor, Copilot, Gemini CLI and others. Nothing in it is tied to one model.

## Principles (why it works)
1. **The owner keeps three jobs**: direction (the plan and the order of work), judgement (merge, release, decisions), and repair (unblocking). An agent never takes these, even when told it may.
2. **One job per agent, one agent per job.** Most failures come from overlap: two coordinators, two builders on one branch, a reviewer who also fixes.
3. **Written hand-offs, not chat.** Work moves through files in the repository, so any agent, tool or machine can pick it up cold.
4. **Repetitive work becomes templates and rubrics.** Every recurring kind of task gets a template with a fixed definition of done. This is how the last 10% of reliability is earned.
5. **Evaluations are the moat.** Tests, gates, review prompts, the defect register and the claims check are the company's most valuable asset. Every defect adds a test, and every review finding adds a rubric line.
6. **Standards are set at the top.** The rules file (AGENTS.md or CLAUDE.md) is the culture, and agents copy whatever the owner tolerates.
7. **Trust is earned with evidence.** A status line is believed only when the evidence is shown: a commit, a test count, a link. "Done" without evidence is "unknown".

## Roles
| Role | Does | Never does |
|---|---|---|
| Owner (a person) | sets direction, merges, releases, decides | builds |
| Chief of staff | turns the owner's goals into numbered instructions, reads reports, checks them against the rules, tells the owner only what needs them | builds, merges |
| Coordinator (exactly one) | works the inbox in order, opens one worktree or branch per instruction, keeps STATUS.md true | builds in the main folder, merges |
| Builder (one per branch) | does one instruction, with failing tests first, then uploads the branch and opens a pull request | reviews its own work, merges |
| Challenger | tries to break the builder's work with failing tests or counter-examples | fixes |
| Independent evaluator (a different model or vendor where possible) | reviews the pull request from a clean checkout against the review prompt | edits the builder's branch |
| Claims officer | checks every public sentence against the evidence | approves content |
| Watch (scheduled) | reads STATUS and reports a few times a day, queues the next builder step when the last one is merged, and pings the owner | anything else |

Give each agent a **Declaration Card** (`templates/declaration-card.md`): what it is for, what it may and may never do, what it can reach, and who answers for it.

## Set-up (about 15 minutes)
1. Run `python3 scripts/init_company.py <repo>`. It creates:
   - `docs/ops/inbox`, `docs/ops/done` and `docs/ops/outbox`;
   - `docs/ops/ROLES.md`;
   - the coordinator's rules in `docs/ops/inbox/README.md`;
   - the templates.
2. In the rules file, write the non-negotiables: which data agents may see, words they must never claim, "failing tests first", "agents never merge", and which steps only the owner takes.
3. Start one coordinator session with: "You are the coordinator. Follow docs/ops/inbox/README.md. Do every instruction in docs/ops/inbox/ in number order."
4. Schedule the watch, two or three times a day.
5. Protect the main branches:
   - with the platform's branch rules where your plan enforces them;
   - otherwise a local pre-push hook, agent deny rules for pushes to protected branches, and a CI job that flags any change that didn't come through a merged pull request.

## The loop
1. **Owner states a goal** in one sentence.
2. **The chief of staff writes an instruction** from `templates/instruction.md`. It holds the owner's words, the **intent** (why the work matters and what "good" looks like, so an agent can adapt sensibly when the plan meets reality), the branch, the steps (failing tests first), the tests to run, the stop point and the order notes. Then it runs `python3 scripts/check_inbox.py <repo>`.
3. **The coordinator dispatches** it to one builder in its own worktree.
4. **The builder** commits the failing tests, then the fix. It runs the named tests, uploads the branch, opens a pull request, writes a brief for the evaluator, and stops.
5. **The challenger** and then **the evaluator** review. Findings go back to the builder as a new round.
6. **The owner merges.** That is the only path into a protected branch.
7. **The coordinator** moves the instruction to `done/` and updates STATUS.md, with commits, test counts and links.
8. **The watch** tells the owner what needs them, and queues the next step if it is builder work.

## Mission discipline (dropping agents into unknown code)
Agents land in places nobody fully mapped. What keeps them effective is what keeps a dropped unit effective:
- the owner's intent, so they can adapt;
- a rally point, STATUS.md, that everyone reports to;
- clear boundaries, so no two agents are on the same branch;
- one channel, the outbox;
- an extraction point, the stop point.

When a plan breaks, an agent acts on the intent within the rules. When the rules and the intent conflict, it stops and reports.

## End to end: design → plan → deploy → orchestrate (with the Harness Marketplace and OpenProof)
Three layers, one loop:
- **Agent Company** runs the team.
- **The Harness Marketplace kit** gives each agent its discipline.
- **OpenProof** proves an agent is ready before it goes live.

1. **Design: the Command map.**
   - Drag roles onto the field and pick the tool each one runs on, choosing a different vendor for the evaluator.
   - Give each role a Declaration Card: may, may never, reach, owner.
   - The readiness ring blocks a team design that breaks the rules.
2. **Plan: the missions.**
   - Each mission is one branch, the owner's words, the intent, tests first, and "don't merge".
   - Inside each agent's repository, `harness-init` sets up the kit's work list, where each item has a `done_when` that can be checked. Acceptance criteria are approved by a named person and locked.
3. **Deploy: Deploy, then start.** Deploy writes `docs/ops/`, and `start` launches exactly one coordinator. Each builder works in its own worktree, inside the kit's guardrails:
   - deny rules for secrets and destructive commands;
   - the sandbox or a container for unattended runs.
4. **Orchestrate: the loop above.** The builder records evidence in the kit's hash-chained ledger, and CI re-runs it on a clean machine. Then:
   1. the challenger and the kit's red team try to break the work, through its real tools, with decoys;
   2. the independent evaluator reviews the pull request;
   3. the owner merges.
5. **Prove: before any agent goes live.**
   1. `harness-audit` scores the repository out of 100 across 7 areas.
   2. Bring the package to OpenProof. It reads the package as untrusted and never runs it, then:
      - runs six checks with file:line evidence;
      - computes reach (MCP and shell grants are flagged);
      - checks the Declaration Card against what it computed;
      - requires approval by two people, neither of them the submitter.
6. **Improve: every week.** Read the metrics. Every defect becomes a test, every review finding a rubric line, and every recurring task a template.

## Rules that stop the common failures
- **Before reporting "merged", "uploaded" or "done", check the source of truth** (the remote, the pull request page, the test output) and quote it.
- **A blocked agent writes the block into STATUS.md and stops.** It never routes around a guard, rewords a command to get past a hook, or loosens a test.
- **Never evade a provider's safety filter.** If a reviewer is blocked, use another independent reviewer, label it honestly, and re-run the original reviewer later.
- **Never send real or sensitive data to a hosted model** unless the owner's rules allow it for that data class.
- **Cost:** targeted tests on each task, the full suite only before merge, stop idle sessions, and keep one coordinator.

## Weekly metrics (the owner reads them in two minutes)
- review rounds per change;
- defects that come back;
- reports that turned out wrong;
- the oldest blocked item;
- cost per accepted change.

When a number gets worse, fix the template or the rubric, not the agent.

## Files
- `templates/instruction.md`: one numbered instruction.
- `templates/status.md`: the coordinator's STATUS.md.
- `templates/report.md`: the builder's report.
- `templates/declaration-card.md`: one per agent role.
- `agent_company.py`: one command line, standard library only:
  - `init` creates the structure;
  - `ui` opens the Command map on 127.0.0.1, with a one-time token; Deploy writes into the repo and never overwrites an instruction;
  - `check` lints the inbox;
  - `status` shows what is pending, done and needs the owner;
  - `start --tool claude|codex|gemini|cursor|copilot [--run]` starts exactly one coordinator.
- `ui/command.html`: the Command map. It also works opened as a plain file, where it copies files instead of writing them.
- `scripts/init_company.py`: creates the structure (standard library only).
- `scripts/check_inbox.py`: refuses an instruction that lacks a branch, tests, a stop point or the owner's words.
