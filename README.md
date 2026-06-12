# Factory Vision Output Counter

Offline factory output counting for manual workstations.

Factory Vision is a local appliance that counts completed output placements from a camera feed. It is designed for a shop-floor station where material starts on one side, an operator and machine do the work in the middle, and completed units are placed in an output area.

The product goal is practical: install on an edge machine, connect a camera, draw zones in a browser, and get an auditable runtime count without cloud services.

## Current Status

This repository contains a working MVP:

- Python FastAPI backend
- React/Vite/TypeScript frontend
- SQLite persistence
- OpenCV frame ingestion
- YOLO/event-based counting
- validation registry and app-vs-truth proof artifacts
- offline-first active-learning and review tooling

Current evidence proves file-backed live counting through the real app path for promoted/verified cases in `validation/registry.json`. It does not yet prove live Reolink/RTSP field operation. See `docs/00_CURRENT_STATE.md` before making product claims.

## Architecture

```text
Camera or demo video
  -> FrameReader / VideoRuntime
  -> VisionWorker
  -> YOLO detector
  -> counting mode
  -> runtime state and event history
  -> FastAPI REST/WebSocket/MJPEG
  -> React dashboard
```

Near-term architecture direction is to keep the current runtime as the system of record and add optional signal fusion, not rewrite around a new vendor stack. See `docs/09_PENNIES_AND_INCHES_STACK_RECOMMENDATION.md`.

## Quick Start

Use the existing virtual environment when present:

```bash
.venv/bin/pip install -r requirements.txt
cd frontend && npm install
```

Run backend tests:

```bash
make test-backend
```

Run frontend checks:

```bash
make lint
make build
```

Run the verified Factory2 demo stack:

```bash
make run-test-case-1
```

Open:

```text
http://127.0.0.1:5173/dashboard
```

Click `Start monitoring`. The verified Factory2 run should reach Runtime Total `23`.

## Common Commands

```bash
make install
make test-backend
make test-frontend
make validate-video CASE_ID=img3254_clean22_candidate
make benchmark-onboarding
make docs-check
make hygiene
```

`make hygiene` is the full local confidence pass for routine repository work. It is intentionally conservative and does not delete artifacts.

## Repository Map

```text
app/                  FastAPI backend, runtime workers, services, database repos
frontend/             React/Vite dashboard, wizard, troubleshooting UI
scripts/              validation, training, active-learning, artifact tooling
tests/                backend and script tests
validation/           validation registry, case manifests, JSON schemas
docs/                 product, architecture, validation, governance docs
docs/decisions/       architecture decision records
INSTALL/              installer and deployment notes
tasks/                working task logs and lessons
data/                 local working cache and reports; mostly not source of truth
models/               local model cache; promotion requires validation evidence
```

Heavy factory artifacts are local-first. Do not assume `data/` or `models/` is clean just because files are present. The durable artifact policy is in `docs/07_ARTIFACT_STORAGE.md`.

## Source Of Truth

Start here:

- `docs/README.md`
- `docs/00_CURRENT_STATE.md`
- `docs/01_PRODUCT_SPEC.md`
- `docs/02_ARCHITECTURE.md`
- `docs/03_VALIDATION_PIPELINE.md`
- `docs/04_TEST_CASE_REGISTRY.md`
- `docs/06_DEVELOPER_RUNBOOK.md`
- `docs/09_PENNIES_AND_INCHES_STACK_RECOMMENDATION.md`
- `docs/10_REPO_GOVERNANCE_AND_CLEANUP_PLAN.md`
- `docs/11_RELEASE_AND_VALIDATION_CHECKLIST.md`
- `docs/12_AI_ONBOARDING_BENCHMARK.md`
- `docs/decisions/`
- `validation/registry.json`
- `validation/learning_registry.json`

Historical docs remain for evidence, but current claims should route through the numbered current docs and decision records.

## Non-Negotiables

- No cloud dependency in the runtime path.
- No VLM or teacher model as live count authority.
- No blob detection, frame differencing, count-line, or generic motion-counting proof paths.
- No Reolink/RTSP field claim until validated on an actual live camera stream.
- No promotion without reviewed truth, app-vs-truth comparison, and registry evidence.
- No silent upload of factory footage or labels.

## Contributing

Read `CONTRIBUTING.md` before changing runtime, validation, models, artifacts, or product claims.

Every meaningful change should identify:

- proof boundary affected
- validation commands run
- artifact impact
- offline/runtime impact
- rollback path

## Security And Data

Factory footage, credentials, model weights, and customer artifacts are sensitive. Keep secrets out of Git, do not upload footage without explicit permission, and follow `SECURITY.md`.
