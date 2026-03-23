# Morning Handoff

Date: 2026-03-12

## Overnight Outcome

The stabilization pass expanded beyond the original low-risk cleanup:
- browser regression coverage
- wizard clarity and save/clear guardrails
- zero-count diagnostics polish
- demo-mode stabilization
- true-motion live media for demo and camera paths
- live-view geometry editing on troubleshooting
- docs and handoff sync

## What Changed

### Frontend behavior
- Demo uploads are now normalized to a browser-safe MP4 and selected immediately for playback.
- Dashboard and troubleshooting demo live view now use a real browser `video` element for prerecorded footage.
- Camera live view now uses a backend MJPEG stream instead of 1 FPS snapshot polling.
- Saved ROI and count-line geometry now render as client-side overlays on top of true-motion live media.
- Troubleshooting live view now lets operators edit the output area and count line directly on the main panel.
- ROI, mask, tracks, and people tabs remain backend snapshot views on purpose.

### Backend and API
- Added `/api/stream.mjpg` for camera live motion.
- Demo video ingest now converts uploads to MP4 for reliable browser playback.
- Existing ROI and line config endpoints now support the new inline troubleshooting editor without contract changes.

### Browser and contract coverage
- Playwright now covers direct ROI and count-line editing from the troubleshooting live panel.
- Playwright keeps coverage for switching between live motion and backend debug snapshot views.
- API smoke coverage now checks the MJPEG stream contract.
- Troubleshooting contract coverage now checks demo upload normalization and active video selection.

## Verification Passed

- `npm run lint`
- `npm run build`
- `npx playwright test -g "troubleshooting switches between live and debug snapshot views"`
- `npx playwright test -g "troubleshooting lets operators edit ROI and count line directly on the live panel"`
- `python -m unittest tests.test_api_smoke tests.test_troubleshooting_contract -v`

## Files Touched

- `app/api/routes.py`
- `app/services/demo_video_library.py`
- `frontend/e2e/app.spec.ts`
- `frontend/src/features/dashboard/DashboardPage.tsx`
- `frontend/src/features/dashboard/useDashboardData.ts`
- `frontend/src/features/troubleshooting/TroubleshootingShellPage.tsx`
- `frontend/src/features/troubleshooting/useTroubleshootingData.ts`
- `frontend/src/index.css`
- `frontend/src/shared/api/client.ts`
- `frontend/src/shared/components/LiveSnapshotPanel.tsx`
- `frontend/src/shared/liveOverlays.ts`
- `tests/test_api_smoke.py`
- `tests/test_troubleshooting_contract.py`
- `docs/IMPLEMENTATION/2026-03-11/MORNING_HANDOFF.md`
- `docs/IMPLEMENTATION/2026-03-11/OVERNIGHT_WORKLOG.md`
- `docs/IMPLEMENTATION/2026-03-11/PHASE_PLAN.md`
- `docs/IMPLEMENTATION/2026-03-11/README.md`

## Residual Risks

- Counting still relies on motion and blob logic, not a more robust object-detection model.
- ROI, mask, tracks, and people debug tabs are still snapshot-based rather than streamed video.
- Camera live motion now uses MJPEG, not WebRTC, so bandwidth and latency still need real-hardware validation.
- Demo reliability still depends on scene quality, ROI placement, line direction, and person-ignore behavior.

## Next Good Steps

1. Validate MJPEG camera live view on the real factory network and record latency and bandwidth.
2. Decide whether wizard drawing should stay on frozen frames or move toward the same inline live-editing model.
3. Keep collecting false positives and misses on real clips before changing the counting core.
