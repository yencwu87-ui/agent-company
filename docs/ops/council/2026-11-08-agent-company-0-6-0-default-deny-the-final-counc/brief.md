# Council brief: Agent Company 0.6.0: default deny, the final council

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

## Work under review (the repo is /home/claude/agent-company)

The owner (Yen-Ching) put the choice "seal 0.5.5 now, or build 0.6.0 first" to a Roast Room council. Its verdict was GO on building 0.6.0, then one final council, then seal by 13 Nov. The verdict is in ~/dev/roast-room/sessions/2026-11-08-agent-company-seal-or-060/verdict.md on her Mac. Its conditions:
1. No general shell or interpreter on the list.
2. The 88 tests and the 402 recorded cases pass, and less than 20% of normal work is refused.
3. **One final council only.** A gap in the program list gets patched and sealed the same day. Only a way past BOTH the separate agent Git account AND branch protection on the Git host reopens the decision.
4. The README never calls the guard a security boundary.

**What 0.6.0 changes (harness/guard.py):**
- **Default deny.** The command that actually runs, after the allowed wrappers are stripped, must be one of these:
  - a program in PROGRAMS, or an owner addition in allowlist.json "programs";
  - a named test command (DEFAULT_TEST_COMMANDS or "test_commands");
  - `python3 <path>/agent_company.py` with a non-setup subcommand.

  Programs must be named, not given by path. No shell or interpreter is listed, and a shell the owner adds is still refused.
- **Wrappers.** Only env (without -C or -S), time, nice, timeout, nohup, stdbuf and ionice are allowed. sudo, xargs, exec, command and script are refused.
- **Commands are split at ; && || | outside quotes,** so a `;` inside a message is not read as a new command.
- **Specific refusals:**
  - git pathspec magic (`:/`, `:(top)`);
  - git grep `--untracked` and `--no-exclude-standard`;
  - cp that makes or follows links;
  - grep `-d recurse`.
- **Secret-folder checks** now follow symlinks.
- **README.** Says plainly that the guard is not a security boundary, and names the controls that hold: real data kept outside the agents' folder, a separate agent Git account, branch protection, and keys kept out of agent sessions. It also states the default-deny rule and how the owner adds programs.
- **Tests.** New class Round8Routes, with every route from the last council and the condition checks.
- **Results.**
  - `python3 -m pytest -q tests`: 92 passed, 555 subtests.
  - Browser checks: 45 passed. `claims` exits 0.
  - Of 42 typical builder commands, 6 are refused (14%): npm install, pip install, a script, make, sed -i.

**How to judge "clean" for this final council.** A fix is BLOCKING only if one of these holds:
1. Something the README, SKILL.md or this brief states is false.
2. A route lets an agent do one of the following, and it is NOT simply a missing or over-wide entry in the program list:
   - (a) read or send real data or secrets;
   - (b) switch off or change the harness;
   - (c) merge or push to a protected branch;
   - (d) record approval or a decision in the owner's name.

A route through a listed program that the list can close is a "list gap". Per the Roast Room verdict, list gaps get patched the same day and do not reopen the decision. Mark them "list gap" rather than BLOCKING. Routes the README names as known limits are not blocking.

**Options:**
- A = seal 0.6.0 (after patching any list gaps the same day).
- B = fix named BLOCKING issues first.
- C = send it back.

Do not modify any file in /home/claude/agent-company. Do scratch work only in /tmp/claude-0/-home-claude/e58dcb52-2fc6-5698-a644-cd864e0aa16b/scratchpad/final-<seat>/. Keep it to at most 30 probes, because the council has a token budget.
