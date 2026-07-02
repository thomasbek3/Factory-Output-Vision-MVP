#!/bin/bash
# Source of truth for the live rig; credentials live only in ~/.factory_camera.env
# (mode 0600), never in git.
# generic drive-proof recorder. args: CAM_IP STATION_TAG START_EPOCH END_EPOCH
. "${FACTORY_CAMERA_ENV:-$HOME/.factory_camera.env}"

CAM_IP="$1"; TAG="$2"; START="$3"; END="$4"
LOG="/Users/thomas/rec_${TAG}.log"
SSD_BASE="/Volumes/Crucial X9 Pro For Mac/Archive/FactoryVisionArtifacts/onboarding"
LOCAL_BASE="/Users/thomas/factory_local_recordings/onboarding"
SRC="rtsp://${FACTORY_RTSP_USER}:${FACTORY_RTSP_PASS}@${CAM_IP}:554/h264Preview_01_main"
FFMPEG=/opt/homebrew/bin/ffmpeg
echo "$(date): ${TAG} (${CAM_IP}) armed start=$(date -r $START) end=$(date -r $END)" >> "$LOG"
while [ "$(date +%s)" -lt "$START" ]; do sleep 20; done
while [ "$(date +%s)" -lt "$END" ]; do
  REMAIN=$(( END - $(date +%s) )); [ "$REMAIN" -lt 20 ] && break
  if [ -d "$SSD_BASE" ]; then OUT="$SSD_BASE/${TAG}/recordings/${TAG}/segments"; else OUT="$LOCAL_BASE/${TAG}/recordings/${TAG}/segments"; fi
  mkdir -p "$OUT" 2>/dev/null || { OUT="$LOCAL_BASE/${TAG}/recordings/${TAG}/segments"; mkdir -p "$OUT"; }
  "$FFMPEG" -nostdin -rtsp_transport tcp -timeout 5000000 -i "$SRC" -map 0:v -c copy -f segment -segment_format matroska -segment_time 60 -reset_timestamps 1 -strftime 1 -t "$REMAIN" "$OUT/%Y%m%dT%H%M%S_${TAG}.mkv" >> "$LOG" 2>&1
  sleep 5
done
echo "$(date): ${TAG} done" >> "$LOG"
