# Implementation Phase Plan

Date: 2026-03-11

## Companion Docs

Use these files with this plan:
- `README.md`
- `CHECKLIST.md`
- `BACKEND_TASKS.md`
- `FRONTEND_TASKS.md`
- `RISKS.md`

## Why This Folder Structure

Use:

`docs/IMPLEMENTATION/<YYYY-MM-DD>/`

Reason:
- sorts cleanly
- avoids illegal path characters like `/`
- keeps planning docs out of the root `docs/`
- makes it easy to add more implementation snapshots later

Recommended contents for each dated folder:
- `PHASE_PLAN.md`
- `BACKEND_TASKS.md`
- `FRONTEND_TASKS.md`
- `CHECKLIST.md`
- `RISKS.md`

This dated snapshot now includes the phase plan, task breakdowns, risks, and execution checklist.

## Non-Negotiable Goal

Everything must keep working while the system evolves.

Rules:
- keep FastAPI as the backend
- separate frontend from backend concerns
- do not rewrite backend logic and UI in the same step unless required
- keep the old UI available until the new UI reaches parity, then delete it only after regression verification
- every phase ends with a smoke test

Smoke test after every phase:
- app boots
- `/api/status` returns valid JSON
- `/api/config` works
- `/api/snapshot` works
- config save/load still works
- calibrate still works
- monitor start/stop still works

## Target Architecture

Backend:
- FastAPI owns API, worker runtime, counting, calibration, anomaly logic, reconnect logic, DB access

Frontend:
- React + TypeScript owns wizard, dashboard, troubleshooting UI, drawing UX, forms, and layout

Boundary:
- frontend talks to backend only through stable REST and WebSocket contracts

## Phase 0 - Freeze The Contract

Goal:
- make backend payloads stable before UI migration

Work:
- define explicit request and response models for config, status, control actions, and events
- keep current endpoints working
- optionally add `/api/v1/...` without removing existing routes

Done when:
- frontend can rely on fixed payload shapes
- backend behavior is no longer inferred from templates

Status:
- completed on 2026-03-11
- current `/api/...` routes remain canonical for now
- future versioning should be additive, not a breaking route swap

## Phase 1 - Harden Backend Runtime

Goal:
- make the runtime reliable before rebuilding UI

Work:
- implement `counts_minute`
- implement `counts_hour`
- implement `health_samples`
- add `GET /api/events`
- add diagnostics endpoints
- add restart-video control
- implement reconnect watchdog and `RUNNING_YELLOW_RECONNECTING`
- replace silent exception swallowing with logging and clear events
- add support-bundle basics

Done when:
- camera or demo mode can configure, calibrate, monitor, stop, drop, reconnect, and emit events correctly

Status:
- completed on 2026-03-11
- added count rollup tables, health samples, diagnostics, restart-video control, support-bundle basics, baseline persistence, reconnect watchdog behavior, and rotating file logging
- current reconnect behavior is implemented around frame staleness and runtime restart

## Phase 2 - Add A Safety Net

Goal:
- reduce breakage risk before migration work accelerates

Work:
- API tests for status, config, snapshot, calibrate, monitor start, monitor stop, reset calibration
- worker-state tests for calibration, drop, stop, reconnect
- demo-mode integration test using sample videos

Done when:
- core behavior has automated checks

Status:
- completed on 2026-03-11
- added a `unittest` suite covering API smoke, worker-state transitions including reconnect logic, and demo-mode integration
- current suite runs with `python -m unittest discover -s tests -v`

## Phase 3 - Create The New Frontend Shell

Goal:
- separate UI from backend without deleting current screens

Work:
- add `frontend/`
- use React + TypeScript + Vite
- add typed API client
- add app shell and routing
- decide whether FastAPI serves built assets or frontend runs separately in dev

Done when:
- new frontend boots and talks to FastAPI
- the existing UI remains intact during shell introduction

Status:
- completed on 2026-03-11
- added `frontend/` with React 19, TypeScript, Vite, and React Router
- added a typed API client and the initial React shell routes for dashboard, wizard, and troubleshooting
- Vite dev now proxies backend API routes to FastAPI

## Phase 4 - Rebuild The Wizard

Goal:
- migrate the most important setup flow first

Work:
- welcome step
- camera setup step
- test camera step
- ROI drawing
- count line drawing
- operator zone step
- calibration step
- isolate canvas and drawing logic into reusable frontend components

Done when:
- a user can complete setup in the React wizard end to end
- the React wizard is the complete setup path

Status:
- completed on 2026-03-11
- `/wizard` now supports welcome, mounting guide, camera save, camera test, ROI drawing, count line drawing, operator-zone setup, and calibration actions
- drawing logic is isolated into a reusable snapshot annotation component
- `/legacy/wizard/welcome` now redirects forward to `/wizard` for bookmark compatibility
- stabilization follow-up added backend-reported calibration progress and backend-driven calibration debug overlays
- post-phase demo validation confirmed that `demo/demo_counter.mp4` needs a horizontal ROI over the block lane and a line direction of `both` / `Either direction` to count reliably

## Phase 5 - Rebuild The Dashboard

Goal:
- migrate live operations without changing business logic

Work:
- current state view
- minute and hour counts
- baseline and rolling rate
- live snapshot panel
- recent events feed
- start, stop, and recalibrate controls
- WebSocket metrics subscription

Done when:
- monitoring can be run entirely from the React dashboard
- dashboard state matches backend state reliably

Status:
- completed on 2026-03-11
- `/dashboard` now uses the WebSocket metrics feed plus REST resync for diagnostics and events
- React dashboard now exposes start, stop, and recalibrate controls, a live snapshot panel, and a recent-events feed
- `/legacy/dashboard` now redirects forward to `/dashboard` for bookmark compatibility
- Phase 5 was swept and refactored after completion; dashboard state/runtime logic now lives in a dedicated frontend hook and has explicit dashboard contract coverage in the test suite
- post-phase stabilization raised reader ingest above the old 2 FPS bottleneck
- dashboard camera live view now uses MJPEG true-motion streaming instead of repeated snapshot polling
- dashboard demo live view now uses a real browser video element for prerecorded footage
- saved ROI and count-line geometry now render as client-side overlays on top of true-motion live media

## Phase 6 - Rebuild Troubleshooting

Goal:
- expose recovery and support tools clearly

Work:
- camera health section
- reconnect details
- latest errors
- restart video action
- calibration reset action
- support-bundle download

Done when:
- common support actions are available without touching raw logs or DB manually

Status:
- completed on 2026-03-11
- `/troubleshooting` now exposes camera health, recovery actions, current camera view, support bundle access, and recent troubleshooting events
- shared event and snapshot panels were consolidated so dashboard and troubleshooting can evolve without duplicating UI logic
- stabilization follow-up added a dedicated diagnostics snapshot endpoint for ROI, mask, and tracks debug views
- troubleshooting now includes a managed demo video library with upload normalization to browser-safe MP4
- troubleshooting live camera view now uses MJPEG true motion while live demo view plays the active video file directly
- troubleshooting live view now supports inline ROI and count-line editing directly on the main panel using the existing config endpoints
- ROI, mask, tracks, and people tabs remain backend snapshot views for debug inspection

## Phase 7 - Cutover And Cleanup

Goal:
- switch to the new UI without creating operational risk

Work:
- make React the default UI
- preserve old URLs during cutover, then reduce them to redirects after verification
- remove dead template and static JS only after parity is confirmed

Done when:
- the system runs through FastAPI APIs plus the React UI
- legacy UI has been removed safely

Status:
- completed on 2026-03-11
- FastAPI now serves the React build from `frontend/dist` when it is present
- `/dashboard`, `/wizard`, and `/troubleshooting` now land on React first
- `/app/...` routes remain compatibility aliases
- `/legacy/...` routes now redirect forward for bookmark compatibility
- the Jinja templates and legacy static-JS files have been removed after backend and browser verification
- when `frontend/dist` is missing, web routes return a clear `503` build-missing page instead of reviving the deleted templates

## Recommended Build Order

1. Phase 0
2. Phase 1
3. Phase 2
4. Phase 3
5. Phase 4
6. Phase 5
7. Phase 6
8. Phase 7

## If You Need The Fastest Pragmatic Version

If time is tight, do this first:

1. Phase 0
2. the most critical parts of Phase 1
3. Phase 3
4. Phase 4

That gets the project onto a clean frontend/backend split quickly while keeping the backend authoritative.
