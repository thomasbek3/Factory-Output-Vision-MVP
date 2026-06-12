# Pennies & Inches Stack Comparison And Architecture Recommendation

Reviewed: 2026-06-04

Source note: this compares the attached `Pennies-and-Inches-Vision-Stack.md` against this repository's current implementation and current public vendor/research docs available on 2026-06-04. Treat this as an architecture decision memo, not an implementation ticket.

## Decision

Do not rewrite the current app around the markdown stack.

The best architecture for this project is the current Factory Vision app plus a new optional signal-fusion layer:

```text
Camera or file source
  -> FrameReader
  -> VisionWorker
  -> detector adapter
  -> object tracking
  -> output placement signal
  -> optional machine-cycle signal
  -> FusionCoordinator
  -> CountStateMachine + FlaggedCycleStore
  -> runtime count, flagged cycles, support artifacts
  -> FastAPI REST/WebSocket/MJPEG
  -> React dashboard
```

The current app remains the system of record. New detector families, Roboflow, Cosmos, Hailo, and Jetson are evaluation lanes until they beat the current stack on this repo's validation registry and live-camera acceptance path.

## What We Actually Use Today

| Layer | Current repo implementation | Keep/change |
| --- | --- | --- |
| Product shell | Offline LAN appliance, FastAPI backend, React/Vite frontend | Keep |
| Backend | Python FastAPI in `app/`, SQLite persistence, REST/WebSocket/MJPEG | Keep |
| Frontend | React 19, TypeScript, Vite, dashboard/wizard/troubleshooting | Keep |
| Source input | Demo file or camera/RTSP through `FrameReader` and `VideoRuntime` | Keep, validate live RTSP next |
| Detector | Ultralytics-compatible YOLO `.pt` loaded from `FC_YOLO_MODEL_PATH` | Keep as current baseline |
| Current count modes | `track_based`, `event_based`, explicit `placed_and_stayed`, explicit `dead_track` | Keep |
| Current validated proof | File-backed live app proof: Factory2 23/23, IMG_3262 21/21, IMG_3254 22/22, IMG_2628 25/25 | Keep as benchmark gate |
| Runtime count authority | YOLO/event app path only | Keep |
| VLM/teacher role | Offline audit, review queue, labeling help, learning library | Keep |
| Validation | `validation/registry.json`, manifests, truth ledgers, app-vs-truth comparisons, pacing evidence | Keep |
| Hardware target | Mac mini now for dev/demo/live-camera shakeout; Ubuntu LTS edge PC for appliance | Keep |

## What The Markdown Proposes

| Markdown proposal | Fit with current repo | Recommendation |
| --- | --- | --- |
| Count output event, not human reps | Strong fit | Adopt as doctrine; already mostly implemented |
| Fuse output-zone arrival + machine cycle + optional place-right gesture | Partial fit | Add machine-cycle corroboration as the next architecture change |
| VLM as auditor, not counter | Strong fit | Keep; map Cosmos/Moondream to offline audit only |
| Roboflow as runtime spine | Not current | Evaluate in lab; do not replace app runtime yet |
| RF-DETR as likely primary detector | Not current | Benchmark against registry before adopting |
| YOLO26 / YOLOE-26 for fast/open-vocabulary onboarding | Not current | Evaluate as detector candidates, not runtime doctrine |
| ByteTrack / BoT-SORT | Similar concept, not current dependency | Evaluate if detector adapter work shows tracking fragmentation |
| Pi 5 + Hailo-8 or Jetson Orin | Not current deployment target | Hardware benchmark later; do not block MVP |
| Cosmos Reason2 auditor | Similar role to current VLM audit lane | Add to active-learning roadmap only |
| Physical AI Data Factory synthetic data | Not current | Later training-data scale option, not MVP |
| Patent/moat framing | Product/legal, not implementation | Keep separate from engineering docs |

## What Needs To Change

### 0. Promote live RTSP acceptance proof

Before model swaps, hardware swaps, or Roboflow runtime experiments, prove the existing app path against a real Reolink/RTSP stream.

The acceptance report should capture:

- camera model and stream URL pattern, with secrets redacted
- source timestamps and wall-clock timestamps
- dropped-frame, reconnect, and frame-stall stats
- runtime settings and model/calibration hashes
- observed count events and dashboard Runtime Total behavior
- reviewed truth comparison
- hard status: `field_proof=true|false`

This should become its own validation lane because the current claim boundary is clear: file-backed app proof exists; live field-stream proof does not.

### 1. Add machine-cycle corroboration in shadow mode

This is the most important useful idea in the markdown that the current repo does not yet implement.

Add an optional machine-cycle signal that can observe a per-unit machine state change:

- indicator light on/off
- ram or press movement
- door open/close
- repeated motion flash
- future discrete input or webhook

The first implementation should be visual-only and local:

```text
MachineCycleDetector
  input: frame, calibrated machine_cycle_roi, detector type, thresholds
  output: MachineCycleSignal(timestamp, frame_index, confidence, signal_type, roi_id)
```

Then wire it into the existing event state machine as corroborating evidence. It should not replace output-zone placement.

Preferred implementation shape: wrap the current `RuntimeEventCounter` / `CountStateMachine` path with a `FusionCoordinator` first. Do not shove all machine-cycle logic into the existing state machine on day one; that would make current count regressions harder to reason about.

### 2. Extend the fusion rule, not the detector

Current placed-and-stayed counting should remain the base. Machine-cycle behavior should be policy-driven:

| Policy | Behavior |
| --- | --- |
| `shadow` | Current output-placement counts remain Runtime Total; cycle signal is logged beside events |
| `corroborate` | Output-placement events count, but uncorroborated events are marked and surfaced |
| `hard_gate` | Count only when output placement and machine cycle agree |

Start in `shadow`, promote per station only after reviewed proof. A flaky cycle detector must not create false undercounts.

The fusion decision should produce:

| Situation | Runtime behavior |
| --- | --- |
| output settled + matching machine cycle | count |
| output settled, no machine cycle | shadow/corroborate/hard_gate behavior based on station policy |
| machine cycle, no output settled | flag possible missed output |
| conflicting timing | flag for review |
| output settled and machine cycle disabled/unavailable | count through existing placed-and-stayed path |

The product benefit is not just accuracy; it gives the dashboard honest uncertainty instead of forcing a false number.

### 3. Add calibration support for machine cycle

Extend runtime calibration with optional machine-cycle config:

```json
{
  "machine_cycle": {
    "enabled": true,
    "policy": "shadow|corroborate|hard_gate",
    "roi": [x, y, width, height],
    "signal_type": "indicator_light|ram_motion|door_motion|visual_change",
    "min_confidence": 0.7,
    "debounce_frames": 8,
    "match_window_ms": 2000
  }
}
```

Wizard/troubleshooting should support drawing or editing this ROI only when the station has a visible cycle. It must be optional because the markdown's open question is real: some stations may not expose a clean cycle.

Use both frame indexes and timestamps. Frame windows are fine for stable file playback, but live RTSP can have jitter, drops, and reconnects. Fusion should match in milliseconds and store source timestamp, wall timestamp, and frame index.

### 4. Persist flagged cycles as first-class artifacts

The existing app has event history and proof-backed/runtime-inferred totals. Add a parallel concept for flagged cycles:

- `cycle_without_output`
- `output_without_cycle`
- `ambiguous_cycle_window`
- `possible_reject_or_rework`
- `machine_cycle_detector_unavailable`

These should flow to SQLite, support bundles, active-learning evidence packets, and validation reports.

### 5. Add a detector adapter benchmark lane

Do not change the live detector yet. Add a narrow adapter/evaluation lane so candidates can be tested without rewriting the app:

```text
DetectorAdapter
  -> YoloUltralyticsAdapter (current baseline)
  -> RfDetrAdapter (candidate)
  -> Yolo26Adapter (candidate)
  -> Yoloe26Adapter (onboarding candidate)
```

The adapter output contract should be strict:

- normalized `xywh` boxes
- confidence
- class id and class name
- model id and model hash
- source frame index
- source timestamp and wall timestamp
- preprocessing dimensions
- excluded classes
- deterministic fixture outputs for tests

Promotion rule: no detector becomes default until it beats the current model on:

- `factory2_test_case_1`
- `img3262_candidate`
- `img3254_clean22_candidate`
- `img2628_candidate`
- any reviewed customer-specific case
- real app path at `1.0x`
- no new validation truth leakage

### 6. Add appliance packaging gates for every new stack lane

For Roboflow, Cosmos, Hailo, Jetson, or any new detector runtime, require a cold-start appliance check before production adoption:

- no internet
- LAN only
- camera connected
- model loads from local disk
- dashboard starts cleanly
- support bundle exports
- manifest records model/runtime/calibration versions and checksums

Running on a device is not the same as being a deployable factory appliance.

### 7. Track licensing as architecture risk

Commercial licensing must be explicit before production deployment:

- Current Ultralytics-compatible YOLO usage may require commercial/enterprise licensing for a proprietary appliance depending on model/package use.
- RF-DETR core Nano through Large is documented as Apache 2.0; RF-DETR XL/2XL use different platform-license terms.
- Roboflow-hosted or API-key workflows may carry account, cloud, or enterprise terms.

Do not let a detector benchmark pass hide a licensing blocker.

## What Should Not Change

- Do not rewrite the app around Roboflow Workflows.
- Do not make VLMs live count authority.
- Do not count operator reps directly.
- Do not revive line-crossing, blob detection, or frame differencing as proof paths.
- Do not move the runtime to cloud dependencies.
- Do not pick Hailo, Jetson, RF-DETR, or YOLO26 by vendor benchmark alone.
- Do not claim live Reolink/RTSP field proof until the current app path is validated on a real live camera stream.

## New Tech From The Markdown

### Roboflow Inference / Workflows / Supervision

Current public docs say Roboflow Workflows can run on-prem through Roboflow Inference and process webcam, RTSP, and video files. Workflows also include zone/time-in-zone style blocks, and Supervision offers common detection/tracking/zone utilities.

Recommended use here:

- good for labeling, training, offline experiments, and benchmark labs
- possible future runtime component only if it preserves offline operation, supportability, and validation artifacts
- not a near-term replacement for the current FastAPI runtime

Key risks:

- the product spec says no Docker/cloud/internet dependency during operation
- workflow deploy examples can be API-key oriented
- Roboflow upload/active-learning helpers could silently create cloud-footage movement if not gated

A Roboflow path must prove offline appliance compatibility and explicit customer permission for any cloud labeling/upload path before it becomes production architecture.

References:

- https://docs.roboflow.com/workflows/deploy-a-workflow
- https://inference.roboflow.com/workflows/blocks/timein_zone/
- https://supervision.roboflow.com/

### RF-DETR

RF-DETR is a serious candidate detector family. Current docs list RF-DETR Nano through Large as Apache 2.0 core models, with XL/2XL under a different platform license. Roboflow positions it as strong for domain transfer and real-time detection.

Recommended use here:

- benchmark RF-DETR Nano/Small against current YOLO models on our videos
- especially test false positives on cluttered piles, occlusion, and worker-held parts
- do not promote until app-vs-truth timing and totals pass

References:

- https://inference-models.roboflow.com/models/rfdetr-object-detection/
- https://rfdetr.roboflow.com/latest/learn/run/detection/

### YOLO26 / YOLOE-26

YOLO26 is current Ultralytics real-time model family. YOLOE-26 adds open-vocabulary detection/segmentation through text or visual prompts.

Recommended use here:

- YOLO26: candidate replacement for current YOLO baseline if faster/cleaner on edge hardware
- YOLOE-26: onboarding helper for new part discovery and weak initial labeling
- neither should be trusted as production count authority without fine-tuning and registry proof

Reference:

- https://docs.ultralytics.com/models/yolo26

### ByteTrack / BoT-SORT

The current repo already does object association/tracking internally. ByteTrack is worth testing if current tracker fragmentation causes split tracks or duplicate events. BoT-SORT is only worth testing if re-identification becomes important.

Recommendation: treat these as tracking candidates inside the detector adapter benchmark lane, not product decisions.

Reference:

- https://supervision.roboflow.com/develop/notebooks/object-tracking/

### Cosmos Reason2

Cosmos Reason2 is an open reasoning VLM for physical AI and robotics with spatial-temporal reasoning goals. It fits the markdown's auditor role, not the counter role.

Recommended use here:

- offline flagged-cycle explanation
- active-learning evidence labeling
- support-bundle narrative summaries
- never block live increments on Cosmos

Reference:

- https://docs.nvidia.com/cosmos/latest/reason2/index.html

### NVIDIA Physical AI Data Factory Blueprint

This is a future data-generation and curation architecture, not an MVP runtime dependency.

Recommended use here:

- later synthetic-data experiments for rare poses, lighting, occlusion, and part variants
- only after real footage and reviewed gold labels define what synthetic data should imitate

Reference:

- https://nvidianews.nvidia.com/news/nvidia-announces-open-physical-ai-data-factory-blueprint-to-accelerate-robotics-vision-ai-agents-and-autonomous-vehicle-development

### Hailo-8 / Jetson Orin / Jetson Thor / DGX Spark

Hailo-8 is attractive on paper for low-power edge inference. Jetson Orin is attractive where CUDA flexibility or local VLM/auditor work matters. Jetson Thor is overkill for a station counter. DGX Spark-style hardware is for lab/training/local-agent work, not factory-floor deployment.

Recommendation:

1. Mac mini: current dev/demo/live-camera shakeout.
2. Ubuntu LTS edge PC: first production appliance target.
3. Jetson Orin: evaluate if GPU acceleration or local auditor becomes necessary.
4. Pi + Hailo-8: evaluate only after model choice is stable and hardware integration time is justified.
5. Jetson Thor/DGX-class hardware: not floor runtime for this MVP.

Reference:

- https://hailo.ai/products/ai-accelerators/hailo-8-ai-accelerator/
- https://developer.nvidia.com/embedded/faq

## Best Architecture As Of 2026-06-04

The best architecture is a conservative hybrid:

```text
Current app runtime
  + explicit signal-fusion interfaces
  + optional machine-cycle detector
  + detector adapter benchmark lane
  + offline active-learning/auditor lane
  + validation registry as promotion gate
```

This gives the product the useful part of the markdown without losing the working app, validation discipline, offline appliance shape, or current proof base.

## Suggested Implementation Order

1. Create the live Reolink/RTSP acceptance lane and run the current app path.
2. Field discovery: answer whether the middle machine has a visible repeatable cycle.
3. Add machine-cycle calibration schema and visual debug view.
4. Implement `MachineCycleDetector` as an optional signal producer in `shadow` mode.
5. Wrap the current counter with `FusionCoordinator` that can log corroboration and flag disagreements.
6. Add tests for output-without-cycle, cycle-without-output, matched-cycle count, detector disabled, and policy modes.
7. Add validation artifact fields for cycle signals and flagged cycles.
8. Run Factory2/IMG registry regressions to prove no breakage.
9. Promote machine-cycle policy per station only after shadow/corroborate evidence.
10. Only then benchmark RF-DETR/YOLO26/YOLOE-26 against the registry.
11. Only after detector benchmarks, evaluate Hailo/Jetson hardware.

## Open Questions

- Does Caleb's machine have a visible cycle per completed unit?
- Is a missed cycle worse than a missed output placement for the customer's workflow?
- Should output-without-cycle default to `flag only` or `count but mark uncorroborated` in production?
- What is the acceptable operator-facing behavior for flagged cycles during a shift?
- Are customer videos allowed to touch Roboflow/cloud for labeling, or must all setup stay local?

## Oracle Review

Oracle reviewed this memo and the current source docs/code on 2026-06-04. Full captured output:

```text
data/reports/oracle_factory_vision_stack_review_2026_06_04.md
```

Oracle's conclusion matched the main decision: keep the current app as system of record, add optional signal fusion, and keep Roboflow/RF-DETR/YOLO26/YOLOE/Cosmos/Hailo/Jetson behind validation gates.

The useful corrections incorporated here:

- move live Reolink/RTSP proof to the top of the implementation order
- add machine-cycle `shadow|corroborate|hard_gate` policy modes
- prefer a `FusionCoordinator` wrapper before deep state-machine rewrites
- use millisecond timestamp matching, not only frame windows
- define a strict `DetectorAdapter` output contract
- add offline appliance packaging gates
- add commercial licensing risk for Ultralytics/RF-DETR/Roboflow paths
- surface flagged cycles in dashboard/support bundles, not just internal logs
- explicitly prevent Roboflow/cloud upload from sneaking into the default offline workflow
