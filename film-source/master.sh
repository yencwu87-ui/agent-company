#!/bin/sh
set -e
HERE=$(cd "$(dirname "$0")" && pwd); cd "$HERE/out"
M=$(ffmpeg -hide_banner -i mix.wav -af loudnorm=I=-14:TP=-1.2:LRA=11:print_format=json -f null - 2>&1 | sed -n '/{/,/}/p')
g() { echo "$M" | grep "\"$1\"" | sed 's/.*: "\(.*\)".*/\1/'; }
ffmpeg -y -loglevel error -i video.mp4 -i mix.wav -map 0:v -map 1:a -c:v libx264 -preset slow -crf 21 -pix_fmt yuv420p -r 30 \
  -af "loudnorm=I=-14:TP=-1.2:LRA=11:measured_I=$(g input_i):measured_TP=$(g input_tp):measured_LRA=$(g input_lra):measured_thresh=$(g input_thresh):offset=$(g target_offset):linear=true,aresample=48000" \
  -c:a aac -b:a 192k -shortest -movflags +faststart ../agent-company-feature-film.mp4
ffmpeg -hide_banner -i ../agent-company-feature-film.mp4 -af ebur128 -f null - 2>&1 | grep -E "^\s+I:" | tail -1
