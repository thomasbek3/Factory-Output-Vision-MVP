# Release And Validation Checklist

Updated: 2026-06-04

Use this before claiming a demo, release, validation proof, or production readiness.

## Claim Boundary

Choose exactly one:

- `local_dev_only`
- `file_backed_app_proof`
- `live_rtsp_field_proof`
- `diagnostic_only`
- `learning_library_only`
- `production_release_candidate`

Do not describe one boundary as another.

## Required Checks

Backend:

```bash
make test-backend
```

Frontend when UI/contracts changed:

```bash
make test-frontend
```

Repository hygiene:

```bash
make docs-check
```

Full local pass when preparing a PR or release:

```bash
make hygiene
```

## Validation Proof Requirements

A validation proof requires:

- reviewed truth rule
- timestamped truth ledger
- observed app events
- app-vs-truth comparison
- pacing evidence
- manifest update
- registry update when promoted/verified
- no teacher/VLM labels as validation truth

Clean promotion target:

```text
matched_count == expected_total
missing_truth_count == 0
unexpected_observed_count == 0
first_divergence == null
wall/source pacing near 1.0
```

## Live RTSP Field Proof Requirements

Live field proof additionally requires:

- real Reolink/RTSP stream
- camera model and stream configuration recorded with secrets redacted
- runtime path matches production path
- reconnect/drop-frame/stall stats captured
- source and wall-clock timing captured
- dashboard starts at Runtime Total `0`
- support bundle captured
- field proof status written explicitly

File-backed proof is not live RTSP proof.

## Runtime Count Authority

Allowed:

- configured app counting path
- YOLO/event-based runtime
- future promoted fusion policy

Not allowed:

- VLM incrementing Runtime Total
- timestamp reveal
- deterministic replay as product proof
- offline retrospective count as live proof
- fake UI count updates

## Model Or Detector Promotion

Before promoting any model or detector:

- record model file path and hash
- record training/eval data lineage
- run registry cases
- compare timing and event alignment
- check offline appliance compatibility
- check commercial licensing
- update ADR or stack recommendation if default changes

## Artifact Handling

- Do not commit secrets.
- Do not upload footage without explicit permission.
- Do not delete historical artifacts during release work.
- Put heavy raw artifacts in `/Users/thomas/FactoryVisionArtifacts`.
- Keep manifests and small proof summaries in Git when they support current claims.

## Final Review Questions

- What can we honestly claim after this change?
- What can we not claim yet?
- Which command proves the claim?
- Which artifact records the proof?
- What breaks if a factory camera drops mid-run?
- Can a new engineer find the source of truth in under five minutes?
