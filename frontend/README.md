# Factory Counter Frontend

The frontend is a separate React app that talks to FastAPI through typed REST calls.

## Stack

- React 19
- TypeScript
- Vite
- React Router

## Run

1. Start the FastAPI backend on `127.0.0.1:8080`
2. From `frontend/`, run `npm install`
3. Run `npm run dev`
4. Open `http://127.0.0.1:5173/dashboard`

## Dev Integration

- Vite proxies `/api`, `/ws`, and `/openapi.json` to the FastAPI backend
- the React app uses canonical routes at `/dashboard`, `/wizard`, and `/troubleshooting`
- `/app/dashboard`, `/app/wizard`, and `/app/troubleshooting` remain compatibility aliases
- FastAPI serves the built frontend from `frontend/dist` in production when assets are present
- old `/legacy/...` URLs redirect forward to the React routes
- if `frontend/dist` is missing, FastAPI returns a clear `503` build-missing page instead of falling back to templates

## Current Scope

Current routes:
- `/dashboard`
- `/wizard`
- `/troubleshooting`

Compatibility aliases:
- `/app/dashboard`
- `/app/wizard`
- `/app/troubleshooting`

Forwarding aliases:
- `/legacy/dashboard`
- `/legacy/wizard/welcome`
- `/legacy/troubleshooting`

Current implementation status:
- `/dashboard` is a live React operations dashboard backed by WebSocket metrics plus API controls
- `/wizard` is a real multi-step setup flow with backend-reported calibration progress and calibration debug overlays
- `/troubleshooting` is a real support and recovery view backed by diagnostics, maintenance APIs, and dedicated debug snapshot modes
- `/troubleshooting` also includes a demo video library UI for uploading a local video, switching the active demo source, restarting playback, and changing playback speed without editing `.env`
- dashboard and troubleshooting use a real HTML video preview for demo sources; backend debug views still stay on snapshot-based overlays
- Playwright browser coverage exists for core wizard, dashboard, and troubleshooting flows
- the Jinja templates and legacy static JS have been removed after the React cutover passed browser and backend verification
