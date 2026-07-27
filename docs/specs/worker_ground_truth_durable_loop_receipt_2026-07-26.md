# Worker Ground-Truth Durable Loop Receipt

Date: 2026-07-26  
Checkpoint: authenticated durable reviewer loop  
Verdict: PASS for this checkpoint; not full worker-spec or production approval

## Implemented

- Supabase Auth identity is held in HttpOnly, same-site cookies.
- Worker RPCs derive reviewer identity from `auth.uid()` and never accept a
  browser-supplied reviewer ID.
- Three reviewers receive the same source chunk through three distinct blind
  assignments.
- Lease tokens are random, hash-only in Postgres, refreshed every 30 seconds,
  and recoverable for the named grace window.
- Tally and undo actions are append-only, client-ID idempotent, server-acknowledged,
  resumable after reload, and retried after connection recovery.
- Final submission returns the original result after a committed response is
  lost, without creating a duplicate submission.
- The reviewer rendition is a private Supabase Storage object. Only a reviewer
  with a current assignment may mint a 15-minute signed URL.
- An idle no-work screen polls every 5 seconds without refresh.

## Footage

- Source: 15 ordered MKV segments under
  `/Users/thomas/FactoryVisionArtifacts/worker_days/20260709/gate-line/segments`
- Source interval: 2026-07-09 12:08 through 12:23 factory-local time
- Source-manifest SHA-256:
  `4293ff1cc19b5cac01268bd099bb4638812182d3f7bfee314022262e916d7985`
- Browser rendition:
  `review-renditions/review/gate-line-20260709-1208-web.mp4`
- Rendition SHA-256:
  `8602f701f3ae025bb7f1fc2d68871a81f897b181b9b81f4f6fed0ce50e1eb4fb`
- Stored bytes: 6,894,523
- Truth tier: rehearsal footage only. The submitted E2E count is test data, not
  reviewed human truth and not an AI-accuracy claim.

## Verification

- `npm run lint` passed.
- `npm test -- --run` passed: 45 tests.
- `npm run build` passed.
- `python3 -m unittest tests/test_supabase_phase1_contract.py` passed: 23 tests.
- Canonical AI Mac `make test-backend` passed: 703 tests.
- Credentialed Playwright passed against the canonical AI Mac launchd service
  on port 3000: 1 test, not skipped.
- The browser proved three distinct assignments for one chunk, no session token
  in local storage, signed private-media delivery, active frame advancement,
  tally/undo persistence, reload resume, offline recovery, and lost-response
  idempotency.
- Desktop and 390x844 screenshots were visually inspected with no overlap.
- Direct Supabase receipt for final round 12: 3 assignments, 3 distinct reviewers,
  4 tally actions, 1 undo, 1 immutable submission, submitted total 3.
- The private rendition receipt reported 1 object and 6,894,523 stored bytes.
- After submission, that reviewer received no new signed media URL.
- Luna high-effort independent QA passed this narrow checkpoint.

## Explicitly Unproven

- Server-enforced 98 percent coverage and weak wall-clock floor.
- IndexedDB outbox, browser monotonic click time, and page-epoch telemetry.
- TOTP MFA enrollment and recovery.
- Three real human reviews, majority resolution, AI comparison, or owner
  publication.
- Real worker comprehension, handle time, payment, legal notice/consent, and
  production staffing.
