# Test Case 1 — Factory2 Investor Demo Runbook

**Purpose:** pull up the verified Factory2 demo quickly and honestly for an investor.

Registry manifest:

```text
validation/test_cases/factory2.json
```

When Thomas says `run test case 1`, start this exact demo.

## One Command

```bash
cd /Users/thomas/Projects/Factory-Output-Vision-MVP
.venv/bin/python scripts/start_factory2_demo_stack.py --backend-port 8091 --frontend-port 5173
```

Open:

```text
http://127.0.0.1:5173/dashboard
```

## Before Showing It

Reset counts and restart the video if the dashboard was already used:

```bash
curl -X POST http://127.0.0.1:8091/api/control/reset_counts
curl -X POST http://127.0.0.1:8091/api/control/restart_video
```

Refresh the browser dashboard, then click `Start monitoring`.

## What The Investor Should See

```text
Initial state: Ready for demo
Source: Demo Video
Live feed: Connected
Runtime Total starts at 0
Runtime Total climbs as panels are placed
Final state: Demo complete
Final Runtime Total: 23
```

## Verified Non-Replay Configuration

The launcher sets the important environment variables:

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

Do not use `deterministic_file_runner` or any timestamp/replay mode for investor evidence.

## Quick Sanity Check

Before the meeting, verify the backend is on the expected path:

```bash
curl -s http://127.0.0.1:8091/api/diagnostics/sysinfo | python -m json.tool | grep -E 'source_kind|demo_video_name|demo_count_mode|counting_mode|demo_loop_enabled'
```

Expected fields:

```text
"source_kind": "demo"
"demo_video_name": "factory2.MOV"
"demo_count_mode": "live_reader_snapshot"
"demo_loop_enabled": false
"counting_mode": "event_based"
```

## Proof Artifact

The verified Chrome dashboard run is:

```text
data/reports/factory2_app_vs_truth.run8104.visible_dashboard_v1.json
```

Expected result:

```text
matched_count: 23
missing_truth_count: 0
unexpected_observed_count: 0
first_divergence: null
wall_per_source: 1.0
```

## Honest Claim Boundary

Say:

```text
This is the real app counting the recorded Factory2 stream at live speed from processed frames.
```

Do not say:

```text
Reolink RTSP is already validated.
```

That needs a real live-camera test.
