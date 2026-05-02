# Factory2 Real-Time Demo Counting

## Goal

Make the verified Factory2 app path count `factory2.MOV` at true real-time (`1.0x`) speed from real processed frames, with the visible runtime count climbing when the worker places each panel and finishing at the human truth total of `23`.

## Checklist

- [x] Re-read the active Factory2 handoff/spec context and confirm the non-negotiable runtime semantics
- [x] Profile the verified `live_reader_snapshot` + `event_based` path to identify the real wall-clock bottlenecks
- [x] Implement the smallest safe performance/reliability changes that preserve ordered frame evidence and one-pass demo semantics
- [x] Reject any `factory2`-specific replay, timestamp, threshold-forcing, or retrospective shortcut that would not generalize to future live videos
- [x] Keep preview, counting, and lifecycle on the same real runtime frame stream so the visible app behavior remains honest
- [x] Add or update tests around the touched runtime/demo behavior
- [x] Verify the touched test suite passes
- [x] Run the live app path on `factory2.MOV` and compare observed events to the human truth ledger
- [x] Confirm the visible app path still finishes at `23` with no replay/timestamp shortcuts

## Review

- Implemented live-path speed/reliability changes without replay/timestamp counting: local crop-based person/panel separation, configurable live analysis cache, fractional frame sampling, source-clock pacing for synchronous demo frames, venv-safe/no-access-log app launcher, stable stack launcher, Vite proxy-based dashboard API calls, and a React Compiler-safe live preview state reset.
- Verified runtime app run `run8103.sourceclock_10fps_v1`: `23` observed events, truth comparison `matched_count=23`, `missing_truth_count=0`, `unexpected_observed_count=0`, `wall_per_source=1.0001`.
- Verified visible dashboard run `run8104.visible_dashboard_v1`: started monitoring from Chrome UI, dashboard reached `Demo complete` and `Runtime Total 23`; comparison artifact has `matched_count=23`, `missing_truth_count=0`, `unexpected_observed_count=0`, `wall_per_source=1.0`.
- Checks passed: `pytest tests/test_vision_worker_states.py tests/test_frame_reader.py tests/test_runtime_event_counter.py tests/test_start_factory2_demo_app.py -q`, `pytest tests/test_demo_mode_flow.py tests/test_api_smoke.py -q`, `npm run lint`, and `npm run build`.
- Documentation synced after verification: `.hermes/HANDOFF.md`, `AGENTS.md`, `CLAUDE.md`, `README.md`, `docs/ARCHITECTURE.md`, active Factory2 PRDs, `tasks/lessons.md`, and `docs/FACTORY2_REALTIME_APP_VALIDATION.md`.

# IMG_3262 Candidate Test Case

## Goal

Repeat the Test Case 1 process for `demo/IMG_3262.MOV`: real app counting from real ordered frames at `1.0x`, no replay or timestamp reveal, with the app count compared against human truth.

## Checklist

- [x] Confirm `IMG_3262.MOV` is present in the project and matches the Downloads copy
- [x] Generate preview assets for human review
- [x] Record the provisional human final total of `21`, including the final-second placement
- [x] Clear stale `8092`/`5174` processes before launching a new run
- [x] Fill or derive timestamped human truth events for all `21` completed placements
- [x] Build `data/reports/img3262_human_truth_ledger.v1.json`
- [x] Run the actual app path against `IMG_3262.MOV` at real-time speed with `live_reader_snapshot` + `event_based`
- [x] Verify the dashboard-visible flow starts at `0`, shows `IMG_3262.MOV`, and counts on completed placements
- [x] Capture observed app events from the real backend path
- [x] Compare observed app events to the timestamped truth ledger
- [x] Diagnose any undercount/overcount/timing failures using general calibration/model/runtime fixes only
- [x] Run relevant pytest after script/runtime changes
- [x] Re-check Test Case 1 behavior if touched runtime code can affect Factory2
- [ ] Promote to a named verified test case only if final total and event comparison are clean

## Review

- Verified on 2026-05-01 through the actual app/dashboard path at `1.0x` without replay, timestamp reveal, fake UI updates, offline retrospective counting, or IMG_3262-only hacks.
- Launch used `FC_DEMO_COUNT_MODE=live_reader_snapshot`, `FC_COUNTING_MODE=event_based`, `FC_DEMO_PLAYBACK_SPEED=1.0`, `models/img3262_active_panel_v2.pt`, no runtime calibration, YOLO confidence `0.25`, event track max age `10`, min frames `4`, and same-frame detection cluster distance `90`.
- Primary observed-events artifact: `data/reports/img3262_app_observed_events.run8092.active_panel_v2_conf025_cluster90_age10.visible_dashboard_1x_paced_v3.json`; result `observed_event_count=21`, `current_state=DEMO_COMPLETE`, final event at `946.892s` from `end_of_stream_active_track_event`.
- Human-total comparison: `data/reports/img3262_app_vs_human_total.run8092.active_panel_v2_conf025_cluster90_age10.visible_dashboard_1x_paced_v3.json`; result `expected_human_total=21`, `observed_event_count=21`, `total_matches=true`.
- Timestamped truth comparison against reviewed v2 ledger: `data/reports/img3262_app_vs_truth.run8092.active_panel_v2_conf025_cluster90_age10.visible_dashboard_1x_paced_v3_ledger_v2.json`; result `matched_count=21`, `missing_truth_count=0`, `unexpected_observed_count=0`, `first_divergence=null`.
- Real-time proof: first-to-final event wall/source delta was `904.291629s / 904.291s`, `wall_per_source=1.0000007`; reattached dashboard sampler ended at `Runtime Total 21` and `DEMO_COMPLETE`.
- The original v1 timestamp CSV was rough and compared at `17/21`; v2 corrected visually reviewed rough timestamps at counts `1`, `3`, `14`, and `17`, especially moving the erroneous `629s` event to `617s`.
- Checks passed: `npm run lint`, `npm run build`, and `.venv/bin/python -m pytest tests/test_frame_reader.py tests/test_vision_worker_states.py tests/test_start_factory2_demo_app.py tests/test_build_human_truth_ledger_from_csv.py tests/test_compare_app_run_to_human_total.py -q`.
- Test Case 1 was rechecked on `8091`: still `DEMO_COMPLETE` with `23` events under `live_reader_snapshot` + `event_based`.

# IMG_3254 Candidate Test Case

## Goal

Make `demo/IMG_3254.MOV` a verified real-time app-counting candidate faster than the prior IMG_3262 effort by reusing the Factory2/IMG_3262 real app validation path, model/settings, capture scripts, and truth-ledger workflow.

## Checklist

- [x] Use `task-kickoff`, goal mode, and the `factory-video-testcase-validation` skill
- [x] Read the active project handoff, lessons, todo, Factory2 runbooks, IMG_3262 workflow, and real-app definition of done
- [x] Check dirty worktree and preserve unrelated existing changes
- [x] Check stale candidate ports/processes without touching Test Case 1 on `8091`/`5173`
- [x] Copy `~/Downloads/IMG_3254.MOV` to `demo/IMG_3254.MOV` without deleting the Downloads copy
- [x] Fingerprint/probe `demo/IMG_3254.MOV` and generate preview assets
- [x] Run an accelerated diagnostic using IMG_3262 verified model/settings as the baseline
- [x] Derive candidate app event timestamps and inspect only ambiguous/mismatch moments
- [x] Generate focused review packet for the current 22-event clean-cycle candidate
- [x] Settle and document the truth rule before final proof: clean-cycle `22` excluding the in-progress-at-start placement, or operational `23` including it if completion is visible after frame `0`
- [x] Build reviewed timestamp truth CSV and ledger for the settled truth total
- [x] Run the visible real dashboard path at `1.0x` with `FC_DEMO_COUNT_MODE=live_reader_snapshot`, `FC_COUNTING_MODE=event_based`, and `FC_DEMO_PLAYBACK_SPEED=1.0`
- [x] Confirm dashboard starts at Runtime Total `0`, shows `IMG_3254.MOV`, and increments on completed-placement moments
- [x] Capture observed app events from the live backend path
- [x] Compare app events to human truth with `matched_count` equal to the settled total, `missing_truth_count=0`, `unexpected_observed_count=0`, and `first_divergence=null`
- [x] Measure wall/source pacing near `1.0`
- [x] Run relevant pytest and frontend checks only if touched code requires them
- [x] Recheck Test Case 1 if any shared runtime/demo code changes
- [x] Update `.hermes/HANDOFF.md`, docs workflow/runbook notes, and lessons if the run creates reusable findings
- [x] Do not promote to a numbered test case unless the final evidence is clean

## Review

- Started 2026-05-01. Goal mode is active for this thread.
- Initial stale candidate stack on `8092`/`5174` is the completed IMG_3262 run; Test Case 1 remains on `8091`/`5173` and reports `DEMO_COMPLETE`, `factory2.MOV`, `live_reader_snapshot`, `event_based`, `23` events.
- Copied source video from `~/Downloads/IMG_3254.MOV` to `demo/IMG_3254.MOV`; SHA-256 `f9b72e2a48e96f1f008a0b750504fde13c8ea43ab62f562bacd715c5b19b19cd`; duration `1280.516667s`; video stream `1920x1080` HEVC Main 10.
- Preview sheet: `data/videos/preview_sheets/img3254/IMG_3254.jpg`; start-review sheet: `data/videos/review_frames/img3254_start_contact.jpg`.
- Baseline detector transfer failed cleanly: `models/img3262_active_panel_v2.pt` produced `0` detections on the first 45 one-second start frames and `0` detections on 120 selected frames spanning the full video. A short live diagnostic with that model reached `0` events by about `237s` source time before being stopped.
- `models/wire_mesh_panel.pt` detects panels in IMG_3254 but repeats the known static-stack failure mode: short live diagnostic artifact `data/reports/img3254_app_observed_events.run8092.wire_mesh_conf025_cluster90_age10_speed8_short_diag_v1.json` reached `8` events while still `RUNNING_GREEN`, with early repeated counts around the same static centroid near `event_ts` `26.402s` and `33.802s`.
- First IMG_3254 adaptation `models/img3254_active_panel_v1.pt` was rejected as an app-counting candidate: it reached `23` runtime events by about `565s` source time with more than half the video remaining, so it failed timing even before final proof. The failure mode was broad output-pallet/static-stack detection rather than completed-placement timing.
- Detector refinement findings:
  - `models/img3254_active_panel_v4_yolov8n.pt` is the current best detector.
  - v4 at `conf=0.25`, `cluster=250`, `max_age=40`, `min_frames=12`, `playback=8` completed with `24` events in `data/reports/img3254_app_observed_events.run8092.active_panel_v4_yolov8n_conf025_cluster250_age40_min12_speed8_diag_v1.json`; visual/track review showed duplicate splits around `470/487s` and `614/629s`.
  - v4 at `max_age=180` completed with `22` events but was rejected as a final-proof setting because it hides the split problem by carrying tracks for about `18s`, delaying count moments.
  - v5 broadened detections and overcounted; v6 suppressed some duplicate-window detections but overfragmented; v7 undercounted with only `14` events by `DEMO_COMPLETE`.
  - Raising confidence is not a credible fix: v4 false/split approach detections around `464.19s` were high-confidence while some likely true late placements were lower-confidence.
- Track-window review showed the duplicate gaps are narrow:
  - First duplicate: early fragment last seen `466.797s`, successor starts `472.097s`.
  - Second duplicate: early fragment last seen `610.206s`, successor starts `614.707s`.
  - This supports a small general tracker-lifetime increase rather than the rejected `max_age=180`.
- Start-of-video truth decision evidence:
  - Timestamped opener sheet: `data/videos/review_frames/img3254_start_truth_decision_sheet.jpg`.
  - Decision packet: `data/reports/img3254_truth_rule_decision_packet.v1.json`.
  - Blocked completion audit: `data/reports/img3254_completion_audit.blocked_v1.json`.
  - At `0.0s`, the worker is already bent over the output pallet with a placement in progress.
  - By about `8-12s`, the worker has moved away, so the opener can be counted only under the operational `23` rule.
  - Under the clean-cycle `22` rule, this opener is excluded because it began before frame `0`.
- Current clean-cycle candidate:
  - Launch settings: `models/img3254_active_panel_v4_yolov8n.pt`, no runtime calibration, YOLO confidence `0.25`, processing/reader FPS `10`, playback `8`, event cluster distance `250`, event track min frames `12`, event track max age `52`.
  - Artifact: `data/reports/img3254_app_observed_events.run8092.active_panel_v4_yolov8n_conf025_cluster250_age52_min12_speed8_diag_v1.json`.
  - Result: `observed_event_count=22`, `state=DEMO_COMPLETE`, `observed_coverage_end_sec=1280.417`.
  - Candidate event timestamps: `87.106`, `139.109`, `190.112`, `245.116`, `288.985`, `332.788`, `387.392`, `488.398`, `569.604`, `630.308`, `686.011`, `739.215`, `787.785`, `831.187`, `880.791`, `918.693`, `1020.500`, `1080.904`, `1118.906`, `1165.409`, `1217.713`, `1261.815`.
  - Focused review packet: `data/videos/review_frames/img3254_candidate_events_v1/manifest.json` with `22` per-event sheets under `data/videos/review_frames/img3254_candidate_events_v1/`. This packet is review evidence only, not a truth ledger or proof artifact.
- Oracle browser escalation was attempted under slug `img3254-next-move` after local diagnostics stalled, but the local ChatGPT browser session was not logged in (`Unable to locate the ChatGPT model selector button`). No API-backed Oracle run was started.
- Thomas locked clean-cycle truth `22` on 2026-05-01: exclude the placement already in progress at frame `0`; operational total would be `23` if that opener were included.
- Clean-cycle truth artifacts:
  - `data/reports/img3254_human_truth_event_times.clean_cycle_v1.csv`
  - `data/reports/img3254_human_truth_total.clean_cycle_v1.json`
  - `data/reports/img3254_human_truth_ledger.clean_cycle_v1.json`
- Verified visible `1.0x` dashboard run:
  - Launch settings: `models/img3254_active_panel_v4_yolov8n.pt`, no runtime calibration, YOLO confidence `0.25`, processing/reader FPS `10`, playback `1`, event cluster distance `250`, event track min frames `12`, event track max age `52`.
  - Observed events: `data/reports/img3254_app_observed_events.run8092.active_panel_v4_yolov8n_conf025_cluster250_age52_min12.visible_dashboard_1x_clean22_v1.json`.
  - Dashboard screenshots: `data/reports/screenshots/img3254_dashboard_visible_start_clean22_1x_v1.png`, `data/reports/screenshots/img3254_dashboard_visible_after_click_clean22_1x_v1.png`, `data/reports/screenshots/img3254_dashboard_visible_mid_clean22_1x_v1.png`, `data/reports/screenshots/img3254_dashboard_visible_end_clean22_1x_v1.png`.
  - Final dashboard text shows `Demo complete`, `Source: Demo Video: IMG_3254.MOV`, and `RUNTIME TOTAL 22`.
- Clean comparison artifacts:
  - Human-total comparison: `data/reports/img3254_app_vs_human_total.run8092.active_panel_v4_yolov8n_conf025_cluster250_age52_min12.visible_dashboard_1x_clean22_v1.json` with `expected_human_total=22`, `observed_event_count=22`, `total_matches=true`.
  - Timestamp truth comparison: `data/reports/img3254_app_vs_truth.run8092.active_panel_v4_yolov8n_conf025_cluster250_age52_min12.visible_dashboard_1x_clean22_v1.json` with `matched_count=22`, `missing_truth_count=0`, `unexpected_observed_count=0`, `first_divergence=null`.
  - Pacing: `data/reports/img3254_wall_source_pacing.run8092.active_panel_v4_yolov8n_conf025_cluster250_age52_min12.visible_dashboard_1x_clean22_v1.json` with `wall_per_source=1.000000154`.
  - Completion audit: `data/reports/img3254_completion_audit.verified_clean22_v1.json`.
- Relevant checks passed: `.venv/bin/python -m pytest tests/test_frame_reader.py tests/test_vision_worker_states.py tests/test_start_factory2_demo_app.py tests/test_build_human_truth_ledger_from_csv.py tests/test_compare_app_run_to_human_total.py -q` (`47 passed`, warnings only).
- Test Case 1 was rechecked after the IMG_3254 diagnostics and again before final proof: `8091` reports `DEMO_COMPLETE`, `factory2.MOV`, `live_reader_snapshot`, `event_based`, `23` events.
- IMG_3254 is now a verified real-app candidate under clean-cycle truth `22`; it has not been promoted to a numbered test case.

# Repo Cleanup And Validation Productization

## Goal

Turn Oracle's repo cleanup review into a concrete productized validation spine: current docs, manifests, registry, schemas, orchestration scripts, developer commands, and tests.

## Checklist

- [x] Use `task-kickoff` and keep the work tied to goal-mode follow-up context
- [x] Preserve the existing dirty worktree and avoid reverting user/project changes
- [x] Add a concise current documentation spine under `docs/00` through `docs/06`
- [x] Add `docs/KNOWN_LIMITATIONS.md` so product limits are explicit
- [x] Add archive directory readmes that mark old material as historical evidence, not current doctrine
- [x] Add `validation/registry.json`
- [x] Add manifests for Factory2/Test Case 1, IMG_3262, and IMG_3254 clean-cycle 22
- [x] Add JSON Schema files for manifests, truth ledgers, app runs, comparisons, and validation reports
- [x] Add `scripts/validate_video.py` as the manifest-backed validation orchestrator
- [x] Add `scripts/register_test_case.py` for registry updates
- [x] Add `Makefile` and `CONTRIBUTING.md`
- [x] Add focused tests for the registry, manifests, registration script, and validation orchestrator
- [x] Run focused verification

## Review

- Oracle's review was saved at `data/reports/oracle_factory_vision_repo_productize.md`.
- Current doctrine now starts at `docs/00_CURRENT_STATE.md` and points to the registry-backed validation path instead of relying on task logs or handoff memory.
- New registry/manifests live under `validation/` and encode the three current verified app records:
  - `factory2_test_case_1`: promoted Test Case 1, truth `23`
  - `img3262_candidate`: verified candidate, truth `21`
  - `img3254_clean22_candidate`: verified candidate, clean-cycle truth `22`
- New scripts:
  - `scripts/validate_video.py`
  - `scripts/register_test_case.py`
- New checks passed: `.venv/bin/python -m pytest tests/test_validation_registry_schema.py tests/test_register_test_case.py tests/test_validate_video.py -q` (`13 passed` after adding existing-artifact report mode).
- Full backend check passed: `make test-backend` (`350 passed`, warnings only).
- `make validate-video` dry-run works and prints the IMG_3254 manifest-backed preview/launch/capture/compare plan.
- Registry-backed validation reports were generated:
  - `data/reports/factory2_validation_report.registry_v1.json`
  - `data/reports/img3262_validation_report.registry_v1.json`
  - `data/reports/img3254_clean22_validation_report.registry_v1.json`
- I did not physically move the historical Factory2 research scripts yet because the current tests import those top-level paths. The product path is now documented and tested; a later mechanical move can add compatibility shims or update imports in one focused change.
