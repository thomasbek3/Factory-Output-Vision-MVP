#!/usr/bin/env bash
# FactoryVision console — live RTSP → HLS relay.
#
# Pulls each factory camera over RTSP (TCP) and remuxes (no re-encode, -c copy)
# into an HLS playlist under console/live-media/<station-slug>/stream.m3u8, which
# the Next.js route app/api/live/[station]/[...file] serves to the browser.
#
# The factory LAN is reached over a Tailscale subnet route that intermittently
# drops (documented mid-afternoon path failures). Camera drops are NORMAL: each
# camera runs in its own retry loop that restarts ffmpeg with a 5s backoff
# forever, so the stream self-heals the moment the path returns.
#
# Credentials + camera IPs live ONLY in ~/.factory_camera.env (mode 0600) and are
# sourced at runtime — never hardcoded, never logged.
#
# Intended to be run by the launchd agent
# ~/Library/LaunchAgents/com.factoryvision.relay.plist (RunAtLoad + KeepAlive),
# independent of the console server agent. Safe to run directly for testing.
set -uo pipefail

CONSOLE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CAMERA_ENV="${FACTORY_CAMERA_ENV:-$HOME/.factory_camera.env}"
FFMPEG="${FV_FFMPEG:-/opt/homebrew/bin/ffmpeg}"
MEDIA_ROOT="${FV_LIVE_MEDIA_DIR:-${CONSOLE_DIR}/live-media}"
LOG_FILE="${FV_LIVE_RELAY_LOG:-/tmp/fv-live-relay.log}"
BACKOFF="${FV_LIVE_RELAY_BACKOFF:-5}"

log() {
  # $1 = camera tag, $2.. = message. Never interpolate credentials/IPs.
  local tag="$1"; shift
  printf '[live-relay %s] [%s] %s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" "${tag}" "$*" \
    | tee -a "${LOG_FILE}"
}

if [[ ! -r "${CAMERA_ENV}" ]]; then
  log "boot" "FATAL: camera env not readable at ${CAMERA_ENV}"
  exit 1
fi
if [[ ! -x "${FFMPEG}" ]]; then
  log "boot" "FATAL: ffmpeg not executable at ${FFMPEG}"
  exit 1
fi

# shellcheck disable=SC1090
set -a; . "${CAMERA_ENV}"; set +a

# Per-camera relay loop. Restarts ffmpeg forever with backoff; logs by tag but
# never prints the RTSP URL (which embeds credentials + IP).
relay_camera() {
  local tag="$1" slug="$2" ip="$3"
  local out_dir="${MEDIA_ROOT}/${slug}"
  local playlist="${out_dir}/stream.m3u8"
  local url="rtsp://${FACTORY_RTSP_USER}:${FACTORY_RTSP_PASS}@${ip}:554/h264Preview_01_main"

  mkdir -p "${out_dir}"
  log "${tag}" "relay armed → station '${slug}' (dir ${out_dir})"

  while true; do
    log "${tag}" "starting ffmpeg RTSP→HLS"
    # -c copy: remux only, no CPU-heavy re-encode. delete_segments+temp_file keep
    # the directory bounded and readers from seeing half-written segments.
    "${FFMPEG}" -nostdin -loglevel error \
      -rtsp_transport tcp -timeout 5000000 \
      -i "${url}" \
      -map 0:v -c copy \
      -f hls -hls_time 2 -hls_list_size 6 \
      -hls_flags delete_segments+temp_file \
      -hls_segment_filename "${out_dir}/seg_%05d.ts" \
      "${playlist}" >>"${LOG_FILE}" 2>&1
    local rc=$?
    log "${tag}" "ffmpeg exited rc=${rc} — path down or camera dropped; retrying in ${BACKOFF}s"
    sleep "${BACKOFF}"
  done
}

# CAM1 → Pallet A (pallet-a); CAM2 → Gate line (gate-line). Slugs match the DB
# Station ids the serving route allowlists against.
relay_camera "CAM1" "pallet-a"  "${CAM1_IP}" &
PID_CAM1=$!
relay_camera "CAM2" "gate-line" "${CAM2_IP}" &
PID_CAM2=$!

log "boot" "supervising CAM1(pid ${PID_CAM1}) + CAM2(pid ${PID_CAM2})"

# Kill the per-camera loops when this supervisor is signalled (launchd stop), so
# no orphan ffmpeg lingers. The loops themselves never exit — each retries its
# ffmpeg forever with backoff — so a normal run simply blocks here on `wait`.
trap 'kill "${PID_CAM1}" "${PID_CAM2}" 2>/dev/null' TERM INT
wait
log "boot" "both camera loops exited — exiting for launchd restart"
exit 1
