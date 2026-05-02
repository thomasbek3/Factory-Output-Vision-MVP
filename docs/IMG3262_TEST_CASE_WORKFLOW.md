# IMG_3262 Candidate Test Case Workflow

`IMG_3262.MOV` is a candidate for the next verified real-app counting test case.

Registry manifest:

```text
validation/test_cases/img3262.json
```

Dry-run the productized validation plan:

```bash
.venv/bin/python scripts/validate_video.py --case-id img3262_candidate --dry-run
```

## Source Video

- Path: `demo/IMG_3262.MOV`
- SHA-256: `4cb1d274cd2a53ca792bd3b7b217b84bf7734c780a7e43a1b7cc77557a32bf6e`
- Duration: `946.991667` seconds
- Resolution/codecs: `1920x1080`, HEVC
- Preview sheet: `data/videos/preview_sheets/img3262/IMG_3262.jpg`

## Current Human Truth

- Human final total: `21`
- Count rule: count each completed placement after the worker finishes putting the part/panel down.
- Include the final placement in the last second of the video.
- Timestamp ledger:
  - Original rough CSV: `data/reports/img3262_human_truth_event_times.template.csv`
  - Reviewed v2 CSV: `data/reports/img3262_human_truth_event_times.v2.csv`
  - Reviewed v2 ledger: `data/reports/img3262_human_truth_ledger.v2.json`

The original v1 timestamp CSV was rough and failed a strict comparison at `17/21`. The v2 CSV corrects visually reviewed rough entries at counts `1`, `3`, `14`, and `17`; the `629s` v1 entry was after the worker had already moved on and is corrected to `617s`.

Build the timestamped ledger after filling the CSV:

```bash
.venv/bin/python scripts/build_human_truth_ledger_from_csv.py \
  --csv data/reports/img3262_human_truth_event_times.template.csv \
  --output data/reports/img3262_human_truth_ledger.v1.json \
  --video demo/IMG_3262.MOV \
  --expected-total 21 \
  --video-sha256 4cb1d274cd2a53ca792bd3b7b217b84bf7734c780a7e43a1b7cc77557a32bf6e \
  --count-rule "Count each completed placement after the worker finishes putting the part/panel down. Include the final placement in the last second of the video." \
  --force
```

Reviewed v2 ledger command:

```bash
.venv/bin/python scripts/build_human_truth_ledger_from_csv.py \
  --csv data/reports/img3262_human_truth_event_times.v2.csv \
  --output data/reports/img3262_human_truth_ledger.v2.json \
  --video demo/IMG_3262.MOV \
  --expected-total 21 \
  --video-sha256 4cb1d274cd2a53ca792bd3b7b217b84bf7734c780a7e43a1b7cc77557a32bf6e \
  --count-rule "Count one completed placement when the worker finishes putting the finished metal/wire-mesh piece in the output/resting area; do not count worker motion, touching/repositioning, static stacks, pallets, partial handling, duplicate views, or motion alone." \
  --force
```

## Honest Validation Rule

Do not mark this as a named verified test case until:

- The app processes `demo/IMG_3262.MOV` through `FC_DEMO_COUNT_MODE=live_reader_snapshot`.
- Counting uses `FC_COUNTING_MODE=event_based`, not replay or timestamp reveal.
- The run completes at real-time playback speed (`FC_DEMO_PLAYBACK_SPEED=1.0`).
- Observed app events are compared to the timestamped human truth ledger.
- Final count equals `21`, with no unexplained missing or unexpected events.

## Baseline Launch

Backend-only baseline run:

```bash
.venv/bin/python scripts/start_factory2_demo_stack.py \
  --backend-port 8092 \
  --skip-frontend \
  --video demo/IMG_3262.MOV
```

Capture observed runtime events:

```bash
.venv/bin/python scripts/capture_factory2_app_run_events.py \
  --base-url http://127.0.0.1:8092 \
  --output data/reports/img3262_app_observed_events.run8092.baseline_v1.json \
  --poll-interval-sec 5 \
  --max-wait-sec 1200 \
  --auto-start \
  --force
```

Compare against the provisional human total:

```bash
.venv/bin/python scripts/compare_app_run_to_human_total.py \
  --human-total data/reports/img3262_human_truth_total.v1.json \
  --observed-events data/reports/img3262_app_observed_events.run8092.baseline_v1.json \
  --output data/reports/img3262_app_vs_human_total.run8092.baseline_v1.json \
  --force
```

Dashboard run:

```bash
.venv/bin/python scripts/start_factory2_demo_stack.py \
  --backend-port 8092 \
  --frontend-port 5174 \
  --video demo/IMG_3262.MOV
```

Then open `http://127.0.0.1:5174/dashboard`.

## Verified App Run: 2026-05-01

IMG_3262 has a clean verified candidate run through the real app path, but it has not been renamed/promoted to a numbered test case in docs.

Launch:

```bash
.venv/bin/python scripts/start_factory2_demo_stack.py \
  --backend-port 8092 \
  --frontend-port 5174 \
  --video demo/IMG_3262.MOV \
  --model models/img3262_active_panel_v2.pt \
  --no-runtime-calibration \
  --yolo-confidence 0.25 \
  --processing-fps 10 \
  --reader-fps 10 \
  --playback-speed 1 \
  --event-track-max-age 10 \
  --event-track-min-frames 4 \
  --event-detection-cluster-distance 90
```

Validated conditions:

- Real app path used `FC_DEMO_COUNT_MODE=live_reader_snapshot`.
- Counting mode was `FC_COUNTING_MODE=event_based`.
- Playback speed was `FC_DEMO_PLAYBACK_SPEED=1.0`.
- Dashboard showed `IMG_3262.MOV`, started at Runtime Total `0`, and finished at `Demo complete` / Runtime Total `21`.
- Captured observed events were generated by the running backend from ordered frames, not replay or timestamp reveal.
- Final event at `946.892s` used `end_of_stream_active_track_event`, covering the final-second placement.

Primary artifacts:

- Observed events: `data/reports/img3262_app_observed_events.run8092.active_panel_v2_conf025_cluster90_age10.visible_dashboard_1x_paced_v3.json`
- Human-total comparison: `data/reports/img3262_app_vs_human_total.run8092.active_panel_v2_conf025_cluster90_age10.visible_dashboard_1x_paced_v3.json`
- Timestamp comparison: `data/reports/img3262_app_vs_truth.run8092.active_panel_v2_conf025_cluster90_age10.visible_dashboard_1x_paced_v3_ledger_v2.json`
- Dashboard reattached report: `data/reports/img3262_dashboard_visible_run_1x_paced_v3_reattached.json`
- Dashboard screenshots: `data/reports/screenshots/img3262_dashboard_visible_start_1x_paced_v3.png`, `data/reports/screenshots/img3262_dashboard_visible_mid_1x_paced_v3.png`, `data/reports/screenshots/img3262_dashboard_visible_reattached_end_1x_paced_v3.png`

Result:

- Human total: `21`
- Observed app events: `21`
- Timestamp comparison to reviewed v2 ledger: `matched_count=21`, `missing_truth_count=0`, `unexpected_observed_count=0`, `first_divergence=null`
- Event wall/source pacing: `904.291629s / 904.291s`, `wall_per_source=1.0000007`
