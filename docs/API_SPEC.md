# API_SPEC — Endpoints and Payloads

All endpoints are local only.

---

## 1) Config

### GET /api/config
Returns current config. Password must be masked.

Current response also includes:
- `baseline_rate_per_min` (nullable)

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
Optional in v1.0. The count line is no longer required for counting — the output zone (ROI) is sufficient. This endpoint is retained for backward compatibility.

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

### v1.5 addition (not in v1.0 scope):
### POST /api/config/count_source
Body:
{
  "mode": "vision" | "beam",
  "beam_port": "/dev/ttyUSB0"
}
Default in v1.0: mode is always "vision", this endpoint does not exist yet.

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
  "message": "Can't connect. Most often camera streaming is turned off.",
  "action_hint": "Enable RTSP in Reolink settings.",
  "details": {"error_code":"AUTH_FAILED|RTSP_DISABLED|TIMEOUT|UNKNOWN"}
}

### POST /api/control/calibrate/start
### POST /api/control/monitor/start
### POST /api/control/monitor/stop
### POST /api/control/restart_video
### POST /api/control/reset_calibration

### POST /api/control/adjust_count
Manually adjust the current count (e.g. operator correction).
Body:
{
  "delta": 1
}
`delta` is clamped to the range -1000 to 1000. Typically +1 or -1.
Returns: StatusResponse (same shape as GET /api/status).

Current `POST /api/control/restart_video` behavior:
- returns `{ "ok": true }` when a source can be restarted
- returns `503` when no video source can be started yet

---

## 3) Status and metrics

### GET /api/status
{
  "state": "RUNNING_GREEN",
  "count_source": "vision",
  "baseline_rate_per_min": 42.0,
  "calibration_progress_pct": 100,
  "calibration_elapsed_sec": 248,
  "calibration_target_duration_sec": 248,
  "rolling_rate_per_min": 41.2,
  "counts_this_minute": 12,
  "counts_this_hour": 520,
  "last_frame_age_sec": 0.4,
  "reconnect_attempts_total": 3,
  "operator_absent": false
}

Note: `count_source` is always "vision" in v1.0. Will be "vision" or "beam" in v1.5.
During calibration, `calibration_progress_pct`, `calibration_elapsed_sec`, and `calibration_target_duration_sec`
are reported by the backend based on the actual minute-boundary calibration window.

### v1.5 additions to status:
- `beam_alive`: true/false (only when count_source = beam)
- `last_beam_event_sec`: seconds since last beam break

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

Query params:
- `overlay_mode=default` returns the normal saved ROI/line/operator overlays
- `overlay_mode=calibration` adds backend-detected object highlights and track labels when the worker is actively processing

---

## 5) Diagnostics

### GET /api/diagnostics/sysinfo
### GET /api/diagnostics/snapshot/debug?view=tracks|mask|roi
### GET /api/diagnostics/support_bundle.zip

`/api/diagnostics/sysinfo` should summarize:
- app version
- uptime
- current state
- count_source (vision or beam)
- last_frame_age_sec
- reconnect_attempts_total
- worker liveness
- db path
- log directory
- source kind (`camera` or `demo`)
- latest error code/message if present

Current response shape:
{
  "app_version": "0.1.0",
  "uptime_sec": 12.3,
  "current_state": "RUNNING_GREEN",
  "count_source": "vision",
  "last_frame_age_sec": 0.4,
  "reconnect_attempts_total": 0,
  "reader_alive": true,
  "vision_loop_alive": true,
  "person_detect_loop_alive": false,
  "db_path": "/abs/path/to/db",
  "log_directory": "/abs/path/to/logs",
  "source_kind": "camera|demo",
  "latest_error_code": null,
  "latest_error_message": null
}

`/api/diagnostics/snapshot/debug` returns `image/jpeg` from worker-cached debug artifacts.
Supported views:
- `tracks` = live frame plus detection boxes and track labels
- `mask` = foreground mask plus detection overlays
- `roi` = ROI-masked frame used by the worker

### v1.5 additions to sysinfo:
- beam_port
- beam_alive
- last_beam_event_timestamp
- total_beam_events

`/api/diagnostics/support_bundle.zip` must include:
- sqlite db
- rotating logs
- config snapshot
- latest frame screenshot

Current implementation includes:
- `factory_counter.db`
- `config_snapshot.json`
- `diagnostics.json`
- `latest_snapshot.jpg` when a frame is available
- `logs/factory_counter.log*`

---

## 6) WebSocket

### WS /ws/metrics
Push one JSON message per second:
- same fields as /api/status
- include last event (type + message)

---
