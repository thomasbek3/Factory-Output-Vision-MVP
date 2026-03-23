# TEST_PLAN — Acceptance and Manual Tests

---

## A) Smoke test (every phase)
1) `uvicorn app.main:app --host 127.0.0.1 --port 8080` starts
2) open `/wizard/welcome` in browser
3) open `/api/status` returns JSON

---

## B) Manual acceptance tests (MVP gates)

### 1) Wrong password
- Enter bad credentials
- Test Camera => shows clear message (no stack trace)

### 2) RTSP disabled / unreachable
- Test Camera => shows "streaming turned off / cannot reach camera" guidance

### 3) Demo mode
- Set FC_DEMO_MODE=1 and FC_DEMO_VIDEO_PATH
- Counting works and updates dashboard

### 4) Stop detection
- Provide a demo video segment with no parts
- Stop triggers after N minutes

### 5) Drop detection
- Simulate reduced output rate
- Drop triggers after M minutes

### 6) Operator absence gated
- Ensure it only runs when Drop is active
- Must not run when Green

### 7) Reconnect resilience
- Disconnect camera network for 30 seconds
- Must enter reconnect state
- Must recover automatically when camera returns

### 8) Support bundle
- Download includes:
  - sqlite db
  - logs
  - config snapshot
  - latest frame screenshot

### 9) Logging coverage
- Trigger monitor start/stop => `events` rows created
- Trigger calibration start/complete/reset => `events` rows created
- Trigger drop/stop => `events` rows created
- Trigger reconnect => `events` rows created for RECONNECTING and RECONNECTED
- Cause a handled failure (bad camera / bad model / ffmpeg missing) => file log entry exists with useful detail
- Run system for several minutes => `health_samples` rows are being written periodically

---

## C) 8-hour soak test
- Run monitoring continuously 8 hours
- Confirm:
  - no memory growth
  - no stuck reconnect
  - counts continue

---
