# ARCHITECTURE — Components, Data Flow, State Machine

---

## 1) Component diagram (text)

Browser (LAN)
- Wizard
- Dashboard
- Troubleshooting
    |
    | HTTP :8080 + WebSocket /ws/metrics
    v
FastAPI App (Edge PC)
- UI server (HTML/JS)
- REST API
- WebSocket broadcaster
- SQLite access
    |
    v
Monitoring Orchestrator (in-process)
- owns state machine
- starts/stops workers
- restart/backoff policy
    |
    +-----------------------------+
    |                             |
    v                             v
FFmpeg RTSP Reader Thread      Vision Processor Thread
- builds RTSP URL              - ROI mask
- spawns ffmpeg subprocess      - bg subtraction
- decodes frames                - blobs -> centroids
- publishes latest frame        - tracking
- bounded queue                 - line crossing count
- watchdog + restart            - overlay rendering
    |
    v
Metrics + Anomaly Engine
- per-second updates
- minute/hour rollups
- baseline calibration
- stop/drop/operator detection
- emits events + overall status

SQLite + Logs
- config, counts, events, health
- rotating logs

---

## 2) Threading model
- Thread A: Reader
- Thread B: Vision processor
- Thread C: Orchestrator / anomaly timer (can be inside B if simpler)

Rules:
- UI must never block on CV
- Worker threads must be restartable
- On failure, emit clear DB event + UI status

---

## 3) Reconnect policy (non-negotiable)
Input signal: `last_frame_time`
If `now - last_frame_time > FRAME_STALL_TIMEOUT`:
- state => RUNNING_YELLOW_RECONNECTING
- emit event: RECONNECTING
- kill ffmpeg process
- restart with exponential backoff
- on first successful frame:
  - emit event: RECONNECTED
  - return to prior RUNNING state based on anomaly engine

---

## 3.1) Failure logging matrix

### Events table (`events`)
Use for operator/support timeline items:
- state transitions
- calibration start / complete / reset
- monitor start / stop
- STOP detected
- DROP detected
- OPERATOR_ABSENT
- RECONNECTING
- RECONNECTED
- ERROR state entry
- manual actions from UI

Each event row should include:
- event_type
- state_from
- state_to
- message
- created_at

### Health table (`health_samples`)
Use for periodic operational telemetry:
- current state
- last_frame_age_sec
- reconnect_attempts_total
- active source
- worker thread/process liveness
- rolling rate
- baseline rate
- counter values
- latest error code/message

Recommended write cadence:
- every 5 to 10 seconds while app is running
- immediately on reconnect attempts and recoveries

### Rotating file logs
Use for engineering detail:
- ffmpeg stderr summaries
- ffprobe failures
- Python stack traces
- DB/IO failures
- model load failures
- unexpected thread exits

Rules:
- UI reads from `events` and current status, not raw file logs
- support bundle includes db + file logs + latest snapshot
- worker loops must not silently discard exceptions

---

## 4) State machine rules
- NOT_CONFIGURED: missing camera config or missing ROI/line
- IDLE: configured but monitoring stopped
- CALIBRATING: computing baseline
- RUNNING_GREEN: normal
- RUNNING_YELLOW_DROP: drop active
- RUNNING_YELLOW_RECONNECTING: video stalled and recovering
- RUNNING_RED_STOPPED: stop active
- ERROR: unrecoverable (avoid)

---

## 5) Why FFmpeg ingest
- More controllable failure/retry behavior than OpenCV RTSP
- Allows explicit timeouts and restarts

---
