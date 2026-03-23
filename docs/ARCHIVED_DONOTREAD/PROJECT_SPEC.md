# PROJECT_SPEC — Factory Vision Output Counter (MVP)
This is the single source of truth for behavior. Do not implement features not defined here.

---

## 1) Mission (non-negotiable)
Build a plug-and-play factory output counter appliance that:
- runs on Ubuntu edge PC
- uses Reolink RTSP camera
- has a local web UI
- requires no CLI after install
- can be configured in under 15 minutes

---

## 2) Target environment
- Ubuntu 22.04 LTS (x86_64)
- Python 3.11.8
- CPU-only acceptable

System packages required:
- ffmpeg
- python3-venv

Optional:
- avahi-daemon (for `factorycounter.local`)

---

## 3) User flow (MVP)
1) Open local UI: `http://<edge-ip>:8080`
2) Enter camera:
   - IP
   - username
   - password
3) Draw output ROI (polygon)
4) Draw count line (2 points) + direction option
5) Optional: enable operator zone (polygon)
6) Click "Calibrate"
7) Click "Start Monitoring"

---

## 4) Counting strategy (MVP)
Primary method:
- OpenCV background subtraction + contours + centroid tracking + line crossing

Fallback:
- Person detection for operator zone only
- Runs ONLY when Drop is active (gated)
- Must be optional and off by default

---

## 5) Anomaly logic
### Stop
Stop when: zero count for **N minutes**
- default N = 2

### Drop
Drop when: rolling rate < **60% baseline** for **M minutes**
- default threshold = 0.60
- default M = 3

### Operator absent (optional)
Only evaluated when:
- operator zone exists AND
- Drop is active

Operator absent when:
- no person detected in operator zone for **X minutes**
- default X = 2

---

## 6) Must tolerate
- lighting variation
- shadows
- brief occlusion
- camera disconnect and reconnect

---

## 7) System states
- NOT_CONFIGURED
- IDLE
- CALIBRATING
- RUNNING_GREEN
- RUNNING_YELLOW_DROP
- RUNNING_YELLOW_RECONNECTING
- RUNNING_RED_STOPPED
- ERROR (rare; only unrecoverable)

State transitions must:
- be logged to DB `events`
- be visible in UI

---

## 8) Storage
SQLite file contains:
- config
- counts_minute
- counts_hour
- events
- health_samples

Retention target:
- keep 90 days (configurable), prune older

### 8.1) Logging requirements
The appliance must produce 3 kinds of operational records:

1) `events` table (human-readable event history)
- purpose: operator/support timeline
- must store:
  - state transitions
  - monitoring start/stop
  - calibration started/completed/reset
  - stop detected
  - drop detected
  - operator absent
  - reconnecting
  - reconnected
  - unrecoverable errors
  - user-triggered maintenance actions (restart video, reset calibration, reset setup)

2) `health_samples` table (machine health over time)
- purpose: troubleshooting and support analysis
- sampled periodically during runtime
- must store:
  - timestamp
  - current state
  - last_frame_age_sec
  - reconnect_attempts_total
  - reader_alive
  - vision_loop_alive
  - person_detect_loop_alive
  - source_kind (`camera` or `demo`)
  - rolling_rate_per_min
  - baseline_rate_per_min
  - counts_this_minute
  - counts_this_hour
  - last_error_code (nullable)
  - last_error_message (nullable)

3) rotating text logs on disk
- purpose: low-level support/debug details not suitable for UI tables
- must store:
  - ffmpeg/ffprobe command failures
  - stack traces
  - reconnect backoff details
  - startup/shutdown messages
  - database/schema migration issues
  - model loading issues

Logging rules:
- every Yellow/Red condition must create an `events` row
- every automatic recovery action must create an `events` row
- swallowed exceptions are not allowed; failures must be surfaced as event and/or log entries
- support bundle must include sqlite db + rotating logs + config snapshot + latest frame snapshot

---

## 9) Performance constraints
- Vision processing capped at 10 FPS
- UI snapshot capped at 2 FPS
- Person detection capped at 1 FPS and only during Drop
- Must run for 8 hours without leaking memory

---

## 10) Deployment constraints
- No Docker
- No YAML editing
- No CLI after install
- Deploy via `.deb` and systemd service
- Service must restart automatically on crash and start at boot

---
