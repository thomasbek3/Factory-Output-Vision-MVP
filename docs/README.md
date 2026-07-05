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

## Specs

These dated specs document the Track B pivot work by day. They are useful
implementation references, but current claim boundaries still come from
`00_CURRENT_STATE.md` first.

| Spec | Purpose |
| --- | --- |
| `specs/day2_zone_miner_spec.md` | Day 2 zone-miner experiment |
| `specs/day3_wide_net_miner_spec.md` | Day 3 wide-net miner experiment |
| `specs/day4_action_recognition_spec.md` | Day 4 tripwire + clip action-recognition design |
| `specs/day5_human_trigger_spec.md` | Day 5 human-trigger workflow |

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
| `validation/schemas/*.schema.json` | Artifact contracts |

## Historical References

Older product specs, roadmaps, PRDs, and archived docs remain useful as evidence, but they are not current source of truth unless a current doc explicitly points to them.

Historical areas:

- `docs/ARCHIVED_DONOTREAD/`
- `docs/archived/`
- older unnumbered docs in `docs/`
- `tasks/`
