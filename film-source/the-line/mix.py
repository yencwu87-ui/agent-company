#!/usr/bin/env python3
"""The Line: score, foley, beds and narration, all synthesised from events.json. Writes out/mix.wav (48 kHz stereo).

The score is event-driven: every landing in the picture carries a note and is played at its exact time.
Palette (STYLE.md section 7): marimba, kalimba, woodblock, bell, a soft pad, shaker and a soft kick. No piano, no strings.
"""
import json
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt, resample_poly

HERE = Path(__file__).resolve().parent
SR = 48000
EV = json.loads((HERE / "events.json").read_text())
DUR = EV["dur"]; EVS = EV["ev"]
N = int((DUR + .6) * SR)
BEAT = 60 / 96
B = lambda bar, beat=1: ((bar - 1) * 4 + (beat - 1)) * BEAT
rng = np.random.default_rng(7)
hz = lambda m: 440 * 2 ** ((m - 69) / 12)
tt = lambda d: np.arange(int(d * SR)) / SR


def filt(x, kind, f, order=2):
    return sosfilt(butter(order, f, kind, fs=SR, output="sos"), x)


def add(bus, sig, at, gain=1.0, pan=0.0):
    i = int(at * SR)
    if i < 0 or i >= N:
        return
    sig = sig[: N - i]
    l, r = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
    bus[i:i + len(sig), 0] += sig * gain * l * 1.414
    bus[i:i + len(sig), 1] += sig * gain * r * 1.414


# ---------------------------------------------------------------- instruments
def marimba(m, d=1.1):
    t = tt(d); f = hz(m)
    return (np.sin(2 * np.pi * f * t) * np.exp(-t * 5) + .32 * np.sin(2 * np.pi * 4 * f * t) * np.exp(-t * 14)
            + .12 * np.sin(2 * np.pi * 10 * f * t) * np.exp(-t * 40)) * np.minimum(1, t / .003)


def kalimba(m, d=1.6):
    t = tt(d); f = hz(m)
    return (np.sin(2 * np.pi * f * t) * np.exp(-t * 3.2) + .22 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t * 6)
            + .1 * np.sin(2 * np.pi * 5.4 * f * t) * np.exp(-t * 22)) * np.minimum(1, t / .002)


def bell(m, d=3.0):
    t = tt(d); f = hz(m)
    parts = [(1, 1, 1.6), (2.76, .5, 2.4), (5.4, .28, 3.6), (8.93, .14, 5.5)]
    return sum(a * np.sin(2 * np.pi * f * p * t) * np.exp(-t * k) for p, a, k in parts) * np.minimum(1, t / .004) * .6


def woodblock(f=880):
    t = tt(.12)
    return (np.sin(2 * np.pi * f * t) + .5 * np.sin(2 * np.pi * f * 1.51 * t)) * np.exp(-t * 55)


def knock(low=180, d=.25):          # wooden landing
    t = tt(d)
    return (np.sin(2 * np.pi * low * t * (1 + .6 * np.exp(-t * 40))) * np.exp(-t * 22)
            + filt(rng.standard_normal(len(t)), "low", 1200) * np.exp(-t * 60) * .5)


def clack():                        # ceramic roof
    t = tt(.1)
    return filt(rng.standard_normal(len(t)), "band", [1800, 5200]) * np.exp(-t * 70)


def tink(f=3600):                   # glass
    t = tt(.5)
    return (np.sin(2 * np.pi * f * t) + .4 * np.sin(2 * np.pi * f * 1.48 * t)) * np.exp(-t * 16) * .5


def whump():                        # something switching on
    t = tt(.5)
    return np.sin(2 * np.pi * (95 - 40 * t) * t) * np.exp(-t * 9) + .12 * np.sin(2 * np.pi * 120 * t) * np.exp(-t * 4) * (t > .05)


def buzz():                         # the refusal: two short low pulses
    t = tt(.5)
    sq = np.sign(np.sin(2 * np.pi * 116 * t)) * .6 + np.sin(2 * np.pi * 174 * t) * .3
    gate = ((t < .16) | ((t > .22) & (t < .42))).astype(float)
    return filt(sq * gate, "low", 900) * np.minimum(1, t / .005)


def ratchet():
    out = np.zeros(int(.5 * SR)); c = filt(rng.standard_normal(int(.02 * SR)), "band", [1500, 4500]) * np.exp(-tt(.02) * 180)
    for k in range(6):
        i = int(k * .07 * SR); out[i:i + len(c)] += c * (1 - k * .08)
    return out


def whoosh_down(d=1.1):             # a crate gone over the edge: falling, no impact
    t = tt(d); n = rng.standard_normal(len(t)); out = np.zeros(len(t)); step = 512
    for i in range(0, len(t), step):
        fc = 2600 * np.exp(-t[i] * 2.4) + 180
        out[i:i + step] = filt(n[i:i + step + 256], "low", fc)[:len(out[i:i + step])]
    return (out * .7 + .35 * np.sin(2 * np.pi * (520 * np.exp(-t * 1.9)) * t)) * np.sin(np.pi * np.minimum(1, t / d)) ** .7


def thunk():                        # the seal: heavy stone
    t = tt(.9)
    return (np.sin(2 * np.pi * (70 - 18 * t) * t) * np.exp(-t * 6) * 1.2 + filt(rng.standard_normal(len(t)), "low", 500) * np.exp(-t * 28) * .9
            + .3 * np.sin(2 * np.pi * 140 * t) * np.exp(-t * 10))


def tick(f=2200):
    t = tt(.04)
    return filt(rng.standard_normal(len(t)), "band", [f * .6, f * 1.5]) * np.exp(-t * 140)


def kick():
    t = tt(.35)
    return np.sin(2 * np.pi * (48 + 60 * np.exp(-t * 30)) * t) * np.exp(-t * 11) * (1 + .3 * np.sin(2 * np.pi * 96 * t))


def shaker():
    t = tt(.07)
    return filt(rng.standard_normal(len(t)), "high", 5500) * np.exp(-t * 60)


def chirp():                        # a bird: downward-gliding FM
    d = .12 + rng.random() * .1; t = tt(d); f0 = 3200 + rng.random() * 1600
    return np.sin(2 * np.pi * (f0 * t - 2600 * t * t) + 2.5 * np.sin(2 * np.pi * 38 * t)) * np.sin(np.pi * t / d) ** 2


music = np.zeros((N, 2)); foley = np.zeros((N, 2)); bed = np.zeros((N, 2)); voice = np.zeros((N, 2))
panx = lambda i, n: (i / max(1, n - 1) - .5) * .9

# ---------------------------------------------------------------- the score, from the picture's events
for e in EVS:
    t, ty, note = e["t"], e["type"], e.get("note")
    if ty == "drop":
        size = e.get("size", 1)
        add(music, marimba(note - (12 if size == 3 else 0), 1.4), t, .5)
        add(foley, knock(110 if size == 3 else 190), t, .55 if size == 3 else .38)
        add(foley, knock(140 if size == 3 else 230, .18), t + .21, .2)
        if e.get("what") in ("house", "depot", "office"):
            add(foley, clack(), t + .02, .22)
    elif ty == "piece":
        add(music, kalimba(note), t, .5, panx(e["i"], 6)); add(music, marimba(note - 12, .9), t, .28)
        add(foley, tink(3200 + e["i"] * 260), t + .01, .16, panx(e["i"], 6))
    elif ty == "lamp":
        add(music, bell(note, 2.2), t, .2); add(foley, whump(), t, .32)
    elif ty == "buzz":
        add(foley, buzz(), t, .5)
    elif ty == "gate":
        add(foley, ratchet(), t, .4); add(music, bell(note, 3.0), t + .42, .34); add(music, marimba(note - 24, 1.6), t + .42, .4)
    elif ty == "order":
        add(music, kalimba(note, 1.2), t, .36, panx(e["i"], 4)); add(foley, tick(1500), t, .3)
    elif ty == "window":
        add(music, kalimba(note, 1.4), t, .3)
    elif ty == "pop":
        add(music, kalimba(note, 1.0), t, .22, rng.uniform(-.6, .6)); add(foley, tick(2600), t, .14)
    elif ty == "fall":
        add(foley, whoosh_down(), t - .1, .5)
    elif ty == "tap":
        add(foley, knock(260, .12), t, .25)
    elif ty == "replay":
        add(music, kalimba(note + 12, 1.8), t, .4, panx(e["i"], 6)); add(music, marimba(note, 1.2), t, .3); add(music, bell(note + 12, 2.0), t, .1)
    elif ty == "seal":
        add(foley, thunk(), t, .95); add(music, bell(note, 4.5), t + .02, .5); add(music, marimba(50, 2.2), t, .55); add(music, marimba(57, 2.0), t, .3)
    elif ty == "title":
        add(music, bell(86, 4.0), t, .22); add(music, kalimba(74, 2.5), t, .3)
        for k in range(19):
            add(foley, tick(1800 + (k % 5) * 240), t + k * .055 + .28, .12, panx(k, 19))

# ostinato (kalimba, eighth notes), thin then full; shaker and soft kick only while the line runs
PAT = [62, 69, 66, 69, 71, 69, 66, 64]
for bar in range(7, 23):
    if bar == 11:
        beats = range(0, 4)          # stops before the refusal's silence
    elif bar in (5, 6):
        continue
    else:
        beats = range(0, 8)
    full = 12 <= bar <= 20
    for k in beats:
        t = B(bar) + k * BEAT / 2
        if B(11, 3) <= t < B(12, 3):
            continue
        if not full and k % 2:
            continue
        add(music, kalimba(PAT[k] - 12, .9), t, .17 if full else .12, -.25 if k % 2 else .25)
for bar in range(17, 23):
    for k in range(8):
        add(music, shaker(), B(bar) + k * BEAT / 2, .05 if k % 2 else .08, .3)
    for beat in (1, 3):
        add(music, kick(), B(bar, beat), .3)
for t in (.9, 2.2, 3.1, 5.6, 6.6):   # section A: sparse woodblock, off the beat
    add(music, woodblock(820 + 60 * rng.random()), t + BEAT / 2, .12, rng.uniform(-.5, .5))

# pad and drone (kept above MIDI 48, with a little 2nd harmonic so it speaks on small speakers)
def pad(notes, t0, t1, g):
    d = t1 - t0; t = tt(d); env = np.minimum(1, t / 1.5) * np.minimum(1, (d - t) / 1.5)
    s = sum(np.sin(2 * np.pi * hz(m) * (1 + dv) * t + ph) + .25 * np.sin(2 * np.pi * 2 * hz(m) * t) for m in notes for dv, ph in ((0, 0), (.004, 1.3), (-.003, 2.1)))
    add(music, s * env / (3 * len(notes)), t0, g)
pad([50, 57], 0, B(5) + 1, .22)                 # dusk drone
pad([50, 57, 62], B(7), B(11, 3) + .5, .16)
pad([50, 57, 66], B(12), B(17) + 1, .18)
pad([50, 57, 62, 66, 69], B(17), B(23) + 2, .24)
pad([50, 62, 69], B(23), DUR + .4, .16)

# silences: the music bus goes to zero before the first arrival and under the refusal
menv = np.ones(N)
def hush(t0, t1, floor=0.0, fade=.06):
    a, b, f = int(t0 * SR), int(t1 * SR), int(fade * SR)
    menv[a:a + f] *= np.linspace(1, floor, f); menv[a + f:b - f] *= floor; menv[b - f:b] *= np.linspace(floor, 1, f)
hush(B(4, 3) + .35, B(5) - .01)
hush(B(11, 3), B(12) - .01)
music *= menv[:, None]

# ---------------------------------------------------------------- beds
def brown(n):
    x = np.cumsum(rng.standard_normal(n)); x = filt(x, "high", 30); return x / np.max(np.abs(x))
t_all = np.arange(N) / SR
wind = filt(brown(N), "low", 420) * (.55 + .45 * np.sin(2 * np.pi * .07 * t_all + 1)) * np.interp(t_all, [0, B(5), B(17), DUR], [1, .7, .5, .35])
bed[:, 0] += wind * .16; bed[:, 1] += np.roll(wind, 4000) * .16
for k in range(120):                 # crickets at night
    t = B(6) + rng.random() * (B(18) - B(6)); d = .5; x = tt(d)
    add(bed, np.sin(2 * np.pi * 4300 * x) * (np.sin(2 * np.pi * 34 * x) > 0) * np.sin(np.pi * x / d) ** 2, t, .012, rng.uniform(-.9, .9))
for k in range(46):                  # birds from first light
    t = B(18) + rng.random() ** .7 * (DUR - B(18) - .5)
    for j in range(rng.integers(1, 4)):
        add(bed, chirp(), t + j * .16, .035, rng.uniform(-.8, .8))
for t in np.arange(.3, B(5) - 1.4, .31):   # footsteps of the loose agents
    add(foley, tick(900), t + rng.uniform(-.04, .04), .05, rng.uniform(-.7, .7))
# belt hum once the line runs
run = next(e["t"] for e in EVS if e["type"] == "run")
d = DUR - run; t = tt(d); humenv = np.minimum(1, t / 1.5) * np.minimum(1, (d - t) / 2.5 + .0)
add(bed, (np.sin(2 * np.pi * 73 * t) * .5 + .3 * np.sin(2 * np.pi * 146 * t) + filt(rng.standard_normal(len(t)), "band", [300, 900]) * .25) * humenv, run, .05)
for tk in np.arange(run + .2, B(23), .25):
    add(foley, tick(1100), tk, .04, np.sin(tk) * .6)

# ---------------------------------------------------------------- narration
spans = []
for e in EVS:
    if e["type"] != "vo":
        continue
    x, sr = sf.read(HERE / "voices" / f"{e['id']}.wav")
    if x.ndim > 1:
        x = x.mean(1)
    if sr != SR:
        from math import gcd
        g = gcd(SR, sr); x = resample_poly(x, SR // g, sr // g)
    x = filt(x, "high", 90)
    x = x / (np.sqrt(np.mean(x ** 2)) + 1e-9) * .1
    x = np.tanh(x * 2.6) / 2.6 * 1.25          # gentle compression: TTS has a high peak-to-average ratio
    add(voice, x, e["t"], 1.0, 0)
    spans.append((e["t"], e["t"] + len(x) / SR))

duck = np.ones(N)
for a, b in spans:
    i0, i1 = int((a - .12) * SR), int((b + .3) * SR)
    duck[max(0, i0):i1] = 10 ** (-8 / 20)
k = int(.12 * SR); duck = np.convolve(duck, np.ones(k) / k, mode="same")

rms = lambda x: np.sqrt(np.mean(x[np.abs(x).max(1) > 1e-4] ** 2))
under = (music + bed * 1.0 + foley * .9)
vm, um = rms(voice), rms(music * duck[:, None])
music *= (vm / 10 ** (10 / 20)) / um              # voice about 10 dB above the music
mix = voice + music * duck[:, None] + foley * (.75 + .25 * duck[:, None]) + bed * duck[:, None] ** .5
mix = np.stack([filt(mix[:, c], "high", 35) for c in (0, 1)], 1)
mix = mix / np.max(np.abs(mix)) * .89
(HERE / "out").mkdir(exist_ok=True)
sf.write(HERE / "out" / "mix.wav", mix[: int(DUR * SR)], SR, subtype="PCM_16")

# checks: true silence on the music bus, and low-end balance
def band(x, lo, hi):
    return 20 * np.log10(np.sqrt(np.mean(filt(x.mean(1), "band", [lo, hi], 4) ** 2)) + 1e-12)
a, b = int((B(5) - .3) * SR), int((B(5) - .08) * SR)
print(f"mix.wav {DUR:.1f}s  peak {np.max(np.abs(mix)):.2f}")
print(f"music bus before the first arrival: {np.max(np.abs(music[a:b])):.6f} (0 = true silence)")
print(f"voice vs music RMS: {20 * np.log10(vm / rms(music * duck[:, None])):.1f} dB")
print(f"bands dB: 20-120 Hz {band(mix, 20, 120):.1f} | 120-1k {band(mix, 120, 1000):.1f} | 1k-8k {band(mix, 1000, 8000):.1f}")
