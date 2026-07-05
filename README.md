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

> **Two tracks (read `docs/00_CURRENT_STATE.md` first).** YOLO/event counting is
> proven for *boxable* products (the test cases above). The **live overhead
> wire-frame station** defeated YOLO (the product is unboxable from above), so it
> pivoted to **camera-only action recognition** — a zone tripwire feeds short
> clips to a small video model that judges "placement / not." That track is the
> current focus; its tripwire recall is proven (7/7 on a held-out exam) and the
> model is in a bake-off pending the exam gate. See ADR 0004 and
> `docs/specs/day4_action_recognition_spec.md`.

## Repository layout

```text
app/                  FastAPI backend, runtime workers, services, database repos
scripts/              Current CLIs; ops/, legacy/, and research/ hold operational or quarantined tools
tests/                Backend, script, validation, and CLI contract tests
docs/                 Current docs; decisions/ for ADRs and specs/ for implementation specs
validation/           Registry, manifests, schemas, and exam/ held-outs; never train on exam data
models/               Manifest/index only; large weights are artifact-managed outside Git
data/                 Gitignored working data, reports, caches, and local run output
demo/                 Small demo media and demo-mode fixtures
frontend/             React/Vite dashboard, wizard, and troubleshooting UI
INSTALL/              Installer and deployment notes
```

## Architecture

Track A — boxable products (proven runtime, system of record):

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

Track B — live overhead wire-frame station (action recognition; unboxable product):

```text
Fixed camera
  -> zone tripwire (cheap pixel change detector, high recall)
  -> per-candidate clip (before / during / after of the output zone)
  -> small video model: placement? yes / no
  -> debounced state-machine counter
```

Near-term direction is to keep the current runtime as the system of record and
extend it (optional signal fusion, the action-recognition lane for the live
station), not rewrite around a new vendor stack. See ADR 0001, ADR 0004, and
`docs/09_PENNIES_AND_INCHES_STACK_RECOMMENDATION.md`.

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
mkdir -p data/videos/from-pc && cp -n /Users/thomas/FactoryVisionArtifacts/videos/raw/factory2.MOV data/videos/from-pc/factory2.MOV
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
- No blob detection, frame differencing, count-line, or generic motion-counting proof paths as Track A proof paths; Track B's tripwire is a sanctioned candidate trigger under `docs/decisions/0004-pivot-from-yolo-to-clip-action-recognition.md`.
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
