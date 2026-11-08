"""Review Council: Agent Company's self-evaluation board.

The mechanism comes from Roast Room (github.com/nateherkai/roast-room, MIT, AI Automation Society): a Chair who never
argues, seats that each own one question, three rounds (open, debate, ratify), weighted option scores, verdict bands,
a ruin cap and a one-way-door cap. The seats here are original roles mapped to the team's own jobs, not simulations of
real people. Standard library only.

A council session lives in docs/ops/council/<date>-<slug>/:
    brief.json      decision, options, seats at the table with weights (written by `council init`)
    brief.md        the same for people
    round-N.json    the seats' cards for round N (a list; one card per seat, written by the Chair from the seats' replies)
    verdict.json    computed by `council score` (never typed by hand)
    verdict.md      the report
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

# Each seat owns one question. "guards" marks the downside seat whose RUIN RISK caps the verdict.
SEATS = [
    {"key": "goal", "name": "Owner's goal", "class": "herald", "coworker": "Coordinator / designer",
     "question": "Is this what the owner asked for, in her words, and how reversible is it?",
     "dimension": "Fit to the owner's goal and reversibility"},
    {"key": "buyer", "name": "Buyer", "class": "ranger", "coworker": "Market Watch / CRO drill",
     "question": "Would a second-line or internal-audit head accept this, use it and pay for it?",
     "dimension": "Value to the buyer"},
    {"key": "examiner", "name": "Examiner", "class": "scribe", "coworker": "Controls and knowledge (KU)",
     "question": "What does it map to, and could an auditor or regulator re-check every piece of evidence?",
     "dimension": "Traceability and re-checkable evidence"},
    {"key": "breaker", "name": "Breaker", "class": "rogue", "coworker": "Reviewer / breaker desk",
     "question": "Which input, scenario or attack makes it fail, and is that tested?",
     "dimension": "Robustness under attack"},
    {"key": "operator", "name": "Operator", "class": "artificer", "coworker": "Release rehearsal / deploy",
     "question": "Can a person with no technical knowledge install, run and recover it?",
     "dimension": "Zero-knowledge deployability"},
    {"key": "claims", "name": "Claims officer", "class": "scribe", "coworker": "Claims officer",
     "question": "Does every statement match the proof, with no claim words?",
     "dimension": "Claims match proof"},
    {"key": "guardian", "name": "Guardian", "class": "paladin", "coworker": "Harness / owner's standing rules", "guards": True,
     "question": "Could it leak real data, expose a key, get past a merge rule, or record a decision in the owner's name?",
     "dimension": "Downside and standing rules"},
    {"key": "purse", "name": "Purse", "class": "herald", "coworker": "Owner (cost)",
     "question": "What does it cost in tokens, money and the owner's time, and is that worth it?",
     "dimension": "Cost discipline"},
]
DEFAULT_BOARD = ["goal", "buyer", "examiner", "breaker", "operator", "claims", "guardian"]
QUICK_BOARD = ["goal", "breaker", "claims", "guardian"]
SELF_EVAL_OPTIONS = {"A": "Ship as it is (open the pull request for the owner)",
                     "B": "Fix the named issues first, then ship",
                     "C": "Send it back to the builder"}
BANDS = [(7.5, "GO"), (6.0, "GO WITH CONDITIONS"), (4.5, "RESHAPE"), (-1, "DON'T DO IT")]
RUIN = ("none", "possible", "likely")


def seat(key: str) -> dict:
    s = next((s for s in SEATS if s["key"] == key), None)
    if not s:
        raise ValueError(f"unknown seat '{key}'. Seats: {', '.join(x['key'] for x in SEATS)}")
    return s


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:48] or "decision"


def init(ops: Path, decision: str, options: dict | None, board: list | None, weights: dict | None, mode: str = "decision") -> Path:
    """Write brief.json and brief.md for a new session; return the folder."""
    options = options or (SELF_EVAL_OPTIONS if mode == "self-eval" else None)
    if not options or len(options) < 2:
        raise ValueError("give at least two options (A=..., B=...); include 'don't do it' or 'keep doing what we do now'")
    board = board or DEFAULT_BOARD
    if not 2 <= len(board) <= 9:
        raise ValueError("seat between 2 and 9 seats")
    if not any(seat(k).get("guards") for k in board):
        board = board + ["guardian"]                     # every council keeps the seat that guards the downside
    weights = {k: int((weights or {}).get(k, 1)) for k in board}
    if any(w not in (1, 2, 3) for w in weights.values()):
        raise ValueError("weights are 1, 2 or 3")
    folder = ops / "council" / f"{time.strftime('%Y-%m-%d')}-{slug(decision)}"
    folder.mkdir(parents=True, exist_ok=True)
    brief = {"decision": decision, "mode": mode, "options": options, "board": board, "weights": weights,
             "created": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    (folder / "brief.json").write_text(json.dumps(brief, indent=1, ensure_ascii=False), encoding="utf-8")
    lines = [f"# Council brief: {decision}", "", f"Mode: {mode}", "", "## Options", ""]
    lines += [f"- **{k}**: {v}" for k, v in options.items()]
    lines += ["", "## Seats and weights", "", "| Seat | Owns the question | Weight |", "|---|---|---|"]
    lines += [f"| {seat(k)['name']} | {seat(k)['question']} | {weights[k]} |" for k in board]
    lines += ["", "Weights: 3 = the decision lives in this seat's question, 2 = materially affected, 1 = touched at the edges.",
              "The Chair runs the rounds and never argues a side. Constructed data only in every card."]
    (folder / "brief.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return folder


def check_card(card: dict, options: dict) -> list:
    errs = []
    if card.get("seat") not in [s["key"] for s in SEATS]:
        errs.append(f"unknown seat {card.get('seat')!r}")
    sc = card.get("scores") or {}
    for o in options:
        v = sc.get(o)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= 10:
            errs.append(f"{card.get('seat')}: score for {o} must be 0-10")
    if card.get("ruin", "none") not in RUIN:
        errs.append(f"{card.get('seat')}: ruin must be one of {', '.join(RUIN)}")
    if not isinstance(card.get("confidence", 3), int) or not 1 <= card.get("confidence", 3) <= 5:
        errs.append(f"{card.get('seat')}: confidence must be 1-5")
    return errs


def claim_words(folder: Path, include_verdict: bool = False) -> list:
    """Claim words in the brief, the cards and the resolution (the verdict is written after this check)."""
    import agent_company as ac
    files = [p for p in sorted(folder.glob("*")) if p.suffix in (".md", ".json") and (include_verdict and p.name != "verdict.json" or not p.name.startswith("verdict"))]
    out = []
    for f in files:
        for n, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if "claims-ok" in line:
                continue
            out += [f"{f.name}:{n} '{m.group(0)}'" for m in ac.CLAIM_RE.finditer(line)]
    return out


def rounds(folder: Path) -> list:
    return sorted((int(m.group(1)), p) for p in folder.glob("round-*.json") if (m := re.match(r"round-(\d+)\.json$", p.name)))


def score(folder: Path) -> dict:
    """Compute the verdict from the last round's cards (scoring as in Roast Room's scoring.md). Writes verdict.json and .md."""
    brief = json.loads((folder / "brief.json").read_text(encoding="utf-8"))
    rs = rounds(folder)
    if not rs:
        raise ValueError("no round-N.json cards yet")
    n, path = rs[-1]
    cards = json.loads(path.read_text(encoding="utf-8"))
    cards = [c for c in cards if c.get("seat") in brief["weights"]]
    abstained = [c for c in cards if c.get("abstain")]
    if len(abstained) >= len(cards) / 2:
        raise ValueError("half or more of the seats abstained; run them again")
    seated = {c["seat"] for c in cards}
    cards = [c for c in cards if not c.get("abstain")]
    errs = [e for c in cards for e in check_card(c, brief["options"])]
    dup = sorted({c["seat"] for c in cards if [x["seat"] for x in cards].count(c["seat"]) > 1})
    if dup:
        errs.append(f"more than one card from: {', '.join(dup)} (one card per seat per round)")
    if n < 3:
        early = [c["seat"] for c in cards if c.get("mitigation_endorsed")]
        if early:
            errs.append(f"mitigation_endorsed is only for round 3 (round {n}: {', '.join(early)})")
    missing = [k for k in brief["board"] if k not in seated]
    if errs or missing:
        raise ValueError("; ".join(errs + ([f"no card from: {', '.join(missing)}"] if missing else [])))
    W = brief["weights"]
    tw = sum(W[c["seat"]] for c in cards)
    opt = {o: round(sum(W[c["seat"]] * c["scores"][o] for c in cards) / tw, 1) for o in brief["options"]}
    math = {o: f"{o} (" + " + ".join(f"{W[c['seat']]}x{c['scores'][o]:g}" for c in cards) + f") / {tw} = {opt[o]}" for o in opt}
    top = max(opt, key=lambda o: opt[o])
    label = next(b for t, b in BANDS if opt[top] >= t)
    vals = [c["scores"][top] for c in cards]
    spread = max(vals) - min(vals)
    conf = max(1, min(10, round(sum(c.get("confidence", 3) for c in cards) / len(cards) * 2) - (1 if spread >= 5 else 0)))
    overrides = []
    stop_words = ("don't", "dont", "keep doing", "send it back", "send back", "do nothing")
    if any(w in brief["options"][top].lower() for w in stop_words):
        label = "DON'T DO IT"
        overrides.append(f"the top option ({top}) is itself the 'don't do it' option")
    ruin = [c for c in cards if c.get("ruin") == "likely" and not c.get("mitigation_endorsed")]
    order = [b for _, b in BANDS]
    if ruin and label in ("GO", "GO WITH CONDITIONS"):
        label = "RESHAPE"
        overrides.append("ruin cap: " + ", ".join(seat(c["seat"])["name"] for c in ruin) +
                         " at RUIN RISK likely, with no mitigation that seat endorsed")
    one_way = sum(1 for c in cards if c.get("one_way")) * 2 > len(cards)
    if one_way and spread >= 4 and label == "GO":
        label = "GO WITH CONDITIONS"
        overrides.append(f"one-way door with spread {spread:g}: the cheapest test becomes a precondition")
    unanimous = False
    if rs[0][0] == 1:
        first = [c for c in json.loads(rs[0][1].read_text(encoding="utf-8")) if c.get("seat") in W and not c.get("abstain")]
        tops = {max(c["scores"], key=lambda o: c["scores"][o]) for c in first}
        if len(tops) == 1 and first:
            t1 = tops.pop()
            v1 = [c["scores"][t1] for c in first]
            unanimous = max(v1) - min(v1) <= 1
    weak = [{"seat": seat(c["seat"])["name"], "dimension": seat(c["seat"])["dimension"], "pillar": c.get("pillar")}
            for c in cards if isinstance(c.get("pillar"), (int, float)) and c["pillar"] <= 4]
    claims = claim_words(folder)
    v = {"claims_check": claims, "decision": brief["decision"], "mode": brief["mode"], "round": n, "recommended": top,
         "recommended_text": brief["options"][top], "label": label, "option_scores": opt, "math": math,
         "spread": spread, "confidence": conf, "overrides": overrides, "unanimity_warning": unanimous,
         "weak_pillars": weak, "abstained": [{"seat": c["seat"], "reason": c.get("stance", "")} for c in abstained], "seats": [{"seat": c["seat"], "name": seat(c["seat"])["name"], "weight": W[c["seat"]],
                                           "scores": c["scores"], "ruin": c.get("ruin", "none"), "stance": c.get("stance", ""),
                                           "fixes": c.get("fixes", [])} for c in cards],
         "scored": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    fixes = sorted({f for c in cards for f in c.get("fixes", [])})
    md = [f"# Council verdict: {brief['decision']}", "", f"**{label}** on option {top}: {brief['options'][top]}", "",
          "## Option scores", ""] + [f"- {math[o]}" for o in opt] + [
          "", f"Spread on {top}: {spread:g}. Council confidence: {conf}/10. Scored from round {n}.", ""]
    if overrides:
        md += ["## Overrides", ""] + [f"- {o}" for o in overrides] + [""]
    if unanimous:
        md += ["## Warning", "", "Round 1 was unanimous within 1 point. The strongest unargued alternative should have been a crux in round 2.", ""]
    if abstained:
        md += ["## Abstained", ""] + [f"- {seat(c['seat'])['name']}: {c.get('stance', 'no card')} (left out of the weights)" for c in abstained] + [""]
    md += ["## Seats", "", "| Seat | Weight | " + " | ".join(opt) + " | Ruin risk | Stance |", "|---|---|" + "---|" * len(opt) + "---|---|"]
    md += [f"| {s['name']} | {s['weight']} | " + " | ".join(f"{s['scores'][o]:g}" for o in opt) + f" | {s['ruin']} | {s['stance'][:140]} |" for s in v["seats"]]
    if weak:
        md += ["", "## Weak pillars (4 or below: each needs a named fix)", ""] + [f"- {w['seat']} ({w['dimension']}): {w['pillar']}" for w in weak]
    if fixes:
        md += ["", "## Fixes the seats asked for", ""] + [f"- {f}" for f in fixes]
    if claims:
        md += ["", "## Claims check", "", f"{len(claims)} claim word(s) in this council's files. Rewrite them before sealing:"] + [f"- {c}" for c in claims]
    md += ["", "The council is a self-evaluation. It does not replace the tests, the sealed evidence record, the owner's merge "
           "or the walkthrough with the customer. Seats are roles, not people."]
    (folder / "verdict.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    v["inputs"] = input_hashes(folder)
    (folder / "verdict.json").write_text(json.dumps(v, indent=1, ensure_ascii=False), encoding="utf-8")
    return v


def input_hashes(folder: Path) -> dict:
    """sha256 of every file the verdict rests on, verdict.md included (verdict.json holds the list itself)."""
    import hashlib
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.glob("*")) if p.is_file() and p.name != "verdict.json"}


def unchanged_since_scoring(folder: Path) -> list:
    """Files added, removed or edited after `council score`; empty means the verdict still matches its inputs."""
    v = json.loads((folder / "verdict.json").read_text(encoding="utf-8"))
    then, now = v.get("inputs") or {}, input_hashes(folder)
    return sorted(k for k in set(then) | set(now) if then.get(k) != now.get(k))


AGENT_TEMPLATE = """---
name: council-{key}
description: Review Council seat "{name}". Owns one question - {question} Use only when the Chair (the coordinator) runs a council round.
tools: Read, Grep, Glob
---

You are the **{name}** seat on the Review Council, Agent Company's self-evaluation board. You stand in for this job on the team: {coworker}.

**The one question you own:** {question}
**Your scorecard dimension:** {dimension}

How you work:
1. Read the brief the Chair points you to (`brief.md` in the council folder), and the earlier rounds when the Chair says so.
2. Judge every option through your question only. Other seats cover the other questions; don't do their job.
3. Be specific: name the file, the line, the test, the input or the number. A card with no evidence counts for little.
4. You are read-only. You never edit code, merge, push, sign, approve on the owner's behalf, or open real data. Constructed data only.
5. Never use the claim words the claims check lists (`agent_company.py claims`). Say what was tested, or "maps to".

Reply with this card and nothing else (the Chair copies it into round-N.json):

```json
{{"seat": "{key}",
 "scores": {{"A": 0, "B": 0, "C": 0}},
 "stance": "one or two sentences: your call and the single strongest reason",
 "evidence": ["file:line, test name, or fact that supports the stance"],
 "ruin": "none | possible | likely",
 "one_way": false,
 "confidence": 3,
 "pillar": 0,
 "fixes": ["each fix you need before you would back the top option"],
 "mitigation_endorsed": false}}
```
- `scores`: 0-10 for every option in the brief, using its letters.
- `ruin`: "likely" only if the top option could do damage that can't be undone, judged by your question{guard_note}.
- `one_way`: true if the top option is hard to undo.
- `pillar`: 0-10, the top option judged on your question alone.
- `mitigation_endorsed`: true only in round 3, if the draft resolution names a mitigation you accept for the ruin you raised.
"""


def agent_files(repo_root: Path, board: list | None = None) -> list:
    out = repo_root / ".claude" / "agents"
    out.mkdir(parents=True, exist_ok=True)
    made = []
    for k in board or [s["key"] for s in SEATS]:
        s = seat(k)
        note = ". As the Guardian, a likely ruin caps the verdict at RESHAPE" if s.get("guards") else ""
        (out / f"council-{k}.md").write_text(AGENT_TEMPLATE.format(guard_note=note, **{**{"coworker": ""}, **s}), encoding="utf-8")
        made.append(f".claude/agents/council-{k}.md")
    return made


PROTOCOL = """# Review Council protocol (the Chair's steps)

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
"""
