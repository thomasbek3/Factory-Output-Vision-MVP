# Current State

Updated: 2026-05-01

This repo is the Factory Vision Output Counter MVP: an offline FastAPI + React/Vite factory appliance that counts finished output events from camera or file-backed live video using YOLO-based detection.

## Verified App Evidence

| Case | Status | Truth Total | Result | Primary Comparison |
| --- | --- | ---: | --- | --- |
| Test Case 1 / Factory2 | promoted test case | 23 | 23/23 clean visible app run | `data/reports/factory2_app_vs_truth.run8104.visible_dashboard_v1.json` |
| IMG_3262 | verified candidate | 21 | 21/21 clean visible app run | `data/reports/img3262_app_vs_truth.run8092.active_panel_v2_conf025_cluster90_age10.visible_dashboard_1x_paced_v3_ledger_v2.json` |
| IMG_3254 | verified candidate | 22 clean-cycle | 22/22 clean visible app run | `data/reports/img3254_app_vs_truth.run8092.active_panel_v4_yolov8n_conf025_cluster250_age52_min12.visible_dashboard_1x_clean22_v1.json` |

The current registry lives in `validation/registry.json`. Per-case manifests live in `validation/test_cases/`.

## Binding Validation Rules

- Real app proof uses `FC_DEMO_COUNT_MODE=live_reader_snapshot`.
- Carried/placed-piece proof uses `FC_COUNTING_MODE=event_based`.
- Promotion proof runs at `FC_DEMO_PLAYBACK_SPEED=1.0`.
- The dashboard Runtime Total must start at `0` and increment from real ordered processed frames.
- Captured app events must compare cleanly to reviewed human truth:
  - `matched_count == chosen truth total`
  - `missing_truth_count == 0`
  - `unexpected_observed_count == 0`
  - `first_divergence == null`
- Wall/source pacing must be measured and near `1.0`.

## Non-Negotiables

- No deterministic replay as validation proof.
- No timestamp reveal.
- No fake UI updates.
- No offline retrospective count presented as app proof.
- No hardcoded video-specific hacks.
- No threshold loosening solely to force a final total.
- No Reolink/RTSP field claim until the same runtime path is validated on a real live camera stream.

## Current Product Boundary

The app has proven file-backed live counting at real-time speed for the cases above. That is legitimate investor-demo evidence for the app path. It is not yet a live Reolink field validation.
