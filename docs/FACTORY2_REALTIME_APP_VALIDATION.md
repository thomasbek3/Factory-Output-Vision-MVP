# Factory2 Real-Time App Validation

**Date:** 2026-05-01  
**Repo:** `/Users/thomas/Projects/Factory-Output-Vision-MVP`  
**Video:** `data/videos/from-pc/factory2.MOV`  
**Alias:** `Test Case 1`
**Registry manifest:** `validation/test_cases/factory2.json`

## Summary

The actual Factory Vision app path now counts `factory2.MOV` at true `1.0x` source-clock speed from real processed frames.

This is not the old offline proof path, deterministic receipt replay, timestamp reveal, or fake UI update. The verified path is:

```text
backend file-backed live source
-> ordered frame reader snapshots
-> event_based runtime counter
-> FastAPI status/WebSocket/MJPEG stream
-> React dashboard Runtime Total
```

The investor-demo flow was verified in Chrome:

```text
open dashboard
click Start monitoring
see Demo Video source and backend live view
watch Runtime Total climb
finish at Demo complete / Runtime Total 23
```

## Verified Configuration

```text
FC_DEMO_MODE=1
FC_DEMO_VIDEO_PATH=/Users/thomas/Projects/Factory-Output-Vision-MVP/data/videos/from-pc/factory2.MOV
FC_DEMO_LOOP=0
FC_DEMO_PLAYBACK_SPEED=1.0
FC_DEMO_COUNT_MODE=live_reader_snapshot
FC_COUNTING_MODE=event_based
FC_RUNTIME_CALIBRATION_PATH=/Users/thomas/Projects/Factory-Output-Vision-MVP/data/calibration/factory2_ai_only_v1.json
FC_PROCESSING_FPS=10
FC_READER_FPS=10
```

## Verification Artifacts

Primary visible-dashboard run:

```text
data/reports/factory2_app_observed_events.run8104.visible_dashboard_v1.json
data/reports/factory2_app_vs_truth.run8104.visible_dashboard_v1.json
```

Result:

```text
observed_event_count: 23
matched_count: 23
missing_truth_count: 0
unexpected_observed_count: 0
first_divergence: null
wall_per_source: 1.0
```

Supporting source-clock backend run:

```text
data/reports/factory2_app_observed_events.run8103.sourceclock_10fps_v1.json
data/reports/factory2_app_vs_truth.run8103.sourceclock_10fps_v1.json
```

Result:

```text
observed_event_count: 23
matched_count: 23
missing_truth_count: 0
unexpected_observed_count: 0
first_divergence: null
wall_per_source: 1.0001
```

## What Changed Technically

- Source-clock pacing for synchronous demo frames: file-backed demo processing now stays aligned to source timestamps instead of accumulating fixed sleep lag after expensive frames.
- Local crop-based live person/panel separation: the default runtime separation analyzer now works on a tight panel/person crop and transforms results back to full-frame coordinates.
- Configurable live analysis cache: stable panel/person geometry can reuse recent expensive separation analysis safely.
- Fractional frame sampling: non-divisor FPS settings are sampled by timestamp rather than rounded integer stride.
- Demo stack launcher reliability: backend uses the active venv Python, disables access logs for demo load, and frontend subprocess stdin is closed so Vite does not crash after launcher exit.
- Vite proxy reliability: dev-dashboard API calls stay same-origin while the proxy targets the selected backend port.
- React preview state fix: live preview fallback/ready state no longer resets synchronously inside an effect.

## What This Proves

- The actual app/runtime path can count Factory2 carried-panel placements at real-time speed from real processed frames.
- The dashboard Runtime Total can climb from the same backend frame stream the user sees.
- The verified Factory2 path finishes at the human truth count of `23`.

## What This Does Not Prove Yet

- It does not prove Reolink RTSP in the field works. The architecture should transfer to RTSP, but a real live camera stream can add codec, network, exposure, reconnect, and camera-angle issues.
- It does not prove any other video will count correctly without a truth ledger and per-video validation.
- It does not make deterministic/timestamp demo modes acceptable evidence for investor claims.

## Available Local Source Videos

Likely next full-source clips:

```text
data/videos/from-pc/real_factory.MOV  1920x1080 HEVC, ~29.5 min
data/videos/from-pc/IMG_2628.MOV      1920x1080 HEVC, ~27.8 min
demo/IMG_3262.MOV                     1920x1080 HEVC, ~15.8 min
```

Already verified:

```text
data/videos/from-pc/factory2.MOV      1920x1080 HEVC, ~7.1 min, truth total 23
```

Synthetic/small demo clips:

```text
data/videos/from-pc/demo_counter.mp4  640x480 H.264, 5 min
demo/demo_counter.mp4                 duplicate small counter demo
demo/demo.mp4                         640x360 H.264, 30 sec
```

## Next-Video Doctrine

For the next real video, do not assume `factory2` calibration, truth count, or tuned carry semantics transfer automatically. The right sequence is:

1. inventory and preview the video
2. build or load a human truth ledger
3. run the actual app path, not offline-only scripts
4. compare observed app events to truth
5. only then claim the video works
