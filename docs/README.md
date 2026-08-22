# Documentation Index

This directory separates current product truth from historical research and task evidence.

When docs conflict, prefer this order:

1. Current numbered docs in this index
2. Architecture decision records in `docs/decisions/`
3. Validation registry and case manifests
4. Implementation code and tests
5. Older PRDs, roadmaps, and task logs
6. Archived docs

## Current Docs

| Doc | Purpose |
| --- | --- |
| `00_CURRENT_STATE.md` | Current validated cases, claim boundaries, and non-negotiables |
| `01_PRODUCT_SPEC.md` | Current MVP product definition |
| `02_ARCHITECTURE.md` | Short architecture map for the runtime path |
| `03_VALIDATION_PIPELINE.md` | Productized path for proving a video candidate |
| `04_TEST_CASE_REGISTRY.md` | Registry and manifest rules |
| `05_OPERATOR_RUNBOOK.md` | Operator workflow |
| `06_DEVELOPER_RUNBOOK.md` | Developer setup, commands, guardrails |
| `06_AI_ONLY_ACTIVE_LEARNING_PIPELINE.md` | VLM/teacher/review boundaries |
| `07_ARTIFACT_STORAGE.md` | Local-first artifact storage policy |
| `08_LEARNING_LIBRARY_ARCHITECTURE.md` | Failed-run and learning-library architecture |
| `09_PENNIES_AND_INCHES_STACK_RECOMMENDATION.md` | June 2026 architecture comparison and stack recommendation |
| `10_REPO_GOVERNANCE_AND_CLEANUP_PLAN.md` | Repository governance and cleanup plan |
| `11_RELEASE_AND_VALIDATION_CHECKLIST.md` | Release and validation checklist |
| `12_AI_ONBOARDING_BENCHMARK.md` | Blind AI-only onboarding benchmark contract and command |
| `13_FACTORY_ONBOARDING_AUTOPILOT_LOOP.md` | Recorder-first onboarding loop, milestones, and verifier gates |
| `14_TEACHER_VERIFICATION_EVENT_LOOP.md` | Teacher-assisted event verification loop and gated milestones |
| `15_AUTONOMOUS_ONBOARDING_REHEARSAL.md` | Real-teacher auto-box onboarding rehearsal with holdout gate |
| `16_LIVE_RECORDING_RUNBOOK.md` | Live recording and artifact capture runbook |
| `KNOWN_LIMITATIONS.md` | Honest current product limitations |

## Legacy Layer (superseded — read-only provenance)

The unnumbered top-level files below are the pre-July 2026 generation. They
differ from the archived twins in `ARCHIVED_DONOTREAD/` (two stale generations
were kept side by side); the newer of each pair is preserved in `archived/`,
and the originals stay here until the next docs sweep decides file-by-file.
Do not update them; the numbered docs above own their topics.

`API_SPEC`, `ARCHITECTURE`, `BUILD_PLAN`, `PROJECT_SPEC`, `TEST_PLAN`,
`UX_SPEC`, `COMPETITORS`, plus the older PRD/roadmap/market files.

## Specs

These specs document the Track B pivot work and approved implementation targets.
They are useful implementation references, but current claim boundaries still
come from `00_CURRENT_STATE.md` first.

| Spec | Purpose |
| --- | --- |
| `specs/day2_zone_miner_spec.md` | Day 2 zone-miner experiment |
| `specs/day3_wide_net_miner_spec.md` | Day 3 wide-net miner experiment |
| `specs/day4_action_recognition_spec.md` | Day 4 tripwire + clip action-recognition design |
| `specs/day5_human_trigger_spec.md` | Day 5 human-trigger workflow |
| `specs/worker_ground_truth_portal_v1.md` | Production three-reviewer ground-truth portal, consensus, and blind AI comparison |
| `specs/worker_ground_truth_portal_v1_fable_review.md` | Independent unknown-unknowns review and disposition for the worker portal spec |
| `specs/worker_ground_truth_portal_v1_fable_checkpoint_0.md` | Fable checkpoint-zero closure attempts, findings, and remediation status |
| `specs/worker_ground_truth_portal_v1_opus_checkpoint_0.md` | High-effort Opus adversary review and checkpoint-zero remediation receipt |

## Script Index

See `../scripts/CURRENT.md` for the current Track B script surface. Most other
scripts are older YOLO-era tooling kept for provenance or tests.

## Decision Records

Architecture decisions live in `docs/decisions/`.

Decision records are required when a change affects:

- count authority
- validation proof
- detector/model family
- runtime hardware target
- cloud/offline posture
- VLM/teacher model role
- artifact storage policy

## Validation Sources

| Path | Purpose |
| --- | --- |
| `validation/registry.json` | Verified/promoted case registry |
| `validation/test_cases/*.json` | Per-case manifests |
| `validation/learning_registry.json` | Failed/diagnostic learning cases |

## Archives

- `archived/` — merged archive: superseded doc generations, obsolete PRDs,
  historical handoffs, April factory2 research, and old plans
  (`superpowers/plans/` 2026-04 worklogs included).
- `ARCHIVED_DONOTREAD/` — frozen oldest generation; kept only so history is
  diffable. Nothing here is current; do not copy content out of it.
- `IMPLEMENTATION/2026-03-11/` — March implementation sprint logs.

Nothing under these three trees should be edited or referenced as current.
