#!/usr/bin/env bash
# يفكّ «TAXO» إلى wav 48k أحاديّ ويقصّ الصمتَ من الطرفين
set -e
cd /mnt/c/Users/loly3/AppData/Local/Temp/claude/2cccde71cb918853/50b89105-7055-4198-9cdb-c683fe51b538/scratchpad/s2
mkdir -p raw
for f in voice/taxo_*.mp3; do
  b=$(basename "$f" .mp3)
  ffmpeg -v error -y -i "$f" -ac 1 -ar 48000 \
    -af "silenceremove=start_periods=1:start_threshold=-42dB,areverse,silenceremove=start_periods=1:start_threshold=-42dB,areverse" \
    "raw/$b.wav"
done
ls raw
