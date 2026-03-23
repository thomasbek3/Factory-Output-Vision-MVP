# BUILD_PLAN — MVP Milestones (each <2 hours)

1) FastAPI skeleton + landing page
- Success: UI opens on LAN

2) SQLite schema + config persistence
- Success: save config, refresh, still there

3) RTSP URL builder (Reolink main/sub + fallback paths)
- Success: URL resolves and stream probe works

4) Test Camera endpoint (grab one frame)
- Success: clear green check or human-readable failure

5) Snapshot endpoint (latest JPEG)
- Success: wizard can show live-ish frame

6) ROI + Count line drawing UI
- Success: stored normalized coords render correctly after reload

7) Background subtractor inside ROI
- Success: moving parts show up in mask; shadows not exploding

8) Contours + centroids
- Success: stable centroid points

9) Lightweight tracker
- Success: IDs persist through brief occlusion

10) Line crossing count + anti-double-count
- Success: accurate on demo video

11) Calibration baseline (median per-minute)
- Success: baseline stored; fail gracefully if 0

12) Metrics rollups (minute/hour)
- Success: /api/status shows rolling rate

13) Stop / Drop anomaly engine
- Success: events emitted and UI state changes

14) Optional operator zone + gated person detect
- Success: runs only during drop; CPU stays low normally

15) Reconnect watchdog + exponential backoff
- Success: unplug camera, system recovers automatically

16) Troubleshooting page + support bundle
- Success: support bundle downloads and includes logs/db/snapshot

---