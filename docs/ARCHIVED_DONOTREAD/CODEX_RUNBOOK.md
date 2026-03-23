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
>
> Do not invent features. Implement exactly what the docs specify.
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
> Include requirements.txt and .env.example.
> No vision logic yet.

Run smoke test from docs/TEST_PLAN.md.

---

## Phase 2 — Database models + config persistence
Paste:

> Implement SQLite schema and persistence for config + events.
> Create /api/config GET and /api/config/camera POST (mask password on GET).
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
> Maintain in-memory counts_this_minute and counts_this_hour.
> Implement demo mode reading from mp4 loop when FC_DEMO_MODE=1.

Test on demo video.

---

## Phase 6 — Calibration + baseline + anomaly engine
Paste:

> Implement calibration mode (median per-minute baseline).
> Implement stop/drop logic and events.
> Update /api/status with baseline, rolling rate, counts, and last_frame_age.

Test stop/drop.

---

## Phase 7 — WebSocket metrics + dashboard UI updates
Paste:

> Implement WebSocket /ws/metrics pushing 1 msg/sec.
> Update dashboard to show:
> status light, counts tiles, rolling rate, baseline, events list.

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
> - line crossing
> - anomaly triggers
> - tracker basics
> Ensure `pytest` runs.

Final acceptance checklist.

---