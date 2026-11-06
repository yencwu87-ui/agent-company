#!/bin/sh
# One command: events → frames → mix → master.  Needs the Lemo-Opuscar library and kokoro-onnx.
set -e
LIB=/root/lemo-opuscar
HERE=$(cd "$(dirname "$0")" && pwd)
export LIB
cd "$HERE"

python3 tts.py                             # Kokoro voice-over → vo/*.wav, vo/dur.json
cd "$LIB"
node core/render/events.mjs "$HERE"
node core/render/video.mjs "$HERE" --fps 30 --workers 4 --out "$HERE/out/video.mp4"
"$LIB/.venv/bin/python" "$HERE/mix.py"
"$LIB/.venv/bin/python" core/render/srt.py "$HERE/cues.json" "$HERE/agent-company-feature-film.srt"
# ffmpeg 6.x: master with two-pass loudnorm directly (mux.sh expects ffmpeg 7+)
sh "$HERE/master.sh"
