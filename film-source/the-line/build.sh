#!/bin/sh
# Rebuild "The Line" from scratch: sh build.sh            (full quality: 1920x1080, 2x supersampling; needs a GPU to be quick)
#                                  SIZE=1280x720 SSAA=1 sh build.sh   (what the delivered file was rendered with, on a machine with no GPU)
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
LIB=${LIB:-$HOME/lemo-opuscar}
export LIB
[ -f "$LIB/core/render/video.mjs" ] || { echo "set LIB to the Lemo-Opuscar library folder (run the skill's setup.sh)"; exit 1; }
SIZE=${SIZE:-1920x1080}; SSAA=${SSAA:-2}; PY="$LIB/.venv/bin/python"
cd "$LIB"
"$PY" core/tts/tts.py "$HERE/lines.json" "$HERE/voices"                 # 1. narration: Kokoro af_heart (American)
"$PY" core/tts/asr_check.py "$HERE/lines.json" "$HERE/voices" || echo "! speech check did not pass or could not run: listen to voices/*.wav"   # 2. speech-to-text check
node core/render/events.mjs "$HERE"                                     # 3. timeline -> events.json (every landing carries its note)
"$PY" "$HERE/mix.py"                                                    # 4. score + foley + beds + narration -> out/mix.wav
"$PY" "$HERE/subs.py" && "$PY" core/render/srt.py "$HERE/out/cues.json" "$HERE/subtitles_en.srt"   # 5. subtitles
node core/render/video.mjs "$HERE" --fps 24 --workers 3 --size "$SIZE" --q "ssaa=$SSAA" --out "$HERE/out/video.mp4"   # 6. picture
sh core/render/mux.sh "$HERE/out/video.mp4" "$HERE/out/mix.wav" "$HERE/the-line.mp4" 24 0                # 7. mux, -14 LUFS, no grain
