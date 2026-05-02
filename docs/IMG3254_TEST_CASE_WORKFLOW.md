# IMG_3254 Candidate Workflow

Updated: 2026-05-01

Status: verified real-app candidate under clean-cycle truth `22`. Not promoted to a numbered test case.

Registry manifest:

```text
validation/test_cases/img3254_clean22.json
```

Dry-run the productized validation plan:

```bash
.venv/bin/python scripts/validate_video.py --case-id img3254_clean22_candidate --dry-run
```

## Video

```text
Path: demo/IMG_3254.MOV
SHA-256: f9b72e2a48e96f1f008a0b750504fde13c8ea43ab62f562bacd715c5b19b19cd
Duration: 1280.516667s
Resolution/codec: 1920x1080 HEVC Main 10
```

## Truth Rule

This video starts with a placement already in progress. The final proof uses clean-cycle truth:

```text
Clean-cycle truth: 22 (locked)
- Exclude the in-progress-at-start placement.

Operational truth: 23 (not the proof target)
- Include the in-progress-at-start placement if its completion is visible after frame 0.
```

Thomas locked clean-cycle truth `22` on 2026-05-01. The opener at frame `0` is documented as operational context only.

Decision evidence:

```text
data/videos/review_frames/img3254_start_truth_decision_sheet.jpg
data/reports/img3254_truth_rule_decision_packet.v1.json
data/reports/img3254_completion_audit.blocked_v1.json
```

At `0.0s`, the worker is already bent over the output pallet with a placement in progress. By about `8-12s`, the worker has moved away. Count that opener only if the final rule is operational truth `23`; exclude it if the final rule is clean-cycle truth `22`.

## Verified Candidate

Verified `1.0x` visible-dashboard launch:

```bash
.venv/bin/python scripts/start_factory2_demo_stack.py \
  --backend-port 8092 \
  --frontend-port 5174 \
  --video demo/IMG_3254.MOV \
  --model models/img3254_active_panel_v4_yolov8n.pt \
  --no-runtime-calibration \
  --yolo-confidence 0.25 \
  --processing-fps 10 \
  --reader-fps 10 \
  --playback-speed 1 \
  --event-track-max-age 52 \
  --event-track-min-frames 12 \
  --event-detection-cluster-distance 250
```

Primary proof artifacts:

```text
data/reports/img3254_human_truth_event_times.clean_cycle_v1.csv
data/reports/img3254_human_truth_total.clean_cycle_v1.json
data/reports/img3254_human_truth_ledger.clean_cycle_v1.json
data/reports/img3254_app_observed_events.run8092.active_panel_v4_yolov8n_conf025_cluster250_age52_min12.visible_dashboard_1x_clean22_v1.json
data/reports/img3254_app_vs_human_total.run8092.active_panel_v4_yolov8n_conf025_cluster250_age52_min12.visible_dashboard_1x_clean22_v1.json
data/reports/img3254_app_vs_truth.run8092.active_panel_v4_yolov8n_conf025_cluster250_age52_min12.visible_dashboard_1x_clean22_v1.json
data/reports/img3254_wall_source_pacing.run8092.active_panel_v4_yolov8n_conf025_cluster250_age52_min12.visible_dashboard_1x_clean22_v1.json
data/reports/img3254_completion_audit.verified_clean22_v1.json
```

Result:

```text
observed_event_count: 22
state: DEMO_COMPLETE
observed_coverage_end_sec: 1280.417
matched_count: 22
missing_truth_count: 0
unexpected_observed_count: 0
first_divergence: null
wall_per_source: 1.000000154
final dashboard: Demo complete / Runtime Total 22
```

Dashboard evidence:

```text
data/reports/screenshots/img3254_dashboard_visible_start_clean22_1x_v1.png
data/reports/screenshots/img3254_dashboard_visible_after_click_clean22_1x_v1.png
data/reports/screenshots/img3254_dashboard_visible_mid_clean22_1x_v1.png
data/reports/screenshots/img3254_dashboard_visible_end_clean22_1x_v1.png
```

Candidate event timestamps:

```text
87.106, 139.109, 190.112, 245.116, 288.985, 332.788, 387.392,
488.398, 569.604, 630.308, 686.011, 739.215, 787.785, 831.187,
880.791, 918.693, 1020.500, 1080.904, 1118.906, 1165.409,
1217.713, 1261.815
```

Focused event-review packet:

```text
data/videos/review_frames/img3254_candidate_events_v1/manifest.json
data/videos/review_frames/img3254_candidate_events_v1/event_*.jpg
```

This packet contains `22` per-event sheets sampled around the current candidate app count moments. It is for human review only; it is not a truth ledger or final proof artifact.

## Rejected Diagnostics

```text
models/img3262_active_panel_v2.pt
- 0 detections on IMG_3254 selected/start frames.

models/wire_mesh_panel.pt
- Detects static stacks and overcounts early.

models/img3254_active_panel_v1.pt
- Reached 23 events by about 565s source time with half the video remaining.

models/img3254_active_panel_v4_yolov8n.pt, max_age=40
- Completed with 24 events due duplicate split windows around 470/487s and 614/629s.

models/img3254_active_panel_v4_yolov8n.pt, max_age=180
- Completed with 22 events but carries tracks for about 18s and is not acceptable as final proof without timing validation.

models/img3254_active_panel_v5.pt
- Broadened detections and overcounted.

models/img3254_active_panel_v6.pt
- Suppressed some duplicate-window detections but overfragmented.

models/img3254_active_panel_v7_from_yolov8n_v6data.pt
- Undercounted; 14 events by DEMO_COMPLETE.
```

## Re-run Command

To repeat the verified clean-cycle candidate path:

```bash
.venv/bin/python scripts/start_factory2_demo_stack.py \
  --backend-port 8092 \
  --frontend-port 5174 \
  --video demo/IMG_3254.MOV \
  --model models/img3254_active_panel_v4_yolov8n.pt \
  --no-runtime-calibration \
  --yolo-confidence 0.25 \
  --processing-fps 10 \
  --reader-fps 10 \
  --playback-speed 1 \
  --event-track-max-age 52 \
  --event-track-min-frames 12 \
  --event-detection-cluster-distance 250
```

Required proof evidence remains the canonical bar in `docs/REAL_APP_TEST_CASE_DEFINITION_OF_DONE.md`: visible dashboard run, Runtime Total starts at `0`, real ordered frames, captured app events, clean reviewed truth comparison, and measured wall/source pacing near `1.0`.

Checks passed for this verification:

```bash
.venv/bin/python -m pytest tests/test_frame_reader.py tests/test_vision_worker_states.py tests/test_start_factory2_demo_app.py tests/test_build_human_truth_ledger_from_csv.py tests/test_compare_app_run_to_human_total.py -q
```

Result: `47 passed`, warnings only.
