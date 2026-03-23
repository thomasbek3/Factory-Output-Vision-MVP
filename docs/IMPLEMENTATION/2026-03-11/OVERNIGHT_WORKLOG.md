# Overnight Worklog

Date: 2026-03-12

Purpose:
- stabilize the working React and FastAPI demo path without rewriting the counting core
- remove the choppy live-media experience for demo review and camera review
- let operators edit ROI and count line directly on the troubleshooting live screen
- capture progress on disk so the work does not depend on chat history

## Scope

1. Browser regression coverage for the failures hit during demo validation
2. Wizard clarity improvements around draft vs saved geometry and save and clear feedback
3. Counting diagnostics polish for zero-count and setup-mismatch cases
4. Demo-mode stabilization and safer defaults and copy
5. True-motion demo and camera live media
6. Live-view overlays and direct troubleshooting geometry editing
7. Verification plus doc sync

## Status Board

- [x] Audit browser coverage gaps
- [x] Add regression coverage for ROI save, clear, step gating, overlay persistence, and live troubleshooting editing
- [x] Improve wizard save and clear clarity and inline guidance
- [x] Add clearer zero-count diagnostics and setup guidance
- [x] Stabilize demo-mode defaults, playback controls, and upload flow
- [x] Replace choppy live snapshot polling with real demo video playback
- [x] Add MJPEG live motion for the camera path
- [x] Render saved geometry over true-motion live media
- [x] Allow ROI and count-line edits directly on troubleshooting live view
- [x] Run verification
- [x] Sync docs and leave handoff notes

## Findings

- Existing Playwright coverage was still too happy-path focused for the real failures seen during demo validation.
- Operator friction was not just counting logic; it was also the UI forcing people to bounce between frozen snapshot tools and live review.
- Real prerecorded demo footage needed a native browser video path, not repeated JPEG snapshots.
- Camera live review also needed true motion, and MJPEG was the fastest low-risk step that fit the existing FastAPI setup.
- Once live media became true motion, the saved ROI and count line also had to move client-side so they stayed visible on top of video and MJPEG.
- After the overlay move, the next obvious gap was editing geometry directly from troubleshooting instead of pushing operators back through setup flow.

## Verification Targets

- `npm run lint`
- `npm run build`
- `python -m unittest tests.test_api_smoke tests.test_troubleshooting_contract -v`
- `npx playwright test -g "troubleshooting switches between live and debug snapshot views"`
- `npx playwright test -g "troubleshooting lets operators edit ROI and count line directly on the live panel"`
- manual smoke for `/dashboard` and `/troubleshooting`
