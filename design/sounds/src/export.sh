#!/usr/bin/env bash
# يصدّر الخيارات: OGG لأندرويد (res/raw)، CAF لـiOS (< ٣٠ ث)، وMP3 للاستماع (طلبُ الكبتن ثلاثَ دوراتٍ كما يرنّ)
set -e
D=/mnt/c/Users/loly3/AppData/Local/Temp/claude/2cccde71cb918853/50b89105-7055-4198-9cdb-c683fe51b538/scratchpad/sounds
cd "$D"
rm -rf out && mkdir -p out/android out/ios out/listen out/master
for n in 1 2 3; do
  cp "raw/opt${n}_driver_cycle.wav" "out/master/taxo_ride_request_${n}.wav"
  cp "raw/opt${n}_rider.wav" "out/master/taxo_captain_arrived_${n}.wav"
  cp "raw/opt${n}_update.wav" "out/master/taxo_ride_update_${n}.wav"
  for kind in ride_request captain_arrived ride_update; do
    src="out/master/taxo_${kind}_${n}.wav"
    ffmpeg -v error -y -i "$src" -c:a libvorbis -q:a 6 "out/android/taxo_${kind}_${n}.ogg"
    ffmpeg -v error -y -i "$src" -ar 44100 -c:a pcm_s16le -f caf "out/ios/taxo_${kind}_${n}.caf"
  done
  ffmpeg -v error -y -stream_loop 2 -i "out/master/taxo_ride_request_${n}.wav" -c:a libmp3lame -b:a 192k "out/listen/driver_${n}.mp3"
  ffmpeg -v error -y -i "out/master/taxo_captain_arrived_${n}.wav" -c:a libmp3lame -b:a 192k "out/listen/rider_${n}.mp3"
  ffmpeg -v error -y -i "out/master/taxo_ride_update_${n}.wav" -c:a libmp3lame -b:a 192k "out/listen/update_${n}.mp3"
done
for f in out/listen/*.mp3 out/ios/*.caf; do
  printf "%-40s %6.2fs  peak %s\n" "$(basename "$f")" "$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$f")" \
    "$(ffmpeg -v info -i "$f" -af volumedetect -f null - 2>&1 | grep -o 'max_volume: [-0-9.]* dB' | cut -d' ' -f2-)"
done
du -sh out/*
