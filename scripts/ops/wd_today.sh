#!/bin/bash
# Source of truth for the live rig; credentials live only in ~/.factory_camera.env
# (mode 0600), never in git.
. "${FACTORY_CAMERA_ENV:-$HOME/.factory_camera.env}"

E=1782509400
while [ "$(date +%s)" -lt "$E" ]; do
  sleep 120
  pgrep -f "rec_cam.sh ${CAM1_IP} factory-live-20260626" >/dev/null || nohup caffeinate -i bash /Users/thomas/rec_cam.sh "${CAM1_IP}" factory-live-20260626 "$(date +%s)" "$E" >/dev/null 2>&1 & disown
  pgrep -f "rec_cam.sh ${CAM2_IP} factory-live-cam2-20260626" >/dev/null || nohup caffeinate -i bash /Users/thomas/rec_cam.sh "${CAM2_IP}" factory-live-cam2-20260626 "$(date +%s)" "$E" >/dev/null 2>&1 & disown
done
