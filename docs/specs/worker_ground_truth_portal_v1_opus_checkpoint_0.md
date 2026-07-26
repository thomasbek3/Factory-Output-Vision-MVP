# Worker Ground-Truth Portal - Opus Checkpoint 0

Date: 2026-07-25
Checkpoint: specification and shipped-surface contract before Phase 1
Invocation: Claude Code `--model opus --effort high`
Canonical model reported by CLI: `claude-opus-5`
Completed review session: `5d0b5ca1-dbbb-45a5-8db9-ad02578a63a6`
Reported turns: 48
Initial verdict: **REVISE**

An earlier invocation, session
`416865a9-090c-4be6-aac1-79ec72bbd6e6`, exhausted its turn limit and produced
no verdict. It is not checkpoint evidence.

## P0 Finding

The amended capability contract said the owner/operator `/ops` surface contained
no AI evidence, reviewer performance, exam results, or label export. The shipped
surface still exposed model agreement, held-out exam score, reviewer accuracy
and throughput, plus an unauthenticated label-export route. Its E2E tests
required those forbidden controls, so this was implementation drift rather than
an ambiguous documentation statement.

## Additional Findings

The review also found fail-open lineage defaults, an exam registry with no
lineage field, incomplete holdout boundary protection, Spanish release-event
copy drift, a literal-only leakage scan, an onboarding budget that omitted
authenticator acquisition, speed-list inconsistency, a circular mapping budget,
worker queue-depth leakage, a synthetic verification trend, and a stale
single-decider review type in the app spec.

## Second High-Effort Review

Session: `13c8e1f6-4e68-4e2c-bb24-f6e8c1600242`

Canonical model: `claude-opus-5`

Reported turns: 42

Verdict: **REVISE**

The reviewer independently closed the original `/ops` P0 and found three new
P0s:

1. `/api/review/day-queue` still enumerated peer-held station/time rows and
   exposed `locked-by-other`.
2. Training extraction/labeling used filename and caller-flag heuristics instead
   of consuming the exam registry with hash/time lineage.
3. The copy-contract test still expected `SEEDED REVIEW` after the shipped
   surface changed to `HISTORICAL / REVIEW DATA`, so the backend receipts could
   not describe that exact tree.

It also identified a `16x` playback fallback, unversioned/internal Spanish copy,
an `/ops` export-authority contradiction, missing presented-interval and
transitive-lineage contracts, full-media prefetch before lease, and a narrow
owner-source scan.

Session `75a8bdf8-a136-4aab-b487-a44507630130` resolved to the same canonical
model but had no usable read tools and produced no verdict. It is not checkpoint
evidence.

## Third High-Effort Review

Session: `4c93b688-5f8c-401f-9d5c-5c5e5a903462`

Canonical model: `claude-opus-5`

Reported turns: 43

Verdict: **REVISE**

The reviewer verified that the three second-pass P0s were closed, then found one
remaining P0: the low-level trainer consumed the exam registry but did not
compose that check with the wider protected source-set registry. Holdout,
practice, qualification, calibration, or resolver-calibration footage could
therefore be declared training-eligible without appearing in the exam registry.

Adjacent findings covered global queue ordinals, a missing composed
exam/source-set guard band, advisory teacher outputs, rendition-source
provenance, a vacuous zero-row queue test, adjudicator-copy ambiguity, worker
lexicon drift, traversal-budget arithmetic, permissive missing
`training_eligible`, and an incorrect download icon on a read-only queue card.

## Third Remediation Applied

- Added one composed review-eligibility service that consumes both the exam
  firewall and protected source-set registry. The low-level trainer now uses
  that service, so no caller or filename can bypass either registry.
- Added negative tests for holdout, practice, qualification,
  resolver-calibration, and the 60-second guard band, plus a positive test for
  ordinary footage outside every protected set.
- Made `training_eligible: true` an explicit fail-closed lineage field for
  training manifests. Advisory teacher-label and evidence outputs cannot enter
  training, and behavioral tests prove they are rejected.
- Made queue ordinals caller-local and gap-free after peer rows are removed.
  API and unit tests now require at least one caller row, assert exact ordinal
  continuity, and prove the peer row is absent.
- Restored the exact canonical English and Spanish release-event instruction,
  replaced internal vocabulary, and expanded the worker problem menu to the six
  specified reasons.
- Clarified that no adjudicator-capable account or endpoint may receive model
  evidence, corrected the fastest-traversal floor to `2m55s`, and removed
  download semantics from the read-only operations queue.
- Renamed remaining seeded/demo-facing owner copy as historical review data.

## Fourth High-Effort Review

Session: `8462af5c-6fe8-4169-871e-3075c733bfc8`

Canonical model: `claude-opus-5`

Reported turns: 59

Verdict: **REVISE**

The reviewer verified every prior portal P0 closure, then found one repo-wide P0
outside the Track B portal lane. The older Track A YOLO pipeline emitted and
consumed `training_eligible=true`, trained weights, and split the
`factory-live-day1` source by filename order without consuming either protected
registry. The non-negotiable spec statement that every training path was
firewalled was therefore false, and the six-file static test could never
discover the older lane.

The same review found that non-holdout composed-eligibility coverage was
overstated, `CONTINUAR VIDEO` ambiguously meant both resume and return-to-edit,
legacy copy checks targeted a re-export file with no strings, playback clamping
could report a false success, the step-down target ignored the validated speed
ladder, source-set eligibility had an asymmetric hash API, and the empty-queue
API branch was not explicitly projected.

## Fourth Remediation Applied

- The Track A YOLO dataset builder now requires source path, exact SHA-256,
  complete transitive lineage, and UTC source interval for every positive and
  hard-negative sample. It validates every row against both registries before
  emitting `training_eligible=true`.
- The YOLO training runner revalidates the complete manifest before invoking the
  trainer. A protected exam-source test proves rejection occurs before the
  trainer callback can run.
- The runner rejects empty manifests and binds the guarded manifest to the exact
  requested `data.yaml`. Every training image and label must exist in the
  declared split, `items` must equal the validated `samples`, and the manifest
  must inventory every file YOLO can consume. Substituted YAML files, mismatched
  rows, missing assets, and unlisted dataset files fail before the trainer.
- Advisory teacher fusion, benchmark, deterministic AI review, and failed-run
  conversion outputs now emit `training_candidate=true` and
  `training_eligible=false`. Only guarded dataset builders can cross that
  boundary.
- The legacy trainer's unreviewed bypass was removed and it now requires a
  firewall-validated training manifest.
- The day-one pipeline no longer partitions by filenames or fractions. It uses
  exact source hashes and UTC intervals from the tracked exam and source-set
  registries, fails when no registered holdout exists, and carries verified
  provenance through proposals, evidence packets, boxes, and dataset assembly.
- An AST discovery test walks `app/` and `scripts/`, identifies literal training
  eligibility emitters and trainer entry points, and requires every discovered
  path to carry the composed guard. New paths fail until explicitly reviewed.
- Synthetic tests populate resolver-calibration, holdout, practice, and
  qualification sets, check the 60-second guard band, check an unrelated source,
  and prove the explicit source hash is considered even when lineage omits it.
- The summary action is now `VOLVER A EDITAR` / `BACK TO EDIT`; the problem
  option is `Vista bloqueada` / `View blocked`.
- Playback now reads back the browser's applied speed and walks down the
  validated `5x -> 2x -> 1x` ladder after throws or silent clamping.
- Both empty and populated next-chunk responses use explicit worker-safe
  projections.

## Second Remediation Applied

- Day-queue responses now contain only the caller's own leased or completed
  rows. Peer rows and `locked-by-other` no longer exist, and an API E2E test
  proves the peer's row is absent.
- The clip extractor, labeler, command-line trainer, and lowest-level model
  training service now require a source file whose SHA-256 matches the manifest,
  a UTC visible interval, and declared complete transitive lineage. All consume
  the tracked exam registry and fail closed. A neutral-path exam fixture proves
  filenames cannot bypass the guard.
- The stale copy assertion now matches the shipped tree, and every backend
  receipt was regenerated after the fix.
- Playback assignment is centralized in a tested helper; unsupported speeds
  step down to `1x` and report the reason.
- All worker-facing Spanish/English strings live in the versioned lexicon.
  Worker copy uses video/piece vocabulary rather than block/queue/placement
  internals, and the required context warnings are checked in.
- `/ops` is unambiguously read-only in v1; label export requires a later,
  separately named capability and contract amendment.
- Exam and source-set APIs require complete transitive lineage declarations;
  source-set checks evaluate the presented interval and have positive and
  negative guard-band tests.
- Full-media prefetch before lease was removed.
- Owner-source scans now include TypeScript and JSON under app/components/lib,
  and seeded reviewer names were removed from the in-memory store.

## Remediation Applied

- Removed AI/model/exam/reviewer-performance controls and the label-export route
  from `/ops`; its API now projects queue-health aggregates only.
- Removed hidden-golden, peer, queue-depth, internal lock-owner, and throughput
  fields from worker payloads.
- Added the versioned Spanish/English release-and-remains lexicon and made
  `+1 PIEZA` the canonical count control.
- Limited the worker surface to the Tier A playback speeds `1x`, `2x`, and `5x`.
- Required non-empty source lineage at assignment time and in the exam registry.
- Added lineage-aware overlap checks, a 60-second protected-source guard band,
  bidirectional exam/holdout containment rules, and negative boundary tests.
- Expanded leakage tests to inspect all affected sources, require files to
  exist, scan leakage classes, and reject the removed export route.
- Clarified that pilot devices are provisioned with an authenticator before the
  five-minute onboarding clock starts.
- Removed the synthetic verification status trend and retired the stale
  single-decider app-spec type.
- Made mobile grid children shrinkable and added responsive review-table tracks;
  the 390x844 proof now has zero horizontal overflow.
- Updated E2E tests so named reviewers cannot return to owner surfaces, active
  relay state is handled honestly, and live media does not make language checks
  wait forever.

## Verification Before Closure Review

- Backend: `676 passed`, 16 dependency warnings.
- Focused manifest/firewall suite: `34 passed`.
- Console unit: `45 passed`.
- Console lint: zero errors, 12 pre-existing warnings under `e2e-audit`.
- Next production build: passed; the removed export route is absent.
- Full browser suite: `63 passed`.
- Browser: desktop and 390x844 `/review` render real factory footage, canonical
  Spanish copy, `+1 PIEZA`, and no worker answer/throughput data.
- Browser: the Spanish summary shows `VOLVER A EDITAR`, contains no
  `CONTINUAR VIDEO`, and the browser log is empty.
- Browser: mobile document width equals viewport width and browser console is
  empty. Desktop review-table overflow is also absent.

## Re-Review Gate

Checkpoint zero remains **REVISE** after four completed high-effort reviews and
will not close until a fresh Opus 5 high-effort pass finds no open P0. This
receipt records the independent finding and remediation rather than
self-certifying closure.
