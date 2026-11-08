# Review Council protocol (the Chair's steps)

The Chair is the coordinator. It runs the room, keeps the score and writes the verdict. It never argues a side.

1. `agent_company.py council init "<decision>" --options "A=...,B=...,C=don't do it"` (or `--self-eval` for a finished
   piece of work: A ship, B fix then ship, C send back). Add `--seats` and `--weights goal=3,breaker=2` as needed.
   Exactly one or two seats get weight 3.
2. **Round 1, open.** Spawn every seat in one message (`subagent_type: council-<key>`), each pointed at `brief.md`.
   Save the cards, verbatim, as a JSON list in `round-1.json`. Name the cruxes: the 1-3 disagreements behind the split.
   If round 1 is unanimous within 1 point, make the strongest unargued alternative a crux and name who must argue it.
3. **Round 2, debate.** Spawn every seat again with `brief.md`, `round-1.json` and the cruxes. Save `round-2.json`.
4. **Draft resolution.** Write `draft-resolution.md`: the call, the conditions (checkable), the fixes, the cheapest test,
   the kill criteria. Weigh arguments, not headcount.
5. **Round 3, ratify** (skip in quick mode when the spread on the top option is 3 or less and no seat is at ruin
   "likely"). Each seat scores the resolution and sets `mitigation_endorsed`. Save `round-3.json`.
6. `agent_company.py council score <folder>` computes the verdict (the Chair never types numbers), then
   `agent_company.py council seal <folder>` seals it into the evidence ledger.

Cost: a quick council is 4 seats x 1-2 rounds (4-8 sub-agent calls; round 2 only when the seats split). A full council
is about 3 calls per seat (about 21). Purse is not on the quick board, so the verdict reports the call count instead; seat
Purse when the work itself spends money.

Where councils can sit in the team's loop (proposals: the owner switches each one on in docs/ops/inbox/README.md, and
can switch any of them off the same way):
- **Design gate (stage 1):** a decision council before a plan is written, for anything costly or hard to undo.
- **Self-eval gate (stage 4, after tests pass):** a quick council on the finished work before the pull request goes
  to the owner. GO opens the PR; GO WITH CONDITIONS or RESHAPE goes back with the seats' fixes; a Guardian at ruin
  "likely" sends it back.
- **Retro (stage 7):** once a week, a council on the week's sent-back and escaped defects decides what changes.

The council is a self-evaluation. It never replaces the tests, `seal`, the owner's merge or the walkthrough with the
customer, and it never earns XP.
