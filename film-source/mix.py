"""Score, foley and voice for the OpenProof cyber-risk film → out/mix.wav (48 kHz stereo).
Everything is synthesized from events.json (window.EV) and the VO timings; no samples."""
import json, sys, numpy as np, soundfile as sf
from pathlib import Path
from scipy.signal import resample_poly
sys.path.insert(0, "/root/lemo-opuscar/core/audio")
from sfx import SR, t_, env_exp, bp, lp, hp, noise, norm, brown, click, clack, crash, whoosh, creak, thump, ding, pop, compress, limit, add

HERE = Path(__file__).parent
E = json.load(open(HERE / "events.json")); DUR = E["dur"]; EV = E["ev"]
N = int((DUR + 0.5) * SR)
music = np.zeros((N, 2)); fx = np.zeros((N, 2)); vo = np.zeros((N, 2))
midi = lambda m: 440 * 2 ** ((m - 69) / 12)
BPM = 96; BEAT = 60 / BPM; BAR = 4 * BEAT
rng = np.random.default_rng(11)

def epiano(f, d, v=0.2):
    t = t_(d); mod = np.sin(2 * np.pi * f * 2 * t) * 1.6 * np.exp(-t * 3)
    return v * np.sin(2 * np.pi * f * t + mod) * np.exp(-t * 1.6) * np.minimum(1, t / 0.004)
def bass(f, d, v=0.35):
    t = t_(d); s = np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * 2 * f * t) + 0.15 * np.sin(2 * np.pi * 3 * f * t)
    return v * s * np.exp(-t * 2.2) * np.minimum(1, t / 0.008)
def glock(f, v=0.12):
    t = t_(1.2); return v * (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-t * 6)) * np.exp(-t * 3.2)
def chip(f, d=0.14, v=0.08):
    t = t_(d); return v * np.sign(np.sin(2 * np.pi * f * t)) * np.minimum(1, (d - t) / 0.02) * np.minimum(1, t / 0.003)
def kick(v=0.5):
    t = t_(0.35); f = 50 + 70 * np.exp(-t * 30); return v * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9)
def snare(v=0.25):
    t = t_(0.22); return v * (bp(noise(0.22), 1200, 7000) * np.exp(-t * 18) + 0.5 * np.sin(2 * np.pi * 190 * t) * np.exp(-t * 25))
def brush(v=0.06):
    d = 0.18; t = t_(d); return v * bp(noise(d), 2000, 9000) * np.sin(np.pi * t / d)
def hat(v=0.05):
    t = t_(0.05); return v * hp(noise(0.05), 7000) * np.exp(-t * 80)
def tom(f, v=0.35):
    t = t_(0.3); return v * np.sin(2 * np.pi * f * t * (1 - 0.15 * t)) * np.exp(-t * 10)
def pad(freqs, d, v=0.04):
    t = t_(d); s = sum(np.sin(2 * np.pi * f * t) + 0.25 * np.sin(2 * np.pi * f * 2.004 * t) for f in freqs)
    return v * s * np.minimum(1, t / 1.2) * np.minimum(1, (d - t) / 1.2)

CH = [[50, 54, 57, 62], [47, 50, 54, 59], [43, 47, 50, 55], [45, 49, 52, 57]]  # D, Bm, G, A
def section(t):
    for a, n in ((70.4, "end"), (61.8, "worlds"), (48.4, "trust"), (39.8, "prove"), (31.4, "work"), (21.0, "deploy"), (5.8, "forge")):
        if t >= a: return n
    return "intro"
bar = 0; t = 0.0
while t < DUR - 1.0:
    sec = section(t); ch = CH[bar % 4]
    add(music, pad([midi(m + 12) for m in ch[1:]], BAR + 1.2), t, 1.0)
    if sec != "intro":
        for b in (0, 2):
            for m in ch[1:]: add(music, epiano(midi(m + 12), 1.6, 0.07), t + b * BEAT, 1.0, -0.2)
    if sec in ("forge", "deploy", "prove", "worlds", "work", "trust"):
        for b in range(4): add(music, bass(midi(ch[0] - 12 + (7 if b == 2 else 0)), BEAT * 0.95, 0.3), t + b * BEAT, 1.0)
    if sec in ("deploy", "prove", "worlds"):
        for b in range(4):
            add(music, kick(0.36 if b in (0, 2) else 0.0), t + b * BEAT, 1.0)
            if b in (1, 3): add(music, snare(0.13), t + b * BEAT, 1.0, 0.1)
            for h in range(2): add(music, hat(0.03), t + b * BEAT + h * BEAT / 2, 1.0, 0.4)
    if sec in ("forge", "work", "trust"):
        for b in (1, 3): add(music, brush(), t + b * BEAT, 1.0, 0.3)
    if sec == "worlds":   # a little chiptune arpeggio over the world changes
        for i in range(8): add(music, chip(midi(ch[1 + i % 3] + 24), 0.1, 0.035), t + i * BEAT / 2, 1.0, 0.3)
    t += BAR; bar += 1
for s0 in (21.0, 39.8, 61.8):
    for i, f in enumerate((180, 150, 120, 95)): add(music, tom(f, 0.2), s0 - 0.5 + i * 0.12, 1.0, -0.3 + i * 0.2)
    add(music, crash(0.15), s0, 1.0, 0.2)
for m in CH[0]: add(music, epiano(midi(m + 12), 4.5, 0.12), 70.8, 1.0)
# hush before the cage drops
g = np.ones(N); a, b = int(54.8 * SR), int(55.5 * SR); g[a:b] = np.linspace(1, 0.1, b - a); g[b:int(56.6 * SR)] = np.linspace(0.1, 1, int(56.6 * SR) - b)
music *= g[:, None]
music[: int(0.6 * SR)] = 0

for e in EV:
    ty, at = e["type"], e["t"]
    if ty == "key": add(fx, click(1.3 + rng.random() * 0.3, 0.22), at + rng.random() * 0.015, 0.45, 0.25)
    elif ty == "click": add(fx, click(1.0, 0.5), at, 0.6, 0.2)
    elif ty == "enter": add(fx, clack(1.1, 0.6), at, 0.5, 0.25)
    elif ty == "chip": add(fx, chip(midi(e.get("note", 76)), 0.12) + np.pad(chip(midi(e.get("note", 76) + 7), 0.12), (int(0.12 * SR), 0))[: int(0.12 * SR)], at, 1.0, 0.2)
    elif ty == "whoosh": add(fx, whoosh(0.9, 0.8), at, 0.6)
    elif ty == "fit": add(fx, glock(midi(76 + [0, 2, 4, 7, 9, 12][e["i"]]), 0.1), at, 1.0, -0.3 + e["i"] * 0.12)
    elif ty == "join":
        for i, n in enumerate((72, 76, 79, 84)): add(fx, chip(midi(n), 0.1, 0.05), at + i * 0.08, 1.0, 0.1)
    elif ty == "place": add(fx, chip(midi(72), 0.07, 0.06) + np.pad(chip(midi(79), 0.08, 0.05), (int(0.06 * SR), 0))[: int(0.07 * SR)], at, 1.0, 0.2)
    elif ty == "buzz": add(fx, chip(midi(40), 0.22, 0.06) * 1.0, at, 1.0, -0.1)
    elif ty == "green":
        for i, n in enumerate((74, 78, 81, 86)): add(fx, glock(midi(n), 0.09), at + i * 0.07, 1.0, 0.2)
    elif ty == "horn":
        for i, n in enumerate((50, 55, 59, 62)): add(fx, bass(midi(n), 0.5, 0.18), at + i * 0.13, 1.0)
    elif ty == "press": add(fx, thump(0.7, 80), at, 0.6)
    elif ty == "probe": add(fx, clack(0.8, 0.5), at, 0.5, 0.3)
    elif ty == "stamp": add(fx, thump(1.0, 60), at, 0.8)
    elif ty == "coin": add(fx, chip(midi(88), 0.07, 0.05) + np.pad(chip(midi(93), 0.2, 0.05), (int(0.07 * SR), 0))[: int(0.07 * SR)], at, 1.0, 0.3)
    elif ty == "level":
        for i, n in enumerate((72, 76, 79, 84, 88)): add(fx, chip(midi(n), 0.16, 0.05), at + i * 0.09, 1.0, 0.1)
    elif ty == "cage": add(fx, thump(1.0, 55) , at, 0.9); add(fx, clack(1.0, 0.9), at + 0.02, 0.5, -0.2)
    elif ty == "world": add(fx, whoosh(0.5, 0.5), at - 0.1, 0.4, 0.3); add(fx, ding(0.18), at, 0.35, 0.3)
    elif ty == "chime": add(fx, ding(0.35) + np.pad(ding(0.25), (int(0.09 * SR), 0))[: len(ding(0.35))], at, 0.5, 0.3)
    elif ty == "jump": add(fx, chip(midi(72), 0.06, 0.04) + np.pad(chip(midi(79), 0.06, 0.04), (int(0.05 * SR), 0))[: int(0.06 * SR)], at, 1.0)
    elif ty == "land": add(fx, chip(midi(55), 0.05, 0.04), at, 1.0)
bed = lp(brown(DUR + 0.5), 400) * 0.012
fx[: len(bed), 0] += bed[: N]; fx[: len(bed), 1] += bed[: N]

# ---- voice: compress, place, duck the music
VO = json.load(open(HERE / "vo/dur.json"))
AT = {e["id"]: e["t"] for e in EV if e["type"] == "vo"}
duck = np.zeros(N)
for vid, at in AT.items():
    a, sr = sf.read(HERE / f"vo/{vid}.wav")
    a = resample_poly(a, SR, sr); a = compress(a / np.abs(a).max() * 0.7, thr=0.2, ratio=3.0)
    add(vo, a, at, 1.0)
    s = int((at - 0.2) * SR); duck[max(0, s): s + len(a) + int(0.5 * SR)] = 1
k = int(0.2 * SR); duck = np.convolve(duck, np.ones(k) / k, mode="same")
music *= (1 - 0.68 * duck)[:, None]
rms = lambda x: np.sqrt(np.mean(x[np.abs(x) > 1e-4] ** 2)) if np.any(np.abs(x) > 1e-4) else 1e-9
music *= (rms(vo) / 10 ** (10 / 20)) / rms(music)   # voice ≈ 10 dB above the music
mix = vo + music + fx * 0.9
mix = np.stack([limit(mix[:, 0]), limit(mix[:, 1])], 1)[: int(DUR * SR)]
sf.write(HERE / "out/mix.wav", mix.astype(np.float32), SR)
print("mix", round(len(mix) / SR, 2), "s · peak", round(float(np.abs(mix).max()), 3))
