# ADR 0001: Current Runtime Is The System Of Record

Status: Accepted

Date: 2026-06-04

## Context

The repository already contains a working Factory Vision app: FastAPI backend, React/Vite frontend, SQLite persistence, frame ingestion, YOLO/event-based counting, validation tooling, and file-backed app proof for multiple cases.

The Pennies & Inches architecture note introduced newer stack options such as Roboflow Inference, RF-DETR, YOLO26/YOLOE-26, Cosmos Reason2, Hailo, and Jetson. Those may be useful, but the project is not greenfield.

## Decision

The existing Factory Vision runtime remains the system of record.

ADR 0004 adds the scoped Track B path for the live overhead wire-frame station:
tripwire + clip action recognition plugs into the app/validation contracts
rather than replacing the product with a vendor workflow.

New architecture work should extend the current runtime through narrow interfaces such as:

- `MachineCycleDetector`
- `FusionCoordinator`
- `DetectorAdapter`
- flagged-cycle artifacts

Do not rewrite the app around a vendor workflow or new detector family unless a future ADR changes this decision after validation proof.

## Consequences

- Current validation evidence remains useful.
- New detector/runtime candidates must plug into existing validation contracts.
- Runtime changes must preserve dashboard, support-bundle, and registry behavior.
- Research and vendor experiments stay in evaluation lanes until promoted.

## Verification Gate

Any change to this decision requires:

- passing current registry cases
- real app path proof at `1.0x`
- explicit offline appliance acceptance
- updated architecture docs and ADR
