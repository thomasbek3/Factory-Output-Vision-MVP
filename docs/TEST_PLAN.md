# TEST_PLAN — Acceptance and Manual Tests

---

## A) Smoke test (every phase)
1) `uvicorn app.main:app --host 127.0.0.1 --port 8080` starts
2) open `/dashboard` in browser
3) open `/wizard` in browser
4) open `/troubleshooting` in browser
5) open `/legacy/dashboard` and confirm it redirects to `/dashboard`
6) open `/legacy/wizard/welcome` and confirm it redirects to `/wizard`
4) open `/api/status` returns JSON
5) open `/api/diagnostics/sysinfo` returns JSON

Current automated suite:
- `python -m unittest discover -s tests -v`
- includes API smoke, dashboard WebSocket/control contract coverage, troubleshooting contract coverage, React cutover routing coverage, worker-state transitions, and demo-mode integration
- `npm run test:e2e` in `frontend/`
- includes Playwright browser coverage for core wizard, dashboard, and troubleshooting interactions against the FastAPI-served React build
- includes explicit browser regressions for demo-mode step gating, ROI clear/resave behavior, and dashboard zero-count guidance
- troubleshooting contract coverage now also exercises demo playback speed changes, count resets, and person-ignore toggles
- troubleshooting contract coverage now also exercises managed demo video upload and active-demo selection

---

## B) Manual acceptance tests — v1.0 Camera-Only MVP

### 1) Wrong password
- Enter bad credentials
- Test Camera => shows clear message (no stack trace)

### 2) RTSP disabled / unreachable
- Test Camera => shows "streaming turned off / cannot reach camera" guidance

### 3) Camera mounting guide
- Wizard Step 0.5 shows visual guide
- Angle, framing, and backlighting advice visible before any drawing steps

### 3.1) React wizard parity
- `/wizard` loads without using Jinja
- Camera settings can be saved
- Test Camera works
- ROI saves and reloads
- Count line saves and reloads
- Operator zone can be skipped or saved
- Calibration can be started from the React flow
- Calibration progress updates from `/api/status`, not from a frontend-only timer
- During calibration, the preview shows backend-detected objects highlighted in green

### 3.2) React dashboard parity
- `/dashboard` loads without using Jinja
- WebSocket metrics connect and update state
- Start Monitoring works
- Stop Monitoring works
- Recalibrate starts calibration cleanly
- Recent events populate without duplicate spam
- Snapshot refreshes and can be forced manually

### 3.3) React troubleshooting parity
- `/troubleshooting` loads without using Jinja
- Diagnostics refresh cleanly
- Restart video action works
- Reset counts works
- Reset calibration works
- Support bundle downloads
- Current camera view refreshes
- ROI, mask, and tracks debug views load once the worker is processing
- In demo mode, playback speed can be changed and the demo can be restarted from frame 1
- In demo mode, a local video file can be uploaded from `/troubleshooting` and selected as the active demo source without editing `.env`
- Person-ignore masking can be toggled for demo evaluation without restarting the app
- Recent troubleshooting events populate

### 3.4) Legacy URL forwarding
- `/legacy/dashboard` redirects to `/dashboard`
- `/legacy/wizard/welcome` redirects to `/wizard`
- `/legacy/troubleshooting` redirects to `/troubleshooting`

### 4) Demo mode
- Set FC_DEMO_MODE=1 and FC_DEMO_VIDEO_PATH
- Counting works and updates dashboard
- For `demo/demo_counter.mp4`, keep the ROI as a horizontal lane around the white block path
- For `demo/demo_counter.mp4`, set the count line direction to `Either direction` unless the line orientation is retuned deliberately
- If the block is outside the ROI or the line direction is reversed, the app may appear healthy while counts remain at zero

### 5) Stop detection
- Provide a demo video segment with no parts
- Stop triggers after N minutes

### 6) Drop detection
- Simulate reduced output rate
- Drop triggers after M minutes

### 7) Calibration quality warning
- Use a video with poor visibility / few detections
- Calibration should warn: "trouble seeing parts, try adjusting camera"
- Confirm auto-detected blob size and velocity are logged

### 8) Operator absence gated
- Ensure it only runs when Drop is active
- Must not run when Green

### 9) Reconnect resilience
- Disconnect camera network for 30 seconds
- Must enter reconnect state
- Must recover automatically when camera returns

### 10) Support bundle
- Download includes:
  - sqlite db
  - logs
  - config snapshot
  - latest frame screenshot
  - diagnostics snapshot

### 11) Logging coverage
- Trigger monitor start/stop => `events` rows created
- Trigger calibration start/complete/reset => `events` rows created
- Trigger drop/stop => `events` rows created
- Trigger reconnect => `events` rows created for RECONNECTING and RECONNECTED
- Cause a handled failure (bad camera / bad model / ffmpeg missing) => file log entry exists with useful detail
- Run system for several minutes => `health_samples` rows are being written periodically
- Verify `GET /api/diagnostics/sysinfo` exposes latest error details when a failure occurs

### 12) Count source column
- Check counts_minute table: count_source column exists and defaults to "vision"
- Confirm /api/status includes count_source: "vision"
- Confirm `/api/status` also includes `operator_absent`

---

## C) 8-hour soak test
- Run monitoring continuously 8 hours
- Confirm:
  - no memory growth
  - no stuck reconnect
  - counts continue
  - SQLite db not corrupted
  - health_samples written throughout

---

## D) Manual acceptance tests — v1.5 Beam + Camera (after v1.0 ships)

### 13) Beam sensor detection
- Plug in beam sensor (Arduino/ESP32 USB)
- Break beam 10 times
- Verify count = 10 in /api/status
- Verify count_source = "beam"

### 14) Beam + vision combined
- Run beam mode with camera active
- Verify: beam counts parts, camera runs at reduced FPS
- Verify: camera detects stop/drop visually (line empty / rate decline)
- Verify: operator zone still works during drop

### 15) Beam disconnect resilience
- Unplug USB sensor during monitoring
- System should: log event, show warning in UI, NOT crash
- Replug: system recovers, counts resume
- Verify events logged for disconnect and reconnect

### 16) Wizard beam flow
- Select "I have a beam sensor" in Step 1.5
- Auto-detect or manually select port
- "Break the beam to test" works
- Step 3 (draw count line) is skipped
- Calibration works with beam as count source
- Dashboard shows "Counting: Beam Sensor"

### 17) Mode switching
- Configure as beam mode, verify counts from beam
- Reconfigure as vision mode, verify counts from vision
- Count history preserved across mode changes

---

## E) Recorded video regression library

Build a folder of test clips for automated replay:

```
test_videos/
  normal_flow/         # steady conveyor, good lighting
  slow_flow/           # reduced rate (should trigger drop)
  full_stop/           # line stops completely
  shadow_changes/      # lighting shift, shadows moving
  brief_occlusion/     # worker hand passes through frame
  operator_present/    # person visible in operator zone
  operator_absent/     # empty operator zone during drop
  camera_bump/         # sudden angle shift
  backlighting/        # camera aimed at window (failure case)
  reconnect_sim/       # video with intentional gaps
```

### Pass criteria for regression:
- Count accuracy ≥ 90% on normal_flow
- False stop rate: 0 in normal_flow (no false positives)
- Drop detection: triggers within expected window on slow_flow
- Stop detection: triggers within expected window on full_stop
- Shadow changes: no false stop/drop triggers
- Operator detection: correct presence/absence on respective clips
- Reconnect: camera recovers automatically after gap

---
