# ARCHITECTURE — Components, Data Flow, State Machine

---

## 1) Component diagram (text)

Browser (LAN)
- React Wizard / Dashboard / Troubleshooting served by FastAPI when `frontend/dist` exists
- old `/legacy/...` URLs redirect forward to the React routes for compatibility
- when `frontend/dist` is missing, FastAPI returns a clear `503` build-missing page instead of a template fallback
    |
    | HTTP :8080 + WebSocket /ws/metrics
    v
FastAPI App (Edge PC)
- UI server (React bundle + API)
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
- builds RTSP URL              - ROI mask (output zone polygon, NOT a count line)
- spawns ffmpeg subprocess      - YOLO inference (custom or COCO model)
- decodes frames                - person exclusion (class 0 always filtered)
- publishes latest frame        - centroid tracking of remaining detections
- bounded queue                 - count unique objects appearing in/exiting output zone
- watchdog + restart            - overlay rendering
                                - model-agnostic: loads whatever .pt model
                                  is specified by FC_YOLO_MODEL_PATH.
                                  Default is yolov8n.pt (COCO 80-class).
                                  Custom per-customer models trained via
                                  Roboflow (~60-100 labeled images) are a
                                  drop-in replacement with zero code changes.
                                - NOTE: disable person-ignore pixel masking
                                  (FC_PERSON_IGNORE_ENABLED=false) when using
                                  custom models that detect parts in workers' hands.
    |
    v
Count Accumulator
- receives count_event(timestamp, source)
- source = "vision" in v1.0
- source = "beam" in v1.5 (not implemented yet)
- feeds into Metrics + Anomaly Engine
    |
    v
Metrics + Anomaly Engine
- per-second updates
- minute/hour rollups
- baseline calibration
- stop/drop/operator detection
- emits events + overall status
- periodic health samples

SQLite + Logs
- config, counts, events, health
- rotating logs

Implemented as of 2026-03-11:
- `counts_minute` and `counts_hour` rollups
- `health_samples`
- rotating file logging
- diagnostics and support-bundle API
- restart-video control path
- React frontend scaffold in `frontend/`
- React-first UI cutover on `/dashboard`, `/wizard`, and `/troubleshooting`
- compatibility aliases retained on `/app/dashboard`, `/app/wizard`, and `/app/troubleshooting`
- old `/legacy/...` URLs now redirect forward instead of serving Jinja pages

---

## 1.1) v1.5 additions (not in v1.0 scope)

```
Beam Reader Thread (optional, v1.5)
- opens serial port to Arduino/ESP32
- each beam break = count_event(timestamp, source="beam")
- writes directly to Count Accumulator
- heartbeat check: no serial data for X seconds = health warning
```

When beam is active:
- Vision Processor Thread still runs at reduced FPS (2–5)
- Vision does NOT increment count
- Vision provides: motion/no-motion signal, operator presence, snapshots
- Beam Reader is authoritative count source

---

## 2) Threading model
- Thread A: FFmpeg RTSP Reader
- Thread B: Vision Processor
- Thread C: Orchestrator / anomaly timer (can be inside B if simpler)

### v1.5 addition:
- Thread D: Beam Serial Reader (only when count_source = beam)

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
- active source (camera, demo, beam in v1.5)
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
- in the current codebase, health samples are written from the vision worker at a configurable interval

---

## 4) State machine rules
- NOT_CONFIGURED: missing camera config or missing ROI (output zone polygon — no count line, just a zone)
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

## 6) Count Accumulator abstraction

The count accumulator is the single point where counts enter the system.
All downstream logic (metrics, anomaly engine, rollups) consumes from it.

```python
def count_event(timestamp: float, source: str = "vision"):
    """
    Called by vision new-object detector (v1.0) or beam serial reader (v1.5).
    Source is recorded for audit but does not change downstream logic.
    """
    # increment in-memory counters
    # write to counts_minute rollup
    # feed anomaly engine
```

This abstraction exists in v1.0 code. The beam reader in v1.5 simply calls
the same function with source="beam".

Current implementation note:
- the count accumulator path now persists minute and hour rollups in SQLite on each recorded count event

---
