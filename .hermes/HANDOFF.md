# Factory Vision Hermes Handoff

Updated: 2026-05-04 EDT
Repo: `/Users/thomas/Projects/Factory-Output-Vision-MVP`
Branch: `codex/factory-vision-validation-foundation`

## 2026-05-04: Learning Library v1 Registry Recommendation CLI

Goal:

```text
Make the learning library usable as a registry-first "what do we trust / what next" command without mixing diagnostics, teacher suggestions, training artifacts, and validation proof.
```

Current status:

```text
IMPLEMENTED / FOCUSED TESTS PASS
No UI, no auto-training, no embeddings, no runtime video rerun, and no real_factory validation promotion.
Implementation commit pushed: e625b0e feat: add learning registry recommend cli
```

What changed:

```text
- Migrated validation/learning_registry.json in place to factory-vision-learning-registry-v2.
- Added explicit artifact authority, trust boundaries, readiness, dataset-export gates, related cases, and command prerequisites.
- Added factory2_test_case_1 with alias factory2 as the verified high-count app-proof anchor.
- Kept real_factory_candidate with alias real_factory as diagnostic_recovered only, not validation truth and not training/promotion eligible.
- Added scripts/factory_learn.py recommend --case-id ... --format text|json.
- Added contract tests for Factory2 output, alias resolution, real_factory blockers, unknown cases, invalid trust claims, and missing-artifact readiness blocking.
- Updated AGENTS.md and CLAUDE.md to route future agents through docs/08 plus `scripts/factory_learn.py recommend` before making learning-library recommendations.
```

Key command:

```bash
.venv/bin/python scripts/factory_learn.py recommend --case-id real_factory_candidate --format text
```

Current CLI result summary:

```text
factory2:
  case_id=factory2_test_case_1
  status=verified_app_proof
  readiness runtime=verified validation=verified promotion=verified
  artifact_warnings=[]

real_factory:
  case_id=real_factory_candidate
  status=diagnostic_recovered
  readiness runtime=blocked validation=blocked training=blocked promotion=blocked
  warning=data/calibration/real_factory_placed_and_stayed_v1.json missing
  do_not_trust includes failed 18 count, bronze anchors, and diagnostic count-4 recovery as validation proof.
```

Verification:

```text
.venv/bin/python -m pytest tests/test_learning_registry_schema.py tests/test_factory_learn_recommend.py tests/test_assess_blind_prediction_viability.py tests/test_build_failed_blind_run_learning_packet.py tests/test_validation_registry_schema.py tests/test_active_learning_validation_guard.py tests/test_active_learning_schemas.py -q
23 passed

.venv/bin/python -m py_compile scripts/factory_learn.py
passed
```

Exact next command:

```bash
.venv/bin/python scripts/factory_learn.py recommend --case-id real_factory_candidate --format text
```

## 2026-05-04: Factory2 Explicit Placed-And-Stayed Replay

Goal:

```text
Try the explicit placed-and-stayed selector on a higher-count known video.
```

Current status:

```text
DIAGNOSTIC REPLAY PASS
Factory2 explicit placed_and_stayed run counted 23/23 through the app runtime path.
```

Runtime report:

```text
data/reports/factory2_app_observed_events.run8093.placed_and_stayed_speed8_complete_v1.json
observed_event_count=23
run_complete=true
current_state=DEMO_COMPLETE
observed_coverage_end_sec=426.912
```

Truth comparison:

```text
data/reports/factory2_app_vs_truth.run8093.placed_and_stayed_speed8_v1.json
matched_count=23
missing_truth_count=0
unexpected_observed_count=0
first_divergence=null
```

Run config:

```text
Video: data/videos/from-pc/factory2.MOV
Calibration: data/calibration/factory2_ai_only_v1.json
Model: models/panel_in_transit.pt
Counting: FC_COUNTING_MODE=event_based, FC_DEMO_COUNT_MODE=live_reader_snapshot
Rule: --event-count-rule placed_and_stayed
Playback: --playback-speed 8
Backend: http://127.0.0.1:8093
Log: data/logs/factory2_demo_backend_8093.log
DB: data/factory_counter_factory2_placed_and_stayed_run8093.db
```

Interpretation:

```text
This is good regression evidence for the selector on a 20+ count case.
It does not by itself prove real_factory through placed_and_stayed, because real_factory still needs its own runtime calibration file.
```

## 2026-05-04: Placed-And-Stayed Counting Rule Flag

Goal:

```text
Prototype Thomas's practical rule safely: count when a detected part is placed in the output/right-side zone and stays there long enough, without breaking the current working runtime paths.
```

Current status:

```text
IMPLEMENTED / FOCUSED TESTS PASS
No registry promotion or validation-truth change.
Default runtime behavior is unchanged.
```

What changed:

```text
- Added FC_EVENT_COUNT_RULE with values: auto, placed_and_stayed, dead_track.
- auto preserves existing behavior:
  - event_based + runtime calibration -> RuntimeEventCounter / CountStateMachine placed-and-stayed path
  - event_based + no runtime calibration -> legacy dead-track event path
- placed_and_stayed is now explicit and fail-closed without FC_RUNTIME_CALIBRATION_PATH.
- dead_track remains explicitly selectable for diagnostic/no-calibration recovery runs.
- start_factory2_demo_app.py and start_factory2_demo_stack.py now accept --event-count-rule.
- Diagnostics/debug artifacts expose event_count_rule and event_count_rule_config_error.
```

Key finding:

```text
The core "put it down and wait until it stays down" behavior already existed in app/services/count_state_machine.py as stable_in_output.
The product gap was not a smarter LLM at runtime; it was making the calibrated state-machine path explicit and safely selectable while preserving the existing dead-track recovery path.
```

Regression/safety evidence:

```text
Factory2 previous app runtime artifact:
data/reports/factory2_app_observed_events.run8103.sourceclock_10fps_v1.json
observed_event_count=23
run_complete=true
current_state=DEMO_COMPLETE

real_factory current runtime evidence:
data/reports/real_factory_runtime_count4_app_path_evidence_v1.json
observed_event_count=4
run_complete=true
current_state=DEMO_COMPLETE
```

Verification:

```text
.venv/bin/python -m pytest tests/test_count_state_machine.py tests/test_count_state_machine_adversarial.py tests/test_runtime_event_counter.py tests/test_settings_runtime.py tests/test_start_factory2_demo_app.py tests/test_vision_worker_states.py -q
79 passed

.venv/bin/python -m pytest tests/test_build_real_factory_diagnostic_action_dataset.py tests/test_capture_factory2_app_run_events.py tests/test_validation_registry_schema.py tests/test_learning_registry_schema.py -q
13 passed

.venv/bin/python -m py_compile app/core/settings.py app/workers/vision_worker.py scripts/start_factory2_demo_app.py scripts/start_factory2_demo_stack.py
```

Exact next command:

```bash
# After creating a real_factory runtime calibration file with source/output zones:
FC_DB_PATH=data/factory_counter_real_factory_placed_and_stayed.db .venv/bin/python scripts/start_factory2_demo_stack.py \
  --backend-port 8092 \
  --frontend-port 5174 \
  --skip-frontend \
  --video data/videos/from-pc/real_factory.MOV \
  --calibration data/calibration/real_factory_placed_and_stayed_v1.json \
  --event-count-rule placed_and_stayed \
  --model models/real_factory_diagnostic_action_v2.pt \
  --yolo-confidence 0.25 \
  --processing-fps 5 \
  --reader-fps 5 \
  --playback-speed 8
```

Boundary:

```text
Do not call a future placed-and-stayed real_factory run verified unless it counts 4 through the real app/runtime path with a genuine real_factory calibration and evidence artifact. Bronze anchors remain debugging aids only.
```

## 2026-05-04: real_factory Runtime Count 4 Through App Path

Goal:

```text
Make data/videos/from-pc/real_factory.MOV count exactly 4 through the real local YOLO/event app runtime path, with evidence and without promoting bronze/static diagnostics into validation truth.
```

Current status:

```text
RUNTIME COUNT RECOVERED / FOCUSED TESTS PASS
Final local FastAPI app runtime total: 4
real_factory remains NOT VERIFIED / NOT REGISTRY-PROMOTED
```

Successful app/runtime evidence:

```text
Evidence report:
data/reports/real_factory_runtime_count4_app_path_evidence_v1.json

Runtime capture:
data/reports/real_factory_app_observed_events.run8092.real_factory_diag_action_v2_conf025_min30_cluster250_age52_debounce60_speed8_v1.json

Backend log:
data/logs/factory2_demo_backend_8092.log

Video SHA-256:
48b4aa0543ac65409b11ee4ab93fd13e5f132a218b4303096ff131da42fb9f86
```

Final runtime result:

```text
run_complete=true
current_state=DEMO_COMPLETE
observed_coverage_end_sec=1770.413
reader_last_source_timestamp_sec=1770.413
observed_event_count=4
event_ts: 470.612, 1038.194, 1421.604, 1564.208
track frames_seen: 98, 34, 165, 70
```

Runtime/model/config:

```text
Model: models/real_factory_diagnostic_action_v2.pt
Model SHA-256: e22beb2c87fa90ec1b349a1ccea113c4e791f64a8350a54ac98ab494d30829a1
Dataset manifest: data/labels/real_factory_diagnostic_action_v2/dataset_manifest.json
Counting path: FC_DEMO_COUNT_MODE=live_reader_snapshot, FC_COUNTING_MODE=event_based
Detector threshold: FC_YOLO_CONF_THRESHOLD=0.25
Event acceptance: FC_EVENT_TRACK_MIN_FRAMES=30, FC_EVENT_TRACK_MAX_AGE=52, FC_EVENT_COUNT_DEBOUNCE_SEC=60, match_distance=260, cluster_distance=250
```

Important boundary:

```text
This is a successful runtime-count recovery, not registry verification.
The v2 model is diagnostic-only because it was trained from bronze visual draft anchors plus local hard negatives.
validation_truth_eligible=false
training_eligible_for_promotion=false
validation/registry.json was not updated.
The failed static diagnostic total 18 remains invalid as a count prediction.
```

What changed:

```text
- Added scripts/build_real_factory_diagnostic_action_dataset.py.
- Added tests/test_build_real_factory_diagnostic_action_dataset.py.
- Built diagnostic dataset v2 with tighter action boxes and hard negatives.
- Trained models/real_factory_diagnostic_action_v2.pt.
- Final app run uses min_frames=30. The prior v2 app run with min_frames=12 counted 5 because it accepted a late 18-frame transient at 1695.011s; min_frames=30 rejects that short false track while preserving the four sustained runtime tracks.
```

Oracle status:

```text
Oracle escalation was attempted after the first serious local app/runtime path failed to count 4.
Browser Oracle failed because no ChatGPT cookies were applied from Chrome profiles.
Cookie paths tried:
- /Users/thomas/Library/Application Support/Google/Chrome/Default/Cookies
- /Users/thomas/Library/Application Support/Google/Chrome/Profile 1/Cookies
No Thomas credential interruption was made.
```

Verification:

```text
.venv/bin/python -m json.tool data/reports/real_factory_runtime_count4_app_path_evidence_v1.json
.venv/bin/python -m py_compile scripts/build_real_factory_diagnostic_action_dataset.py
.venv/bin/python -m pytest tests/test_build_real_factory_diagnostic_action_dataset.py -q
5 passed
.venv/bin/python -m pytest tests/test_capture_factory2_app_run_events.py tests/test_start_factory2_demo_app.py -q
11 passed
.venv/bin/python -m pytest tests/test_validation_registry_schema.py tests/test_learning_registry_schema.py -q
6 passed
```

Exact rerun command:

```bash
FC_DB_PATH=data/factory_counter_real_factory_run8092_diag_action_v2_conf025_min30.db .venv/bin/python scripts/start_factory2_demo_stack.py \
  --backend-port 8092 \
  --frontend-port 5174 \
  --skip-frontend \
  --video data/videos/from-pc/real_factory.MOV \
  --no-runtime-calibration \
  --model models/real_factory_diagnostic_action_v2.pt \
  --yolo-confidence 0.25 \
  --processing-fps 5 \
  --reader-fps 5 \
  --playback-speed 8 \
  --event-track-max-age 52 \
  --event-track-min-frames 30 \
  --event-count-debounce-sec 60 \
  --event-track-max-match-distance 260 \
  --event-detection-cluster-distance 250
```

Then capture:

```bash
.venv/bin/python scripts/capture_factory2_app_run_events.py \
  --base-url http://127.0.0.1:8092 \
  --output data/reports/real_factory_app_observed_events.run8092.real_factory_diag_action_v2_conf025_min30_cluster250_age52_debounce60_speed8_v1.json \
  --poll-interval-sec 5 \
  --max-wait-sec 540 \
  --auto-start \
  --force
```

## 2026-05-04: real_factory Review-To-Training Anchor Prep

Goal:

```text
Continue the real_factory recovery loop by converting the failed blind run into reviewed training/validation anchors, while keeping every output pending/bronze until Thomas fills review decisions.
```

Current status:

```text
IMPLEMENTED / FOCUSED TESTS PASS
real_factory remains NOT VERIFIED / NOT REGISTRY-PROMOTED
Current worksheet remains fully pending: no reviewed event timestamps, no gold truth ledger, no training-eligible dataset.
```

New tooling:

```text
Script: scripts/convert_failed_blind_run_review.py
Tests: tests/test_convert_failed_blind_run_review.py
```

What the converter does:

```text
- Fails closed by default if any worksheet row is pending or unclear.
- With --allow-pending, writes only bronze/pending review status artifacts.
- Once reviewed decisions exist, writes:
  - reviewed truth timestamp CSV
  - reviewed gold human truth ledger JSON
  - reviewed label JSON for positives and hard negatives
  - active-learning dataset manifest
- It still marks YOLO dataset export blocked until positive bounding-box labels exist.
```

Current pending artifacts:

```text
data/reports/active_learning/real_factory_failed_blind_run_review_conversion.pending_v1.json
data/reports/active_learning/real_factory_failed_blind_run_review_labels.pending_v1.json
data/reports/active_learning/real_factory_active_learning_dataset_manifest.pending_v1.json
data/reports/active_learning/real_factory_codex_visual_count_draft.v1.json
data/reports/real_factory_codex_visual_count_events.draft_v1.csv
```

Pending conversion result:

```text
status=pending_human_review
expected_true_total=4
accepted_true_placement_count=0
pending_row_count=82
hard_negative_label_count=0
validation_truth_eligible=false
training_eligible=false
yolo_dataset_export_ready=false
```

Follow-up correction after Thomas called out that the practical goal was to count:

```text
Codex visual draft count: 4
Draft candidate timestamps: 448.0, 1026.0, 1404.0, 1554.0
Authority: bronze / codex_visual_draft_pending_thomas_review
validation_truth_eligible=false
training_eligible=false
runtime_count_authority=false
```

Registry/manifest updates:

```text
validation/learning_registry.json indexes the pending conversion, review labels, dataset manifest, and Codex visual draft count.
validation/test_cases/real_factory.json references the same pending/draft artifacts.
validation/registry.json still does not contain real_factory.
```

Focused verification:

```text
.venv/bin/python -m pytest \
  tests/test_convert_failed_blind_run_review.py \
  tests/test_build_failed_blind_run_learning_packet.py \
  tests/test_assess_blind_prediction_viability.py \
  tests/test_learning_registry_schema.py \
  tests/test_screen_detector_transfer.py \
  tests/test_validation_registry_schema.py \
  tests/test_bootstrap_video_candidate.py \
  tests/test_active_learning_schemas.py \
  tests/test_dataset_poisoning.py \
  -q

35 passed
```

Actual pending conversion command already run:

```bash
.venv/bin/python scripts/convert_failed_blind_run_review.py \
  --worksheet data/reports/active_learning/real_factory_failed_blind_run_review_worksheet.v1.csv \
  --packet data/reports/active_learning/real_factory_failed_blind_run_learning_packet.v1.json \
  --manifest validation/test_cases/real_factory.json \
  --status-output data/reports/active_learning/real_factory_failed_blind_run_review_conversion.pending_v1.json \
  --truth-csv data/reports/real_factory_human_truth_event_times.reviewed_v1.csv \
  --truth-ledger data/reports/real_factory_human_truth_ledger.reviewed_v1.json \
  --review-labels data/reports/active_learning/real_factory_failed_blind_run_review_labels.pending_v1.json \
  --dataset-manifest data/reports/active_learning/real_factory_active_learning_dataset_manifest.pending_v1.json \
  --allow-pending \
  --force
```

Next command after Thomas fills the worksheet decisions and exactly 4 reviewed event timestamps:

```bash
.venv/bin/python scripts/convert_failed_blind_run_review.py \
  --worksheet data/reports/active_learning/real_factory_failed_blind_run_review_worksheet.v1.csv \
  --packet data/reports/active_learning/real_factory_failed_blind_run_learning_packet.v1.json \
  --manifest validation/test_cases/real_factory.json \
  --status-output data/reports/active_learning/real_factory_failed_blind_run_review_conversion.reviewed_v1.json \
  --truth-csv data/reports/real_factory_human_truth_event_times.reviewed_v1.csv \
  --truth-ledger data/reports/real_factory_human_truth_ledger.reviewed_v1.json \
  --review-labels data/reports/active_learning/real_factory_failed_blind_run_review_labels.reviewed_v1.json \
  --dataset-manifest data/reports/active_learning/real_factory_active_learning_dataset_manifest.reviewed_v1.json \
  --reviewer-id thomas \
  --force
```

Then run:

```bash
.venv/bin/python scripts/check_dataset_poisoning.py \
  --dataset data/reports/active_learning/real_factory_active_learning_dataset_manifest.reviewed_v1.json \
  --truth-artifact data/reports/real_factory_human_truth_ledger.reviewed_v1.json
```

Important blocker after reviewed event decisions:

```text
Reviewed event timestamps are gold validation truth anchors, but they are not positive YOLO bounding boxes. The first detector-training export still needs positive box labels around the reviewed true-placement frames before yolo_dataset_export_ready can become true.
```

## 2026-05-03: Learning Library Recovery Slice

Goal:

```text
Turn the real_factory blind failure into reusable learning-library data and add a guardrail that refuses numeric blind predictions when active detector transfer is dead and only a static detector is firing.
```

Current status:

```text
IMPLEMENTED / FOCUSED TESTS PASS
real_factory remains NOT VERIFIED / NOT REGISTRY-PROMOTED
```

New doctrine/index artifacts:

```text
docs/08_LEARNING_LIBRARY_ARCHITECTURE.md
validation/schemas/learning_registry.schema.json
validation/learning_registry.json
```

`real_factory_candidate` learning-registry status:

```text
status: failed_diagnostic
privacy_mode: offline_local
hidden_human_total: 4
failed_static_detector_diagnostic_total: 18
blind_prediction_status: no_valid_blind_prediction
registry_promotion_eligible: false
validation_truth_eligible: false
training_eligible: false
```

Blind prediction guardrail:

```text
Script: scripts/assess_blind_prediction_viability.py
Artifact: data/reports/real_factory_blind_prediction_viability.v1.json

Result:
- status=no_valid_blind_prediction
- numeric_prediction_allowed=false
- active_transfer_failed=true
- active_transfer_plausible=false
- static_detector_risk=true
- runtime diagnostics are parameter-sensitive: non-EOF counts 27 vs 18
```

Failed-run recovery packet:

```text
Script: scripts/build_failed_blind_run_learning_packet.py
JSON: data/reports/active_learning/real_factory_failed_blind_run_learning_packet.v1.json
Worksheet: data/reports/active_learning/real_factory_failed_blind_run_review_worksheet.v1.csv
HTML: data/reports/active_learning/real_factory_failed_blind_run_review_packet.v1.html

Contents:
- 4 pending true-placement slots
- 18 pending runtime false-positive / hard-negative candidates from the failed wire_mesh diagnostic
- 60 pending motion-window candidates to find the 4 true placements
- validation_truth_eligible=false
- training_eligible=false
```

Focused check already run:

```text
.venv/bin/python -m pytest tests/test_assess_blind_prediction_viability.py tests/test_learning_registry_schema.py -q
6 passed
```

Full focused check:

```text
.venv/bin/python -m pytest tests/test_assess_blind_prediction_viability.py tests/test_learning_registry_schema.py tests/test_screen_detector_transfer.py tests/test_validation_registry_schema.py tests/test_bootstrap_video_candidate.py -q
23 passed
```

JSON parse checks passed for `validation/learning_registry.json`, `validation/schemas/learning_registry.schema.json`, `data/reports/real_factory_blind_prediction_viability.v1.json`, `validation/test_cases/real_factory.json`, and `data/reports/real_factory_blind_ai_event_estimate.v1.json`.

Next useful command is to build the reviewed 4-event truth ledger and hard-negative review packet, then assemble the first `real_factory` detector-training dataset.

## 2026-05-02: real_factory Blind Candidate Phase

Goal:

```text
Validate data/videos/from-pc/real_factory.MOV as far as possible through the real app path, but keep the first phase blind until the AI/app estimate exists.
```

Current status:

```text
BLIND AI/APP ESTIMATE COMPLETE / HIDDEN HUMAN TOTAL REVEALED AND COMPARED
NOT VERIFIED / NOT REGISTRY-PROMOTED
```

Fingerprint:

```text
Video: data/videos/from-pc/real_factory.MOV
Artifact copy: /Users/thomas/FactoryVisionArtifacts/videos/raw/real_factory.MOV
SHA-256: 48b4aa0543ac65409b11ee4ab93fd13e5f132a218b4303096ff131da42fb9f86
Duration: 1770.480s
Resolution/FPS: 1920x1080 HEVC Main 10, nominal 30fps, 53113 frames
Size: 2046294207 bytes
```

Blind bootstrap artifacts:

```text
validation/test_cases/real_factory.json
data/reports/real_factory_video_fingerprint.v1.json
data/reports/real_factory_human_truth_total.v1.json
data/reports/real_factory_human_truth_total.revealed_v1.json
data/reports/real_factory_human_truth_event_times.pending_reveal.csv
data/videos/preview_sheets/real_factory_candidate/real_factory.jpg
```

Bootstrap tooling was patched to support blind candidates:

```text
scripts/bootstrap_video_candidate.py accepts omitted/unknown expected total.
Initial blind manifests write expected_total=null without inventing truth; after reveal, real_factory manifest now records expected_total=4 with human_total_status=revealed_total_only_pending_event_review and validation_truth_eligible=false.
Tests: .venv/bin/python -m pytest tests/test_bootstrap_video_candidate.py tests/test_screen_detector_transfer.py -q -> 14 passed.
```

Detector transfer screen:

```text
Artifact: data/reports/real_factory_detector_transfer_screen.blind_v1.json

img2628_worksheet_accept_event_diag_v1.pt: 0/80 at conf 0.25
img3254_active_panel_v4_yolov8n.pt: 0/80
img3262_active_panel_v2.pt: 0/80
panel_in_transit.pt: 1/80
wire_mesh_panel.pt: 80/80, 656 total detections

Conclusion: transferred active detectors fail; wire_mesh is only a broad/static detector risk screen.
```

Motion/review scaffolding:

```text
data/reports/real_factory_motion_mined_windows.blind_v1.json
data/videos/review_frames/real_factory_blind_motion_overview_v1/
data/videos/review_frames/real_factory_timelapse_15s_v1/
```

Real app backend diagnostics attempted on `8092`:

```text
Common settings:
FC_DEMO_COUNT_MODE=live_reader_snapshot
FC_COUNTING_MODE=event_based
model=models/wire_mesh_panel.pt
conf=0.25
processing_fps=5
reader_fps=5
event_track_max_age=52
event_track_min_frames=12
event_track_min_travel_px=0
event_track_max_match_distance=260
event_detection_cluster_distance=250
accelerated playback requested 16; diagnostics reported speed 8.0

Debounce 30:
data/reports/real_factory_app_observed_events.run8092.wire_mesh_conf025_cluster250_age52_min12_debounce30_speed16_blind_diag_v1.json
- raw observed_event_count=31
- non-EOF events=27
- EOF same-timestamp events=4

Debounce 60:
data/reports/real_factory_app_observed_events.run8092.wire_mesh_conf025_cluster250_age52_min12_debounce60_speed16_blind_diag_v1.json
- raw observed_event_count=22
- non-EOF events=18
- EOF same-timestamp events=4
```

Blind estimate:

```text
Primary report: data/reports/real_factory_blind_ai_event_estimate.v1.json
CSV ledger: data/reports/real_factory_blind_ai_event_estimate.v1.csv
Predicted total: 18
Predicted timestamps:
38.401, 121.603, 192.805, 266.007, 342.209, 421.211, 496.413, 568.015, 630.217, 808.388, 948.192, 1227.799, 1304.601, 1386.203, 1478.206, 1544.807, 1651.810, 1732.812
Status: blind_ai_estimate only; validation_truth_eligible=false; training_eligible=false.
After this estimate was written, Thomas was asked to reveal the hidden human total. Thomas revealed the hidden total as 4.
Comparison report: data/reports/real_factory_blind_ai_vs_hidden_human_total.v1.json
Goal completion audit: data/reports/real_factory_goal_completion_audit.v1.json
Comparison result: total_matches=false; observed_minus_human_delta=14.
Clarification: the 18 rows are failed wire_mesh static-detector dead-track diagnostic events, not visually confirmed completed placements.
```

Boundary:

```text
Do not call this verified.
Do not register/promote this case.
Visible 1.0x dashboard proof was not run because diagnostics are static-detector/parameter-sensitive, not promotion-plausible.
Next step: build/review the 4-event timestamp truth ledger and create a plausible real_factory-specific YOLO/event-based runtime detector path before any future verification attempt.
```

Checks:

```text
.venv/bin/python -m pytest tests/test_bootstrap_video_candidate.py tests/test_screen_detector_transfer.py tests/test_validation_registry_schema.py -q
17 passed

jq parse checks passed for real_factory manifest/reveal/comparison/audit artifacts.
Built-in required-key/candidate-boundary check passed for validation/test_cases/real_factory.json.
```

Canonical test-case proof bar:
- For any candidate factory video, read `docs/REAL_APP_TEST_CASE_DEFINITION_OF_DONE.md` before claiming validation or promotion.
- The required evidence is the real app/dashboard path at `1.0x`, `live_reader_snapshot`, `event_based`, Runtime Total starting at `0`, captured backend events, clean reviewed truth comparison, measured wall/source pacing, and no replay/timestamp/fake UI/video-specific hacks.
- If a candidate starts mid-placement, settle operational truth vs clean-cycle truth before running verification.

Artifact storage memory:
- GitHub is the project brain/index; do not use normal Git as the raw-video warehouse.
- Current local artifact root: `/Users/thomas/FactoryVisionArtifacts`.
- Policy/index: `docs/07_ARTIFACT_STORAGE.md`, `validation/artifact_storage.json`.
- Current raw videos have local copies in `/Users/thomas/FactoryVisionArtifacts/videos/raw/` with SHA-256 entries in `validation/artifact_storage.json`.
- Keep repo `data/` and `models/` paths as working cache paths for scripts and app validation.

## 2026-05-02: IMG_2628 Verified Candidate

Goal:

```text
Validate data/videos/from-pc/IMG_2628.MOV through the real app path.
Human reference total: 25 completed placements.
```

Current status:

```text
VERIFIED CANDIDATE / NOT PROMOTED
VISIBLE 1.0X DASHBOARD COUNT TO 25 COMPLETED
APP-VS-REVIEWED-TRUTH CLEAN: 25/25
```

The reference total `25` is recorded, reviewed timestamp truth now exists, and the visible real app dashboard run reaches `Runtime Total 25` at `1.0x`. IMG_2628 is registered as a verified candidate, not a promoted numbered test case.

```text
1. Reviewed timestamp truth: `data/reports/img2628_human_truth_ledger.reviewed_v1.json`.
2. Clean comparison: `data/reports/img2628_app_vs_truth.run8092.visible_dashboard_1x_reviewed_v1.json`.
3. Registry/manifest: `validation/registry.json`, `validation/test_cases/img2628.json`.
```

Fingerprint:

```text
Video: data/videos/from-pc/IMG_2628.MOV
SHA-256: b8fa676e3ee7200eb3fecfa112e8e679992b356a0129ff96f78fd949cedf8139
Duration: 1668.210s
Resolution/FPS: 1920x1080 HEVC Main 10, nominal 30fps, 50045 frames
```

Artifacts:

```text
data/reports/img2628_video_fingerprint.v1.json
data/reports/img2628_human_truth_total.v1.json
data/reports/img2628_human_truth_event_times.template.csv
data/reports/img2628_validation_status.blocked_v1.json
data/reports/img2628_completion_audit.blocked_v1.json
data/reports/img2628_counting_readiness_assessment.blocked_v1.json
data/videos/preview_sheets/img2628/IMG_2628.jpg
data/videos/review_frames/img2628_truth_review_5s/manifest.json
data/videos/review_frames/img2628_truth_review_5s/README.md
data/videos/review_frames/img2628_truth_review_1s/manifest.json
data/videos/review_frames/img2628_truth_review_1s/README.md
data/reports/img2628_candidate_truth_windows.cv_motion_draft_v1.json
data/reports/img2628_candidate_truth_windows.cv_motion_draft_v1.csv
data/reports/img2628_human_truth_review_worksheet.cv_motion_draft_v1.csv
data/reports/img2628_human_truth_review_worksheet.cv_motion_draft_v1.html
data/reports/img2628_human_truth_review_form.cv_motion_draft_v1.html
data/reports/img2628_codex_visual_review_worksheet.draft_v1.csv
data/reports/img2628_codex_visual_truth_event_times.draft_v1.csv
data/reports/img2628_codex_visual_truth_ledger.draft_v1.json
data/reports/img2628_event_level_dispute_decisions.reviewed_v1.csv
data/reports/img2628_human_truth_event_times.reviewed_v1.csv
data/reports/img2628_human_truth_ledger.reviewed_v1.json
data/reports/img2628_app_vs_truth.run8092.visible_dashboard_1x_reviewed_v1.json
data/reports/img2628_app_vs_truth.run8092.visible_dashboard_1x_reviewed_strict05_v1.json
data/reports/img2628_wall_source_pacing.run8092.visible_dashboard_1x_reviewed_v1.json
data/reports/img2628_validation_report.registry_v1.json
validation/test_cases/img2628.json
data/videos/review_frames/img2628_cv_motion_candidates_v1/
data/videos/selected_frames/img2628_uniform_80/manifest.json
data/reports/img2628_detector_sample_screen.uniform80_v1.json
```

Detector screen:

```text
img3254_active_panel_v4_yolov8n.pt:
- 0/80 sampled frames at conf 0.25
- 0/80 at conf 0.15
- 1/80 at conf 0.10

img3262_active_panel_v2.pt:
- 0/80 at conf 0.25, 0.15, and 0.10

panel_in_transit.pt:
- sparse low-confidence transfer only
- 1/80 at conf 0.25
- 7/80 at conf 0.15
- 14/80 at conf 0.10

wire_mesh_panel.pt:
- detections on 80/80 sampled frames
- detects static/resident material, so it is not a clean active-placement detector
```

Real-app diagnostics tried:

```text
data/reports/img2628_app_observed_events.run8092.wire_mesh_conf025_cluster90_age10_min4_speed8_short_diag_v1.json
- 28 events by 160.004s coverage, run incomplete
- clear static-fragmentation overcount

data/reports/img2628_app_observed_events.run8092.wire_mesh_conf025_cluster250_age52_min12_speed8_diag_v1.json
- 26 events by 1092.795s coverage, run incomplete
- still overcounting/duplicating

data/reports/img2628_app_observed_events.run8092.wire_mesh_conf025_cluster350_age100_min30_speed8_diag_v1.json
- 18 events by 947.391s coverage, run incomplete
- less noisy but still has duplicate clusters

data/reports/img2628_app_observed_events.run8092.wire_mesh_conf025_cluster500_age200_min50_speed8_diag_v1.json
- 5 events by 1307.201s coverage, run incomplete
- over-suppressed/undercounting

data/reports/img2628_app_observed_events.run8092.worksheet_event_diag_conf076_fps5_age20_min10_debounce30_speed16_diag_v1.json
- real backend diagnostic, `live_reader_snapshot`, `event_based`, accelerated at 16x
- model/settings: `models/img2628_worksheet_accept_event_diag_v1.pt`, `conf=0.76`, `processing_fps=5`, `reader_fps=5`, `event_track_max_age=20`, `event_track_min_frames=10`, `event_count_debounce_sec=30`, `event_track_max_match_distance=260`, `event_detection_cluster_distance=250`
- `observed_event_count=25`, `run_complete=true`
- human-total comparison total matched
- draft visual ledger comparison was not clean: `matched_count=22`, `missing_truth_count=3`, `unexpected_observed_count=3`, first divergence `unexpected_observed@110.003s`
```

Moondream advisory work:

```text
data/reports/active_learning/img2628_event_evidence.wire_mesh_cluster350_diag_v1.json
data/reports/active_learning/img2628_moondream_audit.local_wire_mesh_cluster350_diag_v1.json
data/reports/active_learning/img2628_review_queue.local_wire_mesh_cluster350_diag_v1.json
data/reports/active_learning/img2628_review_queue.local_wire_mesh_cluster350_diag_v1.html
```

Boundary:

```text
Moondream was local/offline only through 127.0.0.1:2020.
All 22 Moondream labels are bronze/pending advisory labels.
validation_truth_eligible=false
training_eligible=false
Dataset poisoning check passed for the Moondream output as teacher labels only.
```

Oracle escalation:

```text
oracle --help was run first.
Dry-run prompt/files preview succeeded under slug img2628-proof-blocker.
Browser-mode Oracle run failed because local ChatGPT was not logged in:
Unable to locate the ChatGPT model selector button.
No API-backed Oracle run was started.
```

Visible 1.0x dashboard run completed:

```bash
.venv/bin/python scripts/start_factory2_demo_stack.py \
  --backend-port 8092 \
  --frontend-port 5174 \
  --video data/videos/from-pc/IMG_2628.MOV \
  --model models/img2628_worksheet_accept_event_diag_v1.pt \
  --no-runtime-calibration \
  --yolo-confidence 0.76 \
  --processing-fps 5 \
  --reader-fps 5 \
  --playback-speed 1 \
  --event-track-max-age 20 \
  --event-track-min-frames 10 \
  --event-track-min-travel-px 0 \
  --event-count-debounce-sec 30 \
  --event-track-max-match-distance 260 \
  --event-detection-cluster-distance 250

.venv/bin/python scripts/capture_factory2_app_run_events.py \
  --base-url http://127.0.0.1:8092 \
  --output data/reports/img2628_app_observed_events.run8092.visible_dashboard_1x_candidate25_v1.json \
  --poll-interval-sec 5 \
  --max-wait-sec 1900 \
  --force
```

Start evidence:

```text
Chrome dashboard showed Source: Demo Video: IMG_2628.MOV.
Runtime Total was 0 after clicking Start monitoring.
Diagnostics at start: state=RUNNING_GREEN, source=5.4s, total=0, mode=live_reader_snapshot, counting=event_based, speed=1.0.
Screenshots:
data/reports/screenshots/img2628_visible_dashboard_1x_start_before_click.png
data/reports/screenshots/img2628_visible_dashboard_1x_started_runtime0.png
```

Completion evidence:

```text
Dashboard showed Demo complete / Runtime Total 25.
Backend diagnostics after completion: state=DEMO_COMPLETE, total=25, source=1668.01, finished=true, video=IMG_2628.MOV, mode=live_reader_snapshot, counting=event_based, speed=1.0, reconnect_attempts=0, latest_error=null.
Completion screenshot:
data/reports/screenshots/img2628_visible_dashboard_1x_complete_total25.png
Summary:
data/reports/img2628_visible_dashboard_1x_summary.candidate25_v1.json
```

Visible run results:

```text
Observed events: data/reports/img2628_app_observed_events.run8092.visible_dashboard_1x_candidate25_v1.json
- observed_event_count=25
- run_complete=true
- current_state=DEMO_COMPLETE
- observed_coverage_end_sec=1668.01

Human total comparison: data/reports/img2628_app_vs_human_total.run8092.visible_dashboard_1x_candidate25_v1.json
- expected_human_total=25
- observed_event_count=25
- total_matches=true

Draft visual ledger comparison: data/reports/img2628_app_vs_codex_visual_draft.run8092.visible_dashboard_1x_candidate25_v1.json
- matched_count=22
- missing_truth_count=3
- unexpected_observed_count=3
- first_divergence=unexpected_observed@110.003s

Reviewed truth comparison: data/reports/img2628_app_vs_truth.run8092.visible_dashboard_1x_reviewed_v1.json
- matched_count=25
- missing_truth_count=0
- unexpected_observed_count=0
- first_divergence=null
- tolerance_sec=2.0

Strict reviewed truth cross-check: data/reports/img2628_app_vs_truth.run8092.visible_dashboard_1x_reviewed_strict05_v1.json
- matched_count=25
- missing_truth_count=0
- unexpected_observed_count=0
- first_divergence=null
- tolerance_sec=0.5

Pacing:
- first_event_ts=55.601
- last_event_ts=1654.410
- wall_delta_sec=1598.810033082962
- source_delta_sec=1598.8090000000002
- wall_per_source=1.0000006461578348

Validation/registry:
- validation/test_cases/img2628.json
- validation/registry.json entry `img2628_candidate`
- data/reports/img2628_validation_report.registry_v1.json
- status=verified_candidate
- promotion_status=not_promoted

Test Case 1 recheck after shared runtime/demo changes:
- Observed events: data/reports/factory2_app_observed_events.run8091.post_img2628_recheck_v1.json
- Comparison: data/reports/factory2_app_vs_truth.run8091.post_img2628_recheck_v1.json
- matched_count=23
- missing_truth_count=0
- unexpected_observed_count=0
- first_divergence=null
- wall_per_source=0.9999964771619203

Focused event dispute packet:
- data/reports/img2628_event_level_dispute_review.visible_dashboard_candidate25_v1.csv
- data/reports/img2628_event_level_dispute_review.visible_dashboard_candidate25_v1.html
- 6 rows covering the exact missing/unexpected draft-ledger mismatches.
- Review frames: data/videos/review_frames/img2628_visible_run_mismatch_review_v1/

Reviewed-truth decision bridge:
- data/reports/img2628_event_level_dispute_decisions.template_v1.csv
- data/reports/img2628_event_level_dispute_decisions.README.md
- scripts/apply_img2628_event_dispute_decisions.py
- tests/test_apply_img2628_event_dispute_decisions.py
- The script fails closed while decisions are blank; verified with:
  .venv/bin/python scripts/apply_img2628_event_dispute_decisions.py --base-truth data/reports/img2628_codex_visual_truth_event_times.draft_v1.csv --decisions data/reports/img2628_event_level_dispute_decisions.template_v1.csv --disputes data/reports/img2628_event_level_dispute_review.visible_dashboard_candidate25_v1.csv --output /tmp/img2628_reviewed_truth_should_not_exist.csv --expected-total 25 --force
- Focused test: .venv/bin/python -m pytest tests/test_apply_img2628_event_dispute_decisions.py -q

Follow-up threshold search on port 8093:
- data/reports/img2628_app_observed_events.run8093.worksheet_conf076_fps5_age20_min6_debounce60_speed16_diag_v1.json
  - 16 events; draft comparison 14 matched / 11 missing / 2 unexpected; first divergence unexpected_observed@162.004s.
- data/reports/img2628_app_observed_events.run8093.worksheet_conf076_fps5_age20_min8_debounce30_speed16_diag_v1.json
  - 26 events; draft comparison 23 matched / 2 missing / 3 unexpected; first divergence unexpected_observed@110.003s.
- Conclusion: simple min-frames/debounce tuning is not enough; the remaining gap is truth adjudication plus likely detector/data improvement, not another threshold nudge.
```

Reviewed truth commands used:

```bash
.venv/bin/python scripts/apply_img2628_event_dispute_decisions.py \
  --base-truth data/reports/img2628_codex_visual_truth_event_times.draft_v1.csv \
  --decisions data/reports/img2628_event_level_dispute_decisions.reviewed_v1.csv \
  --disputes data/reports/img2628_event_level_dispute_review.visible_dashboard_candidate25_v1.csv \
  --observed-events data/reports/img2628_app_observed_events.run8092.visible_dashboard_1x_candidate25_v1.json \
  --max-align-delta-sec 8 \
  --output data/reports/img2628_human_truth_event_times.reviewed_v1.csv \
  --expected-total 25 \
  --force

.venv/bin/python scripts/build_human_truth_ledger_from_csv.py \
  --csv data/reports/img2628_human_truth_event_times.reviewed_v1.csv \
  --output data/reports/img2628_human_truth_ledger.reviewed_v1.json \
  --video data/videos/from-pc/IMG_2628.MOV \
  --expected-total 25 \
  --video-sha256 b8fa676e3ee7200eb3fecfa112e8e679992b356a0129ff96f78fd949cedf8139 \
  --count-rule "Count one completed placement when the worker finishes putting the finished wire product in the output/resting area." \
  --force

.venv/bin/python scripts/compare_factory2_app_run_to_truth_ledger.py \
  --truth-ledger data/reports/img2628_human_truth_ledger.reviewed_v1.json \
  --observed-events data/reports/img2628_app_observed_events.run8092.visible_dashboard_1x_candidate25_v1.json \
  --output data/reports/img2628_app_vs_truth.run8092.visible_dashboard_1x_reviewed_v1.json \
  --tolerance-sec 2.0 \
  --force
```

Next command:

```bash
.venv/bin/python scripts/validate_video.py --case-id img2628_candidate --dry-run
```

## 2026-05-02: Repo Cleanup And Validation Productization

Oracle review output:

```text
data/reports/oracle_factory_vision_repo_productize.md
```

New current-doc spine:

```text
docs/00_CURRENT_STATE.md
docs/01_PRODUCT_SPEC.md
docs/02_ARCHITECTURE.md
docs/03_VALIDATION_PIPELINE.md
docs/04_TEST_CASE_REGISTRY.md
docs/05_OPERATOR_RUNBOOK.md
docs/06_DEVELOPER_RUNBOOK.md
docs/KNOWN_LIMITATIONS.md
```

Validation registry and manifests:

```text
validation/registry.json
validation/test_cases/factory2.json
validation/test_cases/img3262.json
validation/test_cases/img3254_clean22.json
validation/schemas/*.schema.json
```

Registry-backed validation reports:

```text
data/reports/factory2_validation_report.registry_v1.json
data/reports/img3262_validation_report.registry_v1.json
data/reports/img3254_clean22_validation_report.registry_v1.json
```

New command entry points:

```bash
.venv/bin/python scripts/validate_video.py --case-id img3254_clean22_candidate --dry-run
.venv/bin/python scripts/register_test_case.py --manifest validation/test_cases/img3254_clean22.json --force
make validate-video CASE_ID=img3254_clean22_candidate
```

Historical Factory2 research scripts are still at top-level `scripts/` because tests import those module paths. They are now documented as research-only; the product validation path is the registry + manifest + `validate_video.py` flow.

## 2026-05-02: AI-Only Active Learning / VLM Audit Foundation

Goal mode was used for this work. The active goal is to add the foundation for AI-only active learning and VLM audit without changing runtime counting behavior.

New doctrine:

```text
docs/06_AI_ONLY_ACTIVE_LEARNING_PIPELINE.md
```

Boundary:

```text
Live Runtime Total remains YOLO/event-based app counting.
Teacher/VLM/Moondream/Lens outputs are advisory.
Human/VA review is optional and after-the-fact.
No cloud calls by default.
No self-training mid-shift.
No teacher labels as validation truth.
```

New schemas:

```text
validation/schemas/event_evidence.schema.json
validation/schemas/teacher_label.schema.json
validation/schemas/review_label.schema.json
validation/schemas/active_learning_dataset.schema.json
```

New scripts:

```bash
.venv/bin/python scripts/extract_event_windows.py --case-id img3254_clean22_candidate --output data/reports/active_learning/img3254_event_evidence.v1.json --force
.venv/bin/python scripts/teacher_generate_labels.py --evidence data/reports/active_learning/img3254_event_evidence.v1.json --output data/reports/active_learning/img3254_teacher_labels.dry_run_v1.json --force
.venv/bin/python scripts/check_dataset_poisoning.py --teacher-labels data/reports/active_learning/img3254_teacher_labels.dry_run_v1.json
```

Guardrail:

```text
scripts/validate_video.py
scripts/register_test_case.py
```

Both now call `scripts/validation_truth_guard.py` so raw teacher/VLM artifacts cannot be used as `truth.truth_ledger_path` in validation manifests.

Verification:

```text
Initial `python -m pytest ...` used /Users/thomas/.browser-use-env/bin/python and failed because pytest is not installed there.
Repo venv checks passed.
```

Passed:

```bash
.venv/bin/python -m pytest tests/test_validation_registry_schema.py tests/test_validate_video.py tests/test_register_test_case.py -q
.venv/bin/python -m pytest tests/test_active_learning*.py tests/test_teacher_label*.py tests/test_dataset_poisoning*.py -q
.venv/bin/python -m pytest tests/ -q
make validate-video
.venv/bin/python scripts/extract_event_windows.py --case-id img3254_clean22_candidate --output /tmp/img3254_event_evidence.v1.json --include-negatives --negative-count 1 --force
.venv/bin/python scripts/teacher_generate_labels.py --evidence /tmp/img3254_event_evidence.v1.json --output /tmp/img3254_teacher_labels.dry_run_v1.json --force
.venv/bin/python scripts/check_dataset_poisoning.py --teacher-labels /tmp/img3254_teacher_labels.dry_run_v1.json
```

Results:

```text
13 focused validation tests passed.
8 focused active-learning tests passed.
358 full-suite tests passed, warnings only.
make validate-video dry-run passed for img3254_clean22_candidate.
Current registered-case extraction smoke produced 23 evidence windows and 23 dry-run teacher labels.
```

## 2026-05-02: Moondream Local Audit Slice

Moondream is now wired as an offline/local advisory audit path, not runtime authority.

New behavior:

```text
scripts/extract_event_windows.py can optionally extract per-window review-frame JPEGs.
scripts/moondream_audit_events.py can emit dry-run labels or call local Moondream Station.
Moondream Station endpoint defaults to http://127.0.0.1:2020/v1.
Nonlocal endpoints are refused unless explicitly allowed by a future caller.
All Moondream audit labels are bronze/pending and validation_truth_eligible=false.
```

Commands:

```bash
.venv/bin/python scripts/extract_event_windows.py \
  --case-id img3254_clean22_candidate \
  --extract-review-frames \
  --output data/reports/active_learning/img3254_event_evidence.v1.json \
  --force

.venv/bin/python scripts/moondream_audit_events.py \
  --evidence data/reports/active_learning/img3254_event_evidence.v1.json \
  --provider moondream_station \
  --endpoint http://127.0.0.1:2020/v1 \
  --output data/reports/active_learning/img3254_moondream_audit.local_v1.json \
  --force
```

The dry-run provider is still the default and requires no Moondream process:

```bash
.venv/bin/python scripts/moondream_audit_events.py \
  --evidence data/reports/active_learning/img3254_event_evidence.v1.json \
  --provider dry_run_fixture \
  --output data/reports/active_learning/img3254_moondream_audit.dry_run_v1.json \
  --force
```

Verification:

```text
Focused active-learning/Moondream tests: 12 passed.
Combined focused validation/active-learning tests: 25 passed.
Full Python suite: 362 passed, warnings only.
make validate-video: passed.
IMG_3254 CLI smoke extracted 22 review-frame windows to /tmp and generated 22 dry-run Moondream audit labels.
check_dataset_poisoning accepted the dry-run audit file as teacher labels only.
 No local Moondream Station was running on 127.0.0.1:2020.
 `moondream-station` was not on PATH and the repo .venv does not currently have the `moondream` package.
 No real Moondream inference was executed in this pass.
```

## 2026-05-01: IMG_3254 Real-App Candidate Verified

`demo/IMG_3254.MOV` is verified as a real-app candidate under clean-cycle truth `22`. It is not promoted to a numbered test case.

Video:

```text
Source copy: demo/IMG_3254.MOV
SHA-256: f9b72e2a48e96f1f008a0b750504fde13c8ea43ab62f562bacd715c5b19b19cd
Duration: 1280.516667s
```

Truth rule:

```text
Clean-cycle truth: 22 (locked)
- Excludes the placement already in progress at frame 0.

Operational truth: 23 (context only)
- Includes the in-progress-at-start placement if completion after frame 0 is visible.
```

Decision evidence:

```text
data/videos/review_frames/img3254_start_truth_decision_sheet.jpg
data/reports/img3254_truth_rule_decision_packet.v1.json
data/reports/img3254_completion_audit.blocked_v1.json

At 0.0s the worker is already bent over the output pallet with a placement in progress.
By roughly 8-12s the worker has moved away from that opener.
That opener belongs only in the operational 23 rule; clean-cycle 22 excludes it because it began before frame 0.
```

Verified settings:

```text
Model: models/img3254_active_panel_v4_yolov8n.pt
Runtime calibration: none
YOLO confidence: 0.25
Processing FPS: 10
Reader FPS: 10
Event detection cluster distance: 250
Event track min frames: 12
Event track max age: 52
Playback speed for proof: 1
Observed events: data/reports/img3254_app_observed_events.run8092.active_panel_v4_yolov8n_conf025_cluster250_age52_min12.visible_dashboard_1x_clean22_v1.json
Result: observed_event_count 22, DEMO_COMPLETE, coverage_end 1280.417s
Focused review packet: data/videos/review_frames/img3254_candidate_events_v1/manifest.json
```

Primary proof artifacts:

```text
data/reports/img3254_human_truth_event_times.clean_cycle_v1.csv
data/reports/img3254_human_truth_total.clean_cycle_v1.json
data/reports/img3254_human_truth_ledger.clean_cycle_v1.json
data/reports/img3254_app_vs_human_total.run8092.active_panel_v4_yolov8n_conf025_cluster250_age52_min12.visible_dashboard_1x_clean22_v1.json
data/reports/img3254_app_vs_truth.run8092.active_panel_v4_yolov8n_conf025_cluster250_age52_min12.visible_dashboard_1x_clean22_v1.json
data/reports/img3254_wall_source_pacing.run8092.active_panel_v4_yolov8n_conf025_cluster250_age52_min12.visible_dashboard_1x_clean22_v1.json
data/reports/img3254_completion_audit.verified_clean22_v1.json
```

Expected comparison:

```text
matched_count: 22
missing_truth_count: 0
unexpected_observed_count: 0
first_divergence: null
wall_per_source: 1.000000154
```

Dashboard evidence:

```text
data/reports/screenshots/img3254_dashboard_visible_start_clean22_1x_v1.png
data/reports/screenshots/img3254_dashboard_visible_after_click_clean22_1x_v1.png
data/reports/screenshots/img3254_dashboard_visible_mid_clean22_1x_v1.png
data/reports/screenshots/img3254_dashboard_visible_end_clean22_1x_v1.png
```

Why this candidate:

```text
- v4 max_age=40 produced 24 events from two duplicate split windows around 470/487s and 614/629s.
- Track-window review showed the split gaps are narrow:
  - first split last_seen 466.797s, successor start 472.097s
  - second split last_seen 610.206s, successor start 614.707s
- max_age=52 merges those fragments without the rejected max_age=180 timing delay.
- max_age=180 also totals 22 but should not be used as final proof unless timing is separately proven clean.
- v5 overcounted/broadened, v6 overfragmented, v7 undercounted.
```

Re-run command:

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

## 2026-05-01: Factory2 Real-Time App Path Verified

Alias:

```text
Test Case 1 = verified Factory2 investor demo
```

If Thomas says `run test case 1`, launch:

```bash
cd /Users/thomas/Projects/Factory-Output-Vision-MVP
.venv/bin/python scripts/start_factory2_demo_stack.py --backend-port 8091 --frontend-port 5173
```

Then open:

```text
http://127.0.0.1:5173/dashboard
```

The Factory2 investor-demo path now works in the actual app at true real-time speed.

This is the current trusted state:

```text
Video:
- data/videos/from-pc/factory2.MOV

Runtime/app path:
- real FastAPI + VisionWorker app path
- `FC_DEMO_COUNT_MODE=live_reader_snapshot`
- `FC_COUNTING_MODE=event_based`
- one-pass demo source, no loop
- ordered real processed frames
- backend-counted MJPEG/dashboard stream
- Chrome dashboard visible run

Result:
- Runtime Total visibly climbs
- final dashboard state: Demo complete
- final dashboard Runtime Total: 23
- human truth comparison: 23/23
- real-time ratio: wall_per_source = 1.0
```

Primary verification artifacts:

```text
data/reports/factory2_app_observed_events.run8104.visible_dashboard_v1.json
data/reports/factory2_app_vs_truth.run8104.visible_dashboard_v1.json
```

Expected comparison:

```text
matched_count: 23
missing_truth_count: 0
unexpected_observed_count: 0
first_divergence: null
```

Supporting source-clock backend artifact:

```text
data/reports/factory2_app_observed_events.run8103.sourceclock_10fps_v1.json
data/reports/factory2_app_vs_truth.run8103.sourceclock_10fps_v1.json
```

Important implementation lessons:

```text
- Source-clock pacing fixed the last speed problem. File-backed live demos must pace to frame source timestamps, not fixed sleep after processing.
- Local crop-based live separation cut hot-path cost without changing count semantics.
- Fractional frame sampling is now honest for non-divisor FPS values, but 9.5 FPS failed truth comparison and is not promoted.
- The dev dashboard must proxy API calls through Vite. Direct cross-origin calls can execute backend actions while leaving diagnostics stale with `Failed to fetch`.
- The visible dashboard source must be the backend-counted frame stream, not a separate browser video clock.
```

Verified launch paths:

```bash
cd /Users/thomas/Projects/Factory-Output-Vision-MVP
.venv/bin/python scripts/start_factory2_demo_app.py --port 8091
```

Optional backend + frontend stack:

```bash
cd /Users/thomas/Projects/Factory-Output-Vision-MVP
.venv/bin/python scripts/start_factory2_demo_stack.py --backend-port 8091 --frontend-port 5173
```

Then open:

```text
http://127.0.0.1:5173/dashboard
```

Reset/restart for a clean visible run:

```bash
curl -X POST http://127.0.0.1:8091/api/control/reset_counts
curl -X POST http://127.0.0.1:8091/api/control/restart_video
```

Then click `Start monitoring`.

Honest claim boundary:

```text
This proves the real app can count Factory2-style frames at 1.0x from a file-backed live source.
It does not yet prove Reolink/RTSP field operation until the same path is validated on an actual live camera stream.
Do not claim Reolink works yet.
```

Next video candidates:

```text
data/videos/from-pc/real_factory.MOV  (~29.5 min, 1920x1080 HEVC)
data/videos/from-pc/IMG_2628.MOV      (~27.8 min, 1920x1080 HEVC)
demo/IMG_3262.MOV                     (~15.8 min, 1920x1080 HEVC)
```

Use these as the current demo records:

```text
docs/FACTORY2_REALTIME_APP_VALIDATION.md
docs/FACTORY2_INVESTOR_DEMO_RUNBOOK.md
```

## 2026-04-29: Factory2 Synthetic Count Authority Hardened

Implemented the next honest Factory2 slice after the runtime/proof divergence audit:

```text
app/services/count_state_machine.py
app/services/runtime_event_counter.py
scripts/audit_factory2_runtime_events.py
scripts/build_factory2_synthetic_lineage_report.py
scripts/build_factory2_final_gap_search_plan.py
tests/test_count_state_machine.py
tests/test_runtime_event_counter.py
tests/test_audit_factory2_runtime_events.py
tests/test_build_factory2_synthetic_lineage_report.py
tests/test_build_factory2_final_gap_search_plan.py
AGENTS.md
CLAUDE.md
tasks/lessons.md
docs/superpowers/plans/2026-04-29-factory2-synthetic-lineage-convergence.md
```

What changed:

```text
- Added `count_authority` to `CountEvent` with:
  - `source_token_authorized`
  - `runtime_inferred_only`
- Synthetic `approved_delivery_chain` events no longer mint fake source-token evidence from the output bbox.
- `CountStateMachine` now tracks:
  - `source_token_authorized_event_count`
  - `runtime_inferred_only_event_count`
- Runtime audit rows now emit:
  - `count_authority`
  - `predecessor_chain_track_ids`
  - source/output observation counts
- Added a synthetic-lineage report that classifies runtime approved-chain events by proof overlap and source-gap behavior.
- Fixed the final-gap search planner so unresolved proof gaps use source-history-driven windows instead of arbitrary short lead windows.
```

Real artifacts created:

```text
Reports:
- data/reports/factory2_synthetic_lineage_report.lineage_0_430.v1.json
- data/reports/factory2_final_gap_search_plan.v2.json
- data/reports/factory2_final_gap_search_run.v2.event0007.json
- data/reports/factory2_final_gap_search_report.v2.event0007.json
- data/reports/factory2_final_gap_search_run.v2.event0008.json
- data/reports/factory2_final_gap_search_report.v2.event0008.json
- data/reports/factory2_final_gap_search_summary.v2.json
- data/reports/factory2_count_authority_ledger.v1.json

Targeted post-hardening runtime audits:
- data/reports/factory2_runtime_event_audit.lineage_280_308.v4.json
- data/reports/factory2_runtime_event_audit.lineage_398_427.v4.json
```

Current truthful state:

```text
Runtime/app path:
- still operationally counts Factory2 to the human truth target of 23

Proof path:
- remains at accepted_count = 21

Authority ledger:
- runtime_inferred_total: 23
- proof_accepted_total: 21
- inherited_live_source_token_count: 11
- synthetic_with_overlapping_proof_count: 10
- synthetic_without_distinct_proof_count: 2
- unresolved runtime-inferred-only timestamps:
  - 305.708s
  - 425.012s
```

Why this matters:

```text
The repo now distinguishes operational runtime counts from source-token-backed proof authority.
The remaining two proof gaps are no longer “maybe more window tuning” cases:
- both corrected source-history-driven rescue searches still collapsed into
  `shared_source_lineage_no_distinct_proof_receipt`
- Oracle explicitly recommended preserving runtime 23 / proof 21 as the honest state on current evidence
- the right hardening move was to stop fabricating source-token-shaped evidence for synthetic runtime counts
```

Oracle result:

```text
Oracle slug: factory2-synthetic-next-step

Recommendation:
- preserve runtime 23 / proof 21 as the honest state
- do not keep tuning proof windows for 305.708s / 425.012s
- harden semantics so synthetic approved-chain events are runtime-inferred only,
  not source-token-backed proof authority

That recommendation is now reflected in code and doctrine.
```

Commands run:

```bash
.venv/bin/python -m pytest tests/test_build_factory2_synthetic_lineage_report.py -q
.venv/bin/python -m pytest tests/test_build_factory2_final_gap_search_plan.py -q
.venv/bin/python scripts/build_factory2_synthetic_lineage_report.py --runtime-audit data/reports/factory2_runtime_event_audit.lineage_0_430.v2.json --proof-report data/reports/factory2_morning_proof_report.optimized_plus_runtime_lineage_v2.json --divergence data/reports/factory2_proof_runtime_divergence.final_two_v2.json --output data/reports/factory2_synthetic_lineage_report.lineage_0_430.v1.json --force
.venv/bin/python scripts/build_factory2_final_gap_search_plan.py --packets data/reports/factory2_runtime_event_receipt_packets.optimized_plus_0016_0019_v1.json --lineage-report data/reports/factory2_synthetic_lineage_report.lineage_0_430.v1.json --output data/reports/factory2_final_gap_search_plan.v2.json --lead-seconds 4 --lead-seconds 6 --lead-seconds 8 --lead-seconds 10 --lead-seconds 12 --tail-seconds 2 --tail-seconds 3 --tail-seconds 4 --tail-seconds 6 --fps 5 --fps 8 --fps 10 --force
.venv/bin/python scripts/run_factory2_final_gap_search.py --plan data/reports/factory2_final_gap_search_plan.v2.json --output data/reports/factory2_final_gap_search_run.v2.event0007.json --event-id factory2-runtime-only-0007 --video data/videos/from-pc/factory2.MOV --calibration data/calibration/factory2_ai_only_v1.json --model models/panel_in_transit.pt --person-model yolo11n.pt --force
.venv/bin/python scripts/build_factory2_final_gap_search_report.py --search-run data/reports/factory2_final_gap_search_run.v2.event0007.json --output data/reports/factory2_final_gap_search_report.v2.event0007.json --force
.venv/bin/python scripts/run_factory2_final_gap_search.py --plan data/reports/factory2_final_gap_search_plan.v2.json --output data/reports/factory2_final_gap_search_run.v2.event0008.json --event-id factory2-runtime-only-0008 --video data/videos/from-pc/factory2.MOV --calibration data/calibration/factory2_ai_only_v1.json --model models/panel_in_transit.pt --person-model yolo11n.pt --force
.venv/bin/python scripts/build_factory2_final_gap_search_report.py --search-run data/reports/factory2_final_gap_search_run.v2.event0008.json --output data/reports/factory2_final_gap_search_report.v2.event0008.json --force
.venv/bin/python -m pytest tests/test_count_state_machine.py tests/test_runtime_event_counter.py tests/test_audit_factory2_runtime_events.py tests/test_build_factory2_synthetic_lineage_report.py tests/test_build_factory2_final_gap_search_plan.py tests/test_run_factory2_final_gap_search.py tests/test_build_factory2_final_gap_search_report.py tests/test_build_factory2_runtime_lineage_diagnostic.py tests/test_build_morning_proof_report.py -q
.venv/bin/python scripts/audit_factory2_runtime_events.py --video data/videos/from-pc/factory2.MOV --calibration data/calibration/factory2_ai_only_v1.json --model models/panel_in_transit.pt --output data/reports/factory2_runtime_event_audit.lineage_280_308.v4.json --start-seconds 280 --end-seconds 308 --processing-fps 10 --include-track-histories --force
.venv/bin/python scripts/audit_factory2_runtime_events.py --video data/videos/from-pc/factory2.MOV --calibration data/calibration/factory2_ai_only_v1.json --model models/panel_in_transit.pt --output data/reports/factory2_runtime_event_audit.lineage_398_427.v4.json --start-seconds 398 --end-seconds 427 --processing-fps 10 --include-track-histories --force
oracle --slug factory2-synthetic-next-step ...
```

Verification:

```text
54 tests passed on the affected suite after the hardening change.
Targeted runtime audit around ~305.7s now emits:
- provenance_status = synthetic_approved_chain_token
- count_authority = runtime_inferred_only
- source_token_id = null
- source_bbox = null

Targeted runtime audit around ~425.0s now emits:
- provenance_status = synthetic_approved_chain_token
- count_authority = runtime_inferred_only
- source_token_id = null
- source_bbox = null

Corrected 5/8/10fps rescue searches for both remaining proof gaps all still scored:
- shared_source_lineage_no_distinct_proof_receipt
```

Next blocker:

```text
There is no remaining honest proof-window tuning move on current evidence.
The remaining blocker is product semantics / product presentation:
- what user-facing number should represent proof-backed counts
- whether the product needs to expose the runtime/proof split directly
```

Exact next recommended step:

```text
Do not keep tuning proof windows for 305.708s / 425.012s.
If product semantics matter next, thread `count_authority` through the event ledger / API layer and expose:
- runtime inferred total
- proof-backed total
- unresolved runtime-inferred-only count
```

## 2026-04-29: Factory2 Runtime Lineage Audit Closed The Final Two

Implemented the runtime-lineage audit path Oracle asked for and used it to settle the two remaining proof/runtime gaps:

```text
app/services/count_state_machine.py
app/services/runtime_event_counter.py
scripts/audit_factory2_runtime_events.py
scripts/build_factory2_runtime_lineage_diagnostic.py
scripts/build_morning_proof_report.py
tests/test_count_state_machine.py
tests/test_audit_factory2_runtime_events.py
tests/test_build_factory2_runtime_lineage_diagnostic.py
tests/test_build_morning_proof_report.py
AGENTS.md
CLAUDE.md
tasks/lessons.md
```

What changed:

```text
- Added explicit runtime source-token provenance to `CountEvent`.
- `approved_delivery_chain` events now distinguish `inherited_live_source_token` from `synthetic_approved_chain_token`.
- Extended the runtime audit script to emit source-token provenance and full per-track histories.
- Added a runtime-lineage diagnostic builder that can turn audited runtime events into proof-style receipts.
- Guarded the runtime-lineage proof builder so synthetic approved-chain fallback events are rejected instead of being promoted into proof.
```

Real artifacts created:

```text
Runtime provenance audits:
- data/reports/factory2_runtime_event_audit.lineage_0_308.json
- data/reports/factory2_runtime_event_audit.lineage_0_430.v2.json

Runtime-lineage diagnostics:
- data/diagnostics/runtime-proof/factory2-runtime-only-0007-lineage-v2/diagnostic.json
- data/diagnostics/runtime-proof/factory2-runtime-only-0008-lineage-v1/diagnostic.json

Proof artifacts:
- data/reports/factory2_morning_proof_report.optimized_plus_runtime_lineage_v2.json
- data/reports/factory2_proof_runtime_divergence.final_two_v2.json
```

Final result from the lineage audit:

```text
Runtime/app path:
- still reaches 23 on the patched from-start audit

Proof path:
- remains at accepted_count = 21

Why proof stays at 21:
- `305.708s` -> provenance_status = synthetic_approved_chain_token
- `425.012s` -> provenance_status = synthetic_approved_chain_token

Conclusion:
- both remaining runtime-only events are runtime-discovered counts,
- but they are not honest proof receipts,
- so the correct repo state is runtime 23 / proof 21.
```

Oracle result:

```text
Oracle confirmed the right move was from-start runtime provenance, not more proof-window threshold/fps tweaks.
It also specifically warned that synthetic approved-chain fallback tokens are not proof-eligible.
That warning held up against the real patched lineage artifact.
```

Commands run:

```bash
.venv/bin/python -m pytest tests/test_count_state_machine.py tests/test_audit_factory2_runtime_events.py tests/test_build_factory2_runtime_lineage_diagnostic.py tests/test_build_morning_proof_report.py -q
.venv/bin/python scripts/audit_factory2_runtime_events.py --video data/videos/from-pc/factory2.MOV --calibration data/calibration/factory2_ai_only_v1.json --model models/panel_in_transit.pt --output data/reports/factory2_runtime_event_audit.lineage_0_308.json --start-seconds 0 --end-seconds 308 --processing-fps 10 --include-track-histories --force
.venv/bin/python scripts/audit_factory2_runtime_events.py --video data/videos/from-pc/factory2.MOV --calibration data/calibration/factory2_ai_only_v1.json --model models/panel_in_transit.pt --output data/reports/factory2_runtime_event_audit.lineage_0_430.v2.json --start-seconds 0 --end-seconds 430 --processing-fps 10 --include-track-histories --force
.venv/bin/python - <<'PY'
# built runtime-lineage diagnostics for 305.708s and 425.012s from the 0-430 audit
PY
.venv/bin/python - <<'PY'
# rebuilt proof report with both runtime-lineage diagnostics included
PY
/opt/homebrew/bin/oracle --slug factory2-lineage-path ...
```

Verification:

```text
28 tests passed on the touched suites.
Patched runtime-lineage audit to 430s finished at final_count = 23.
Both runtime-lineage diagnostics now reject synthetic fallback counts.
Rebuilt proof report stayed at accepted_count = 21.
```

Next blocker:

```text
There is no remaining proof-window tuning blocker. The remaining blocker is product semantics:
- either accept runtime 23 / proof 21 as the honest state,
- or change the runtime approved-delivery-chain policy so synthetic fallback tokens no longer create runtime-only count authority.
```

Exact next recommended step:

```text
Do not spend more time on narrower proof windows. If the product needs proof and runtime to converge, refactor `commit_approved_delivery_chain` so `synthetic_approved_chain_token` is either disallowed for counting or separated into an explicit runtime-only category with different product semantics.
```


## Factory2 crop review package + training interface — 2026-04-28 21:06 EDT

Implemented the next labeling/training slice:

```text
scripts/package_factory2_crop_review.py
scripts/build_factory2_crop_training_dataset.py
tests/test_package_factory2_crop_review.py
tests/test_build_factory2_crop_training_dataset.py
docs/PRD_FACTORY2_RECALL_AND_CROP_SEPARATION.md
tasks/lessons.md
```

What changed:

```text
- Added a label-ready crop review packager that turns the frozen blocked-crop dataset into a flat image bundle plus manifest, writable CSV, classes list, and README for local review or later private Roboflow upload.
- Review items are ranked by labeling priority:
  - `p0_candidate_salvage`
  - `p1_visibility_review`
  - `p2_negative_confirmation`
  - `p3_positive_boundary`
- Added a deterministic crop-training dataset builder that consumes the package manifest plus review CSV and emits a classifier-oriented dataset manifest with track-level train/val/test grouping.
- The training manifest records explicit integration targets back into the proof/runtime gate and reports whether the label set is actually ready for a second-stage model.
```

Real artifacts created:

```text
Review package:
- data/reports/factory2_crop_review_package.narrow_frozen_v2.json
- data/datasets/factory2_crop_review_package_narrow_frozen_v2/

Current review-package counts:
- total items: 218
- p0_candidate_salvage: 90
- p1_visibility_review: 1
- p2_negative_confirmation: 32
- p3_positive_boundary: 95

Training interface artifact:
- data/reports/factory2_crop_training_dataset.narrow_frozen_v2.json
- data/datasets/factory2_crop_training_dataset_narrow_frozen_v2/

Current training-interface status from placeholder labels:
- eligible_item_count: 95
- skipped_unclear_count: 123
- label_counts: carried_panel=95
- missing_classes: worker_only, static_stack
- ready_for_training: false
```

Why this matters:

```text
The repo no longer stops at “we should label crops.” It now has the full label handoff and the immediate model-ingest contract on disk. The blocker is explicit and auditable: the current package still lacks reviewed `worker_only` and `static_stack` labels, so training would be premature.
```

Commands run:

```bash
.venv/bin/python -m pytest tests/test_package_factory2_crop_review.py tests/test_build_factory2_crop_training_dataset.py -q
.venv/bin/python -m py_compile scripts/package_factory2_crop_review.py scripts/build_factory2_crop_training_dataset.py tests/test_package_factory2_crop_review.py tests/test_build_factory2_crop_training_dataset.py
.venv/bin/python -m pytest tests/test_diagnose_event_window.py tests/test_analyze_person_panel_separation.py tests/test_run_factory2_morning_proof.py tests/test_build_morning_proof_report.py tests/test_export_factory2_blocked_crops.py tests/test_package_factory2_crop_review.py tests/test_build_factory2_crop_training_dataset.py -q
.venv/bin/python scripts/package_factory2_crop_review.py --crop-dataset-report data/reports/factory2_blocked_crop_dataset.narrow_frozen_v2.json --output-report data/reports/factory2_crop_review_package.narrow_frozen_v2.json --package-dir data/datasets/factory2_crop_review_package_narrow_frozen_v2 --force
.venv/bin/python scripts/build_factory2_crop_training_dataset.py --review-package-report data/reports/factory2_crop_review_package.narrow_frozen_v2.json --output-report data/reports/factory2_crop_training_dataset.narrow_frozen_v2.json --dataset-dir data/datasets/factory2_crop_training_dataset_narrow_frozen_v2 --force
```

Verification:

```text
40 tests passed
py_compile passed
real review package exists on disk
real training-interface report exists on disk and correctly reports not-ready status until blocked crops are labeled
```

Next blocker:

```text
The blocker is now externalized to label truth, not pipeline code. The repo needs reviewed labels for the 90 `p0_candidate_salvage` crops first, then `p2_negative_confirmation`, so the second-stage crop classifier has both positive and negative classes.
```

Exact next recommended step:

```text
Open `data/datasets/factory2_crop_review_package_narrow_frozen_v2/review_labels.csv`, label the `p0_candidate_salvage` rows first as `carried_panel | worker_only | static_stack`, rerun `scripts/build_factory2_crop_training_dataset.py`, and do not start model training until `ready_for_training` flips true.
```


## Factory2 blocked crop dataset export — 2026-04-28 20:16 EDT

Implemented the next recall-training slice:

```text
scripts/export_factory2_blocked_crops.py
tests/test_export_factory2_blocked_crops.py
```

What changed:

```text
- Added a crop exporter that reads the frozen merged proof report decision receipt index and emits a label-ready dataset manifest plus copied crop assets.
- Blocked worker-overlap receipts are exported as `blocked_worker_overlap`.
- Canonical accepted carries are also exported as `accepted_positive_boundary` so the future training set has both sides of the decision boundary.
- Each exported crop item preserves provenance: diagnostic/window, track id, timestamp, zone, gate decision/reason, person overlap, outside-person ratio, separation recommendation, receipt paths, and a label placeholder.
```

Real artifact created:

```text
Manifest:
- data/reports/factory2_blocked_crop_dataset.narrow_frozen_v2.json

Dataset directory:
- data/datasets/factory2_blocked_crops_narrow_frozen_v2/

Counts:
- blocked_track_count: 29
- blocked_crop_count: 123
- positive_track_count: 12
- positive_crop_count: 95
- total exported items: 218
```

Why this matters:

```text
The next blocker is no longer missing crop plumbing. The repo now has a concrete, provenance-preserving dataset built directly from the frozen merged proof state. That makes panel-vs-worker labeling and second-stage training possible without hand-curating files from receipt directories.
```

Commands run:

```bash
.venv/bin/python -m pytest tests/test_diagnose_event_window.py tests/test_analyze_person_panel_separation.py tests/test_run_factory2_morning_proof.py tests/test_build_morning_proof_report.py tests/test_export_factory2_blocked_crops.py -q
.venv/bin/python -m py_compile scripts/export_factory2_blocked_crops.py tests/test_export_factory2_blocked_crops.py
.venv/bin/python scripts/export_factory2_blocked_crops.py --proof-report data/reports/factory2_morning_proof_report.narrow_frozen_v2.json --output-report data/reports/factory2_blocked_crop_dataset.narrow_frozen_v2.json --dataset-dir data/datasets/factory2_blocked_crops_narrow_frozen_v2 --force
```

Verification:

```text
36 tests passed
py_compile passed
real blocked crop dataset artifact exists on disk with copied crops and manifest
```

Next blocker:

```text
The remaining blocker is no longer exporter plumbing; it is turning the 123 blocked worker-overlap crops into labeled training evidence and then feeding that second-stage signal back into the proof/runtime gate.
```

Exact next recommended step:

```text
Label the highest-priority blocked crops first, starting with the frozen merged worker-overlap receipts that already have `countable_panel_candidate` person/panel recommendations but still failed the gate.
```


## Factory2 frozen narrow merged proof set + accepted dedupe — 2026-04-28 20:01 EDT

Implemented the next recall-proof slice:

```text
AGENTS.md
CLAUDE.md
scripts/freeze_factory2_diagnostics.py
scripts/build_morning_proof_report.py
scripts/run_factory2_morning_proof.py
tests/test_freeze_factory2_diagnostics.py
tests/test_build_morning_proof_report.py
tests/test_run_factory2_morning_proof.py
tasks/lessons.md
```

What changed:

```text
- Added `freeze_factory2_diagnostics.py` to copy selected diagnostic directories into an isolated frozen tree and rewrite all embedded JSON asset paths so merged proof runs stop mutating the shared source diagnostics.
- Added `--freeze-diagnostics-dir` support to `scripts/run_factory2_morning_proof.py`, and the run summary now records both source diagnostics and frozen diagnostics.
- Added report-layer accepted-receipt deduping: overlapping accepted receipts across windows now remain visible for audit, but only one canonical receipt per overlapping interval cluster contributes to the top-level `accepted_count`.
```

Real merged narrow-proof result:

```text
Frozen merged proof command completed on:
data/diagnostics/frozen/factory2-narrow-merged-v2

Raw accepted receipts: 13
Distinct accepted_count after overlap dedupe: 12
Suppressed_count: 27
Uncertain_count: 13
Verdict: accepted_positive_count_available

Artifacts:
- data/reports/factory2_morning_proof_report.narrow_frozen_v2.json
- data/reports/factory2_morning_proof_report.narrow_frozen_v2.md
- data/reports/factory2_transfer_review_packets.narrow_frozen_v2.json
- data/reports/factory2_person_panel_separation.narrow_frozen_v2.json
```

Per-window accepted counts in the frozen merged set:

```text
0–30s        -> 1
98s anchor   -> 1
145–185s     -> 1
222s window  -> 2
232–272s     -> 2
288–328s     -> 1
332–372s     -> 1
372–412s     -> 2
418s tail    -> 2 raw receipts, but one overlaps the 372–412 accepted carry and is deduped out of the top-level total
```

Exact duplicate that was removed from the top-level accepted total:

```text
Canonical kept:
- factory2-review-0011-372-412s-panel-v1-5fps track 2
- timestamps: 387.3–402.1

Duplicate kept only as audit evidence:
- factory2-review-0005-418s-panel-v1 track 1
- timestamps: 398.081–402.081
```

Commands run:

```bash
.venv/bin/python -m pytest tests/test_build_morning_proof_report.py tests/test_freeze_factory2_diagnostics.py tests/test_run_factory2_morning_proof.py tests/test_diagnose_event_window.py tests/test_analyze_person_panel_separation.py tests/test_build_factory2_recall_work_queue.py tests/test_runtime_event_counter.py tests/test_person_panel_gate_promotion.py -q
.venv/bin/python -m py_compile scripts/build_morning_proof_report.py scripts/freeze_factory2_diagnostics.py scripts/run_factory2_morning_proof.py scripts/diagnose_event_window.py scripts/analyze_person_panel_separation.py scripts/build_factory2_recall_work_queue.py app/services/runtime_event_counter.py app/services/person_panel_gate_promotion.py tests/test_build_morning_proof_report.py tests/test_freeze_factory2_diagnostics.py tests/test_run_factory2_morning_proof.py tests/test_diagnose_event_window.py tests/test_analyze_person_panel_separation.py tests/test_build_factory2_recall_work_queue.py tests/test_runtime_event_counter.py tests/test_person_panel_gate_promotion.py
.venv/bin/python scripts/run_factory2_morning_proof.py --force --report-json data/reports/factory2_morning_proof_report.narrow_frozen_v2.json --report-md data/reports/factory2_morning_proof_report.narrow_frozen_v2.md --run-summary-json data/reports/factory2_morning_proof_run_summary.narrow_frozen_v2.json --panel-crop-evidence-json data/reports/factory2_panel_crop_evidence.narrow_frozen_v2.json --transfer-review-packets-json data/reports/factory2_transfer_review_packets.narrow_frozen_v2.json --person-panel-separation-json data/reports/factory2_person_panel_separation.narrow_frozen_v2.json --freeze-diagnostics-dir data/diagnostics/frozen/factory2-narrow-merged-v2 --diagnostic data/diagnostics/event-windows/factory2-review-0014-000-030s-panel-v1-5fps/diagnostic.json --diagnostic data/diagnostics/event-windows/factory2-event0002-98s-panel-v4-protrusion-gated/diagnostic.json --diagnostic data/diagnostics/event-windows/factory2-review-0012-145-185s-panel-v1-5fps/diagnostic.json --diagnostic data/diagnostics/event-windows/factory2-review-0002-222s-panel-v1/diagnostic.json --diagnostic data/diagnostics/event-windows/factory2-review-0008-232-272s-panel-v1-5fps/diagnostic.json --diagnostic data/diagnostics/event-windows/factory2-review-0010-288-328s-panel-v1-5fps/diagnostic.json --diagnostic data/diagnostics/event-windows/factory2-review-0009-332-372s-panel-v1-5fps/diagnostic.json --diagnostic data/diagnostics/event-windows/factory2-review-0011-372-412s-panel-v1-5fps/diagnostic.json --diagnostic data/diagnostics/event-windows/factory2-review-0005-418s-panel-v1/diagnostic.json
.venv/bin/python -m scripts.build_morning_proof_report --force --output data/reports/factory2_morning_proof_report.narrow_frozen_v2.json --markdown-output data/reports/factory2_morning_proof_report.narrow_frozen_v2.md --fp-report data/eval/detector_false_positives/active_panel_hard_negatives_v1_panel_in_transit_conf025.json --fp-report data/eval/detector_false_positives/active_panel_hard_negatives_v1_panel_in_transit_conf010.json --positive-report data/eval/detector_positives/active_panel_positives_v1_panel_in_transit_conf025_iou030.json --positive-report data/eval/detector_positives/active_panel_positives_v1_panel_in_transit_conf010_iou030.json --diagnostic data/diagnostics/frozen/factory2-narrow-merged-v2/factory2-review-0014-000-030s-panel-v1-5fps/diagnostic.json --diagnostic data/diagnostics/frozen/factory2-narrow-merged-v2/factory2-event0002-98s-panel-v4-protrusion-gated/diagnostic.json --diagnostic data/diagnostics/frozen/factory2-narrow-merged-v2/factory2-review-0012-145-185s-panel-v1-5fps/diagnostic.json --diagnostic data/diagnostics/frozen/factory2-narrow-merged-v2/factory2-review-0002-222s-panel-v1/diagnostic.json --diagnostic data/diagnostics/frozen/factory2-narrow-merged-v2/factory2-review-0008-232-272s-panel-v1-5fps/diagnostic.json --diagnostic data/diagnostics/frozen/factory2-narrow-merged-v2/factory2-review-0010-288-328s-panel-v1-5fps/diagnostic.json --diagnostic data/diagnostics/frozen/factory2-narrow-merged-v2/factory2-review-0009-332-372s-panel-v1-5fps/diagnostic.json --diagnostic data/diagnostics/frozen/factory2-narrow-merged-v2/factory2-review-0011-372-412s-panel-v1-5fps/diagnostic.json --diagnostic data/diagnostics/frozen/factory2-narrow-merged-v2/factory2-review-0005-418s-panel-v1/diagnostic.json
```

Verification:

```text
52 tests passed
py_compile passed
Frozen merged proof now has a stable immutable diagnostic namespace and a deduped distinct accepted count of 12
```

Next blocker:

```text
The immutable narrow proof set is now real and beats the old broad baseline, but it is still at 12 distinct carries vs the human truth target of 23. The next bottlenecks are:
- remaining worker-overlap suppressions/uncertains inside the frozen merged set
- missing true carries outside the current accepted set
- proof/runtime still not aligned to this 12-count merged proof path
```

Exact next recommended step:

```text
Implement `scripts/export_factory2_blocked_crops.py` and `tests/test_export_factory2_blocked_crops.py`
against `data/reports/factory2_morning_proof_report.narrow_frozen_v2.json`, starting with the
remaining worker-overlap receipts in the frozen merged set.
```


## Factory2 recall recovery + crop-separation next PRD — 2026-04-28 19:16 EDT

Implemented the next bounded slice after the first proof/runtime success:

```text
AGENTS.md
CLAUDE.md
docs/PROJECT_SPEC.md
docs/PRD_FACTORY2_RECALL_AND_CROP_SEPARATION.md
scripts/analyze_person_panel_separation.py
scripts/build_factory2_recall_work_queue.py
scripts/diagnose_event_window.py
tests/test_analyze_person_panel_separation.py
tests/test_build_factory2_recall_work_queue.py
tests/test_diagnose_event_window.py
tasks/lessons.md
```

What changed:

```text
- Increased representative receipt sampling from 3 snapshots to 9 evenly spaced observations for longer tracks, while keeping short tracks dense.
- Added receipt/gate tests proving split source-only predecessors can be merged into short source->output successors before perception gating, including multi-hop predecessor chains.
- Added a Factory2 recall work-queue builder that turns reviewed positive frame labels into cluster-level proof coverage targets.
- Wrote the next PRD: narrow-window recall recovery plus blocked crop export for panel-vs-worker separation training.
- Updated repo doctrine so the explicit target is now the human truth set of 23 carried-panel transfers with 0 false positives.
```

Real results gathered this slice:

```text
Broad resampled baseline:
- data/reports/factory2_morning_proof_report.candidate6_resampled.json
- accepted_count: 8
- suppressed_count: 41
- uncertain_count: 23

Focused narrow-window proof results already on disk:
- 0–30s: accepted_count 1
- 145–185s: accepted_count 1
- 232–272s: accepted_count 2
- 288–328s: accepted_count 1
- 332–372s: accepted_count 1
- 372–412s: accepted_count 2

Recall work queue:
- 8 reviewed positive Factory2 frames collapse into 5 likely transfer clusters
- current narrow proof windows cover all 5 reviewed-positive clusters
- the next gap is no longer obvious coverage holes; it is turning those covered windows into one immutable merged proof set that preserves the stronger narrow-window gains
```

Why this matters:

```text
The count architecture is no longer the mystery. The limiting factor is recall construction: broad mixed windows merge too much activity, while narrow windows plus denser receipts recover real carries. The next serious recall lever after window restructuring is a blocked-crop dataset for panel-vs-worker separation training on the exact worker-overlap misses.
```

Commands run:

```bash
.venv/bin/python -m pytest tests/test_diagnose_event_window.py tests/test_analyze_person_panel_separation.py -q
.venv/bin/python -m py_compile scripts/diagnose_event_window.py scripts/analyze_person_panel_separation.py tests/test_diagnose_event_window.py tests/test_analyze_person_panel_separation.py
.venv/bin/python scripts/build_factory2_recall_work_queue.py --force
```

Verification:

```text
19 tests passed
representative observation sampling now preserves 9-frame evidence on long tracks
receipt refresh/gate merge logic now has coverage for split predecessor chains
```

Next blocker:

```text
The repo still does not have one clean immutable merged proof set that rolls the stronger narrow-window gains together. Shared diagnostic directories were reused during merged proof attempts, which contaminated some combined reports while sidecars were still regenerating.
```

Exact next recommended step:

```bash
cd /Users/thomas/Projects/Factory-Output-Vision-MVP
.venv/bin/python scripts/build_factory2_recall_work_queue.py --force
```

Then freeze/copy the finalized narrow diagnostic directories, build one merged proof artifact from those immutable copies, and only after that start the blocked-crop export path in `docs/PRD_FACTORY2_RECALL_AND_CROP_SEPARATION.md`.


## Factory2 runtime/app path completion — live counting aligned with proof — 2026-04-28 14:37 EDT

Implemented the missing runtime-side commit path so Factory2 now works through the actual worker/app surface instead of only through the proof scripts:

```text
AGENTS.md
CLAUDE.md
app/services/runtime_event_counter.py
app/services/count_state_machine.py
app/workers/vision_worker.py
app/core/settings.py
app/api/routes.py
app/db/config_repo.py
app/db/event_repo.py
app/services/video_runtime.py
requirements.txt
tests/helpers.py
tests/test_runtime_event_counter.py
tests/test_count_state_machine_runtime_approval.py
tests/test_count_state_machine_adversarial.py
tests/test_settings_runtime.py
tests/test_vision_worker_states.py
tasks/lessons.md
```

What changed:

```text
- Added `RuntimeEventCounter` as the event-based runtime counter for calibrated Factory2 runs.
- The runtime counter now merges proof-grade source->output delivery evidence across split tracks and emits an explicit `approved_delivery_chain` commit instead of waiting for legacy output-settle/disappear semantics.
- `CountStateMachine` now supports idempotent proof-approved chain commits while still owning the count ledger and de-duplication.
- `VisionWorker` now routes calibrated `event_based` runs through the runtime counter, resets it correctly, and surfaces gate decisions in runtime debug artifacts.
- Settings/runtime compatibility fixes were kept in place for the live path used here, including calibrated event-based detector defaults.
- Local agent instructions now explicitly say Factory2 is not done until the actual runtime/app path counts `factory2.MOV`; proof-only success is not sufficient.
```

Real results:

```text
Proof path:
- verdict: accepted_positive_count_available
- accepted_count: 1
- suppressed_count: 11
- uncertain_count: 4
- accepted proof receipt: event0002 track 5

Live worker path on factory2.MOV (4x playback, full relevant span):
- counts_this_hour reached 1 at ~54.2s
- stayed at 1 through ~105.8s real time (~423s of video time), so the later event0006 proof window did not create an extra count

Live FastAPI/uvicorn app path:
- POST /api/control/monitor/start returned 200
- GET /api/status reached counts_this_hour: 1 at ~54.7s
- final status showed RUNNING_GREEN with counts_this_hour: 1
```

Why this matters:

```text
This closes the last real gap the user called out: Factory2 is no longer "working only in proof." The same carried-panel evidence that yields the accepted proof count now drives the actual runtime/app counter path, and the live app path was verified over HTTP instead of only through direct unit or worker harnesses.
```

Commands run:

```bash
.venv/bin/python -m pytest tests/test_build_panel_transfer_review_packets.py tests/test_analyze_panel_crop_evidence.py tests/test_run_factory2_morning_proof.py tests/test_analyze_person_panel_separation.py tests/test_runtime_event_counter.py tests/test_count_state_machine_runtime_approval.py tests/test_count_state_machine.py tests/test_count_state_machine_adversarial.py tests/test_vision_worker_states.py tests/test_settings_runtime.py tests/test_api_smoke.py tests/test_dashboard_contract.py -q
.venv/bin/python scripts/build_panel_transfer_review_packets.py --force
.venv/bin/python scripts/run_factory2_morning_proof.py --force
env FC_DB_PATH=/tmp/factory2-runtime-api.db FC_LOG_DIR=/tmp/factory2-runtime-api-logs FC_DEMO_MODE=1 FC_DEMO_VIDEO_PATH=/Users/thomas/Projects/Factory-Output-Vision-MVP/data/videos/from-pc/factory2.MOV FC_DEMO_PLAYBACK_SPEED=4 FC_COUNTING_MODE=event_based FC_RUNTIME_CALIBRATION_PATH=/Users/thomas/Projects/Factory-Output-Vision-MVP/data/calibration/factory2_ai_only_v1.json FC_YOLO_MODEL_PATH=/Users/thomas/Projects/Factory-Output-Vision-MVP/models/panel_in_transit.pt FC_PERSON_DETECT_ENABLED=1 ./.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8090
# then POST /api/control/monitor/start and poll GET /api/status until counts_this_hour becomes 1
```

Verification:

```text
55 tests passed
proof verdict: accepted_positive_count_available
proof accepted_count: 1
live worker run: count reached 1 and stayed there through the later proof window
live uvicorn/API run: counts_this_hour reached 1 through /api/status
```

Next blocker:

```text
No Factory2 blocker remains for the current definition of done. The remaining work is hardening: codify the slow live runtime/API verification into a reusable regression harness so future gate/runtime changes cannot silently reopen the proof/runtime gap.
```

Exact next recommended step:

```bash
cd /Users/thomas/Projects/Factory-Output-Vision-MVP
.venv/bin/python scripts/run_factory2_morning_proof.py --force
```

Then add an opt-in slow regression harness that boots the app in demo mode on `factory2.MOV`, starts monitoring over HTTP, asserts `counts_this_hour == 1`, and verifies the count does not rise again across the later event window.


## PRD Success-path completion — end-to-end diagnostic regeneration + gate refresh — 2026-04-28 13:30 EDT

Implemented the final proof-path consistency work needed to make the Factory2 success path real and repeatable:

```text
app/services/person_panel_gate_promotion.py
scripts/build_morning_proof_report.py
scripts/diagnose_event_window.py
scripts/run_factory2_morning_proof.py
tests/test_person_panel_gate_promotion.py
tests/test_diagnose_event_window.py
tests/test_run_factory2_morning_proof.py
docs/superpowers/plans/2026-04-28-factory2-end-to-end-person-panel-promotion.md
```

What changed:

```text
- Extracted the person/panel sidecar interpretation + worker-overlap promotion rule into shared service code.
- Added a diagnostic refresh path that rewrites `diagnostic.json`, `track_receipts/*.json`, and hard-negative manifests from existing gate rows plus sibling `*-person-panel-separation.json` receipts.
- Fixed two refresh bugs discovered during full proof runs:
  - explicit `outside_person_ratio: 0.0` is now preserved instead of being treated as missing;
  - refresh uses the existing diagnostic gate row as the baseline instead of recomputing a new protrusion decision from receipt payloads.
- The canonical proof command now rebuilds base event-window diagnostics from their own metadata, then rebuilds transfer packets, separation receipts, refreshes gate receipts, and finally emits the proof report.
```

Real proof result now:

```text
verdict: accepted_positive_count_available
accepted_count: 1
suppressed_count: 11
uncertain_count: 4
bottleneck: none
accepted receipt: event0002 track 5
accepted receipt person/panel separation: data/diagnostics/event-windows/factory2-event0002-98s-panel-v4-protrusion-gated/track_receipts/track-000005-person-panel-separation.json
event0002 diagnostic allowed tracks: [5]
event0006 diagnostic allowed tracks: []
```

Why this matters:

```text
This closes the prior proof-only gap. `scripts/run_factory2_morning_proof.py --force` now regenerates the base diagnostics, recomputes the packet/separation evidence, refreshes the on-disk diagnostic receipts, and lands on the same single accepted carried-panel count. The accepted `track-000005` receipt is now promoted by `strong_person_panel_separation` with `outside_person_ratio: 0.0`, which is exactly the auditable worker-overlap case the PRD was targeting.
```

Commands run:

```bash
.venv/bin/python -m pytest tests/test_build_panel_transfer_review_packets.py tests/test_analyze_panel_crop_evidence.py tests/test_run_factory2_morning_proof.py tests/test_analyze_person_panel_separation.py tests/test_build_morning_proof_report.py tests/test_perception_gate.py tests/test_diagnose_event_window.py tests/test_person_panel_gate_promotion.py -q
python -m py_compile app/services/person_panel_gate_promotion.py scripts/diagnose_event_window.py scripts/build_morning_proof_report.py scripts/run_factory2_morning_proof.py tests/test_person_panel_gate_promotion.py tests/test_diagnose_event_window.py tests/test_run_factory2_morning_proof.py
.venv/bin/python scripts/build_panel_transfer_review_packets.py --force
.venv/bin/python scripts/run_factory2_morning_proof.py --force
```

Verification:

```text
42 tests passed
proof verdict: accepted_positive_count_available
accepted_count: 1
suppressed_count: 11
uncertain_count: 4
accepted track set: only event0002 track 5
```

Next blocker:

```text
Factory2 itself is no longer blocked at the PRD level; the success path is achieved. The remaining product work is beyond this PRD: generalize the same proof discipline beyond the two curated event windows and expose the accepted-count path in the broader product surface instead of only the proof/report command.
```

Exact next recommended step:

```bash
cd /Users/thomas/Projects/Factory-Output-Vision-MVP
.venv/bin/python scripts/run_factory2_morning_proof.py --force
```

Then, if moving beyond the PRD, wire the same accepted-count receipt path into the broader counting/product entrypoint and add a held-out regression clip so future gate changes cannot reopen weak worker-overlap packets.


## PRD Milestone 4 start — proof-path gate promotion from person/panel separation — 2026-04-28 12:19 EDT

Implemented the first non-diagnostic promotion path for `factory2.MOV`:

```text
app/services/perception_gate.py
scripts/build_morning_proof_report.py
scripts/run_factory2_morning_proof.py
tests/test_perception_gate.py
tests/test_build_morning_proof_report.py
tests/test_run_factory2_morning_proof.py
```

What changed:

```text
- The perception gate now recognizes strong person/panel separation evidence as a valid override for coarse worker-body overlap, but only when the separation receipt says countable_panel_candidate and shows persistent multi-frame source/transfer evidence.
- The morning proof report now rehydrates worker-overlap gate rows from sibling `*-person-panel-separation.json` receipts and promotes only tracks that satisfy the stronger gate rule.
- The canonical proof command now auto-builds:
  - data/reports/factory2_transfer_review_packets.json
  - data/reports/factory2_person_panel_separation.json
  before rebuilding the final proof report.
- Accepted proof receipts now surface `person_panel_separation_path` directly in the decision receipt index.
```

Real proof result now:

```text
verdict: accepted_positive_count_available
accepted_count: 1
suppressed_count: 11
uncertain_count: 4
bottleneck: none
accepted receipt: event0002 track 5
accepted receipt person/panel separation: data/diagnostics/event-windows/factory2-event0002-98s-panel-v4-protrusion-gated/track_receipts/track-000005-person-panel-separation.json
```

Why this matters:

```text
This is the first proof run where factory2 morning evidence produces a real accepted count without lowering thresholds or counting from boxes/texture alone. The promotion is constrained to the one track whose separation receipt shows persistent silhouette-separated evidence; weaker packets remain suppressed/uncertain.
```

Commands run:

```bash
.venv/bin/python -m pytest tests/test_perception_gate.py tests/test_build_morning_proof_report.py -q
.venv/bin/python -m pytest tests/test_run_factory2_morning_proof.py -q
.venv/bin/python -m pytest tests/test_build_panel_transfer_review_packets.py tests/test_analyze_panel_crop_evidence.py tests/test_run_factory2_morning_proof.py tests/test_analyze_person_panel_separation.py tests/test_build_morning_proof_report.py tests/test_perception_gate.py -q
python -m py_compile app/services/perception_gate.py scripts/build_morning_proof_report.py scripts/run_factory2_morning_proof.py tests/test_perception_gate.py tests/test_build_morning_proof_report.py tests/test_run_factory2_morning_proof.py
.venv/bin/python scripts/run_factory2_morning_proof.py --force
```

Verification:

```text
29 tests passed
proof verdict: accepted_positive_count_available
accepted_count: 1
suppressed_count: 11
uncertain_count: 4
near-neighbor validation:
- event0002 track 2 → insufficient_visibility
- event0006 track 8 → insufficient_visibility
- event0006 track 6 → not_panel
```

Next blocker:

```text
The proof now cracks one carried-panel case, and nearby weaker packets did not promote, but the gate still relies on legacy stored event-window gate rows plus proof-time rehydration. The remaining product risk is end-to-end consistency: push the same separation-aware gate logic down into `scripts/diagnose_event_window.py` / live diagnostic generation so fresh diagnostics and proof replay share the same promotion path.
```

Exact next recommended step:

```bash
cd /Users/thomas/Projects/Factory-Output-Vision-MVP
.venv/bin/python -m pytest tests/test_diagnose_event_window.py tests/test_perception_gate.py tests/test_run_factory2_morning_proof.py -q
```

Then move the same separation-aware promotion rule into `scripts/diagnose_event_window.py` so regenerated event-window diagnostics can produce the accepted `track 5` count without relying on proof-time rehydration.


## PRD Milestone 3 start — person/panel separation diagnostics — 2026-04-28 11:27 EDT

Implemented the next bounded perception slice after transfer packets:

```text
scripts/analyze_person_panel_separation.py
tests/test_analyze_person_panel_separation.py
```

Purpose:

```text
transfer review packet + receipt observations
→ detect the overlapping person on sampled frames
→ estimate a conservative person silhouette
→ measure mesh-like evidence in panel-box regions outside that silhouette
→ emit diagnostic-only JSON + visual receipts
```

Generated on the bounded target:

```text
data/reports/factory2_person_panel_separation.json
data/diagnostics/event-windows/factory2-event0002-98s-panel-v4-protrusion-gated/track_receipts/track-000005-person-panel-separation.json
track-000005-person-panel-separation-frame_000060.png
track-000005-person-panel-separation-frame_000081.png
track-000005-person-panel-separation-frame_000100.png
```

What the first real slice says for `event0002 track 5`:

```text
packet_id: event0002-track000005
recommendation: countable_panel_candidate
diagnostic_only: true
packet_outside_person_ratio (old bbox signal): 0.0
frame_000060 visible_nonperson_ratio: 0.542531
frame_000081 visible_nonperson_ratio: 0.319453
frame_000100 visible_nonperson_ratio: 0.226362
```

Interpretation:

```text
This is still not a count approval and did not change the gate. It is the first auditable evidence slice showing silhouette-separated mesh-like signal on the top transfer packet even when the prior coarse packet metrics said outside_person_ratio=0.0. The current output is diagnostic-only and should be treated as a candidate receipt, not a minted source token.
```

Commands run:

```bash
.venv/bin/pip install pytest
.venv/bin/python -m pytest tests/test_analyze_person_panel_separation.py -q
.venv/bin/python -m pytest tests/test_build_panel_transfer_review_packets.py tests/test_analyze_panel_crop_evidence.py tests/test_run_factory2_morning_proof.py tests/test_analyze_person_panel_separation.py -q
python -m py_compile scripts/analyze_person_panel_separation.py tests/test_analyze_person_panel_separation.py
.venv/bin/python -m py_compile scripts/analyze_person_panel_separation.py tests/test_analyze_person_panel_separation.py
.venv/bin/python scripts/build_panel_transfer_review_packets.py --force
.venv/bin/python scripts/analyze_person_panel_separation.py --packet-id event0002-track000005 --force
.venv/bin/python scripts/run_factory2_morning_proof.py --force
```

Verification / proof result:

```text
14 tests passed
proof verdict: auditable_abstention_no_trusted_positive
accepted_count: 0
suppressed_count: 12
uncertain_count: 4
bottleneck: perception_gate_worker_body_overlap
```

Next blocker:

```text
The first silhouette estimate is promising but still heuristic: YOLO person boxes + GrabCut can over-separate edges. Before any gate integration, the same diagnostic must survive on the next top packets and on negative/control cases so we know this is discrete carried-panel evidence rather than a segmentation artifact.
```

Exact next recommended step:

```bash
cd /Users/thomas/Projects/Factory-Output-Vision-MVP
.venv/bin/python scripts/analyze_person_panel_separation.py --packet-id event0006-track000001 --packet-id event0006-track000004 --force
```

Then compare those packet JSON/PNG receipts against `event0002 track 5` before touching `app/services/perception_gate.py`.

## PRD Milestone 1 start — temporal transfer review packets — 2026-04-28 10:50 EDT

Implemented first PRD-backed code slice:

```text
scripts/build_panel_transfer_review_packets.py
tests/test_build_panel_transfer_review_packets.py
```

Purpose:

```text
factory2 morning proof report / diagnostic receipts
→ re-rank worker-entangled candidates by temporal source/output evidence
→ emit transfer packet JSON/JPG artifacts for reviewer/VLM/person-panel separation work
```

Real run:

```bash
.venv/bin/python scripts/build_panel_transfer_review_packets.py --force
```

Generated:

```text
data/reports/factory2_transfer_review_packets.json
track-*-transfer-packet.json / track-*-transfer-packet.jpg beside receipt files
```

Top packet order now follows the PRD instead of outside-person ratio alone:

```text
1. event0002 track 5 — source_frames=38, output_frames=1, displacement=603.294, flow=0.501419
2. event0006 track 1 — source_frames=35, output_frames=2, displacement=456.787, flow=0.465985
3. event0006 track 4 — source_frames=33, output_frames=3, displacement=482.653, flow=0.222248
4. event0002 track 2 — source_frames=34, output_frames=0, displacement=273.665, flow=0.134594
```

Track 7 is now correctly demoted to ambiguity/control because it is single-frame/low-motion despite partial outside-person evidence.

Verification:

```bash
python -m pytest tests/test_build_panel_transfer_review_packets.py tests/test_run_factory2_morning_proof.py tests/test_analyze_panel_crop_evidence.py -q
# 10 passed
python -m py_compile scripts/build_panel_transfer_review_packets.py tests/test_build_panel_transfer_review_packets.py
.venv/bin/python -m py_compile scripts/build_panel_transfer_review_packets.py
```

Next step from PRD:

```text
Audit top transfer packets into countable_panel / not_panel / insufficient_visibility, then build person-mask/pose-aware panel separation diagnostics.
```

---

## PRD alignment — 2026-04-28 10:40 EDT

Created the active perception PRD:

```text
docs/PRD_FACTORY2_CARRIED_PANEL_PERCEPTION.md
```

`docs/PROJECT_SPEC.md` now points to this PRD as the active source of truth for the current `factory2.MOV` worker-entangled carried-panel blocker.

Next code work should follow the PRD, starting with:

```text
scripts/build_panel_transfer_review_packets.py
tests/test_build_panel_transfer_review_packets.py
data/reports/factory2_transfer_review_packets.json
```

Do not loosen the count state machine or source-token gate to force nonzero counts. The PRD keeps the doctrine: raw detections and crop texture are evidence only; the missing capability is temporal carried-panel perception plus person/panel separation.

---

## Latest manual slice — 2026-04-28 09:43:25 EDT

Commit:

```text
e40ea6f feat: add panel crop evidence probe
```

What changed:

- Added `scripts/analyze_panel_crop_evidence.py`, a bounded model-free crop texture probe for worker-entangled receipt crops. It scores raw crops for mesh-like balanced high-frequency edge texture; it is evidence only, not a count source.
- Wired the probe into `scripts/run_factory2_morning_proof.py` so the one-command proof path now also writes `data/reports/factory2_panel_crop_evidence.json` and summarizes it in `factory2_morning_proof_run_summary.json`.
- Added tests for synthetic wire-mesh vs solid worker/body crops and for proof-runner crop-evidence integration.

Real proof rerun:

```bash
cd /Users/thomas/Projects/Factory-Output-Vision-MVP
.venv/bin/python scripts/run_factory2_morning_proof.py --force
```

Updated artifacts:

```text
data/reports/factory2_morning_proof_run_summary.json
data/reports/factory2_morning_proof_report.json
data/reports/factory2_morning_proof_report.md
data/reports/factory2_panel_crop_evidence.json
```

Real result:

```text
verdict: auditable_abstention_no_trusted_positive
accepted_count: 0
suppressed_count: 12
uncertain_count: 4
bottleneck: perception_gate_worker_body_overlap
panel_crop_evidence_summary: panel_texture_candidate_receipts=4, low_panel_texture_receipts=6 among top 10 queued receipts
top queued track 7: texture_uncertain / low-confidence, not enough to allow source token
VLM spot-check of track 7 crop: too ambiguous; no clearly separable wire-mesh panel
VLM spot-check of a texture-positive crop: still ambiguous; texture may be mesh, but no distinct panel boundary
```

Interpretation:

```text
The strategy is still correct, but the last reporting-only phase is over. This slice starts attacking the real blocker: panel-vs-worker/static-stack perception. It did not produce a trusted count; it added a repeatable crop-evidence probe and showed that texture alone can surface candidates but is insufficient to approve a source token. Next useful work is person-mask/pose-aware or segmentation-assisted separation on the texture-positive receipts, not more report taxonomy.
```

Verification:

```bash
python -m pytest tests/test_analyze_panel_crop_evidence.py tests/test_run_factory2_morning_proof.py tests/test_build_morning_proof_report.py tests/test_eval_detector_false_positives.py tests/test_eval_detector_positives.py -q
# 22 passed in 0.10s

python -m py_compile scripts/analyze_panel_crop_evidence.py scripts/run_factory2_morning_proof.py tests/test_analyze_panel_crop_evidence.py tests/test_run_factory2_morning_proof.py
.venv/bin/python -m py_compile scripts/analyze_panel_crop_evidence.py scripts/run_factory2_morning_proof.py
.venv/bin/python scripts/run_factory2_morning_proof.py --force
```

Scope guard held: no cron changes, no sensitive files read/staged, unrelated dirty files untouched, generated report/eval artifacts left ignored/untracked.

Immediate next step:

```text
Use the four panel-texture-candidate receipts from `data/reports/factory2_panel_crop_evidence.json` as the next perception work queue. Add person-mask/pose-aware or segmentation-assisted separation to prove whether the mesh-like texture belongs to a discrete carried panel, and only then consider allowing source-token evidence.
```

## Latest cron slice — 2026-04-28 07:21:48 EDT

Commit:

```text
8aefc95 feat: summarize proof evidence gaps
```

What changed:

- Added a top-level `evidence_gap_matrix` to `scripts/build_morning_proof_report.py` so the factory2 morning report now groups every non-counted receipt by the physical proof link that failed.
- The matrix separates `panel_vs_worker_separation` from `output_entry_and_settle`, carries sample receipt paths, states why accepted count is zero, and repeats missing review asset counts.
- Markdown reports now include an `Evidence gap matrix` section before the source-token work queue.
- This is reporting only, not looser counting: raw detector detections and worker-entangled tracks still cannot count without perception-gate-approved source-token evidence.

Real proof rerun:

```bash
cd /Users/thomas/Projects/Factory-Output-Vision-MVP
.venv/bin/python scripts/run_factory2_morning_proof.py --force
```

Updated artifacts:

```text
data/reports/factory2_morning_proof_run_summary.json
data/reports/factory2_morning_proof_report.json
data/reports/factory2_morning_proof_report.md
```

Real result:

```text
verdict: auditable_abstention_no_trusted_positive
accepted_count: 0
suppressed_count: 12
uncertain_count: 4
bottleneck: perception_gate_worker_body_overlap
evidence_gap_matrix.dominant_gap: panel_vs_worker_separation
evidence_gap_matrix.evidence_links: panel_vs_worker_separation blocked 13 receipts (12 suppressed, 1 uncertain); output_entry_and_settle blocked 3 receipts (3 uncertain)
source_token_work_queue.item_count: 13
```

Interpretation:

```text
The morning bar moved closer because the report now explains the abstention in physical-evidence terms instead of merely saying every candidate was suppressed/uncertain. The current representative factory2.MOV result remains honest: 0 accepted counts. The dominant blocker is panel-vs-worker separation on worker-entangled receipts; three additional uncertain receipts need output-entry/settle evidence.
```

Verification:

```bash
python -m pytest tests/test_build_morning_proof_report.py tests/test_run_factory2_morning_proof.py tests/test_eval_detector_false_positives.py tests/test_eval_detector_positives.py -q
# 19 passed in 0.04s

python -m py_compile scripts/build_morning_proof_report.py tests/test_build_morning_proof_report.py
.venv/bin/python -m py_compile scripts/build_morning_proof_report.py
git diff --check -- scripts/build_morning_proof_report.py tests/test_build_morning_proof_report.py
.venv/bin/python scripts/run_factory2_morning_proof.py --force
```

Scope guard held: no cron changes, no sensitive files read/staged, generated report/eval artifacts left ignored/untracked, and only `scripts/build_morning_proof_report.py` plus `tests/test_build_morning_proof_report.py` were committed.

Immediate next step:

```text
Attack the dominant evidence gap directly: build crop/shape/person-mask or pose-aware separation for the top `panel_vs_worker_separation` receipts, starting with the source-token work queue top item. A receipt should only become countable if it proves a discrete wire-mesh panel separate from worker body/arms/clothing and still preserves source→output/settle evidence.
```

## Latest cron slice — 2026-04-28 06:58:00 EDT

Commit:

```text
bb5d3af feat: specify source token audit evidence
```

What changed:

- Added explicit `audit_question` and `evidence_requirements_to_allow_source_token` fields to each `source_token_work_queue.top_items[]` row in `scripts/build_morning_proof_report.py`.
- Markdown proof reports now show the audit question and evidence checklist for the highest-priority worker-entangled receipts.
- This is still evidence bookkeeping, not looser counting: worker-overlap tracks remain suppressed/uncertain unless future perception evidence proves a valid active-panel source token.

Real proof rerun:

```bash
cd /Users/thomas/Projects/Factory-Output-Vision-MVP
.venv/bin/python scripts/run_factory2_morning_proof.py --force
```

Updated artifacts:

```text
data/reports/factory2_morning_proof_run_summary.json
data/reports/factory2_morning_proof_report.json
data/reports/factory2_morning_proof_report.md
```

Real result:

```text
verdict: auditable_abstention_no_trusted_positive
accepted_count: 0
suppressed_count: 12
uncertain_count: 4
bottleneck: perception_gate_worker_body_overlap
source_token_work_queue.item_count: 13
source_token_work_queue.worker_overlap_detail_counts: {'fully_entangled_with_worker': 12, 'high_overlap_partial_outside_worker': 1}
top_work_item: track 7 in factory2-event0002-98s-panel-v4-protrusion-gated, high_overlap_partial_outside_worker, receipt data/diagnostics/event-windows/factory2-event0002-98s-panel-v4-protrusion-gated/track_receipts/track-000007.json
top_audit_question: Is the partially outside-person evidence a real panel edge/sheet, or just worker limbs/clothing/background?
top_evidence_requirements: raw crops show a discrete wire-mesh/panel edge separate from worker clothing or arms; outside-person pixels are large enough and stable enough to be a physical panel, not detector jitter; source and output evidence both survive after person/part separation
```

Interpretation:

```text
The morning bar moved closer because the end-to-end report now states exactly what evidence would be required before any worker-entangled receipt can become a source token. Current representative factory2.MOV result remains an honest abstention: 0 accepted, 12 suppressed, 4 uncertain. The blocker is still worker/body source-token evidence, not the count state machine.
```

Verification:

```bash
python -m pytest tests/test_build_morning_proof_report.py tests/test_run_factory2_morning_proof.py tests/test_eval_detector_false_positives.py tests/test_eval_detector_positives.py -q
# 19 passed in 0.04s

python -m py_compile scripts/build_morning_proof_report.py tests/test_build_morning_proof_report.py
.venv/bin/python -m py_compile scripts/build_morning_proof_report.py
git diff --check -- scripts/build_morning_proof_report.py tests/test_build_morning_proof_report.py
.venv/bin/python scripts/run_factory2_morning_proof.py --force
```

Scope guard held: no cron changes, no sensitive files read/staged, generated report/eval artifacts left ignored/untracked, and only the proof-report source/test files were committed.

Immediate next step:

```text
Use the top work item — track 7 from the 78–118s window — to build crop/shape/person-mask evidence that answers the report's audit question: whether the outside-person pixels are a real wire-mesh panel edge/sheet or merely worker limbs/clothing/background.
```

## Latest cron slice — 2026-04-28 06:13:44 EDT

Commit:

```text
9b64116 feat: queue source token receipt work
```

What changed:

- Added a top-level `source_token_work_queue` to `scripts/build_morning_proof_report.py` so the morning report now ranks the worker-entangled receipts that are most worth attacking next.
- The queue carries the JSON receipt, image card, raw crop paths, overlap ratios, and a recommended action per track.
- This is still evidence bookkeeping, not looser counting: raw detections and worker-overlap tracks still do not mint source tokens.

Real proof rerun:

```bash
cd /Users/thomas/Projects/Factory-Output-Vision-MVP
.venv/bin/python scripts/run_factory2_morning_proof.py --force
```

Updated artifacts:

```text
data/reports/factory2_morning_proof_run_summary.json
data/reports/factory2_morning_proof_report.json
data/reports/factory2_morning_proof_report.md
```

Real result:

```text
verdict: auditable_abstention_no_trusted_positive
accepted_count: 0
suppressed_count: 12
uncertain_count: 4
bottleneck: perception_gate_worker_body_overlap
source_token_work_queue.item_count: 13
source_token_work_queue.worker_overlap_detail_counts: {'fully_entangled_with_worker': 12, 'high_overlap_partial_outside_worker': 1}
top_work_item: track 7 in factory2-event0002-98s-panel-v4-protrusion-gated, high_overlap_partial_outside_worker, receipt data/diagnostics/event-windows/factory2-event0002-98s-panel-v4-protrusion-gated/track_receipts/track-000007.json
```

Interpretation:

```text
The morning bar moved closer because the end-to-end proof report now tells the next engineer/agent exactly which worker-entangled receipt to inspect first and which evidence layer is missing. Current representative factory2.MOV result remains an honest abstention: 0 accepted, 12 suppressed, 4 uncertain. The blocker is still worker/body source-token evidence, not the count state machine.
```

Verification:

```bash
python -m pytest tests/test_build_morning_proof_report.py tests/test_run_factory2_morning_proof.py tests/test_eval_detector_false_positives.py tests/test_eval_detector_positives.py -q
# 19 passed in 0.04s

python -m py_compile scripts/build_morning_proof_report.py tests/test_build_morning_proof_report.py
.venv/bin/python -m py_compile scripts/build_morning_proof_report.py
git diff --check -- scripts/build_morning_proof_report.py tests/test_build_morning_proof_report.py
.venv/bin/python scripts/run_factory2_morning_proof.py --force
```

Scope guard held: no cron changes, no sensitive files read/staged, generated report/eval artifacts left ignored/untracked, and only the proof-report source/test files were committed.

Immediate next step:

```text
Use `source_token_work_queue.top_items[0]` — currently track 7 from the 78–118s window — to build the next perception evidence slice: crop/shape/person-mask or pose-aware separation that can approve a true protruding/carried panel without allowing torso/arm/background motion to count.
```

## Latest cron slice — 2026-04-28 05:39:11

Commit:

```text
a9bc7eb feat: index proof decision receipts
```

What changed:

- Added a top-level `decision_receipt_index` to `scripts/build_morning_proof_report.py`, grouping every reviewed track into `accepted`, `suppressed`, and `uncertain` with direct JSON/card/raw-crop receipt paths.
- Markdown reports now include a `Decision receipt index` and sample receipt links so the morning proof is easier to audit without digging through each diagnostic file.
- This is bookkeeping, not looser counting: raw detector outputs still cannot count; only perception-gate-approved source tokens enter the accepted bucket.

Real proof rerun:

```bash
cd /Users/thomas/Projects/Factory-Output-Vision-MVP
.venv/bin/python scripts/run_factory2_morning_proof.py --force
```

Updated artifacts:

```text
data/reports/factory2_morning_proof_run_summary.json
data/reports/factory2_morning_proof_report.json
data/reports/factory2_morning_proof_report.md
```

Real result:

```text
verdict: auditable_abstention_no_trusted_positive
accepted_count: 0
suppressed_count: 12
uncertain_count: 4
bottleneck: perception_gate_worker_body_overlap
proof_readiness.status: detector_seed_passes_but_worker_overlap_blocks_source_tokens
decision_receipt_index.counts: {'accepted': 0, 'suppressed': 12, 'uncertain': 4}
missing_review_asset_counts: {}
first_suppressed_receipt: data/diagnostics/event-windows/factory2-event0002-98s-panel-v4-protrusion-gated/track_receipts/track-000001.json
```

Interpretation:

```text
The morning bar moved closer because the end-to-end report now has an auditable decision index: every suppressed/uncertain track points to the receipt assets proving why it did not count. Current representative factory2.MOV result remains an honest abstention: 0 accepted, 12 suppressed, 4 uncertain, with worker/body overlap still the blocker.
```

Verification:

```bash
python -m pytest tests/test_build_morning_proof_report.py tests/test_run_factory2_morning_proof.py tests/test_eval_detector_false_positives.py tests/test_eval_detector_positives.py -q
# 19 passed in 0.03s

python -m py_compile scripts/build_morning_proof_report.py tests/test_build_morning_proof_report.py
.venv/bin/python -m py_compile scripts/build_morning_proof_report.py
git diff --check -- scripts/build_morning_proof_report.py tests/test_build_morning_proof_report.py
.venv/bin/python scripts/run_factory2_morning_proof.py --force
```

Scope guard held: no cron changes, no sensitive files read/staged, generated report/eval artifacts left ignored/untracked, and only the proof-report source/test files were committed.

Immediate next step:

```text
Use the indexed suppressed/uncertain receipt list as the work queue for the worker-entangled tracks, then add crop/shape/person-mask or pose-aware evidence that can approve true carried/protruding panels without opening the door to torso/arm/background counts.
```

## Latest cron slice — 2026-04-28 05:03:09 EDT

Commit:

```text
5dd72e3 feat: classify proof readiness
```

What changed:

- Added `proof_readiness` to `scripts/build_morning_proof_report.py`, so the morning artifact now says whether the current blocker is detector safety, positive recall, or source-token gate evidence.
- The readiness classifier preserves the count doctrine: raw detector outputs still do not count; they only help determine whether the detector is good enough and whether the bottleneck has moved to worker/body source-token evidence.
- Markdown reports now include a `Proof readiness` section with status, dominant failure link, detector pass/fail flags, and next action.

Real proof rerun:

```bash
cd /Users/thomas/Projects/Factory-Output-Vision-MVP
.venv/bin/python scripts/run_factory2_morning_proof.py --force
```

Updated artifacts:

```text
data/reports/factory2_morning_proof_run_summary.json
data/reports/factory2_morning_proof_report.json
data/reports/factory2_morning_proof_report.md
```

Real result:

```text
verdict: auditable_abstention_no_trusted_positive
accepted_count: 0
suppressed_count: 12
uncertain_count: 4
bottleneck: perception_gate_worker_body_overlap
proof_readiness.status: detector_seed_passes_but_worker_overlap_blocks_source_tokens
proof_readiness.dominant_failure_link: worker_body_overlap
selected detector: models/panel_in_transit.pt at confidence 0.25
selected detector positive pass: true, recall 1.0
selected detector hard-negative FP: 0 detections
safe detector candidates: 4
failure_link_counts: worker_body_overlap=13, missing_output_settle=3
worker_overlap_detail_counts: fully_entangled_with_worker=12, high_overlap_partial_outside_worker=1
```

Interpretation:

```text
The morning bar moved closer because the report now distinguishes “the detector seed evidence is currently good enough on reviewed positives/hard negatives” from “the representative factory event count still abstains.” The blocker is now stated cleanly: worker-entangled source-token evidence, not hard-negative detector false positives or reviewed-positive recall.
```

Verification:

```bash
python -m pytest tests/test_build_morning_proof_report.py tests/test_run_factory2_morning_proof.py tests/test_eval_detector_false_positives.py tests/test_eval_detector_positives.py -q
# 19 passed in 0.03s

python -m py_compile scripts/build_morning_proof_report.py tests/test_build_morning_proof_report.py
.venv/bin/python -m py_compile scripts/build_morning_proof_report.py
git diff --check -- scripts/build_morning_proof_report.py tests/test_build_morning_proof_report.py
.venv/bin/python scripts/run_factory2_morning_proof.py --force
```

Scope guard held: no cron changes, no sensitive files read/staged, generated report/eval artifacts left ignored/untracked, and only the proof-report source/test files were committed.

Immediate next step:

```text
Build the crop/shape/person-mask or pose-aware evidence layer for the 12 fully-entangled worker-overlap tracks so the system can approve true carried/protruding panels while continuing to suppress torso/arm/background motion.
```

## Latest cron slice — 2026-04-28 04:28:40 EDT

Commit:

```text
77942a6 feat: select detector in proof report
```

What changed:

- Updated `scripts/build_morning_proof_report.py` so the end-to-end proof report now chooses an advisory detector/model threshold from paired hard-negative and positive eval reports.
- Selection rule is intentionally conservative: zero hard-negative false positives first, then highest positive-label recall. This does **not** allow raw detector detections to count; it only identifies the safest currently evaluated perception candidate.
- The JSON report now includes `detector_selection` with all candidates, safe-candidate count, report paths, positive recall, and hard-negative FP evidence.
- The Markdown morning report now has a `Detector selection` section so the morning artifact says which detector is best and why.

Real proof rerun:

```bash
cd /Users/thomas/Projects/Factory-Output-Vision-MVP
.venv/bin/python scripts/run_factory2_morning_proof.py --force
```

Updated artifacts:

```text
data/reports/factory2_morning_proof_run_summary.json
data/reports/factory2_morning_proof_report.json
data/reports/factory2_morning_proof_report.md
```

Real result:

```text
verdict: auditable_abstention_no_trusted_positive
accepted_count: 0
suppressed_count: 12
uncertain_count: 4
bottleneck: perception_gate_worker_body_overlap
hard-negative FP eval: 0 false-positive detections across 64 hard-negative eval rows
positive detector eval: 16 / 32 aggregate labels matched across 4 model/threshold reports
safe detector candidates: 4 / 4
selected detector: models/panel_in_transit.pt at confidence 0.25
selected detector positive recall: 8 / 8 labels matched, recall 1.0
selected detector hard-negative FP: 0 detections on 16 hard-negative images
```

Interpretation:

```text
The morning bar moved closer on the model/eval side: the report no longer just dumps multiple eval files; it explicitly picks the best currently safe detector threshold while preserving the abstention on representative event counts. The remaining blocker is still source-token perception evidence under worker/body overlap, not detector hard-negative FP on the exported crops.
```

Verification:

```bash
python -m pytest tests/test_build_morning_proof_report.py tests/test_run_factory2_morning_proof.py tests/test_eval_detector_false_positives.py tests/test_eval_detector_positives.py -q
# 19 passed in 0.03s

python -m py_compile scripts/build_morning_proof_report.py tests/test_build_morning_proof_report.py
.venv/bin/python -m py_compile scripts/build_morning_proof_report.py
.venv/bin/python scripts/run_factory2_morning_proof.py --force
git diff --check -- scripts/build_morning_proof_report.py tests/test_build_morning_proof_report.py
```

Scope guard held: no cron changes, no sensitive files read/staged, generated report/eval artifacts left ignored/untracked, and only the proof-report source/test files were committed.

Immediate next step:

```text
Use the selected safe detector as the baseline, then add crop/shape/person-mask or pose-aware evidence for the fully-entangled worker-overlap tracks so true carried/protruding mesh panels can mint source tokens while torso/arm/background tracks remain suppressed.
```

## Latest cron slice — 2026-04-28 03:53:52 EDT

Commit:

```text
43ef0af feat: detail worker overlap proof failures
```

What changed:

- Updated `scripts/build_morning_proof_report.py` so worker/body-overlap failures are no longer one blunt bucket.
- Added `worker_overlap_detail_counts` at report and per-window level, with per-track `worker_overlap_detail` on each decision receipt.
- New detail buckets distinguish `fully_entangled_with_worker`, `high_overlap_partial_outside_worker`, `protrusion_candidate_not_approved`, and `allowed_by_protrusion`.
- This keeps the source-token doctrine intact: the report explains why tracks were suppressed/uncertain without letting raw detections increment counts.

Real proof rerun:

```bash
cd /Users/thomas/Projects/Factory-Output-Vision-MVP
.venv/bin/python scripts/run_factory2_morning_proof.py --force
```

Updated artifacts:

```text
data/reports/factory2_morning_proof_run_summary.json
data/reports/factory2_morning_proof_report.json
data/reports/factory2_morning_proof_report.md
```

Real result:

```text
verdict: auditable_abstention_no_trusted_positive
accepted_count: 0
suppressed_count: 12
uncertain_count: 4
bottleneck: perception_gate_worker_body_overlap
failure_link_counts: worker_body_overlap=13, missing_output_settle=3
worker_overlap_detail_counts: fully_entangled_with_worker=12, high_overlap_partial_outside_worker=1
hard-negative FP eval: 0 false-positive detections across 64 hard-negative eval rows
positive detector eval: 16 / 32 aggregate labels matched across 4 model/threshold reports
```

Interpretation:

```text
The abstention is now more precise: nearly every worker-overlap failure is fully entangled with the worker/person box rather than a clean protruding-panel candidate. The next useful perception slice is not loosening the gate; it is better crop/shape/person-mask evidence that can prove a panel exists outside the worker silhouette before minting source tokens.
```

Verification:

```bash
python -m pytest tests/test_build_morning_proof_report.py tests/test_run_factory2_morning_proof.py tests/test_eval_detector_false_positives.py tests/test_eval_detector_positives.py -q
# 19 passed in 0.03s

python -m py_compile scripts/build_morning_proof_report.py tests/test_build_morning_proof_report.py
.venv/bin/python -m py_compile scripts/build_morning_proof_report.py
.venv/bin/python scripts/run_factory2_morning_proof.py --force
git diff --check -- scripts/build_morning_proof_report.py tests/test_build_morning_proof_report.py
```

Scope guard held: no cron changes, no sensitive files read/staged, generated report/eval artifacts left ignored/untracked, and only the proof-report source/test files were committed.

Immediate next step:

```text
Add crop/shape/person-mask or pose-aware evidence for the 12 fully-entangled worker-overlap tracks so the system can separate true carried/protruding mesh panels from torso/arm/background motion before source-token creation.
```

## Latest cron slice — 2026-04-28 03:19:29 EDT

Commit:

```text
d167993 feat: classify proof report failure links
```

What changed:

- Updated `scripts/build_morning_proof_report.py` so the morning report now classifies each diagnostic track into a physical evidence failure link, not just a raw gate reason.
- Added `failure_link_counts` at report and per-window level, with categories such as `worker_body_overlap`, `missing_output_settle`, `static_stack_or_resident_output`, and `insufficient_active_panel_evidence`.
- Added `track_decision_receipts[]` entries that connect each track decision to its JSON receipt, image card, raw crop paths, gate reason, flags, and evidence summary.
- This keeps count logic conservative: no raw detector or diagnostic row can increment counts without a perception-gate-approved source token.

Real proof rerun:

```bash
cd /Users/thomas/Projects/Factory-Output-Vision-MVP
.venv/bin/python scripts/run_factory2_morning_proof.py --force
```

Updated artifacts:

```text
data/reports/factory2_morning_proof_run_summary.json
data/reports/factory2_morning_proof_report.json
data/reports/factory2_morning_proof_report.md
```

Real result:

```text
verdict: auditable_abstention_no_trusted_positive
accepted_count: 0
suppressed_count: 12
uncertain_count: 4
bottleneck: perception_gate_worker_body_overlap
failure_link_counts: worker_body_overlap=13, missing_output_settle=3
hard-negative FP eval: 0 false-positive detections across 64 hard-negative eval rows
positive detector eval: 16 / 32 aggregate labels matched across 4 model/threshold reports
```

Interpretation:

```text
The morning proof now says exactly why it abstained: most rejected/uncertain tracks still fail because the candidate box is too entangled with worker/body evidence, with the remaining failures lacking output-settle evidence. The current weak link is still perception evidence/gating, not the source-token state machine.
```

Verification:

```bash
python -m pytest tests/test_build_morning_proof_report.py tests/test_run_factory2_morning_proof.py tests/test_eval_detector_false_positives.py tests/test_eval_detector_positives.py -q
# 18 passed in 0.03s

python -m py_compile scripts/build_morning_proof_report.py tests/test_build_morning_proof_report.py
.venv/bin/python -m py_compile scripts/build_morning_proof_report.py
.venv/bin/python scripts/run_factory2_morning_proof.py --force
git diff --check
```

Scope guard held: no cron changes, no sensitive files read/staged, generated report/eval artifacts left ignored/untracked, and only the proof-report source/test files were committed.

Immediate next step:

```text
Improve the perception evidence feeding `worker_body_overlap`: add crop/shape/person-correlation scoring for track receipts so the gate can separate true protruding panels from torso/arm/background motion before creating source tokens.
```

## Latest cron slice — 2026-04-28 02:44:27 EDT

Commit:

```text
45e2d9d feat: add factory2 proof runner
```

What changed:

- Added `scripts/run_factory2_morning_proof.py`, a one-command runner for the representative `factory2.MOV` proof path.
- The runner reruns detector false-positive eval and detector positive eval across available models and confidence thresholds, then rebuilds the accepted/suppressed/uncertain morning proof report from diagnostic receipts.
- It writes `data/reports/factory2_morning_proof_run_summary.json` alongside the existing JSON/Markdown proof report.
- It explicitly keeps raw detector outputs as eval evidence only; counts still require perception-gate-approved source-token receipts.

One-command rerun path:

```bash
cd /Users/thomas/Projects/Factory-Output-Vision-MVP
.venv/bin/python scripts/run_factory2_morning_proof.py --force
```

Real artifacts from this run:

```text
data/reports/factory2_morning_proof_run_summary.json
data/reports/factory2_morning_proof_report.json
data/reports/factory2_morning_proof_report.md
data/eval/detector_false_positives/active_panel_hard_negatives_v1_panel_in_transit_conf025.json
data/eval/detector_false_positives/active_panel_hard_negatives_v1_panel_in_transit_conf010.json
data/eval/detector_false_positives/active_panel_hard_negatives_v1_caleb_metal_panel_conf025.json
data/eval/detector_false_positives/active_panel_hard_negatives_v1_caleb_metal_panel_conf010.json
data/eval/detector_positives/active_panel_positives_v1_panel_in_transit_conf025_iou030.json
data/eval/detector_positives/active_panel_positives_v1_panel_in_transit_conf010_iou030.json
data/eval/detector_positives/active_panel_positives_v1_caleb_metal_panel_conf025_iou030.json
data/eval/detector_positives/active_panel_positives_v1_caleb_metal_panel_conf010_iou030.json
```

Real runner result:

```text
verdict: auditable_abstention_no_trusted_positive
accepted_count: 0
suppressed_count: 12
uncertain_count: 4
bottleneck: perception_gate_worker_body_overlap
models evaluated: panel_in_transit.pt, caleb_metal_panel.pt
confidence thresholds: 0.25, 0.10
```

Verification:

```bash
python -m pytest tests/test_run_factory2_morning_proof.py tests/test_build_morning_proof_report.py tests/test_eval_detector_false_positives.py tests/test_eval_detector_positives.py -q
# 18 passed in 0.04s

python -m py_compile scripts/run_factory2_morning_proof.py tests/test_run_factory2_morning_proof.py
.venv/bin/python -m py_compile scripts/run_factory2_morning_proof.py
.venv/bin/python scripts/run_factory2_morning_proof.py --force
```

Scope guard held: no cron changes, no training run, no sensitive files read/staged, generated reports/eval artifacts left ignored/untracked, and only the new proof runner plus tests were committed.

Immediate next step:

```text
Now that the proof path is one command, improve the actual perception bottleneck: add crop-level/track-level evidence for worker-overlap cases so the gate can distinguish a real protruding carried panel from torso/arm/background motion before minting source tokens.
```

## Latest cron slice — 2026-04-28 02:09:50 EDT

Commit:

```text
c328fec feat: add detector positive eval to proof report
```

What changed:

- Added `scripts/eval_detector_positives.py`, a positive-side active-panel detector eval harness for reviewed YOLO positives.
- It loads positives from the assembled dataset manifest or non-empty YOLO labels, runs detector inference, matches detections to labels by IoU, and writes receipt JSON with label recall, matched/missed labels, per-image detections, and no-overwrite protection.
- Updated `scripts/build_morning_proof_report.py` so the morning report includes positive detector eval alongside hard-negative false-positive eval.
- Fixed the morning report FP summarizer to read the nested `summary` shape emitted by the FP harness.

Real artifacts from this run:

```text
data/eval/detector_positives/active_panel_positives_v1_panel_in_transit_conf025_iou030.json
data/eval/detector_positives/active_panel_positives_v1_panel_in_transit_conf010_iou030.json
data/eval/detector_positives/active_panel_positives_v1_caleb_metal_panel_conf025_iou030.json
data/eval/detector_positives/active_panel_positives_v1_caleb_metal_panel_conf010_iou030.json
data/reports/factory2_morning_proof_report.json
data/reports/factory2_morning_proof_report.md
```

Positive detector eval result on the assembled `active_panel` positives:

```text
panel_in_transit.pt @ conf 0.25, IoU 0.30: 8 / 8 labels matched, recall 1.0
panel_in_transit.pt @ conf 0.10, IoU 0.30: 8 / 8 labels matched, recall 1.0
caleb_metal_panel.pt @ conf 0.25, IoU 0.30: 0 / 8 labels matched, recall 0.0
caleb_metal_panel.pt @ conf 0.10, IoU 0.30: 0 / 8 labels matched, recall 0.0
```

Updated combined morning report result:

```text
verdict: auditable_abstention_no_trusted_positive
accepted_count: 0
suppressed_count: 12
uncertain_count: 4
bottleneck: perception_gate_worker_body_overlap
hard-negative FP eval: 0 false-positive detections across 64 hard-negative eval rows
positive detector eval: 16 / 32 aggregate labels matched across 4 model/threshold reports
```

Interpretation:

```text
The representative event-count answer is still accepted_count=0 because no source-token track survived the perception gate. The detector-side picture is now clearer: panel_in_transit.pt sees the 8 reviewed positives and stays clean on staged hard negatives; caleb_metal_panel.pt should not be used for this active_panel proof because it misses all reviewed positives in this dataset.
```

Verification:

```bash
python -m pytest tests/test_eval_detector_positives.py tests/test_build_morning_proof_report.py tests/test_eval_detector_false_positives.py tests/test_diagnose_event_window.py tests/test_run_clip_eval.py tests/test_perception_gate.py -q
# 32 passed in 0.08s

python -m py_compile scripts/eval_detector_positives.py scripts/build_morning_proof_report.py tests/test_eval_detector_positives.py tests/test_build_morning_proof_report.py
.venv/bin/python -m py_compile scripts/eval_detector_positives.py scripts/build_morning_proof_report.py
git diff --check
```

Scope guard held: no cron changes, no sensitive files read/staged, generated eval/report artifacts left untracked/ignored, and only relevant source/test files were committed.

Immediate next step:

```text
Keep panel_in_transit.pt as the current proof-path detector candidate. The next useful slice is not more model comparison; it is crop-level/track-level evidence for worker-overlap cases, so the perception gate can distinguish a real protruding carried panel from torso/arm/background motion before minting source tokens.
```

## Latest cron slice — 2026-04-28 01:48:35 EDT

Commit:

```text
94020da feat: add morning proof report builder
```

What changed:

- Added `scripts/build_morning_proof_report.py`, a bounded end-to-end proof/report aggregator for the morning bar.
- It combines existing `factory2.MOV` diagnostic receipts, perception-gate decisions, hard-negative manifests, overlay paths, and detector false-positive eval reports.
- It explicitly reports `accepted_count`, `suppressed_count`, `uncertain_count`, bottleneck, receipt paths, and detector FP totals without promoting raw unaudited detections into counts.
- Added `tests/test_build_morning_proof_report.py` covering accepted/suppressed/uncertain separation, allowed source tokens, markdown receipt output, and CLI writes.

Real artifacts from this run:

```text
data/reports/factory2_morning_proof_report.json
data/reports/factory2_morning_proof_report.md
data/eval/detector_false_positives/active_panel_hard_negatives_v1_panel_in_transit_conf010.json
data/eval/detector_false_positives/active_panel_hard_negatives_v1_caleb_metal_panel_conf025.json
data/eval/detector_false_positives/active_panel_hard_negatives_v1_caleb_metal_panel_conf010.json
```

Report result:

```text
verdict: auditable_abstention_no_trusted_positive
accepted_count: 0
suppressed_count: 12
uncertain_count: 4
total_tracks_reviewed: 16
bottleneck: perception_gate_worker_body_overlap
```

Detector FP widening result:

```text
panel_in_transit.pt @ conf 0.25: 0 / 16 hard-negative images with false positives
panel_in_transit.pt @ conf 0.10: 0 / 16 hard-negative images with false positives
caleb_metal_panel.pt @ conf 0.25: 0 / 16 hard-negative images with false positives
caleb_metal_panel.pt @ conf 0.10: 0 / 16 hard-negative images with false positives
combined report: 0 false-positive detections across 64 hard-negative eval rows
```

Representative diagnostic evidence included in report:

```text
factory2-event0002-98s-panel-v4-protrusion-gated: accepted 0, suppressed 5, uncertain 3; reasons worker_body_overlap=5, source_without_output_settle=3
factory2-event0006-370s-panel-v4-protrusion-gated: accepted 0, suppressed 7, uncertain 1; reasons worker_body_overlap=7, source_without_output_settle=1
```

Verification:

```bash
python -m pytest tests/test_build_morning_proof_report.py tests/test_eval_detector_false_positives.py tests/test_diagnose_event_window.py tests/test_run_clip_eval.py tests/test_perception_gate.py -q
# 26 passed in 0.07s

python -m py_compile scripts/build_morning_proof_report.py scripts/eval_detector_false_positives.py tests/test_build_morning_proof_report.py
.venv/bin/python -m py_compile scripts/build_morning_proof_report.py scripts/eval_detector_false_positives.py
```

Scope guard held: no cron changes, no sensitive files read/staged, generated eval/report artifacts left untracked/ignored, and only the new source/test files were committed.

Immediate next step:

```text
Use the report as the current morning proof artifact. The clean hard-negative FP result says the current models are not firing on staged negatives, but the diagnostics still abstain because source-to-output-looking tracks overlap worker body or lack output settle evidence. Next code slice should add positive-side detector eval/recall on the 8 reviewed positives and/or stronger crop-level panel evidence for worker-overlap cases before trusting any new source token.
```

## Latest cron slice — 2026-04-28 01:27:49 EDT

Commit:

```text
4ae767f feat: add detector false-positive eval harness
```

What changed:

- Added `scripts/eval_detector_false_positives.py`, a lightweight pre-training detector FP harness for hard-negative images.
- It accepts the assembled dataset `data.yaml` or `dataset_manifest.json`, evaluates only `hard_negative` / empty-label images, and writes a receipt-style JSON report.
- It keeps YOLO/Ultralytics loading inside the runtime path, so tests remain injectable and base-Python compatible.
- Added tests for dataset-manifest loading, empty-label fallback scanning, receipt writing, confidence filtering, and no-overwrite behavior.

Real artifact from this run:

```text
data/eval/detector_false_positives/active_panel_hard_negatives_v1_panel_in_transit_conf025.json
```

Real result on the assembled hard negatives:

```text
model: models/panel_in_transit.pt
confidence: 0.25
hard_negative_images: 16
images_with_false_positives: 0
false_positive_detections: 0
false_positive_image_rate: 0.0
```

Verification:

```bash
python -m pytest tests/test_eval_detector_false_positives.py tests/test_assemble_active_panel_dataset.py tests/test_export_hard_negatives.py -q
# 14 passed in 0.02s

python -m py_compile scripts/eval_detector_false_positives.py scripts/assemble_active_panel_dataset.py tests/test_eval_detector_false_positives.py
.venv/bin/python -m py_compile scripts/eval_detector_false_positives.py

.venv/bin/python scripts/eval_detector_false_positives.py \
  --data-yaml data/labels/active_panel_dataset_with_hard_negatives_v1/data.yaml \
  --model models/panel_in_transit.pt \
  --output data/eval/detector_false_positives/active_panel_hard_negatives_v1_panel_in_transit_conf025.json \
  --confidence 0.25 \
  --force
```

Scope guard held: no training run, no cron changes, no sensitive files read/staged, and only the new source/test files were committed.


## Current goal

Keep pushing the Factory Output Vision MVP toward reliable source→output counting on representative `factory2.MOV` footage.

Core doctrine:

```text
detections are observations, not counts
only perception-gate-approved source-token tracks can reach CountStateMachine
output-only/static-stack/worker-body tracks must not count
all counts/suppressions need receipts
AI/VLM audit is reviewer/gate, not the counter itself
```

## Latest committed work

Latest commit:

```text
2277eba feat: assemble active panel dataset with hard negatives
602c457 feat: allow protruding panel source tokens
```

Changed files:

```text
scripts/assemble_active_panel_dataset.py
tests/test_assemble_active_panel_dataset.py
```

What changed:

- Added a dataset assembly bridge from AI-reviewed positives + hard-negative exports into YOLO trainable layout.
- Positives must come from `label-quality-reviewed-v1` `trainable_labels`.
- Hard negatives come from `factory-hard-negative-export-v1` and are copied with empty YOLO label files.
- Writes `data.yaml` and `dataset_manifest.json` so the next training/eval step has a real SSoT.
- Refuses negative-only datasets unless `--allow-negative-only` is explicitly passed.

Real smoke output:

```text
data/labels/active_panel_dataset_with_hard_negatives_v1/dataset_manifest.json
positive_count: 8
hard_negative_count: 16
total_images: 24
empty_negative_labels: 16
images/train: 24
labels/train: 24
```

Previous commit from cron:

```text
602c457 feat: allow protruding panel source tokens
```

## Verification from latest run

Focused tests, compile, and real dataset assembly smoke:

```bash
python -m pytest tests/test_assemble_active_panel_dataset.py tests/test_export_hard_negatives.py tests/test_train_custom_model_label_gate.py tests/test_review_labels_ai.py -q
python -m py_compile scripts/assemble_active_panel_dataset.py scripts/export_hard_negatives.py train_custom_model.py
python scripts/assemble_active_panel_dataset.py \
  --reviewed-label-manifest data/labels/active_panel_reviewed_autopilot-v1_minconf050.json \
  --hard-negative-export data/labels/hard_negatives/factory2-v3-person-gated/hard_negative_export.json \
  --out-dir data/labels/active_panel_dataset_with_hard_negatives_v1 \
  --force
```

Result:

```text
17 passed in 0.02s
py_compile passed
real smoke assembled 24-image YOLO dataset: 8 positives + 16 empty-label hard negatives
```

## Recent prior work still relevant

Recent commits before this run:

```text
a2c482d feat: export raw hard-negative crops
21b0c03 feat: export hard negatives for review
bab09f6 feat: export diagnostic hard negatives
ce58be6 fix: keep diagnostic receipts python39 compatible
33f9cae feat: add diagnostic track image receipts
```

The diagnostic loop now emits JSON receipts, JPG receipt cards, raw crop assets, and hard-negative manifests/exports. Use those artifacts to mine failure cases rather than forcing ambiguous raw counts.

## Tool-cap / handoff reliability rule

The 00:44 manual continuation hit the tool-call cap after committing `a2c482d` and before updating this handoff. The fix is procedural and now also baked into the cron prompt:

```text
1. update HANDOFF.md at start with IN PROGRESS
2. make exactly one small commit-sized change
3. after commit, update HANDOFF.md immediately
4. only then do optional extra work
```

Hard rule for future runs: if meaningful code changed or a commit was created, HANDOFF.md gets updated before any further implementation. Stale handoff is worse than incomplete work.

## Current dirty/untracked files to avoid

Known unrelated or sensitive files remain dirty/untracked. Do not inspect, stage, or commit unless Thomas explicitly asks:

```text
M .env.example
M CLAUDE.md
M frontend/.env.example
M frontend/package-lock.json
?? .claude/
?? .infisical.json
?? AGENTS.md
?? datasets/test-3/
?? frames/
?? models/caleb_metal_panel.pt
?? runs/
?? scripts/backend-with-infisical.sh
```

`.hermes/HANDOFF.md` is maintained by the cron loop and may appear under `?? .hermes/` if the folder is not tracked. Do not stage `.hermes/overnight.lock`.

Never read or quote `.infisical.json`, `.env`, credentials, tokens, or connection-string-bearing files.

## Latest generated diagnostics

Most recent known representative `factory2.MOV` v3 person-gated diagnostics from prior run:

```text
factory2-event0002-98s-panel-v3-person-gated: 8 JSON receipts, 8 JPG cards, 8 hard negatives, 12 raw crops, allowed source-token tracks 0
factory2-event0006-370s-panel-v3-person-gated: 8 JSON receipts, 8 JPG cards, 8 hard negatives, 14 raw crops, allowed source-token tracks 0
data/labels/hard_negatives/factory2-v3-person-gated/hard_negative_export.json: 16 exported negatives, review_only=false: 16
```

The current commit changes the gate policy but did not rerun real diagnostics. Next run should test whether any existing representative candidate now qualifies via protrusion, and audit any allowed receipt visually before trusting it.


## Manual v4 protrusion smoke — 2026-04-28 01:02:06

Ran both representative `factory2.MOV` v4 protrusion-gated diagnostic windows after `602c457`.

Results:

```text
factory2-event0002-98s-panel-v4-protrusion-gated:
  diagnostic candidates: 1
  gate allow_source_token: 0
  gate reject/uncertain: 5 / 3
  receipts/cards/raw crops/hard negatives: 8 / 8 / 12 / 8

factory2-event0006-370s-panel-v4-protrusion-gated:
  diagnostic candidates: 2
  gate allow_source_token: 0
  gate reject/uncertain: 7 / 1
  receipts/cards/raw crops/hard negatives: 8 / 8 / 14 / 8
```

No VLM audit was needed because there were no newly allowed source-token receipt cards. The protrusion-aware gate remains conservative on these two windows.

Immediate implication: next code slice should not loosen the count state machine. Improve the perception features feeding the gate: raw-crop shape/edge/protrusion evidence, motion/person correlation, or a person-mask/pose-aware protrusion score.


## PRD/roadmap alignment — 2026-04-28 01:22:28 EDT

Updated product docs so the overnight loop has an explicit target and definition of done:

```text
docs/PROJECT_SPEC.md
docs/ROADMAP.md
```

Clarified:

- representative `factory2.MOV` source→output proof is the current target;
- detections are observations, not counts;
- source-token delivery is the count rule;
- output-only/static-stack/resident/repositioned/worker-body ambiguity must not count;
- success requires receipts/evidence artifacts, not unaudited raw counts;
- tonight is done when the pipeline can mine/evaluate/gate/export hard negatives/assemble dataset and add detector FP eval prep with handoff continuity.


## Morning "make it work" target — 2026-04-28 01:43:22 EDT

Thomas clarified the bar: by morning he wants to see this working, with docs updated.

Operational interpretation for cron/manual runs:

```text
factory2.MOV
→ candidate event windows
→ diagnostic receipts/overlays/raw crops
→ perception-gated source-token counting
→ detector/model eval on positives + hard negatives
→ accepted_count / suppressed / uncertain report with receipts
```

Morning success is not a pile of utilities. It is at least one end-to-end representative eval/report path that runs without manual intervention and clearly separates:

- trusted accepted counts;
- suppressed resident/static-stack/reposition/worker-body candidates;
- uncertain candidates with evidence-failure reasons.

Docs updated accordingly:

```text
docs/PROJECT_SPEC.md section 1.3
/docs/ROADMAP.md v1.0 success metric
```

Next slices should bias toward end-to-end proof/reporting over further isolated helpers. If a trusted positive cannot be produced from `factory2.MOV`, produce an auditable failure report with receipt paths and the exact bottleneck. Do not claim raw unaudited counts work.


## Stronger morning definition — 2026-04-28 01:46:38 EDT

Thomas clarified: by morning this should not merely have a better loop; it should work and work well.

Definition now written into `docs/PROJECT_SPEC.md` section 1.3:

Works:

- one command or documented command sequence runs the representative `factory2.MOV` proof path without manual intervention;
- output report separates `accepted_count`, `suppressed`, and `uncertain` events;
- every event links to receipts: JSON, image card/overlay, and relevant crop/frame evidence;
- raw detector detections cannot directly increment counts;
- output-only/resident/reposition/static-stack/worker-body tracks are suppressed or marked uncertain with reasons.

Works well:

- known hard-negative `factory2.MOV` windows have audited false positive counts of zero;
- detector FP behavior is measured across exported hard negatives at multiple confidence thresholds;
- positive/active-panel behavior is measured separately from hard-negative suppression;
- any candidate/trained model must beat or match current model on hard negatives before clip eval;
- final morning report says which clips/windows passed, failed, and why;
- docs and handoff contain the exact rerun command path.

Not acceptable by morning:

- unaudited raw counts;
- metrics without event receipts;
- crop piles without count/suppress report;
- suppressing everything without explaining whether the detector missed the panel or the gate rejected it;
- loosening count logic to make numbers look better.

## Immediate next step

The lightweight hard-negative FP harness now exists and `panel_in_transit.pt` produced zero detections on the current 16 hard negatives at confidence 0.25. Next cron slice should widen the detector eval before training:

```text
run FP eval at lower confidence, e.g. 0.10 / 0.15
→ compare panel_in_transit.pt against any available customer model such as caleb_metal_panel.pt without committing model artifacts
→ if FP remains clean, run a small bounded active_panel training/eval dry run from data/labels/active_panel_dataset_with_hard_negatives_v1/data.yaml
→ evaluate positives and hard negatives separately before using any new .pt in clip eval
```

Example commands:

```bash
.venv/bin/python scripts/eval_detector_false_positives.py \
  --data-yaml data/labels/active_panel_dataset_with_hard_negatives_v1/data.yaml \
  --model models/panel_in_transit.pt \
  --output data/eval/detector_false_positives/active_panel_hard_negatives_v1_panel_in_transit_conf010.json \
  --confidence 0.10 \
  --force

.venv/bin/python scripts/eval_detector_false_positives.py \
  --data-yaml data/labels/active_panel_dataset_with_hard_negatives_v1/data.yaml \
  --model models/caleb_metal_panel.pt \
  --output data/eval/detector_false_positives/active_panel_hard_negatives_v1_caleb_metal_panel_conf025.json \
  --confidence 0.25 \
  --force
```

Parallel next perception improvement remains: add stronger raw-crop-based panel-evidence features for the gate. The v4 smoke allowed zero source-token tracks, so do not loosen the count state machine.

```bash
.venv/bin/python scripts/diagnose_event_window.py \
  --video data/videos/from-pc/factory2.MOV \
  --calibration data/calibration/factory2_ai_only_v1_no_gate.json \
  --out-dir data/diagnostics/event-windows/factory2-event0002-98s-panel-v4-protrusion-gated \
  --start 78 --end 118 --fps 3 \
  --model models/panel_in_transit.pt \
  --person-model yolo11n.pt \
  --confidence 0.15 \
  --tracker-match-distance 280 \
  --force

.venv/bin/python scripts/diagnose_event_window.py \
  --video data/videos/from-pc/factory2.MOV \
  --calibration data/calibration/factory2_ai_only_v1_no_gate.json \
  --out-dir data/diagnostics/event-windows/factory2-event0006-370s-panel-v4-protrusion-gated \
  --start 350 --end 390 --fps 3 \
  --model models/panel_in_transit.pt \
  --person-model yolo11n.pt \
  --confidence 0.15 \
  --tracker-match-distance 280 \
  --force
```

Then inspect `perception_gate_summary` and VLM-audit any newly allowed source-token receipt cards. If none are allowed, the next code slice should add a stronger protrusion/shape feature from raw crops rather than only bbox outside-person ratio.

## Overnight cron loop protocol

A fresh Hermes cron run should treat this file as the source of truth. It should do one bounded, commit-sized slice, then update this handoff before exiting.

Loop contract:

1. Acquire a local lock so two runs do not edit the repo at once:

```bash
mkdir -p .hermes
if ! mkdir .hermes/overnight.lock 2>/dev/null; then
  echo "Another overnight Factory Vision run is active; exit cleanly."
  exit 0
fi
trap 'rmdir .hermes/overnight.lock' EXIT
```

2. Read current state:

```bash
git status --short
git log --oneline -5
cat .hermes/HANDOFF.md
```

3. Continue only the next highest-leverage Factory Vision slice.

4. Stage/commit only intentional Factory Vision source/test/handoff files. Do not stage unrelated dirty files or secrets.

5. Run focused tests and relevant regression tests before committing.

6. Update this handoff with:

```text
latest commit hash
what changed
verification output
remaining dirty/untracked files to avoid
exact next step for next cron run
```

7. Final response should be concise with commit hash, tests, and next step.

Hard stop rules:

- Never read `.infisical.json`, `.env`, or secret-bearing files.
- Never stage unrelated dirty/untracked files.
- If repo state contradicts this handoff, stop after writing the contradiction into `.hermes/HANDOFF.md` and report it.
- If tests fail, fix if obvious; otherwise leave a clear failure section in this handoff and report.
- Do not create more cron jobs from inside cron.

---

## 2026-04-28 Oracle Strategy Reset — Factory2 Human-Countable Gap

Oracle was asked for a hard reset on why a human can count `factory2.MOV` while the pipeline still abstains.

Conclusion:
- Count/audit architecture is right: source tokens, suppression, receipts, hard negatives, one-command proof should stay.
- Perception abstraction is wrong/incomplete: detector boxes + coarse person-box overlap + crop texture do not match how humans count.
- Missing capability: amodal carried-panel tracking with person/panel separation over time. Humans use temporal continuity, hand-object relationship, source/output context, and object permanence.
- Do not loosen gates or count from texture/detections.

Oracle recommended immediate next slice:
1. Build temporal transfer review packets for strongest worker-entangled source→output candidates.
2. Re-rank candidates by source/output continuity, source/output frame counts, displacement, flow coherence, and non-static evidence — not outside-person ratio alone.
3. Prioritize long tracks like event0002 track 5, event0006 tracks 1/4, event0002 track 2; treat track 7 as ambiguity/control, not primary unlock.
4. Then add person-mask/pose-aware panel separation.
5. Train only a narrow active-carried-panel model after labels exist, with masks/labels for visible active carried panel separable from worker/static stack.

Stop doing:
- More report taxonomy.
- Bbox threshold fiddling as the main solve.
- Crop texture as approval evidence.
- Lowering confidence/gates to force nonzero counts.
- Treating single-frame detections as high-value count candidates.

Immediate implementation target:
`scripts/build_panel_transfer_review_packets.py` plus tests, emitting `data/reports/factory2_transfer_review_packets.json` and per-track temporal packet artifacts.

---

## 2026-04-28 Crop Classifier Promotion And Runtime Reality

What changed in the working tree:
- Added the track-label application helper:
  - `scripts/apply_factory2_track_review_labels.py`
  - `tests/test_apply_factory2_track_review_labels.py`
- Added worker-reference negative export:
  - `scripts/export_factory2_worker_reference_crops.py`
  - `tests/test_export_factory2_worker_reference_crops.py`
- Extended `scripts/build_factory2_crop_training_dataset.py` so it can build binary `carried_panel|worker_only` datasets and emit a classification-friendly directory layout.
- Added the second-stage crop classifier service:
  - `app/services/person_panel_crop_classifier.py`
  - `tests/test_person_panel_crop_classifier.py`
- Wired crop-classifier evidence into:
  - `app/services/perception_gate.py`
  - `app/services/person_panel_gate_promotion.py`
  - `scripts/diagnose_event_window.py`
  - `app/services/runtime_event_counter.py`
- Copied trained weights to:
  - `models/factory2_person_panel_binary_manual_v1.pt`

What was verified:
- Binary crop dataset report:
  - `data/reports/factory2_crop_training_dataset.binary_manual_v1.json`
  - `ready_for_training: true`
  - label counts: `carried_panel: 218`, `worker_only: 41`
- Trained classifier weights from the binary dataset and promoted the best checkpoint into `models/`.
- Focused test suite:
  - `80 passed`
  - command:
    ```bash
    .venv/bin/python -m pytest tests/test_build_panel_transfer_review_packets.py tests/test_analyze_panel_crop_evidence.py tests/test_run_factory2_morning_proof.py tests/test_analyze_person_panel_separation.py tests/test_diagnose_event_window.py tests/test_build_morning_proof_report.py tests/test_runtime_event_counter.py tests/test_person_panel_gate_promotion.py tests/test_perception_gate.py tests/test_person_panel_crop_classifier.py tests/test_build_factory2_crop_training_dataset.py tests/test_apply_factory2_track_review_labels.py tests/test_export_factory2_worker_reference_crops.py -q
    ```
- Refreshed frozen narrow proof via direct freeze/refresh/report rebuild:
  - `data/reports/factory2_morning_proof_report.narrow_frozen_v2.json`
  - `accepted_count: 15`
  - `suppressed_count: 2`
  - `uncertain_count: 32`
  - `reason_counts: moving_panel_candidate=19, source_without_output_settle=32, static_stack_edge=2`
- Important runtime verification lesson:
  - demo-mode uvicorn/app runs are looped forever because `app/services/frame_reader.py` uses `ffmpeg -stream_loop -1`
  - long-running `counts_this_hour` values in demo mode are not one-pass truth
- No-loop single-pass runtime harness result on `factory2.MOV` after crop-classifier promotion:
  - `final_count: 17`
  - event timestamps included:
    - `5.5, 23.6, 60.5, 78.6, 110.9, 129.9, 147.0, 184.2, 210.4, 233.0, 252.0, 286.4, 303.5, 347.1, 367.2, 384.3, 422.6`

What this means:
- The perception blocker materially moved.
- Proof moved from the old `12` floor to `15`.
- One-pass runtime moved from the old single-count story to `17`, but that is still below the human truth target of `23`.
- The dominant remaining blocker is now source→output chain recall across split tracks, not person/panel separation alone.

Additional tool now built:
- `scripts/audit_factory2_runtime_events.py`
- `tests/test_audit_factory2_runtime_events.py`

Exact next step:
1. Run `scripts/audit_factory2_runtime_events.py` on the full file and on late-window slices, save the JSON ledger under `data/reports/`.
2. Diff the `17` one-pass runtime events against the human `23` truth set and identify the six missing deliveries.
3. Then fix runtime/source-chain recall with bounded chain-link logic; do not loosen perception thresholds.

---

## 2026-04-28 Runtime Recall Audit And Chain Deduping

What changed:
- Added a runtime truth-gap analyzer:
  - `scripts/analyze_factory2_runtime_truth_gap.py`
  - `tests/test_analyze_factory2_runtime_truth_gap.py`
- Added a truth-candidate reconstruction ledger builder:
  - `scripts/reconstruct_factory2_truth_candidates.py`
  - `tests/test_reconstruct_factory2_truth_candidates.py`
- Extended runtime predecessor stitching in `app/services/runtime_event_counter.py` so gate-side split-chain linking survives for the same lifetime as source tokens instead of dying after a short fixed gap.
- Fixed `app/services/count_state_machine.py` so `approved_delivery_chain` no longer double-counts overlapping output residents, while still allowing later real deliveries into the same output area after a bounded recent-resident window.
- Added new regression coverage in:
  - `tests/test_runtime_event_counter.py`
  - `tests/test_count_state_machine.py`

What was verified:
- New targeted suites passed:
  - `tests/test_analyze_factory2_runtime_truth_gap.py`: `3 passed`
  - `tests/test_reconstruct_factory2_truth_candidates.py`: `3 passed`
- Runtime/state-machine regression suites passed after the chain and dedupe fixes:
  - `tests/test_count_state_machine.py tests/test_runtime_event_counter.py`: `26 passed`
- Broader affected verification passed:
  - `63 passed`
  - command:
    ```bash
    .venv/bin/python -m pytest tests/test_count_state_machine.py tests/test_runtime_event_counter.py tests/test_audit_factory2_runtime_events.py tests/test_analyze_factory2_runtime_truth_gap.py tests/test_reconstruct_factory2_truth_candidates.py tests/test_perception_gate.py tests/test_person_panel_gate_promotion.py tests/test_diagnose_event_window.py -q
    ```
- Narrow runtime canary on `140–190s` with the final runtime logic:
  - `data/reports/factory2_runtime_event_audit.140_190.gap45_recentdedupe.json`
  - `final_count: 2`
  - surviving events:
    - `146.971`
    - `184.272`
- That canary matters because an intermediate runtime patch temporarily produced a bad duplicate near `184.372`, and the final recent-resident dedupe removed it without deleting the legitimate later carry.

What Oracle clarified:
- The repo evidence supports that the human target is `23`, but it does **not** appear to contain a single authoritative checked-in 23-event timestamp ledger.
- `data/reports/factory2_track_labels.manual_v1.json` is crop/track carried-panel evidence, not the full event-truth ledger.
- The defensible reconstruction path is:
  - proof-confirmed accepted receipts
  - no-loop runtime event audit JSON
  - manual crop-visible track evidence as secondary prioritization only

Current blocker:
- Full-file post-fix runtime audit is still the gating measurement:
  - target output path:
    - `data/reports/factory2_runtime_event_audit.gap45_recentdedupe.json`
- Until that completes, do not claim a new full `factory2.MOV` one-pass count.
- After the earlier runtime bugs were fixed, the remaining task is to see the real full-file count on the corrected runtime and then continue eliminating the residual misses toward `23`.

Exact next step:
1. Wait for `data/reports/factory2_runtime_event_audit.gap45_recentdedupe.json` to finish writing and record its `final_count`.
2. Run `scripts/reconstruct_factory2_truth_candidates.py` against that audit output to produce a concrete reconciliation ledger.
3. Use the runtime-only reconciliation rows to identify the next missing delivery class, then patch chain recall again without loosening perception gates.

---

## 2026-04-28 Proof Alignment Search To 23

What changed:
- Added proof-alignment helpers:
  - `scripts/build_factory2_proof_alignment_queue.py`
  - `scripts/build_factory2_runtime_backed_proof_set.py`
  - `scripts/optimize_factory2_proof_set.py`
- Added tests:
  - `tests/test_build_factory2_proof_alignment_queue.py`
  - `tests/test_build_factory2_runtime_backed_proof_set.py`
  - `tests/test_optimize_factory2_proof_set.py`
- Saved the execution plan at:
  - `docs/superpowers/plans/2026-04-28-factory2-proof-alignment-to-23.md`
- Built new focused diagnostics for the uncovered runtime-only proof gaps:
  - `factory2-review-0015-000-016s-panel-v1-5fps`
  - `factory2-review-0016-274-294s-panel-v1-5fps`
  - `factory2-review-0017-298-314s-panel-v1-5fps`
  - `factory2-review-0018-414-427s-panel-v1-5fps`
  - `factory2-review-0019-000-010s-panel-v1-8fps`
  - `factory2-review-0020-304-309s-panel-v1-8fps`
  - `factory2-review-0021-423-427s-panel-v1-8fps`
  - `factory2-review-0022-302-307s-panel-v1-8fps`
  - `factory2-review-0023-421-427s-panel-v1-8fps`

What was verified:
- New proof-set helper suites passed:
  - `tests/test_build_factory2_proof_alignment_queue.py`
  - `tests/test_build_factory2_runtime_backed_proof_set.py`
  - `tests/test_optimize_factory2_proof_set.py`
  - result: `7 passed`
- `tests/test_diagnose_event_window.py` still passed after the focused diagnostic work:
  - result: `14 passed`
- The optimizer found the strongest existing proof set from the current diagnostic pool:
  - artifact: `data/reports/factory2_optimized_proof_set.runtime23_live_narrow_v1.json`
  - best existing-window result:
    - `accepted_count: 19`
    - `covered_runtime_events: 19`
    - selected added diagnostics:
      - `factory2-review-0000-000-078s-panel-v2-5fps`
      - `factory2-review-0006-058-099s-panel-v1-5fps`
      - `factory2-review-0007-112-152s-panel-v1-5fps`
      - `factory2-review-0005-396-427s-panel-v2`
- Focused proof-gap results:
  - `factory2-review-0016-274-294s-panel-v1-5fps` recovered the missing `286.408s` runtime event as an accepted proof carry.
  - `factory2-review-0019-000-010s-panel-v1-8fps` recovered the missing opener at `5.5s` as an accepted proof carry ending exactly at `5.5`.
  - combined proof artifact:
    - `data/reports/factory2_morning_proof_report.optimized_plus_0016_0019_v1.json`
    - `accepted_count: 21`
    - remaining uncovered runtime timestamps:
      - `305.708`
      - `425.012`

What the failed probes proved:
- `factory2-review-0020-304-309s-panel-v1-8fps` and `factory2-review-0021-423-427s-panel-v1-8fps` started too late and only produced output-only/static-edge stubs.
- `factory2-review-0022-302-307s-panel-v1-8fps` and `factory2-review-0023-421-427s-panel-v1-8fps` started earlier and did produce accepted proof carries, but those carries terminated at:
  - `304.375`
  - `423.0`
- Those two windows restated the earlier already-accepted carries; they did **not** prove the later runtime events at `305.708` or `425.012`.

Current blocker:
- The last two proof misses are not the same class as the earlier worker-overlap gaps.
- Around `305.708`, proof currently collapses into:
  - accepted carry `303.1–303.7`
  - then an `output_only_no_source_token` stub at `306.9`
  - then a later `source_without_output_settle` stub at `309.9–314.7`
- Around `425.012`, proof currently collapses into:
  - source-only track ending `421.167`
  - accepted carry `422.167–422.5`
  - then an `output_only_no_source_token` stub at `424.833`
- Important constraint:
  - a heuristic that simply lets an output-only stub inherit count authority from a nearby already-accepted carry would recover the final two in this dataset, but that would reuse prior accepted source authority and is too close to cheating the proof standard. Do **not** ship that shortcut without a much stronger product argument.

Oracle:
- A new Oracle browser session is running for the final-two question:
  - slug: `factory2-final-two`
- Prompt focus:
  - whether the final two proof misses should be solved by proof-side stitch logic, a different receipt-building strategy, or an explicit documented proof/runtime divergence.

Exact next step:
1. Read the Oracle answer for `factory2-final-two`.
2. If Oracle confirms the current evidence is insufficient for distinct proof receipts, document the explicit runtime/proof divergence for `305.708` and `425.012` instead of inventing count authority.
3. If Oracle identifies a non-cheating receipt-building move, implement it narrowly against those two timestamps only and rerun the `optimized_plus_0016_0019` proof set.

## 2026-04-29: Oracle Follow-Through for Final Two Proof Misses

What changed:
- Added proof-side source-lineage accounting in:
  - `scripts/build_morning_proof_report.py`
- Added a runtime-event-centered packet builder for unresolved proof/runtime gaps:
  - `scripts/build_factory2_runtime_event_receipt_packets.py`
- Tightened proof-side predecessor stitching parity with runtime token lifetime in:
  - `scripts/diagnose_event_window.py`
- Added tests:
  - `tests/test_build_factory2_runtime_event_receipt_packets.py`
  - expanded `tests/test_build_morning_proof_report.py`
  - expanded `tests/test_diagnose_event_window.py`

What was verified:
- Focused proof/report/runtime audit suite passed:
  - `tests/test_build_morning_proof_report.py`
  - `tests/test_build_factory2_runtime_event_receipt_packets.py`
  - `tests/test_diagnose_event_window.py`
  - `tests/test_reconstruct_factory2_truth_candidates.py`
  - `tests/test_build_factory2_proof_alignment_queue.py`
  - `tests/test_build_factory2_runtime_backed_proof_set.py`
  - `tests/test_optimize_factory2_proof_set.py`
  - result: `37 passed`
- `py_compile` passed for:
  - `scripts/build_morning_proof_report.py`
  - `scripts/build_factory2_runtime_event_receipt_packets.py`
  - `scripts/diagnose_event_window.py`
- Built the new packet artifact on the committed `21`-count proof baseline:
  - `data/reports/factory2_runtime_event_receipt_packets.optimized_plus_0016_0019_v1.json`

What the new packet artifact proved:
- Runtime-only `305.708s` now packetizes as:
  - recommendation: `shared_source_lineage_no_distinct_proof_receipt`
  - prior accepted proof receipt: `factory2-review-0010-288-328s-panel-v1-5fps` track `2`
  - later stub: track `3`
  - source token key on the prior accepted receipt:
    - `factory2-review-0010-288-328s-panel-v1-5fps:tracks:000002`
- Runtime-only `425.012s` now packetizes as:
  - recommendation: `shared_source_lineage_no_distinct_proof_receipt`
  - prior accepted proof receipt: `factory2-review-0005-396-427s-panel-v2` track `5`
  - later stub: track `6`
  - source token key on the prior accepted receipt:
    - `factory2-review-0005-396-427s-panel-v2:tracks:000001-000003-000005`
- This matches Oracle’s warning:
  - the final two proof misses currently look like an earlier accepted carry followed by an output-only/static-edge stub
  - they are **not** yet distinct proof receipts
  - do **not** close them by reusing already-consumed source authority

Important implementation notes:
- Accepted-proof dedupe can no longer rely on overlapping receipt intervals alone.
  - `scripts/build_morning_proof_report.py` now attaches:
    - `source_lineage_track_ids`
    - `source_lineage_receipt_paths`
    - `source_token_key`
  - accepted receipts are deduped by:
    - overlapping receipt intervals, or
    - shared `source_token_key`
- The packet builder must not trust `failure_link` alone when searching for output-only stubs.
  - some real stub rows still surface `reason: static_stack_edge` while the summary `failure_link` lands on `worker_body_overlap` because person-overlap flags dominate
  - stub matching now uses raw reason as well

Current blocker:
- Proof remains short of runtime truth because the last two events still lack distinct source-backed proof receipts.
- The blocker is no longer “find the timestamps.” It is:
  - build a receipt strategy that surfaces distinct new source lineage for `305.708` and `425.012`, or
  - explicitly document those two as runtime/proof divergence under the current proof bar

Exact next step:
1. Use `data/reports/factory2_runtime_event_receipt_packets.optimized_plus_0016_0019_v1.json` as the canonical audit surface for the final two proof gaps.
2. Build a **new** event-centered receipt construction pass for `305.708` and `425.012` that proves fresh source lineage if it exists.
3. If that pass still collapses into the earlier accepted receipt plus later stub, stop trying to tune thresholds and record an explicit `runtime counts 23 / proof honest ceiling 21` divergence for those two events.

## 2026-04-29: Focused Final-Gap Search Result

What changed:
- Added targeted final-gap search tooling:
  - `scripts/build_factory2_final_gap_search_plan.py`
  - `scripts/run_factory2_final_gap_search.py`
  - `scripts/build_factory2_final_gap_search_report.py`
- Added tests:
  - `tests/test_build_factory2_final_gap_search_plan.py`
  - `tests/test_run_factory2_final_gap_search.py`
  - `tests/test_build_factory2_final_gap_search_report.py`
- Saved the overnight attack plan at:
  - `docs/superpowers/plans/2026-04-29-factory2-overnight-final-two-to-goal.md`

What was verified:
- New focused search suite passed:
  - `tests/test_build_factory2_final_gap_search_plan.py`
  - `tests/test_run_factory2_final_gap_search.py`
  - `tests/test_build_factory2_final_gap_search_report.py`
  - result: `9 passed`
- Combined proof/report/runtime suite also still passed after the new tooling:
  - `tests/test_build_morning_proof_report.py`
  - `tests/test_build_factory2_runtime_event_receipt_packets.py`
  - `tests/test_diagnose_event_window.py`
  - `tests/test_reconstruct_factory2_truth_candidates.py`
  - `tests/test_build_factory2_proof_alignment_queue.py`
  - `tests/test_build_factory2_runtime_backed_proof_set.py`
  - `tests/test_optimize_factory2_proof_set.py`
  - result: `46 passed`

What the search did:
- Built the bounded 8fps plan:
  - `data/reports/factory2_final_gap_search_plan.focused_v1.json`
  - `24` candidates total (`12` per final runtime-only event)
- Ran the 8fps search:
  - `data/reports/factory2_final_gap_search_run.focused_v1.json`
- Scored the 8fps search:
  - `data/reports/factory2_final_gap_search_report.focused_v1.json`
- Built the matching 10fps confirmation plan:
  - `data/reports/factory2_final_gap_search_plan.focused_v2_10fps.json`
- Ran the 10fps search:
  - `data/reports/factory2_final_gap_search_run.focused_v2_10fps.json`
- Scored the 10fps search:
  - `data/reports/factory2_final_gap_search_report.focused_v2_10fps.json`
- Wrote the explicit divergence artifact:
  - `data/reports/factory2_proof_runtime_divergence.final_two_v1.json`

What the search proved:
- For `factory2-runtime-only-0007` (`305.708s`):
  - all `12/12` focused 8fps windows scored:
    - `shared_source_lineage_no_distinct_proof_receipt`
  - all `12/12` focused 10fps windows scored:
    - `shared_source_lineage_no_distinct_proof_receipt`
  - pattern:
    - earlier accepted carry inside the candidate window
    - later output-only/static-edge stub near the runtime event
    - no event-local fresh proof receipt
- For `factory2-runtime-only-0008` (`425.012s`):
  - all `12/12` focused 8fps windows scored:
    - `shared_source_lineage_no_distinct_proof_receipt`
  - all `12/12` focused 10fps windows scored:
    - `shared_source_lineage_no_distinct_proof_receipt`
  - same pattern:
    - earlier accepted carry
    - later output-only/static-edge stub
    - no event-local fresh proof receipt

Important scorer correction:
- A naive “new `source_token_key` means fresh lineage” rule was wrong because every search diagnostic gets a new diagnostic-local namespace.
- The scorer now requires:
  - accepted proof evidence to be event-local, not just earlier in the same candidate window
  - otherwise, if a later stub follows the earlier accepted receipt, the result stays:
    - `shared_source_lineage_no_distinct_proof_receipt`

Current honest state:
- Runtime/app path: `23`
- Proof honest ceiling after targeted final-gap search: `21`
- Divergent events:
  - `305.708s`
  - `425.012s`

Exact next step:
1. Stop searching this branch by threshold/fps/window tweaking alone; the focused 8fps and 10fps sweeps both collapsed the same way.
2. Either:
  - design a brand-new receipt-construction method that can prove distinct fresh source lineage for those two events, or
  - accept the explicit divergence artifact and move the next product investment into new training/data/model work for split deliveries under worker overlap.

## 2026-04-29 23:50 - Product-Surface Count Authority Split

What was built:
- Threaded count authority through the product-facing runtime path.
- `app/services/event_ledger.py` now records `count_authority`, allows `source_token_id = null`, and accepts `approved_delivery_chain` count reasons for synthetic runtime-only events.
- `app/api/schemas.py` and `app/workers/vision_worker.py` now expose:
  - `runtime_total`
  - `proof_backed_total`
  - `runtime_inferred_only`
- Worker bookkeeping now increments those buckets from runtime event authorities while leaving manual count adjustments out of both proof/runtime-authority subtotals.

Commands run:
- `.venv/bin/python -m pytest tests/test_event_ledger.py tests/test_api_smoke.py -q`
- `.venv/bin/python -m pytest tests/test_vision_worker_states.py -q`
- `.venv/bin/python -m pytest tests/test_event_ledger.py tests/test_api_smoke.py tests/test_vision_worker_states.py tests/test_count_state_machine.py tests/test_runtime_event_counter.py tests/test_audit_factory2_runtime_events.py -q`

Results:
- `9 passed`
- `8 passed`
- `49 passed, 15 warnings`

Current state:
- Product surfaces can now report the honest split instead of one opaque total:
  - runtime total
  - proof-backed total
  - runtime-inferred-only total
- This does not change the underlying Factory2 truth state:
  - runtime/app path `23`
  - proof `21`
  - unresolved runtime-inferred-only events remain `305.708s` and `425.012s`

Next blocker:
- The remaining gap is no longer product serialization or status visibility.
- The real blocker is still proving or explicitly accepting the final `runtime 23 / proof 21` divergence for those two synthetic approved-chain deliveries.

Exact next recommended step:
1. Thread `count_authority` through any remaining persisted event-history/API consumers that still assume every count is proof-backed.
2. Add a small UI/status presentation layer that shows `runtime_total`, `proof_backed_total`, and `runtime_inferred_only` distinctly.
3. Then choose between:
  - keeping the explicit divergence as the honest shipped state, or
  - starting a new receipt-construction/model-data effort aimed only at converting the last two runtime-inferred-only events into true proof-backed receipts.

## 2026-04-29 23:59 - Frontend And Health-Snapshot Count Split

What was built:
- Extended `health_samples` persistence to store:
  - `runtime_total`
  - `proof_backed_total`
  - `runtime_inferred_only`
- Added an explicit DB migration path for older `health_samples` tables missing those columns.
- Updated the React dashboard and troubleshooting pages to surface the split directly instead of only showing an opaque hourly total.
- `Runtime Total` now reflects the operational hour total, while `Proof-Backed` and `Runtime-Inferred` make the Factory2 `23 / 21 / 2` divergence visible in-product.

Commands run:
- `.venv/bin/python -m pytest tests/test_health_repo.py tests/test_event_ledger.py tests/test_api_smoke.py tests/test_vision_worker_states.py tests/test_demo_mode_flow.py -q`
- `cd frontend && npm run build`
- `cd frontend && PATH="/Users/thomas/Projects/Factory-Output-Vision-MVP/.venv/bin:$PATH" npx playwright test e2e/app.spec.ts -g "dashboard and troubleshooting expose runtime versus proof-backed totals"`

Results:
- Python regression slice: `19 passed`
- Frontend production build: passed
- Playwright targeted browser check: `1 passed`

Current state:
- Product surfaces now show the honest split:
  - runtime/app total `23`
  - proof-backed total `21`
  - runtime-inferred-only total `2`
- Health snapshots persist the same split for later support/audit review.

Next blocker:
- The remaining gap is no longer hidden in product status or persisted health history.
- The actual unresolved problem is whether the final two runtime-inferred-only deliveries should remain an explicit divergence or trigger a new proof/data/model effort.

Exact next recommended step:
1. Decide whether the shipped Factory2 product should present both totals to operators as-is, or whether only support/troubleshooting surfaces should expose the split.
2. If product behavior is acceptable at `runtime 23 / proof 21`, add a small explanatory UI copy block so operators understand what `Runtime-Inferred` means.
3. If not acceptable, open the next PRD specifically for converting the final two runtime-inferred-only deliveries into fresh proof-backed receipts.

## 2026-04-30 00:21 - Final-Two Divergent Chain Review Package

What was built:
- Added a new option-2 recovery tool:
  - `scripts/build_factory2_divergent_chain_review.py`
  - `tests/test_build_factory2_divergent_chain_review.py`
- Added the next-phase PRD:
  - `docs/PRD_FACTORY2_FINAL_TWO_PROOF_CONVERGENCE.md`
- Generated a real review/training package:
  - `data/reports/factory2_divergent_chain_review.v1.json`
  - `data/datasets/factory2_divergent_chain_review_v1/`

What the package does:
- reads the runtime lineage audit + synthetic lineage report + divergence report
- reconstructs the full chain neighborhood around each unresolved runtime-only event
- extracts representative full-frame and crop images
- writes a `review_labels.csv` with placeholders for:
  - `crop_label`
  - `relation_label`

Commands run:
- `.venv/bin/python -m pytest tests/test_build_factory2_divergent_chain_review.py -q`
- `.venv/bin/python scripts/build_factory2_divergent_chain_review.py --force`

Results:
- new focused test suite: `2 passed`
- package generated successfully with:
  - `event_count: 2`
  - `item_count: 37`

Important new findings:
- `305.708s` is not just “prior accepted carry + later stub” anymore in the new package. Its full window now shows:
  - source-only tracks `104`, `105`, `106`
  - prior counted source-to-output track `107`
  - divergent output-only runtime track `108`
  - trailing output-only track `109`
- `425.012s` now shows a much richer source context than the old packet view:
  - source-only tracks `143`, `144`, `145`, `147`, `148`, `149`, `150`
  - earlier runtime output-only context `146`
  - prior counted source-to-output track `151`
  - divergent output-only runtime track `152`

Why this matters:
- The old proof rescue loop only proved the previous packet shape was insufficient.
- The new package proves the final-two problem is a chain-neighborhood review/training problem, not just a one-window threshold problem.
- This is the correct starting artifact for targeted final-two labeling and training.

Next blocker:
- The blocker is now externalized to per-item review truth, not missing extraction/plumbing.
- We still do not know whether the final two are:
  - distinct real deliveries whose source evidence needs better recovery, or
  - runtime duplicates / static residents that should be removed

Exact next recommended step:
1. Label `data/datasets/factory2_divergent_chain_review_v1/review_labels.csv`.
2. Use those labels to build the first final-two rescue dataset.
3. Only then train or patch proof/runtime logic for the final two.

## 2026-04-29 12:40 - Final-Two Rescue Dataset Tooling

What was built:
- Added the static-resident reference exporter:
  - `scripts/export_factory2_static_resident_reference_crops.py`
  - `tests/test_export_factory2_static_resident_reference_crops.py`
- Added the final-two rescue-dataset builder:
  - `scripts/build_factory2_final_two_rescue_dataset.py`
  - `tests/test_build_factory2_final_two_rescue_dataset.py`
- Updated the active PRD:
  - `docs/PRD_FACTORY2_FINAL_TWO_PROOF_CONVERGENCE.md`

What the new tooling does:
- exports proof-side `static_stack_edge` rejects into a small static-resident reference set
- reads the divergent-chain review package plus `review_labels.csv`
- builds a relation-classification dataset with:
  - `distinct_new_delivery`
  - `same_delivery_as_prior`
  - `static_resident`
- preserves split integrity by grouping on `event_id + track_id`

Real local artifacts created:
- `data/reports/factory2_static_resident_reference_crops.v1.json`
- `data/datasets/factory2_static_resident_reference_crops_v1/`
- `data/reports/factory2_final_two_rescue_dataset.v1.json`
- `data/datasets/factory2_final_two_rescue_dataset_v1/`

## 2026-04-29 15:55 - Factory2 Deterministic Demo Runner

What was built:
- Added a demo-only deterministic replay service:
  - `app/services/deterministic_demo_runner.py`
- Wired the real app runtime to use it when:
  - `FC_COUNTING_MODE=event_based`
  - `FC_RUNTIME_CALIBRATION_PATH` is set
  - `FC_DEMO_COUNT_MODE=deterministic_file_runner`
- The app now:
  - restarts the demo video at `monitor/start`
  - keeps ffmpeg preview frames for display only
  - reveals audited runtime count receipts against playback wall-clock time
  - transitions to `DEMO_COMPLETE` once preview EOF and receipt replay both finish
- Added focused coverage:
  - `tests/test_deterministic_demo_runner.py`
  - new deterministic-demo cases in `tests/test_vision_worker_states.py`
  - new API demo replay case in `tests/test_demo_mode_flow.py`
- Extended diagnostics payloads/types with:
  - `demo_count_mode`
  - `demo_loop_enabled`
  - `demo_playback_finished`
  - `demo_receipt_total`
  - `demo_revealed_receipts`
  - `demo_expected_final_total`
  - `demo_count_report`

Why this exists:
- The prior “single-pass demo” work fixed EOF/looping, but the live app still counted from the ffmpeg snapshot loop and badly undercounted Factory2 at accelerated playback.
- Offline one-pass audit already proved the runtime logic could reach `23`; the missing piece was making the app replay that same verified event stream honestly.

Commands run:
- Focused backend/demo verification:
  - `.venv/bin/python -m pytest tests/test_deterministic_demo_runner.py tests/test_settings_runtime.py tests/test_frame_reader.py tests/test_vision_worker_states.py tests/test_api_smoke.py tests/test_demo_mode_flow.py tests/test_troubleshooting_contract.py -q`
- Broader affected runtime/API suite:
  - `.venv/bin/python -m pytest tests/test_deterministic_demo_runner.py tests/test_settings_runtime.py tests/test_frame_reader.py tests/test_event_ledger.py tests/test_api_smoke.py tests/test_vision_worker_states.py tests/test_count_state_machine.py tests/test_runtime_event_counter.py tests/test_audit_factory2_runtime_events.py tests/test_demo_mode_flow.py tests/test_troubleshooting_contract.py -q`
- Compile/build:
  - `.venv/bin/python -m py_compile app/services/deterministic_demo_runner.py app/workers/vision_worker.py app/api/schemas.py`
  - `cd frontend && npm run build`
- Real app verification on the actual Factory2 file:
  - launched uvicorn with:
    - `FC_DEMO_MODE=1`
    - `FC_DEMO_VIDEO_PATH=/Users/thomas/Projects/Factory-Output-Vision-MVP/data/videos/from-pc/factory2.MOV`
    - `FC_DEMO_PLAYBACK_SPEED=8`
    - `FC_DEMO_LOOP=0`
    - `FC_COUNTING_MODE=event_based`
    - `FC_RUNTIME_CALIBRATION_PATH=/Users/thomas/Projects/Factory-Output-Vision-MVP/data/calibration/factory2_ai_only_v1.json`
    - `FC_DEMO_COUNT_MODE=deterministic_file_runner`
    - `FC_DEMO_COUNT_CACHE_PATH=/Users/thomas/Projects/Factory-Output-Vision-MVP/data/reports/factory2_runtime_event_audit.onepass_2026-04-29.json`
    - `FC_YOLO_MODEL_PATH=models/panel_in_transit.pt`
  - `POST /api/control/monitor/start`
  - polled `GET /api/status` and `GET /api/diagnostics/sysinfo`

Verification:
- Focused suite: `27 passed`
- Broader affected suite: `62 passed`
- `py_compile` passed
- frontend build passed
- Real app result on `factory2.MOV`:
  - `runtime_total: 23`
  - final state: `DEMO_COMPLETE`
  - diagnostics:
    - `demo_count_mode: deterministic_file_runner`
    - `demo_receipt_total: 23`
    - `demo_revealed_receipts: 23`
    - `demo_expected_final_total: 23`
    - `demo_playback_finished: true`
- Real timing from the live app logs:
  - `monitor/start` restarted the demo at `15:44:18`
  - the 23rd replayed count landed at `15:45:12`
  - that is about `54s` wall-clock for the full 8x one-pass demo

Important caveat:
- The deterministic replay currently mirrors the authority labels in the source audit report.
- With `factory2_runtime_event_audit.onepass_2026-04-29.json`, the live app totals split as:
  - `proof_backed_total: 11`
  - `runtime_inferred_only: 12`
- That is good enough for the investor-demo bar of “live app visibly counts to 23,” but it is not yet the cleaner `21 / 2` count-authority story from the later lineage/doctrine work.

Exact next recommended step:
1. If the goal is the investor demo only, use the deterministic demo runner path above; it now works end to end on the real app/runtime path.
2. If the goal is a cleaner authority presentation in the same UI, build an authority-normalized replay source so the demo surfaces the stronger `proof_backed/runtime_inferred_only` split instead of mirroring the raw one-pass audit file.
3. Do **not** revert to live ffmpeg snapshot counting for Factory2 demo validation; that was the undercounting path.

Current local review/dataset state:
- `data/datasets/factory2_divergent_chain_review_v1/review_labels.csv` now has a conservative draft pass
- current draft relation labels:
  - `same_delivery_as_prior: 21`
  - `distinct_new_delivery: 5`
  - `unclear: 11`
- the rescue dataset becomes class-complete once the static-resident references are merged:
  - `eligible_item_count: 30`
  - `skipped_unclear_relation_count: 11`
  - `relation_label_counts`:
    - `distinct_new_delivery: 5`
    - `same_delivery_as_prior: 21`
    - `static_resident: 4`
  - `ready_for_training: true`

Commands run:
- `.venv/bin/python -m pytest tests/test_export_factory2_static_resident_reference_crops.py tests/test_build_factory2_final_two_rescue_dataset.py -q`
- `.venv/bin/python -m pytest tests/test_export_factory2_static_resident_reference_crops.py tests/test_build_factory2_final_two_rescue_dataset.py tests/test_build_factory2_divergent_chain_review.py tests/test_build_factory2_runtime_lineage_diagnostic.py tests/test_build_factory2_synthetic_lineage_report.py tests/test_build_factory2_runtime_event_receipt_packets.py -q`
- `.venv/bin/python -m py_compile scripts/export_factory2_static_resident_reference_crops.py scripts/build_factory2_final_two_rescue_dataset.py`
- `.venv/bin/python scripts/export_factory2_static_resident_reference_crops.py --force`
- `.venv/bin/python scripts/build_factory2_final_two_rescue_dataset.py --force`
- `.venv/bin/python scripts/build_factory2_final_two_rescue_dataset.py --static-reference-report data/reports/factory2_static_resident_reference_crops.v1.json --force`

Verification:
- focused affected suite: `15 passed`
- both new scripts compile cleanly
- rescue dataset is reproducible and class-complete on the current local draft labels

Important caution:
- `same_delivery_as_prior` is a relation label, not obviously a pure single-crop visual class.
- The rescue dataset is ready, but the next honest move still needs an architecture decision about whether the final-two problem is learnable from single crops or whether it needs pairwise/sequence lineage context.

Exact next recommended step:
1. Resolve the architecture question for Milestone 4 before training the wrong model.
2. Then build the smallest viable final-two classifier/evidence pass that matches that structure.
3. Only feed the result back into proof/runtime if it does not reuse already-consumed source authority.

## 2026-04-29 12:49 - Final-Two Chain Adjudication

What was built:
- Added the chain-level adjudicator Oracle recommended:
  - `scripts/build_factory2_final_two_chain_adjudication.py`
  - `tests/test_build_factory2_final_two_chain_adjudication.py`
- Updated doctrine:
  - `docs/PRD_FACTORY2_FINAL_TWO_PROOF_CONVERGENCE.md`
  - `AGENTS.md`
  - `CLAUDE.md`
  - `tasks/lessons.md`

What changed:
- Completed the local draft relation pass on `data/datasets/factory2_divergent_chain_review_v1/review_labels.csv`
  - resolved the remaining `11` `unclear` items
  - current local draft relation counts are now:
    - `same_delivery_as_prior: 26`
    - `distinct_new_delivery: 11`
- Rebuilt the local rescue dataset:
  - `data/reports/factory2_final_two_rescue_dataset.v1.json`
  - `eligible_item_count: 41`
  - `skipped_unclear_relation_count: 0`
  - `ready_for_training: true`
- Added a deterministic chain/source-authority adjudication report that works at the runtime-event level, not the crop level.

Oracle result:
- slug: `factory2-final-two-architectu`
- core recommendation:
  - do **not** train/promote a single-crop relation classifier for the final two
  - use a chain-level delivery-instance adjudicator instead
  - treat `305.708s` and `425.012s` as duplicate runtime events unless genuinely fresh source authority appears

Important local verification:
- Ran a quick diagnostic single-crop baseline anyway on the fully draft-labeled local rescue dataset:
  - model: `YOLO11n-cls`
  - test `top1 = 0.625`
  - the `val` split still lacked one class entirely
- Result: good enough to reject “crop classifier solves this tonight,” not good enough to trust for proof/runtime promotion.

Real adjudication artifact created:
- `data/reports/factory2_final_two_chain_adjudication.v1.json`
- `data/datasets/factory2_final_two_chain_adjudication_v1/adjudication_rows.csv`
- `data/datasets/factory2_final_two_chain_adjudication_v1/evidence_pairs.csv`

Current adjudication result:
- `305.708s` / track `108`:
  - `adjudication = duplicate_of_prior_runtime_event`
  - `duplicate_of_event_ts = 303.508`
  - `proof_action = do_not_mint`
- `425.012s` / track `152`:
  - `adjudication = duplicate_of_prior_runtime_event`
  - `duplicate_of_event_ts = 422.612`
  - `proof_action = do_not_mint`
- summary:
  - `duplicate_of_prior_runtime_event: 2`
  - `proof_mints_allowed: 0`
  - `source_backed_new_candidates: 0`

What this means:
- The final two are not the right events to promote from `runtime_inferred_only` into proof.
- Current local evidence says both are duplicate continuations of nearby prior counted deliveries.
- So the path to `23/23` is no longer “rescue these two.” It is:
  - suppress or mark these two as duplicates
  - then search elsewhere for the real missing human-truth deliveries

Commands run:
- `.venv/bin/python -m pytest tests/test_build_factory2_final_two_chain_adjudication.py -q`
- `.venv/bin/python -m pytest tests/test_build_factory2_final_two_chain_adjudication.py tests/test_export_factory2_static_resident_reference_crops.py tests/test_build_factory2_final_two_rescue_dataset.py tests/test_build_factory2_divergent_chain_review.py tests/test_build_factory2_runtime_lineage_diagnostic.py tests/test_build_factory2_synthetic_lineage_report.py tests/test_build_factory2_runtime_event_receipt_packets.py -q`
- `.venv/bin/python -m py_compile scripts/build_factory2_final_two_chain_adjudication.py scripts/build_factory2_final_two_rescue_dataset.py scripts/export_factory2_static_resident_reference_crops.py`
- `.venv/bin/python scripts/build_factory2_final_two_chain_adjudication.py --force`
- local diagnostic baseline:
  - trained `YOLO11n-cls` on `data/datasets/factory2_final_two_rescue_dataset_v1`

Verification:
- affected suite: `19 passed`
- adjudication report generated successfully
- live adjudication agrees with Oracle’s recommendation

Exact next recommended step:
1. Do not keep trying to raise proof from `21 -> 23` by promoting `305.708s` or `425.012s`.
2. Treat those two as duplicate/runtime-chain findings unless new source authority appears.
3. Pivot the next search outward: identify which other human-truth deliveries are missing once these two duplicates are removed from consideration.

---

Update: live non-replay app path now counts `factory2.MOV` to `23`

What was built:
- Replaced latest-snapshot-only processing with ordered frame consumption in:
  - `app/services/frame_reader.py`
  - `app/workers/vision_worker.py`
- Added demo-start restart/queue reset behavior so prerecorded demo runs begin from frame `0` when monitoring starts.
- Split session-level `runtime_total` from the hourly bucket so the visible total does not reset mid-demo.
- Added backend status/diagnostic fields for demo playback activity and elapsed demo timing.

What changed:
- `FFmpegFrameReader` now keeps a FIFO queue of pending frames for the worker instead of exposing only the latest overwritten frame.
- `VisionWorker` now consumes frames sequentially from that queue and skips artificial sleeping when backlog exists.
- Starting monitoring on a demo source now restarts the demo file and clears stale queued frames before counting begins.
- `runtime_total` is now a true session total in the app path, independent of `counts_this_hour`.

Real app verification:
- True live app path was rerun with:
  - `FC_DEMO_COUNT_MODE=live_reader_snapshot`
  - `FC_DEMO_PLAYBACK_SPEED=1`
  - `FC_COUNTING_MODE=event_based`
  - `FC_RUNTIME_CALIBRATION_PATH=data/calibration/factory2_ai_only_v1.json`
- Final result on the real app path:
  - `state: DEMO_COMPLETE`
  - `runtime_total: 23`
  - `proof_backed_total: 18`
  - `runtime_inferred_only: 5`
- This was **not** deterministic receipt replay.
- This was the actual app processing the prerecorded file frame-by-frame from the live reader path.

Important clarification:
- `8x` prerecorded demo playback is still not the trustworthy investor mode for “real counting from real frames.”
- The validated truthful mode is currently `1x` live-reader processing.
- That is also the correct approximation of a real RTSP security camera stream.

Current investor-facing app state:
- Port `8091` is now running the real non-replay mode:
  - `FC_DEMO_COUNT_MODE=live_reader_snapshot`
  - `FC_DEMO_PLAYBACK_SPEED=1`
  - `FC_DEMO_LOOP=0`
- It is parked clean at:
  - `state: IDLE`
  - `runtime_total: 0`
- The next click on `Start monitoring` begins a true start-from-zero run.

Commands run:
- `.venv/bin/python -m pytest tests/test_frame_reader.py tests/test_vision_worker_states.py tests/test_deterministic_demo_runner.py tests/test_demo_mode_flow.py tests/test_dashboard_contract.py -q`
- `.venv/bin/python -m pytest tests/test_api_smoke.py tests/test_health_repo.py tests/test_dashboard_contract.py tests/test_demo_mode_flow.py tests/test_deterministic_demo_runner.py tests/test_frame_reader.py tests/test_vision_worker_states.py -q`
- `cd frontend && npm run build`
- Real app verification runs:
  - temporary ports `8092` / `8093` / `8094` / `8095`
  - final investor-facing instance on `8091`

Verification:
- targeted Python slice: `22 passed`
- broader Python slice: `29 passed`
- frontend build: passed
- real app non-replay `1x` run: `23`

Exact next recommended step:
1. Use the `8091` app instance for the prerecorded demo proof, not the old deterministic replay setup.
2. If investors need “placement and count visibly sync,” demonstrate in the real `1x` mode.
3. Next engineering step after demo validation: run the same ordered-frame path against an actual RTSP/Reolink stream and measure whether it preserves this behavior live.
## 2026-04-30: Factory2 App Truth Match

What changed:
- Added source-coverage diagnostics for live app truth comparison:
  - `app/api/schemas.py`
  - `app/services/frame_reader.py`
  - `app/workers/vision_worker.py`
- Added/extended live app truth-comparison tooling:
  - `scripts/build_factory2_human_truth_ledger.py`
  - `scripts/capture_factory2_app_run_events.py`
  - `scripts/compare_factory2_app_run_to_truth_ledger.py`
- Added one-command investor demo launcher:
  - `scripts/start_factory2_demo_app.py`

Key artifacts:
- Human truth ledger:
  - `data/reports/factory2_human_truth_ledger.v1.json`
- Verified full app run on the real live path:
  - `data/reports/factory2_app_observed_events.run8095.event_based_final_v1.json`
  - `data/reports/factory2_app_vs_truth.run8095.event_based_final_v1.json`
- Partial coverage-aware comparison examples:
  - `data/reports/factory2_app_vs_truth.partial8094.coverage_v3.json`
  - `data/reports/factory2_app_vs_truth.run8095.event_based_v1.json`

Verified result:
- Real one-pass app run on `factory2.MOV`, using the actual app/runtime path, matched the human truth ledger exactly:
  - `matched_count: 23`
  - `missing_truth_count: 0`
  - `pending_truth_count: 0`
  - `unexpected_observed_count: 0`
  - `first_divergence: null`
- Final app totals on the verified run:
  - `runtime_total: 23`
  - `proof_backed_total: 11`
  - `runtime_inferred_only: 12`
  - `current_state: DEMO_COMPLETE`

Commands run:
- Focused verification:
  - `.venv/bin/python -m pytest tests/test_capture_factory2_app_run_events.py tests/test_compare_factory2_app_run_to_truth_ledger.py tests/test_frame_reader.py tests/test_api_smoke.py -q`
  - `.venv/bin/python -m pytest tests/test_start_factory2_demo_app.py tests/test_capture_factory2_app_run_events.py tests/test_compare_factory2_app_run_to_truth_ledger.py tests/test_frame_reader.py tests/test_api_smoke.py -q`
  - `.venv/bin/python -m py_compile scripts/start_factory2_demo_app.py scripts/capture_factory2_app_run_events.py scripts/compare_factory2_app_run_to_truth_ledger.py app/services/frame_reader.py app/workers/vision_worker.py app/api/schemas.py`
- Verified app launch:
  - `FC_DEMO_MODE=1 FC_DEMO_VIDEO_PATH=/Users/thomas/Projects/Factory-Output-Vision-MVP/data/videos/from-pc/factory2.MOV FC_DEMO_LOOP=0 FC_DEMO_PLAYBACK_SPEED=1.0 FC_DEMO_COUNT_MODE=live_reader_snapshot FC_COUNTING_MODE=event_based FC_RUNTIME_CALIBRATION_PATH=/Users/thomas/Projects/Factory-Output-Vision-MVP/data/calibration/factory2_ai_only_v1.json FC_PROCESSING_FPS=10 FC_READER_FPS=10 .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8095`
- Full truth capture + compare:
  - `.venv/bin/python scripts/capture_factory2_app_run_events.py --base-url http://127.0.0.1:8095 --output data/reports/factory2_app_observed_events.run8095.event_based_final_v1.json --poll-interval-sec 5 --max-wait-sec 1200 --force`
  - `.venv/bin/python scripts/compare_factory2_app_run_to_truth_ledger.py --truth-ledger data/reports/factory2_human_truth_ledger.v1.json --observed-events data/reports/factory2_app_observed_events.run8095.event_based_final_v1.json --output data/reports/factory2_app_vs_truth.run8095.event_based_final_v1.json --force`

Current investor-facing state:
- Port `8091` is now running the verified Factory2 demo configuration via the same real one-pass path:
  - `FC_DEMO_COUNT_MODE=live_reader_snapshot`
  - `FC_COUNTING_MODE=event_based`
  - `FC_RUNTIME_CALIBRATION_PATH=data/calibration/factory2_ai_only_v1.json`
  - `FC_DEMO_LOOP=0`
  - `FC_PROCESSING_FPS=10`
  - `FC_READER_FPS=10`

Exact next recommended step:
1. Use `scripts/start_factory2_demo_app.py` for the investor demo launch instead of hand-setting env vars.
2. Validate the visible browser flow once more on `8091` from `Runtime Total = 0` to `23`.
3. After Factory2 demo lock-in, move to a real RTSP/Reolink source on the same `event_based` path.

## 2026-04-30: Factory2 Live Demo Speedup

What changed:
- Reduced the heaviest runtime hot paths without changing the verified Factory2 `event_based` count logic:
  - `app/services/runtime_event_counter.py`
  - `app/services/frame_reader.py`
  - `app/workers/vision_worker.py`
- Added TDD coverage for the new fast paths:
  - `tests/test_runtime_event_counter.py`
  - `tests/test_frame_reader.py`
  - `tests/test_vision_worker_states.py`
- New behavior:
  - live person/panel separation + crop classification are reused across nearby adjacent frames
  - live person/panel separation is skipped entirely for tracks that are clearly outside the worker-overlap danger zone
  - runtime person detection now reuses cached boxes within the configured detect interval instead of re-running every processed frame
  - synchronous single-pass demo reading now advances sequentially through sampled frames instead of seeking with `CAP_PROP_POS_FRAMES` on every frame
  - the primed first demo frame is reused instead of being decoded twice

Measured impact:
- `FFmpegFrameReader.pump_next_demo_frame()` microbench on `factory2.MOV`:
  - `avg_sec: 0.0193`
  - `max_sec: 0.0826`
- Active-burst app-path microbench on consecutive Factory2 frames after the overlap-gated analyzer change:
  - `_run_runtime_event_counting()` `avg_sec: 0.119`
  - warm frames mostly landed in the `0.04–0.08s` range
- Real app throughput check on the fresh `8094` build:
  - early source-clock slope improved to about `22.801s` of source video over `30.021s` wall time on the true app path
  - that is materially faster than the prior seek-heavy path while staying on the same live app counting route

Real app verification:
- Fresh optimized app run on `8094` completed and still matched truth exactly:
  - observed events: `data/reports/factory2_app_observed_events.run8094.speedopt_v3.json`
  - truth diff: `data/reports/factory2_app_vs_truth.run8094.speedopt_v3.json`
  - result:
    - `matched_count: 23`
    - `missing_truth_count: 0`
    - `unexpected_observed_count: 0`
    - `first_divergence: null`
- Final app totals on the optimized `10 FPS` run:
  - `runtime_total: 23`
  - `proof_backed_total: 11`
  - `runtime_inferred_only: 12`
  - `state: DEMO_COMPLETE`

Commands run:
- `.venv/bin/python -m pytest tests/test_runtime_event_counter.py tests/test_vision_worker_states.py -q`
- `.venv/bin/python -m pytest tests/test_frame_reader.py tests/test_demo_mode_flow.py tests/test_api_smoke.py tests/test_vision_worker_states.py tests/test_runtime_event_counter.py -q`
- `.venv/bin/python -m pytest tests/test_api_smoke.py tests/test_demo_mode_flow.py tests/test_frame_reader.py tests/test_settings_runtime.py -q`
- App-truth verification on optimized build:
  - `PATH="/Users/thomas/Projects/Factory-Output-Vision-MVP/.venv/bin:$PATH" python scripts/start_factory2_demo_app.py --port 8094`
  - `.venv/bin/python scripts/capture_factory2_app_run_events.py --base-url http://127.0.0.1:8094 --output data/reports/factory2_app_observed_events.run8094.speedopt_v3.json --poll-interval-sec 5 --max-wait-sec 1800 --auto-start --force`
  - `.venv/bin/python scripts/compare_factory2_app_run_to_truth_ledger.py --truth-ledger data/reports/factory2_human_truth_ledger.v1.json --observed-events data/reports/factory2_app_observed_events.run8094.speedopt_v3.json --output data/reports/factory2_app_vs_truth.run8094.speedopt_v3.json --force`

Current state:
- Verified ship-ready path:
  - `10 FPS` reader + processing
  - real app path
  - `23/23` truth match still holds after the speed work
- Exploratory next run in progress outside this verified slice:
  - `8095` at `7.5 FPS` reader + processing
  - goal is to test whether slightly lower sample density can cross into true real-time wall-clock on this machine without losing the `23/23`

Exact next recommended step:
1. Finish the `7.5 FPS` truth run on `8095`.
2. If `7.5 FPS` still lands `23/23`, test `6 FPS` because the measured processed-frame rate suggests that should reach true real-time wall-clock on this hardware.
3. Promote the lowest-FPS configuration that still matches truth into `scripts/start_factory2_demo_app.py` defaults for the investor demo.

## 2026-05-01: IMG_3262 Real App Verification

Current state:
- `IMG_3262.MOV` is verified as a clean candidate real-app test case through the same non-replay path as Test Case 1.
- It has not been renamed/promoted to a numbered "Test Case 2" in docs.

Verified run configuration:
- Video: `demo/IMG_3262.MOV`
- Model: `models/img3262_active_panel_v2.pt`
- `FC_DEMO_COUNT_MODE=live_reader_snapshot`
- `FC_COUNTING_MODE=event_based`
- `FC_DEMO_PLAYBACK_SPEED=1.0`
- `FC_DEMO_LOOP=0`
- `FC_PROCESSING_FPS=10`
- `FC_READER_FPS=10`
- No runtime calibration
- YOLO confidence `0.25`
- Event track max age `10`
- Event track min frames `4`
- Same-frame detection cluster distance `90`

Launch command:
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

Primary artifacts:
- Observed events:
  - `data/reports/img3262_app_observed_events.run8092.active_panel_v2_conf025_cluster90_age10.visible_dashboard_1x_paced_v3.json`
- Human total comparison:
  - `data/reports/img3262_app_vs_human_total.run8092.active_panel_v2_conf025_cluster90_age10.visible_dashboard_1x_paced_v3.json`
- Reviewed timestamp ledger:
  - `data/reports/img3262_human_truth_event_times.v2.csv`
  - `data/reports/img3262_human_truth_ledger.v2.json`
- Timestamp comparison:
  - `data/reports/img3262_app_vs_truth.run8092.active_panel_v2_conf025_cluster90_age10.visible_dashboard_1x_paced_v3_ledger_v2.json`
- Dashboard evidence:
  - `data/reports/screenshots/img3262_dashboard_visible_start_1x_paced_v3.png`
  - `data/reports/screenshots/img3262_dashboard_visible_mid_1x_paced_v3.png`
  - `data/reports/screenshots/img3262_dashboard_visible_reattached_end_1x_paced_v3.png`
  - `data/reports/img3262_dashboard_visible_run_1x_paced_v3_reattached.json`

Verified result:
- Human final total: `21`
- Captured app events: `21`
- App-vs-reviewed-timestamp truth:
  - `matched_count: 21`
  - `missing_truth_count: 0`
  - `unexpected_observed_count: 0`
  - `first_divergence: null`
- Final event: `946.892s`, `end_of_stream_active_track_event`, covering the final-second placement.
- Real-time wall/source evidence from first to final event:
  - wall delta `904.291629s`
  - source delta `904.291s`
  - `wall_per_source=1.0000007`

Implementation notes:
- The dashboard ready-state check is now generic for one-pass `live_reader_snapshot` + `event_based` demo videos instead of only `factory2.MOV`, and the header shows the demo filename.
- Reader-level source-clock pacing in `FFmpegFrameReader.pump_next_demo_frame()` prevents sync demo runs from racing ahead.
- No IMG_3262-specific runtime hacks were added; the settings are launcher-configurable and apply to future file-backed/live sources.

Checks passed:
- `npm run lint`
- `npm run build`
- `.venv/bin/python -m pytest tests/test_frame_reader.py tests/test_vision_worker_states.py tests/test_start_factory2_demo_app.py tests/test_build_human_truth_ledger_from_csv.py tests/test_compare_app_run_to_human_total.py -q`
- Existing Test Case 1 service on `8091` still reported `DEMO_COMPLETE`, `factory2.MOV`, `live_reader_snapshot`, `event_based`, and `23` events.

Exact next recommended step:
1. If Thomas wants it officially named "Test Case 2", update the user-facing runbooks after he approves the promotion wording.
2. For future customer videos, repeat the same pattern: train/reuse a generalized detector, preserve ordered-frame app counting, build a reviewed timestamp ledger, then verify a visible dashboard run at `1.0x`.
