#!/usr/bin/env python3
"""Subtitle cues from the same timeline the page uses (events.json + voices/dur.json) -> out/cues.json"""
import json
from pathlib import Path
H = Path(__file__).resolve().parent
ev = [e for e in json.loads((H / "events.json").read_text())["ev"] if e["type"] == "vo"]
dur = json.loads((H / "voices" / "dur.json").read_text())
title = next(e["t"] for e in json.loads((H / "events.json").read_text())["ev"] if e["type"] == "title")
cues = []
for i, e in enumerate(ev):
    end = e["t"] + max(1.8, dur[e["id"]] + .6, len(e["text"]) / 15 + 1.5)
    if i + 1 < len(ev):
        end = min(end, ev[i + 1]["t"] - .05)
    cues.append({"t0": round(e["t"] - .05, 3), "t1": round(min(end, title - .2), 3), "text": e["text"]})
(H / "out").mkdir(exist_ok=True)
(H / "out" / "cues.json").write_text(json.dumps(cues, indent=1))
for c in cues:
    print(f"{c['t0']:6.2f} -> {c['t1']:6.2f}  ({c['t1'] - c['t0']:.1f}s)  {c['text']}")
