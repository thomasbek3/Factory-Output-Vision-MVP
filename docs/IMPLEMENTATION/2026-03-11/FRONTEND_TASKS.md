# Frontend Tasks

Date: 2026-03-11

This file breaks the frontend migration into concrete tasks while keeping the backend stable.

## Frontend Principles

- React owns presentation only
- all backend communication goes through a typed API layer
- drawing logic lives in isolated components
- avoid coupling screens to raw backend response quirks
- keep the old Jinja UI until React reaches parity, then remove it after regression verification

## Phase 3 - Create The Shell

- [x] Add `frontend/` with React, TypeScript, and Vite.
Files:
`frontend/package.json`
`frontend/src/main.tsx`
`frontend/src/App.tsx`
Verify:
The frontend boots locally and can be developed without touching backend templates.

- [x] Define frontend folder structure by feature, not by page sprawl.
Recommended structure:
`frontend/src/app/`
`frontend/src/features/wizard/`
`frontend/src/features/dashboard/`
`frontend/src/features/troubleshooting/`
`frontend/src/shared/api/`
`frontend/src/shared/components/`
`frontend/src/shared/styles/`
Verify:
The first three screens can share components without circular imports.

- [x] Add a typed API client.
Files:
`frontend/src/shared/api/client.ts`
`frontend/src/shared/api/types.ts`
Verify:
No screen fetches endpoints directly with inline request code.

- [x] Add a small state and data layer.
Files:
`frontend/src/shared/api/`
Verify:
REST and WebSocket state are centralized instead of scattered across components.

- [x] Decide integration mode.
Option:
serve the built frontend from FastAPI in production, but allow separate dev servers locally.
Verify:
The repo supports both local iteration and appliance deployment.
Decision:
- current Phase 3 implementation uses a separate Vite dev server with proxying to FastAPI
- the React router now uses canonical routes at `/dashboard`, `/wizard`, and `/troubleshooting`
- `/app/...` routes remain as compatibility aliases for the earlier shell URLs
- FastAPI production serving is now in place for `frontend/dist`, while separate Vite dev remains available locally

## Phase 4 - Wizard

- [x] Build a proper multi-step wizard shell.
Screens:
- Welcome
- Camera Setup
- Test Camera
- ROI
- Count Line
- Operator Zone
- Calibration
Verify:
Users can move through steps in order and return to earlier steps safely.

- [x] Build a camera setup form connected to `/api/config/camera`.
Verify:
Camera IP, username, password, and stream profile save cleanly.

- [x] Build a camera test screen connected to `/api/control/test_camera`.
Verify:
Success and failure states are clear and do not expose backend internals.

- [x] Build a reusable snapshot annotation component.
Responsibilities:
- load snapshot
- scale image correctly
- keep normalized coordinates
- support polygon drawing
- support line drawing
Verify:
Saved shapes reload accurately on a different viewport size.

- [x] Build ROI, count line, and operator-zone steps on top of the shared annotation component.
Verify:
The frontend keeps one drawing system rather than separate ad hoc code per step.

- [x] Build the calibration screen.
Verify:
Start calibration, show progress/status, and handle completion cleanly.

Current implementation note:
- calibration progress now comes from backend status fields, not a frontend-only timer
- the preview now uses `/api/snapshot?overlay_mode=calibration` to show backend-detected object highlights during calibration

## Phase 5 - Dashboard

- [x] Build a status header component.
Verify:
State colors and wording map directly to backend state without custom guesswork.

- [x] Build metric tiles for current counts and rates.
Verify:
Values match `/api/status` and WebSocket updates.

- [x] Build a recent-events feed.
Verify:
It can load from `GET /api/events` and append WebSocket updates without duplicates.

- [x] Build monitoring controls.
Controls:
- Start Monitoring
- Stop Monitoring
- Recalibrate
Verify:
Button clicks map to control endpoints and refresh state correctly.

- [x] Build a live snapshot panel.
Verify:
Snapshot refresh behavior does not block the rest of the dashboard.

Current implementation note:
- WebSocket `/ws/metrics` is the live source for counts and last-event updates
- diagnostics and event history still resync over REST so the dashboard can recover from dropped socket updates cleanly
- dashboard orchestration was later refactored into a dedicated React hook so the page stays presentational and easier to redesign safely

## Phase 6 - Troubleshooting

- [x] Build a camera-health section.
Verify:
Frame age, reconnect attempts, and source status are visible.

- [x] Build diagnostics and maintenance actions.
Actions:
- Restart Video
- Reset Calibration
- Download Support Bundle
Verify:
Each action is API-backed and exposes success and failure clearly.

- [x] Build error and recovery messaging that matches the operator audience.
Verify:
The UI says what is happening and what to do next in plain language.

Current implementation note:
- troubleshooting now uses shared event and snapshot components instead of feature-local duplicates
- the page now switches between `/api/snapshot` and `/api/diagnostics/snapshot/debug` for live, ROI, mask, and tracks views

## Phase 7 - Cutover

- [x] Route the main UI to React by default.
Verify:
The app lands on the new frontend without removing backend API routes.

- [x] Preserve old URLs during cutover and reduce them to redirects after verification.
Verify:
Existing bookmarks and links still resolve cleanly after the cutover.

- [x] Remove dead Jinja and static JS only after parity.
Files removed:
`app/templates/`
`app/static/js/`
Verify:
No production route depends on deleted template files.

Current implementation note:
- FastAPI now serves `frontend/dist` when built assets are present
- canonical React routes are `/dashboard`, `/wizard`, and `/troubleshooting`
- compatibility aliases remain at `/app/dashboard`, `/app/wizard`, and `/app/troubleshooting`
- old `/legacy/...` URLs now redirect forward instead of serving Jinja pages
- template and legacy static-JS deletion is complete
- when the frontend build is missing, FastAPI returns a clear `503` build-missing page instead of falling back to deleted templates

## Frontend Exit Criteria

Do not remove the old UI until:
- setup works end to end in React
- dashboard controls work
- troubleshooting actions work
- layout works on desktop and tablet
- smoke test passes against the production backend
