#!/usr/bin/env bash
# التصدير: أندرويد OGG · iOS CAF (أقلُّ من ٣٠ ث) · MP3 للاستماع (نغمةُ الكبتن دورتان) — بحدٍّ حقيقيٍّ −1 dBTP
set -e
S=/mnt/c/Users/loly3/AppData/Local/Temp/claude/2cccde71cb918853/50b89105-7055-4198-9cdb-c683fe51b538/scratchpad/s2
cd "$S"
mkdir -p android ios mp3
LIM="alimiter=limit=0.89:attack=2:release=40:level=disabled"
for f in out/*.wav; do
  b=$(basename "$f" .wav)
  ffmpeg -v error -y -i "$f" -af "$LIM" -c:a libvorbis -q:a 6 "android/$b.ogg"
  ffmpeg -v error -y -i "$f" -af "$LIM" -c:a pcm_s16le -ar 44100 -f caf "ios/$b.caf"
  case "$b" in
    *driver*) ffmpeg -v error -y -stream_loop 1 -i "$f" -af "$LIM" -c:a libmp3lame -b:a 192k "mp3/$b.mp3" ;;
    *) ffmpeg -v error -y -i "$f" -af "$LIM" -c:a libmp3lame -b:a 192k "mp3/$b.mp3" ;;
  esac
done
for f in mp3/*.mp3; do
  printf "%-42s %6ss  peak %s\n" "$(basename $f)" "$(ffprobe -v error -show_entries format=duration -of csv=p=0 $f | cut -c1-5)" \
    "$(ffmpeg -v info -i $f -af volumedetect -f null - 2>&1 | grep -o 'max_volume: [-0-9.]* dB')"
done
