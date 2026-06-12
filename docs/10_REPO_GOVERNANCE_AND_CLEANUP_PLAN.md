# Repository Governance And Cleanup Plan

Updated: 2026-06-04

## Goal

Make this repository easy for a serious engineering team or investor-side technical reviewer to understand without erasing the validation history that proves the product.

The cleanup rule is:

```text
Organize and route first. Delete or move only after proof that nothing depends on it.
```

## Repository Standard

The repo should have:

- clear README
- current docs index
- architecture decision records
- validation and release checklist
- contribution rules
- security/data handling policy
- non-destructive hygiene check
- explicit artifact storage policy

## Current Cleanup Boundary

This first pass is governance and presentation only.

Allowed:

- improve README and contribution docs
- add docs index and ADRs
- add release/checklist docs
- add non-destructive hygiene script
- route stale docs through indexes

Not allowed in this pass:

- deleting `data/`, `models/`, `training_runs/`, or `datasets/`
- moving validation artifacts without updating manifests/tests
- mass-formatting unrelated code
- changing runtime behavior
- changing validation truth
- uploading artifacts to cloud

## Artifact Policy

The repo contains a mix of source code, small proof summaries, local working cache files, and large historical artifacts. Cleanup must preserve evidence until each artifact is classified.

Artifact classes:

| Class | Examples | Policy |
| --- | --- | --- |
| Source | `app/`, `frontend/src/`, `scripts/`, `tests/` | Keep in Git |
| Contracts | `validation/`, schemas, manifests, current docs | Keep in Git |
| Small proof summaries | selected JSON reports referenced by manifests | Keep when referenced |
| Heavy raw artifacts | raw videos, frame dumps, training runs | Store under local artifact root, not normal Git |
| Working cache | local DBs, logs, temporary reports | Ignore unless explicitly promoted |

Current durable artifact root:

```text
/Users/thomas/FactoryVisionArtifacts
```

## Cleanup Workflow

1. Run hygiene checks.
2. Build an inventory before moving anything.
3. Classify each candidate file as source, contract, proof, heavy artifact, or cache.
4. Check whether validation manifests, registries, docs, scripts, or tests reference it.
5. Move/delete only in a dedicated cleanup PR.
6. Run relevant tests and registry checks.
7. Update docs and lessons if the cleanup changes future workflow.

## Hygiene Checks

Default:

```bash
make docs-check
```

Full local confidence pass:

```bash
make hygiene
```

`docs-check` is intentionally lightweight and non-destructive. It verifies required docs exist, required JSON files parse, and obviously unsafe tracked files are not present.

## Future Tooling Candidates

Add these only after the current docs/process cleanup is stable:

- Ruff for Python lint/format in check-only mode first.
- Knip for frontend unused files/exports/dependencies in report-only mode first.
- pre-commit hooks for fast local checks.

Do not introduce auto-fix or mass-format behavior until current test/validation gates are green.

## Pull Request Standard

Every meaningful PR should answer:

- What proof boundary does this affect?
- What validation commands ran?
- Did this touch live runtime count authority?
- Did this touch artifacts or model weights?
- Does this preserve offline operation?
- Is there a licensing or cloud-data implication?
- What is the rollback path?

Use `.github/pull_request_template.md`.

## Long-Term Cleanup Backlog

- Classify tracked `data/` and `models/` files into retained proof vs local artifact cache.
- Move heavyweight retained artifacts to the artifact root and keep small manifests in Git.
- Convert older unnumbered docs into current docs, ADRs, or archived references.
- Split research scripts from product scripts only when imports/tests are updated in the same PR.
- Add CI once the local `make hygiene` target is stable.
