# API_SPEC — Endpoints and Payloads

All endpoints are local only.

---

## 1) Config

### GET /api/config
Returns current config. Password must be masked.

### POST /api/config/camera
Body:
{
  "camera_ip": "192.168.1.10",
  "camera_username": "admin",
  "camera_password": "secret",
  "stream_profile": "sub" | "main"
}

### POST /api/config/roi
Body:
{
  "roi_polygon": [{"x":0.1,"y":0.2}, {"x":0.9,"y":0.2}, ...]
}

### POST /api/config/line
Body:
{
  "p1": {"x":0.2,"y":0.6},
  "p2": {"x":0.8,"y":0.6},
  "direction": "both" | "p1_to_p2" | "p2_to_p1"
}

### POST /api/config/operator_zone
Enable:
{
  "enabled": true,
  "polygon": [{"x":0.1,"y":0.1}, ...]
}
Disable:
{
  "enabled": false
}

---

## 2) Control

### POST /api/control/test_camera
Attempts to connect and grab 1 frame (timeout <= 5 seconds).
Response success:
{
  "ok": true,
  "message": "Camera connected",
  "details": {"width":1920,"height":1080,"fps":15}
}
Response failure:
{
  "ok": false,
  "message": "Can't connect. Most often RTSP is turned off.",
  "action_hint": "Enable RTSP in Reolink settings.",
  "details": {"error_code":"AUTH_FAILED|RTSP_DISABLED|TIMEOUT|UNKNOWN"}
}

### POST /api/control/calibrate/start
### POST /api/control/monitor/start
### POST /api/control/monitor/stop
### POST /api/control/restart_video
### POST /api/control/reset_calibration

---

## 3) Status and metrics

### GET /api/status
{
  "state": "RUNNING_GREEN",
  "baseline_rate_per_min": 42.0,
  "rolling_rate_per_min": 41.2,
  "counts_this_minute": 12,
  "counts_this_hour": 520,
  "last_frame_age_sec": 0.4,
  "reconnect_attempts_total": 3
}

### GET /api/events?limit=200
### GET /api/counts/minute?hours=24
### GET /api/counts/hour?days=7

`/api/events` must include at minimum:
- state transitions
- calibration events
- stop/drop events
- reconnecting/reconnected
- operator absent/recovered
- user-triggered maintenance actions

---

## 4) Media

### GET /api/snapshot
Returns image/jpeg with overlays.

---

## 5) Diagnostics

### GET /api/diagnostics/sysinfo
### GET /api/diagnostics/support_bundle.zip

`/api/diagnostics/sysinfo` should summarize:
- app version
- uptime
- current state
- last_frame_age_sec
- reconnect_attempts_total
- worker liveness
- db path
- log directory
- source kind (`camera` or `demo`)
- latest error code/message if present

`/api/diagnostics/support_bundle.zip` must include:
- sqlite db
- rotating logs
- config snapshot
- latest frame screenshot

---

## 6) WebSocket

### WS /ws/metrics
Push one JSON message per second:
- same fields as /api/status
- include last event (type + message)

---
