# Worker Ground-Truth Portal - Opus Checkpoint 0

Date: 2026-07-25
Checkpoint: specification and shipped-surface contract before Phase 1
Invocation: Claude Code `--model opus --effort high`, tool-less review
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

- Backend: `651 passed`, 16 dependency warnings.
- Console unit: `42 passed`.
- Console lint: zero errors, 12 pre-existing warnings under `e2e-audit`.
- Next production build: passed; the removed export route is absent.
- Full browser suite: `62 passed`.
- Browser: desktop and 390x844 `/review` render real factory footage, canonical
  Spanish copy, `+1 PIEZA`, and no worker answer/throughput data.
- Browser: mobile document width equals viewport width and browser console is
  empty.

## Re-Review Gate

Checkpoint zero remains **REVISE** until a fresh Opus 5 high-effort pass finds no
open P0. This receipt will record that independent closure result rather than
self-certifying the remediation.
