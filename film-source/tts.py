import json, soundfile as sf, numpy as np, sys
from kokoro_onnx import Kokoro
k = Kokoro("/home/claude/tts/kokoro-v1.0.onnx", "/home/claude/tts/voices-v1.0.bin")
out = {}
for l in json.load(open("lines.json")):
    a, sr = k.create(l["text"], voice="bf_emma", speed=0.97, lang="en-gb")
    nz = np.where(np.abs(a) > 0.01)[0]; a = a[max(0, nz[0]-240): nz[-1]+2400]
    sf.write(f"vo/{l['id']}.wav", a, sr); out[l["id"]] = round(len(a)/sr, 3)
json.dump(out, open("vo/dur.json", "w"), indent=1); print(out, round(sum(out.values()),1))
