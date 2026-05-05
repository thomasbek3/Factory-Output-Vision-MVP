# Contributing

## What To Read First

Start with:

- `docs/00_CURRENT_STATE.md`
- `docs/01_PRODUCT_SPEC.md`
- `docs/02_ARCHITECTURE.md`
- `docs/03_VALIDATION_PIPELINE.md`
- `docs/04_TEST_CASE_REGISTRY.md`
- `docs/06_DEVELOPER_RUNBOOK.md`
- `docs/KNOWN_LIMITATIONS.md`

Use `docs/ARCHIVED_DONOTREAD/` and `docs/archived/` only as historical evidence.

## Development Rules

- Keep the app offline/LAN-first.
- Do not add cloud, Docker, YAML-editing, or network dependencies to the MVP path without an explicit product decision.
- Preserve the real app validation doctrine: no timestamp replay, deterministic reveal, fake UI counts, or offline retrospective count as proof.
- Keep Test Case 1 intact when changing shared runtime code.
- Add focused tests for scripts, manifests, and runtime behavior touched by a change.

## Validation Artifacts

Every verified candidate should have:

- A manifest in `validation/test_cases/`.
- A registry entry in `validation/registry.json`.
- A reviewed truth ledger.
- Captured observed app events.
- An app-vs-truth comparison.
- Pacing evidence.

## Checks

```bash
make test-backend
make lint
make build
```

Run frontend checks only when frontend code or contracts are touched.
