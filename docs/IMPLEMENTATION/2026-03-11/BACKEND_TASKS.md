# Backend Tasks

Date: 2026-03-11

This file breaks backend work into execution-ready tasks.

## Phase 0 - Freeze The Contract

- [x] Create explicit API schemas for config, status, control results, events, and diagnostics.
Files:
`app/api/routes.py`
`app/api/schemas.py` or `app/api/models.py`
Verify:
`/openapi.json` shows named schemas and existing routes still return `200`.

- [x] Normalize `/api/status` so the payload is stable and future-proof.
Files:
`app/api/routes.py`
`app/workers/vision_worker.py`
Verify:
Response always includes `state`, `baseline_rate_per_min`, `rolling_rate_per_min`, `counts_this_minute`, `counts_this_hour`, `last_frame_age_sec`, `reconnect_attempts_total`, `operator_absent`, and `count_source`.

- [x] Add a read endpoint for recent events.
Files:
`app/api/routes.py`
`app/db/event_repo.py`
Verify:
`GET /api/events?limit=20` returns recent rows in descending order.

- [x] Decide and document route compatibility strategy.
Files:
`docs/IMPLEMENTATION/2026-03-11/PHASE_PLAN.md`
`app/api/routes.py`
Verify:
Either current routes remain canonical or `/api/v1` aliases are added without breaking existing callers.
Decision:
Current `/api/...` routes remain canonical for now. If versioning is added later, it should be additive rather than a route replacement.

## Phase 1 - Harden Runtime

- [x] Expand SQLite schema with `counts_minute`, `counts_hour`, and `health_samples`.
Files:
`app/db/database.py`
`app/db/*.py`
Verify:
Database initializes cleanly on an empty file and migrates an existing file without loss of current config and events.

- [x] Add repositories for count rollups and health samples.
Files:
`app/db/count_repo.py`
`app/db/health_repo.py`
Verify:
The worker can write minute and hour counts plus health samples without direct SQL in worker code.

- [x] Route all count increments through a single accumulator function.
Files:
`app/services/counting.py`
`app/workers/vision_worker.py`
Verify:
Vision counting still works and rollups are written from one code path.

- [x] Persist calibration baseline and any runtime state that must survive restart.
Files:
`app/db/config_repo.py`
`app/workers/vision_worker.py`
Verify:
Restarting the app does not silently erase baseline if that is not intended.

- [x] Implement reconnect detection based on frame staleness.
Files:
`app/workers/vision_worker.py`
`app/services/video_runtime.py`
`app/services/frame_reader.py`
Verify:
When frames stop updating, state moves to `RUNNING_YELLOW_RECONNECTING`, an event is written, the reader restarts, and the state recovers on fresh frames.

- [x] Track reconnect attempts and expose them in status.
Files:
`app/workers/vision_worker.py`
`app/api/routes.py`
Verify:
`reconnect_attempts_total` increments during recovery attempts.

- [x] Add restart-video control endpoint.
Files:
`app/api/routes.py`
`app/services/video_runtime.py`
Verify:
`POST /api/control/restart_video` forces the reader to restart without restarting the whole app.

- [x] Add diagnostics endpoint.
Files:
`app/api/routes.py`
`app/core/settings.py`
`app/workers/vision_worker.py`
Verify:
`GET /api/diagnostics/sysinfo` returns app state, source kind, DB path, worker liveness, and current error details.

- [x] Add support-bundle endpoint.
Files:
`app/api/routes.py`
`app/services/`
Verify:
`GET /api/diagnostics/support_bundle.zip` returns a zip containing DB, config snapshot, and latest frame snapshot at minimum.

- [x] Replace silent exception swallowing with structured logging and event emission.
Notes:
- `POST /api/control/restart_video` now returns `503` if no source can be started, which is expected when the app is not configured.
- support bundle currently includes DB, config snapshot, diagnostics snapshot, latest frame snapshot when available, and rotating logs.
Files:
`app/workers/vision_worker.py`
`app/services/frame_reader.py`
`app/db/event_repo.py`
Verify:
Unexpected failures create logs and visible events instead of disappearing.

## Phase 2 - Add Tests

- [x] Create a `tests/` package and API smoke tests.
Files:
`tests/test_api_status.py`
`tests/test_api_config.py`
`tests/test_api_controls.py`
Verify:
Tests cover status, config, calibration, monitor start and stop, and reset calibration.

- [x] Add worker-state tests.
Files:
`tests/test_vision_worker_states.py`
Verify:
Tests cover `NOT_CONFIGURED`, `IDLE`, `CALIBRATING`, `RUNNING_GREEN`, `RUNNING_YELLOW_DROP`, `RUNNING_RED_STOPPED`, and reconnect behavior.

- [x] Add demo-mode integration tests using the sample videos.
Notes:
- test suite uses `unittest` and runs with `python -m unittest discover -s tests -v`
- current coverage includes API smoke, worker-state transitions including reconnect logic, and demo-mode diagnostics/support-bundle flow
Files:
`tests/test_demo_mode_flow.py`
`demo/demo.mp4`
`demo/demo_counter.mp4`
Verify:
The app can run in demo mode and produce counts without a camera.

## Backend Exit Criteria

Do not start frontend cutover until these are true:
- `/api/status` contract is stable
- `/api/events` exists
- reconnect behavior is implemented
- diagnostics exist
- core API tests pass
