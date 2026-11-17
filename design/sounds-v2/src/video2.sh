#!/usr/bin/env bash
# فيديو لكلِّ خيار: لقطةُ الشاشة الحقيقيّة المطابقة لكلِّ صوت + الصوت + موجةٌ حيّة (ليس تسجيلاً من هاتف)
set -e
S=/mnt/c/Users/loly3/AppData/Local/Temp/claude/2cccde71cb918853/50b89105-7055-4198-9cdb-c683fe51b538/scratchpad/s2
OFFER=/mnt/d/prj/TAXO/video-studio/projects/2026-11-01-aqrab/assets/screens/offer.png
ARRIVED=/mnt/d/prj/TAXO/video-studio/projects/2026-10-31-khatt-wahid/assets/screens/arrived.png
FONT=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf
cd "$S"
mkdir -p video seg
seg() { # $1 image  $2 audio  $3 label  $4 out  $5 seconds
  ffmpeg -v error -y -loop 1 -i "$1" -i "$2" -filter_complex "
    [0:v]scale=540:-2,pad=540:1240:0:0:color=0x0b0d10[bg];
    [1:a]aresample=48000,aformat=channel_layouts=stereo,apad=whole_dur=$5,asplit[a1][a2];
    [a1]showwaves=s=500x90:mode=cline:colors=0xff6a2b:rate=30[w];
    [bg][w]overlay=20:1140[v1];
    [v1]drawtext=fontfile=$FONT:text='$3':fontcolor=white:fontsize=28:x=20:y=1100:box=1:boxcolor=0x000000AA:boxborderw=8[v]" \
    -map "[v]" -map "[a2]" -c:v libx264 -preset veryfast -crf 28 -pix_fmt yuv420p -r 30 -c:a aac -b:a 160k -ar 48000 -t "$5" "$4"
}
for n in 1 2 3 4 5; do
  rm -f seg/list.txt
  seg "$OFFER"   "mp3/option${n}_driver_ride_request.mp3"   "OPTION ${n} - DRIVER RIDE REQUEST (loop x2)" seg/a.mp4 "$(ffprobe -v error -show_entries format=duration -of csv=p=0 mp3/option${n}_driver_ride_request.mp3)"
  seg "$ARRIVED" "mp3/option${n}_rider_captain_arrived.mp3" "OPTION ${n} - RIDER CAPTAIN ARRIVED" seg/b.mp4 3
  seg "$OFFER"   "mp3/option${n}_soft_accepted.mp3"        "OPTION ${n} - SOFT: ACCEPTED" seg/c.mp4 2
  seg "$ARRIVED" "mp3/option${n}_soft_started.mp3"         "OPTION ${n} - SOFT: STARTED" seg/d.mp4 2
  seg "$ARRIVED" "mp3/option${n}_soft_ended.mp3"           "OPTION ${n} - SOFT: ENDED" seg/e.mp4 2
  seg "$ARRIVED" "mp3/option${n}_soft_payment.mp3"         "OPTION ${n} - SOFT: PAYMENT OK" seg/f.mp4 2
  for k in a b c d e f; do echo "file '$S/seg/$k.mp4'" >> seg/list.txt; done
  ffmpeg -v error -y -f concat -safe 0 -i seg/list.txt -c copy "video/TAXO-sounds-option${n}.mp4"
done
ls -la video
