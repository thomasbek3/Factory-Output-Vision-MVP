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

- Backend: `655 passed`, 16 dependency warnings.
- Focused firewall/training/copy suite: `39 passed`.
- Console unit: `44 passed`.
- Console lint: zero errors, 12 pre-existing warnings under `e2e-audit`.
- Next production build: passed; the removed export route is absent.
- Full browser suite: `63 passed`.
- Browser: desktop and 390x844 `/review` render real factory footage, canonical
  Spanish copy, `+1 PIEZA`, and no worker answer/throughput data.
- Browser: mobile document width equals viewport width and browser console is
  empty. Desktop review-table overflow is also absent.

## Re-Review Gate

Checkpoint zero remains **REVISE** until a fresh Opus 5 high-effort pass finds no
open P0. This receipt will record that independent closure result rather than
self-certifying the remediation.
