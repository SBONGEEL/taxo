#!/usr/bin/env bash
# يفكّ أصوات «TAXO» إلى wav 48k أحاديّ ويقصّ الصمتَ من الطرفين
set -e
D=/mnt/c/Users/loly3/AppData/Local/Temp/claude/2cccde71cb918853/50b89105-7055-4198-9cdb-c683fe51b538/scratchpad/sounds
cd "$D"
for f in voice/*.mp3; do
  b=$(basename "$f" .mp3)
  ffmpeg -v error -y -i "$f" -ac 1 -ar 48000 \
    -af "silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse" \
    "raw/$b.wav"
  printf "%s %s\n" "$b" "$(ffprobe -v error -show_entries format=duration -of csv=p=0 "raw/$b.wav")"
done
