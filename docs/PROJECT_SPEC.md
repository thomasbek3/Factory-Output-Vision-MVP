# PROJECT_SPEC — Factory Vision Output Counter (v1.0 Camera-Only MVP)
This is the single source of truth for behavior. Do not implement features not defined here.

See ROADMAP.md for v1.5 (beam), v2.0 (OEE/intelligence), and beyond.

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

### v1.5 additions (not in v1.0 scope):
- USB photo-eye beam sensor pair + Arduino/ESP32 serial bridge
- python3-serial (pyserial)

---

## 3) User flow (v1.0 MVP)
1) Open local UI: `http://<edge-ip>:8080`
2) Enter camera:
   - IP
   - username
   - password
3) Draw output zone (polygon)
4) Optional: enable operator zone (polygon)
5) Click "Calibrate"
6) Click "Start Monitoring"

### v1.5 additions (not in v1.0 scope):
- Step 2.5: Select count source (camera-only or beam+camera)
- If beam: auto-detect USB device, test beam break

---

## 4) Counting strategy (v1.0 MVP)

### v1.0 — Vision-only
Primary method:
- YOLOv8 object detection (person-excluded) + centroid tracking + new-object counting in output zone
- Person-ignore masking is always on by default (persons are excluded from part detections)

### v1.5 — Beam + vision (not in v1.0 scope)
- USB photo-eye via serial bridge for deterministic count
- Camera provides anomaly context, operator detection, visual timeline
- Vision pipeline runs at reduced FPS (2–5) since it is not counting
- Beam events are the authoritative count source
- Custom YOLO training pipeline for customer-specific parts

### Custom model training (required for real factory parts)
The YOLOv8n COCO pre-trained model detects 80 common object classes but NOT custom factory parts
(wire mesh panels, metal gratings, stamped brackets, etc.). Zero-shot models (YOLO-World, Grounding DINO)
were evaluated and proved unreliable for niche industrial objects.

**Validated workflow (tested 2026-03-18 with wire mesh panels):**
1. Extract 80-120 frames from customer's camera feed (motion-diverse sampling preferred)
2. Upload to Roboflow → auto-label with Grounding DINO + SAM at ~45% confidence
3. Customer reviews/corrects labels in Roboflow annotator (~15-20 min)
4. Export dataset in YOLOv8 format via Roboflow API
5. Fine-tune YOLOv8n locally (50 epochs, ~25 min on CPU, faster on GPU)
6. Deploy custom .pt model file via FC_YOLO_MODEL_PATH env var

**Critical labeling rule:** Label parts IN TRANSIT (being carried/held by worker) — NOT parts
sitting on the output stack. Stacked parts create permanent detections (count = 1 forever).
Transit detections are transient and map correctly to counting events.

**Critical config rule:** Person-ignore pixel masking must be OFF when using a custom model
trained on in-transit parts, because the part is inside the worker's person bbox.
The custom model already excludes person class 0, so pixel masking is unnecessary.

Total onboarding time per customer: ~1 hour from camera footage to counting.
This becomes a product feature: "Upload footage → label parts → train model → count."
The pipeline architecture is model-agnostic — swapping models requires zero code changes.

### Design for v1.5 now
Even in v1.0, the count accumulator should be abstracted behind an interface:
```
count_event(timestamp, source="vision")
```
This makes it trivial to add `source="beam"` in v1.5 without refactoring the metrics/anomaly engine.

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

### Camera mounting guidance (surface in UI)
Before counting can be accurate, the camera must be properly positioned.
The setup wizard must show guidance:
- Mount camera above and angled down at 30–45°
- Ensure full conveyor width is visible in frame
- Avoid backlighting (don't aim camera toward windows/lights)
- Keep camera on same network as edge PC (wired preferred)

This guidance prevents the majority of accuracy failures. Show as a visual diagram in wizard Step 0.

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

### 8.1) Schema design note
`counts_minute` and `counts_hour` rows should include a `count_source` column (default: `vision`).
This adds zero overhead now and makes v1.5 beam integration seamless.
`health_samples` should include `source_kind` (currently `camera` or `demo`, will add `beam` in v1.5).

### 8.2) Logging requirements
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
- Person-ignore masking runs always (not gated to Drop)
- Must run for 8 hours without leaking memory

### v1.5 note:
When beam is active, vision processing can drop to 2–5 FPS since counting is handled by beam. This frees significant CPU headroom for future intelligence features.

---

## 10) Deployment constraints
- No Docker
- No YAML editing
- No CLI after install
- Deploy via `.deb` and systemd service
- Service must restart automatically on crash and start at boot

---
