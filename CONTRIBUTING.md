# Contributing

Factory Vision is a factory-appliance codebase, not a generic computer-vision sandbox. Changes must preserve offline operation, count-authority boundaries, and validation evidence.

## Read First

Start with:

- `README.md`
- `docs/README.md`
- `docs/00_CURRENT_STATE.md`
- `docs/01_PRODUCT_SPEC.md`
- `docs/02_ARCHITECTURE.md`
- `docs/03_VALIDATION_PIPELINE.md`
- `docs/06_DEVELOPER_RUNBOOK.md`
- `docs/10_REPO_GOVERNANCE_AND_CLEANUP_PLAN.md`
- `docs/11_RELEASE_AND_VALIDATION_CHECKLIST.md`
- `docs/decisions/`

Use archived docs only as historical evidence.

## Change Classes

Classify every meaningful change before editing:

| Class | Examples | Required gate |
| --- | --- | --- |
| Runtime count | `VisionWorker`, counters, detector behavior | focused tests + registry regressions |
| Track B action recognition | tripwire, clip dataset, clip student, placement counter, exam scorer | focused tests + blind exam gate before promotion |
| Validation | manifests, registry, truth comparison scripts | schema tests + dry-run validation |
| Frontend | dashboard, wizard, troubleshooting | lint + build + relevant e2e/manual check |
| Artifacts | `data/`, `models/`, training outputs | artifact policy review |
| Docs/process | README, ADRs, runbooks | `make docs-check` |
| Vendor/model stack | RF-DETR, YOLO26, Roboflow, Hailo, Jetson | evaluation lane + ADR before promotion |

## Local Checks

Docs/process only:

```bash
make docs-check
```

Backend/runtime/scripts:

```bash
make test-backend
```

Frontend:

```bash
make test-frontend
```

Full local confidence pass:

```bash
make hygiene
```

## Validation Rules

Do not claim validation proof unless the real app path produced:

- reviewed truth
- observed app events
- app-vs-truth comparison
- pacing evidence
- manifest and registry updates when applicable

Clean target:

```text
matched_count == expected_total
missing_truth_count == 0
unexpected_observed_count == 0
first_divergence == null
wall/source pacing near 1.0
```

File-backed app proof is not live RTSP field proof.

Track B action-recognition promotion additionally requires the blind exam gate:
all seven held-out placements matched, zero false counts, and no training on
`validation/exam/`. That exam is the sealed answer key, not training material.

## Runtime Authority

Allowed count authority:

- current app runtime path: Track A YOLO/event counting for boxable products
- promoted Track B clip-student counting after the blind exam gate
- promoted future fusion policy after validation

Not allowed:

- VLMs incrementing Runtime Total
- timestamp reveal
- deterministic replay as product proof
- offline retrospective count as live proof
- fake UI count updates

## Data And Artifacts

- Do not commit secrets.
- Do not upload footage without explicit permission.
- Do not delete artifacts during unrelated cleanup.
- Do not move heavy artifacts without updating manifests/tests.
- Use `/Users/thomas/FactoryVisionArtifacts` for durable local raw artifacts.

## Pull Requests

Use `.github/pull_request_template.md`.

Every PR should state:

- proof boundary affected
- commands run
- artifacts changed
- offline/cloud impact
- licensing impact when relevant
- rollback path
