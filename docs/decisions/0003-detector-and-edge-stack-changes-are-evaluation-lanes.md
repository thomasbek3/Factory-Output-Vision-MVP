# ADR 0003: Detector And Edge Stack Changes Are Evaluation Lanes

Status: Accepted

Date: 2026-06-04

## Context

June 2026 stack options include RF-DETR, YOLO26, YOLOE-26, Roboflow Inference/Workflows, Hailo-8, Jetson Orin, and Cosmos tooling. These may improve detection, onboarding, or deployment, but adopting them directly would add risk to a working app path.

## Decision

New detectors, trackers, vendor runtimes, and hardware platforms belong in evaluation lanes until promoted.

The Track A production baseline remains the current Ultralytics-compatible
YOLO/event path until a candidate beats it under the validation gate. Track B is
separately governed by ADR 0004 for the live overhead wire-frame station.

## Consequences

- RF-DETR, YOLO26, YOLOE-26, ByteTrack, BoT-SORT, Roboflow Workflows, Hailo, and Jetson can be tested without being product defaults.
- Candidate integrations must use a strict adapter output contract.
- Hardware changes wait until the runtime and model choice are stable.
- Commercial licensing and offline packaging must be evaluated before production use.

## Verification Gate

A candidate must pass:

- Factory2/Test Case 1
- verified IMG candidate cases
- any relevant customer-specific cases
- real app path at `1.0x`
- offline appliance acceptance
- licensing review
- support-bundle and manifest version capture
