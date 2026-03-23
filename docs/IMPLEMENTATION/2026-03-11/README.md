# Implementation Packet

Date: 2026-03-11

This folder is the working implementation packet for the current migration plan.

## Read In This Order

1. `PHASE_PLAN.md`
2. `CHECKLIST.md`
3. `BACKEND_TASKS.md`
4. `FRONTEND_TASKS.md`
5. `RISKS.md`

## Current Repo Reality

The repo already has:
- a FastAPI backend
- a SQLite config and events store
- a vision worker with calibration and stop/drop logic
- a separate React frontend under `frontend/`
- FastAPI-served React routes for dashboard, wizard, and troubleshooting
- legacy URL forwarding without server-rendered Jinja fallback pages

Current automated coverage now exists for:
- API smoke
- dashboard WebSocket and control contract coverage
- troubleshooting contract coverage
- React cutover routing and legacy URL forwarding coverage
- worker-state transitions including reconnect logic
- demo-mode diagnostics and support-bundle flow
- Playwright browser coverage for wizard, dashboard, and troubleshooting

Current frontend status:
- React is now the default UI when `frontend/dist` exists
- canonical React routes are `/dashboard`, `/wizard`, and `/troubleshooting`
- compatibility aliases remain at `/app/dashboard`, `/app/wizard`, and `/app/troubleshooting`
- old `/legacy/...` URLs now redirect forward to the React routes
- calibration progress in the React wizard now comes from backend status fields instead of a frontend timer
- calibration preview now uses backend-detected overlays from the live worker
- troubleshooting now uses a dedicated diagnostics snapshot endpoint for ROI, mask, and tracks views
- the old Jinja templates and legacy static JS have been removed
- when `frontend/dist` is missing, the web routes now return a clear `503` build-missing page instead of falling back to templates
- demo-mode validation on `demo/demo_counter.mp4` now depends on a horizontal ROI over the block travel lane and a count line direction of `both` / `Either direction`
- reader ingest now defaults to 12 FPS
- the wizard now makes draft vs saved geometry explicit and labels clear actions more honestly
- dashboard and troubleshooting now surface backend-aware zero-count guidance instead of forcing operators to infer line-direction / ROI mistakes blindly
- troubleshooting now includes demo playback controls for restart, 0.5x/1x/2x/4x speed changes, and runtime count resets
- the backend now exposes a toggleable person-ignore mask that blacks out detected people before motion counting for demo evaluation
- troubleshooting now includes a managed demo video library so operators can upload a local video and switch the active demo source from the UI
- uploaded demo videos are now normalized to a browser-safe MP4 on ingest
- dashboard and troubleshooting camera live view now use MJPEG true-motion streaming
- dashboard and troubleshooting live demo view now use a real browser video element backed by the active demo file
- saved ROI and count-line geometry now render as client-side overlays on top of live media
- troubleshooting live view now lets operators edit ROI and count line directly on the main panel and save them without leaving the screen
- ROI, mask, tracks, and people debug tabs remain snapshot-driven on purpose

## Execution Rule

The number one goal is that the system keeps working at every step.

That means:
- keep FastAPI as the authority
- stabilize backend contracts before UI migration
- leave the old UI in place until React reaches parity
- verify the core flow after every phase
