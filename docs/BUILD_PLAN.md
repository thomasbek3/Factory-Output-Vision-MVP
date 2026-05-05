# BUILD_PLAN — MVP Milestones

Current execution status as of 2026-03-11:
- backend contract freeze completed
- backend runtime hardening completed
- initial automated safety-net tests completed
- separate frontend shell completed
- React wizard rebuild completed
- React dashboard rebuild completed
- React troubleshooting rebuild completed
- React-first cutover completed
- browser-driven frontend interaction coverage completed
- legacy template/static cleanup completed
- current implementation focus is incremental stabilization and broader regression coverage

2026-05-01 update:
- The current counting doctrine is YOLO/event-based output-zone counting, not background subtraction, contours, or count-line crossing.
- The Factory2 real-time app path is verified in `docs/FACTORY2_REALTIME_APP_VALIDATION.md`.
- Older line-crossing milestones below are retained as historical build-plan context, not current implementation guidance.

## v1.0 — Camera-Only MVP (each milestone <2 hours)

1) FastAPI skeleton + landing page
- Success: UI opens on LAN

2) SQLite schema + config persistence
- Include `count_source` column in counts tables (default: "vision")
- Success: save config, refresh, still there

3) RTSP URL builder (Reolink main/sub + fallback paths)
- Success: URL resolves and stream probe works

4) Test Camera endpoint (grab one frame)
- Success: clear green check or human-readable failure

5) Snapshot endpoint (latest JPEG)
- Success: wizard can show live-ish frame

6) ROI + Count line drawing UI
- Success: stored normalized coords render correctly after reload

7) Camera mounting guide in wizard Step 0.5
- Show visual diagram: angle, framing, backlighting avoidance
- Success: user sees guidance before drawing anything

8) Background subtractor inside ROI
- Success: moving parts show up in mask; shadows not exploding

9) Contours + centroids
- Success: stable centroid points

10) Lightweight tracker
- Success: IDs persist through brief occlusion

11) Line crossing count via Count Accumulator + anti-double-count
- All counts go through count_event(timestamp, source="vision")
- Success: accurate on demo video

12) Calibration baseline (median per-minute)
- Auto-detect blob size and crossing velocity during calibration
- Warn if detection confidence <95%
- Success: baseline stored; fail gracefully if 0

13) Metrics rollups (minute/hour)
- Success: /api/status shows rolling rate

14) Stop / Drop anomaly engine
- Success: events emitted and UI state changes

15) Optional operator zone + gated person detect
- Success: runs only during drop; CPU stays low normally

16) Reconnect watchdog + exponential backoff
- Success: unplug camera, system recovers automatically

17) Troubleshooting page + support bundle
- Success: support bundle downloads and includes logs/db/snapshot

---

## v1.5 — Beam + Camera (after v1.0 factory pilot)

18) Beam serial reader thread
- Arduino/ESP32 reads beam break, sends serial event
- Python serial listener thread on edge PC
- Each beam break = count_event(timestamp, source="beam")
- Success: beam breaks register as counts in /api/status

19) Count source config + mode switch
- POST /api/config/count_source endpoint
- Config toggle between vision and beam
- When beam active: vision pipeline drops to 2–5 FPS, does not count
- Success: both modes produce counts, status shows correct source

20) Wizard Step 1.5: count source selection UI
- Option A: camera counts / Option B: beam sensor
- Beam auto-detect or manual port select
- "Break the beam to test" verification
- Success: user can select and test beam in wizard

21) Beam health monitoring
- Heartbeat check: no serial data for X seconds = warning
- USB disconnect detection + event logging
- Beam status on troubleshooting page
- Success: unplug beam USB, warning appears, replug recovers

22) Skip count line in beam mode
- When beam selected, wizard skips Step 3 (draw count line)
- ROI still drawn for visual monitoring
- Dashboard shows "Counting: Beam Sensor" badge
- Success: full wizard flow works in both modes

---

## v2.0 milestones (post-funding, see ROADMAP.md)

These are not scoped in detail yet. High-level:

23) Ideal cycle time + shift schedule configuration
24) OEE calculation engine (Availability × Performance)
25) Downtime reason tagging UI (operator taps reason on stop)
26) Shift reports (automated end-of-shift summary)
27) Target vs. actual tracking with projection
28) Six Big Losses breakdown
29) Multi-line dashboard (factory overview)
30) Visual timeline (snapshot on every state change, browsable)

---
