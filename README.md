# Factory Vision Output Counter (MVP)
### Plug-and-Play Factory Output Monitoring using Reolink RLC-510WA + Ubuntu Edge PC

---

## What this is
This is **not** "a computer vision project."

This is a **factory appliance** that must:
- Start on boot
- Heal itself when the camera stream drops
- Explain problems in plain language
- Be configurable by a shop owner in **under 15 minutes**
- Require **no CLI after install**
- Run fully offline on a LAN

If setup takes >15 minutes, it fails.

---

## What it does (MVP)
- User enters camera IP + login in a local web UI
- User draws:
  - Output ROI (polygon)
  - Count line (2 points)
  - Optional operator zone (polygon)
- User clicks "Calibrate" to set baseline output rate
- User clicks "Start Monitoring"

System automatically:
- Counts parts crossing the line (per minute/hour)
- Detects **Stop** (zero count for N minutes)
- Detects **Drop** (rolling rate < 60% baseline for M minutes)
- Optionally detects **Operator Absence** ONLY during drop
- Displays a simple **Green / Yellow / Red** status
- Logs events
- Auto-reconnects RTSP if the stream drops
- Exposes diagnostics and a support bundle endpoint

---

## What it does NOT do (MVP)
- No MES/ERP platform
- No PLC integration required
- No cloud required
- No Docker
- No YAML editing
- No ML training required

---

## Hardware assumptions
- Camera: Reolink RLC-510WA
- Edge compute: Ubuntu mini PC (CPU-only OK)
- Network: Ethernet LAN
- Browser: any device on LAN

---

## Repo documentation (source of truth)
All requirements and implementation rules live in:
- `docs/PROJECT_SPEC.md` (full requirements)
- `docs/ARCHITECTURE.md` (components + state machine)
- `docs/API_SPEC.md` (endpoints + payloads)
- `docs/UX_SPEC.md` (blue-collar UI copy + flows)
- `docs/BUILD_PLAN.md` (milestones)
- `docs/TEST_PLAN.md` (acceptance + manual tests)
- `docs/COMPETITORS.md` (market positioning)
- `docs/CODEX_RUNBOOK.md` (how to use Codex to generate the codebase safely)
- `INSTALL/windows/README.md` (Windows install bundle)

Current implementation note:
- `frontend/` now contains the React + TypeScript + Vite frontend introduced in Phase 3
- FastAPI now serves the React build from `frontend/dist` when built assets are present
- `/dashboard`, `/wizard`, and `/troubleshooting` are now the primary UI routes
- `/app/dashboard`, `/app/wizard`, and `/app/troubleshooting` remain compatibility aliases
- the React wizard now uses backend-reported calibration progress instead of a local timer estimate
- the calibration preview now uses backend-detected object overlays during calibration
- troubleshooting now includes live, ROI, mask, and tracks debug views backed by a diagnostics snapshot endpoint
- troubleshooting now includes a demo playback lab for restart-from-beginning, 0.5x/1x/2x/4x playback speed, person-ignore masking, and count resets
- troubleshooting now also supports managed demo video uploads and active-demo switching directly from the UI
- dashboard and troubleshooting now use a real browser `<video>` preview for demo sources instead of 1-second snapshot polling
- old `/legacy/...` URLs now redirect forward to the React routes so existing bookmarks still resolve cleanly
- the old Jinja templates and legacy static JS have been removed
- if `frontend/dist` is missing, the web routes return a clear `503` page instead of falling back to deleted templates
- a real Windows installer EXE is now built at `dist/windows-installer/FactoryCounterSetup-0.1.0.exe`
- demo-mode validation now works end to end with `demo/demo_counter.mp4` when the ROI covers the block travel lane and the count line direction is set to `Either direction`
- real-factory demo testing can now reset runtime counts and restart demo playback without restarting the whole app
- real-factory demo testing no longer requires editing `.env` just to swap video files; uploaded demo files are stored under `data/demo_videos/`

---

## Success criteria (must pass)
- Setup wizard can complete in <15 minutes
- RTSP drop triggers reconnect automatically (no user action)
- Counting works in demo mode using a video file
- Stop/Drop logic triggers correctly
- Troubleshooting page explains failures clearly and offers actions
- Support bundle exports logs + db + snapshot

---

## Non-functional constraints
- CPU-only, cap processing at 10 FPS
- Reader ingest defaults to 12 FPS for smoother demo and operator validation
- Dashboard/troubleshooting snapshot polling refreshes at 1-second intervals
- No memory leaks in 8-hour run
- No thread deadlocks on reconnect
- Clear user-facing errors (no stack traces in UI)

---
