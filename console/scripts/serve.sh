#!/usr/bin/env bash
# FactoryVision console — production serving supervisor.
#
# Serves the console with `next start` (production build) inside a restart loop
# with backoff. Never runs `next build` implicitly: a build is only performed
# when .next/BUILD_ID is missing or --build is passed, so a running server's
# .next is never clobbered by an accidental rebuild.
#
# Intended to be invoked by the launchd agent
# ~/Library/LaunchAgents/com.factoryvision.console.plist (RunAtLoad + KeepAlive),
# but is safe to run directly for local testing.
set -uo pipefail

CONSOLE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${CONSOLE_DIR}"

LOG_FILE="${FV_CONSOLE_LOG:-/tmp/fv-console.log}"
HOSTNAME_BIND="${FV_CONSOLE_HOST:-127.0.0.1}"
PORT="${FV_CONSOLE_PORT:-3000}"
NODE_ENV="production"
export NODE_ENV

# Ensure the toolchain (node/npm/npx from the version-managed dir) is on PATH
# even under launchd's minimal environment.
export PATH="/Users/thomas/.hermes/node/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"

log() {
  printf '[serve.sh %s] %s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" "$*" | tee -a "${LOG_FILE}"
}

FORCE_BUILD=0
for arg in "$@"; do
  case "${arg}" in
    --build) FORCE_BUILD=1 ;;
    *) ;;
  esac
done

# --- 0. Native module ABI: better-sqlite3 must load under the runtime node -----
# The #1 historical flakiness cause: node_modules was built against a different
# Node ABI than the runtime node, so every DB write threw ERR_DLOPEN_FAILED (500)
# while read-only pages looked healthy. Probe it and rebuild in place if broken.
ensure_native() {
  if node -e "require('better-sqlite3')" >/dev/null 2>&1; then
    log "better-sqlite3 native module loads OK (node ABI $(node -e 'process.stdout.write(process.versions.modules)'))"
  else
    log "WARN: better-sqlite3 failed to load under this node — running npm rebuild"
    npm rebuild better-sqlite3 2>&1 | tee -a "${LOG_FILE}" || log "WARN: npm rebuild better-sqlite3 failed"
  fi
}

# --- 1. Prisma DB: ensure it exists (db push + seed) --------------------------
ensure_db() {
  local db_path="${CONSOLE_DIR}/prisma/dev.db"
  if [[ ! -f "${db_path}" ]]; then
    log "prisma/dev.db missing — running db push + seed"
    npx prisma db push --skip-generate 2>&1 | tee -a "${LOG_FILE}" || log "WARN: prisma db push failed"
    npm run seed 2>&1 | tee -a "${LOG_FILE}" || log "WARN: seed failed"
  else
    log "prisma/dev.db present ($(du -h "${db_path}" | cut -f1))"
  fi
}

# --- 2. Demo media: prepare only if missing AND source SSD mounted ------------
ensure_media() {
  local media_probe="${CONSOLE_DIR}/demo-media/pallet-a/midday.mp4"
  local ssd_root="/Users/thomas/FactoryVisionArtifacts/onboarding/factory-live-20260626"
  if [[ -f "${media_probe}" ]]; then
    log "demo-media present"
    return 0
  fi
  if [[ -d "${ssd_root}" ]]; then
    log "demo-media missing, source SSD mounted — running prepare-demo-media.sh"
    bash "${CONSOLE_DIR}/scripts/prepare-demo-media.sh" 2>&1 | tee -a "${LOG_FILE}" || log "WARN: prepare-demo-media failed"
  else
    log "WARN: demo-media missing AND source SSD unmounted — serving whatever exists"
  fi
}

# --- 3. Build: only if BUILD_ID missing or --build passed --------------------
ensure_build() {
  if [[ "${FORCE_BUILD}" -eq 1 ]]; then
    log "--build passed — running next build"
    npm run build 2>&1 | tee -a "${LOG_FILE}"
  elif [[ ! -f "${CONSOLE_DIR}/.next/BUILD_ID" ]]; then
    log ".next/BUILD_ID missing — running next build"
    npm run build 2>&1 | tee -a "${LOG_FILE}"
  else
    log ".next/BUILD_ID present — skipping build (pass --build to force)"
  fi
}

ensure_native
ensure_db
ensure_media
ensure_build

# --- 4. Serve inside a restart loop with backoff -----------------------------
backoff=1
log "starting supervisor loop: next start --hostname ${HOSTNAME_BIND} --port ${PORT}"
while true; do
  start_ts=$(date +%s)
  npx next start --hostname "${HOSTNAME_BIND}" --port "${PORT}" 2>&1 | tee -a "${LOG_FILE}"
  exit_code=${PIPESTATUS[0]}
  end_ts=$(date +%s)
  ran_for=$(( end_ts - start_ts ))

  log "next start exited (code=${exit_code}) after ${ran_for}s"

  # If it ran healthily for a while, reset backoff.
  if [[ "${ran_for}" -ge 60 ]]; then
    backoff=1
  else
    backoff=$(( backoff * 2 ))
    if [[ "${backoff}" -gt 30 ]]; then backoff=30; fi
  fi

  log "restarting in ${backoff}s"
  sleep "${backoff}"
done
