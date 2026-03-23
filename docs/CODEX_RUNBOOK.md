# CODEX_RUNBOOK — Exact step-by-step Codex workflow

This is the only process you follow. Do not improvise.

---

## Phase 0 — Guardrails (paste this first)
Paste to Codex:

> Read these files:
> - README.md
> - docs/PROJECT_SPEC.md
> - docs/ARCHITECTURE.md
> - docs/API_SPEC.md
> - docs/UX_SPEC.md
> - docs/BUILD_PLAN.md
> - docs/TEST_PLAN.md
> - docs/COMPETITORS.md
> - docs/CODEX_RUNBOOK.md
> - docs/ROADMAP.md
>
> Do not invent features. Implement exactly what the docs specify.
> v1.0 is camera-only. Do not implement beam/serial/v1.5 features.
> Build in phases. After each phase, ensure the server starts and /api/status works.

---

## Phase 1 — Repo skeleton + server boots
Paste to Codex:

> Implement the repo directory structure exactly as described in docs/PROJECT_SPEC.md (use FastAPI + Jinja2 + SQLite + OpenCV headless + ffmpeg).
> Create minimal app that boots and serves:
> - /wizard/welcome
> - /dashboard
> - /troubleshooting
> Also create /api/status that returns state=NOT_CONFIGURED.
> Include count_source="vision" in status response.
> Include requirements.txt and .env.example.
> No vision logic yet.

Run smoke test from docs/TEST_PLAN.md.

---

## Phase 2 — Database models + config persistence
Paste:

> Implement SQLite schema and persistence for config + events.
> Create /api/config GET and /api/config/camera POST (mask password on GET).
> Include count_source column in counts_minute and counts_hour tables (default: "vision").
> Ensure config persists across restart.

Smoke test.

---

## Phase 3 — RTSP URLs + Test Camera + Snapshot
Paste:

> Implement Reolink RTSP URL builder and ffprobe-based stream probe.
> Implement /api/control/test_camera to grab one frame within 5 seconds.
> Implement ffmpeg reader that can output latest frame.
> Implement /api/snapshot to return JPEG (no overlays yet).

Smoke test + test_camera works.

---

## Phase 3.5 — Camera mounting guide
Paste:

> Implement wizard Step 0.5 showing camera mounting guidance.
> Show visual diagram with 3 rules:
> 1) Mount above, angle down 30-45 degrees
> 2) Full belt width visible
> 3) Don't aim at windows or lights
> Show good vs bad example.
> This step appears before any drawing steps.

Manual test: wizard flow includes mounting guide before ROI.

---

## Phase 4 — ROI + line drawing UI (store normalized coords)
Paste:

> Implement wizard canvas for ROI polygon and count line.
> Store normalized coordinates via /api/config/roi and /api/config/line.
> Render overlays on snapshot response.
> Ensure drawings re-load correctly.

Manual test: draw shapes, reload page.

---

## Phase 5 — Vision pipeline + tracker + line crossing count
Paste:

> Implement OpenCV pipeline:
> ROI mask -> bg subtraction -> contours -> centroids -> tracker -> line crossing.
> All counts must go through a count_event(timestamp, source="vision") function.
> This Count Accumulator function is the single entry point for all counts.
> Maintain in-memory counts_this_minute and counts_this_hour.
> Implement demo mode reading from mp4 loop when FC_DEMO_MODE=1.

Test on demo video.

---

## Phase 6 — Calibration + baseline + anomaly engine
Paste:

> Implement calibration mode (median per-minute baseline).
> During calibration, auto-detect typical blob size and crossing velocity.
> If detection confidence <95% during calibration, show warning to user.
> Implement stop/drop logic and events.
> Update /api/status with baseline, rolling rate, counts, count_source, and last_frame_age.

Test stop/drop.

---

## Phase 7 — WebSocket metrics + dashboard UI updates
Paste:

> Implement WebSocket /ws/metrics pushing 1 msg/sec.
> Update dashboard to show:
> status light, counts tiles, rolling rate, baseline, events list.
> Include count_source badge on dashboard (always "Camera" in v1.0).

Verify live updates.

---

## Phase 8 — Reconnect watchdog + troubleshooting + support bundle
Paste:

> Implement frame stall watchdog and exponential backoff reconnect.
> Troubleshooting page must show last frame age, reconnect attempts, last errors.
> Add support bundle endpoint returning zip with logs + db + snapshot.

Unplug/replug camera test.

---

## Phase 9 — systemd service + deb build script + unit tests
Paste:

> Add systemd unit file and build_deb.sh (best effort).
> Add unit tests for:
> - line crossing via count_event interface
> - anomaly triggers
> - tracker basics
> - count_source column in db
> Ensure `pytest` runs.

Final acceptance checklist.

---

## Phase 10 — v1.5 Beam + Camera (only after v1.0 factory pilot)

Do NOT start this phase until v1.0 has run in at least one factory.

Paste:

> Implement beam serial reader thread.
> - Opens serial port to Arduino/ESP32
> - Each beam break = count_event(timestamp, source="beam")
> Add /api/config/count_source endpoint (mode: vision | beam).
> When beam mode:
> - Beam reader is authoritative count source
> - Vision pipeline drops to 2-5 FPS
> - Vision does NOT increment count, only provides anomaly/presence data
> Add wizard Step 1.5: count source selection with beam test.
> When beam selected, skip wizard Step 3 (draw count line).
> Add beam health monitoring: heartbeat check, disconnect detection, event logging.
> Add beam status to troubleshooting page.
> Add "Counting: Beam Sensor" badge to dashboard.

Test: beam breaks register as counts. Vision anomaly detection still works.
Test: unplug beam USB, warning appears, replug recovers.
Test: full wizard flow in both modes.

---
