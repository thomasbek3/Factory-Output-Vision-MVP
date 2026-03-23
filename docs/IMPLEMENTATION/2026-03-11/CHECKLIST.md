# Execution Checklist

Date: 2026-03-11

Use this as the practical working order.

## Priority Rules

- do not break the existing flow
- ship working increments
- backend contract before frontend cutover
- tests before deletion

## Critical Path

- [x] Create API schemas and stabilize payloads
- [x] Add `GET /api/events`
- [x] Add count rollup tables
- [x] Add health-sample table and writer
- [x] Implement reconnect watchdog
- [x] Add restart-video and diagnostics endpoints
- [x] Add structured logging and support-bundle basics
- [x] Add backend smoke tests
- [x] Scaffold `frontend/` with React + TypeScript + Vite
- [x] Add typed API client
- [x] Rebuild wizard in React
- [x] Rebuild dashboard in React
- [x] Rebuild troubleshooting in React
- [x] Switch default UI to React
- [x] Remove legacy UI only after parity and testing

## Repo-Level Checklist

### Backend
- [x] `app/api/` has explicit schemas
- [x] `app/db/` has config, events, counts, and health repositories
- [x] `app/workers/vision_worker.py` no longer swallows exceptions silently
- [x] `app/services/video_runtime.py` supports forced restart
- [x] diagnostics routes exist

### Frontend
- [x] `frontend/` exists
- [x] typed client exists
- [x] routes exist for wizard, dashboard, troubleshooting
- [x] drawing code is isolated into reusable components
- [x] no page uses scattered inline fetch logic

### Tests
- [x] API smoke tests exist
- [x] dashboard WebSocket/control contract tests exist
- [x] troubleshooting contract tests exist
- [x] state-machine tests exist
- [x] demo-mode tests exist
- [x] browser-driven Playwright tests exist for wizard, dashboard, and troubleshooting

## Smoke Test After Every Phase

- [ ] app starts
- [ ] `/api/status` returns `200`
- [ ] `/api/config` returns `200`
- [ ] `/api/snapshot` returns a JPEG when source is available
- [ ] config persists after restart
- [ ] calibration starts and completes
- [ ] monitor start and stop work
- [ ] recent events can be read

## Cutover Checklist

- [x] React wizard reaches parity with current setup flow
- [x] React dashboard reaches parity with live metrics flow
- [x] React troubleshooting can perform maintenance actions
- [x] old template URLs redirect forward for compatibility
- [x] final regression pass completed before template deletion
- [x] legacy Jinja templates and static JS removed after regression verification

## Current Verification Commands

- [x] `python -m unittest discover -s tests -v`
- [x] `npm run lint`
- [x] `npm run test:e2e`
