#!/usr/bin/env bash
# Re-record the 60-second product video from the running app and rebuild the slide-2 poster.
# Needs: the app on http://localhost:8000 (or pass a URL), Playwright (frontend/node_modules), ffmpeg (brew install ffmpeg).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
URL="${1:-http://localhost:8000}"
VID="$ROOT/round2_submission/slides/video"
cd "$ROOT/frontend"
NODE_PATH="$PWD/node_modules" node "$ROOT/round2_submission/slides/figures/src/record_video.cjs" "$URL"
# Drop the ~1.8 s of blank page load, encode H.264 MP4 (plays in QuickTime, PowerPoint, browsers).
ffmpeg -y -v error -ss 1.8 -i "$VID/raw.webm" -c:v libx264 -preset slow -crf 22 -pix_fmt yuv420p -movflags +faststart -r 30 "$VID/plumeproof_60s.mp4"
# Poster for slide 2: the "closure rejected" moment.
ffmpeg -y -v error -ss 37 -i "$VID/plumeproof_60s.mp4" -frames:v 1 "$ROOT/round2_submission/slides/figures/video_poster.png"
rm -f "$VID/raw.webm"
echo "done: $VID/plumeproof_60s.mp4 ($(ffprobe -v error -show_entries format=duration -of csv=p=0 "$VID/plumeproof_60s.mp4") s)"
