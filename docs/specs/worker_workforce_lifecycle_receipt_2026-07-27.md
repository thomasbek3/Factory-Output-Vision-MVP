# FactoryVision Worker Workforce Lifecycle Receipt

Date: 2026-07-27

## GOAL

Give FactoryVision a fail-closed path from inviting a reviewer through secure
onboarding, qualification, three-person production review, support, work
evidence, suspension, and offboarding.

## NOW

- The canonical worker loop remains three blind human submissions with a
  two-of-three human majority. AI is not available to workers and cannot break
  a human tie.
- Supabase Auth, private Storage, RLS, TOTP MFA, lifecycle records, device
  registration, invitation receipts, coverage, support requests, work sessions,
  automatic scheduling, expiry replacement, and human finalization are
  implemented.
- Ready 15-minute production chunks are scheduled to exactly three qualified
  reviewers without an additional one-hour delay. Logged-in empty queues poll
  every five seconds.
- Factory-local source date and time are shown in the worker header.
- The worker can use English or Spanish, save event timestamps durably, recover
  from offline and dropped-response cases, and request help separately from a
  footage-quality report.
- Ops can inspect reviewers and support requests, acknowledge or close support,
  suspend or offboard reviewers, and preview the bilingual invitation email.
- Invitation sending fails closed until all server/email environment values are
  present. A created invitation is recorded before delivery, then marked sent
  or delivery_failed from the provider receipt.
- Production activation requires a server-recorded result against a private
  qualification reference. Ops cannot convert the conceptual quiz into a
  passing qualification.

## VERIFIED

- Live Supabase project: `jhoshtiffhwsgurntgxp`.
- Applied migrations: reviewer lifecycle, quality/scheduler, terminal round
  replacement, invitation delivery, work sessions, support inbox, stale-session
  cleanup, support rate limit, qualification gate, and immediate ready scheduler.
- Static gates: 29 Supabase contract tests, 47 Vitest tests, ESLint, and a clean
  Next.js production build.
- Live Playwright: three isolated QA reviewer accounts shared one real
  15-minute factory chunk through distinct assignments. The run covered private
  signed media, actual playback, desktop/mobile layouts, durable tally/undo,
  reload recovery, offline recovery, a dropped committed response, idempotent
  retry, support creation, active-device registration, and work-session
  submission evidence.
- Live Playwright: authenticated ops roster, stored support request,
  acknowledgement, invitation dialog, and rendered Spanish invitation email.
- Visual evidence:
  - `console/e2e-audit/shots/worker-review-desktop.png`
  - `console/e2e-audit/shots/worker-review-mobile.png`
  - `console/e2e-audit/shots/ops-worker-support.png`
  - `console/e2e-audit/shots/reviewer-invitation-email.png`

## NEXT 3

1. Curate and approve a disjoint 90-second qualification video with a private
   gold reference answer, then connect its assignment/scoring service to
   `service_record_reviewer_qualification`.
2. Configure the production host and email delivery values, send a real
   invitation to a controlled inbox, and prove its activate-account link.
3. Run one full first-worker rehearsal from received email through qualification
   and three-person production resolution, then approve launch.

## WAITING ON THOMAS

- Verified sending domain, sender name/address, Resend credential, Supabase
  server key, public review URL, and staffed support address.
- Final worker country/classification, pay basis and rate, time-rounding policy,
  privacy/data-handling terms, support SLA, and owner for payroll disputes.
- Approval of the gold qualification clip and pass thresholds.
- Hiring at least three qualified reviewers. The scheduler intentionally does
  not create partial production rounds with fewer than three.

## OPEN RISKS

- No production email was sent because no verified sender configuration exists.
- No normal worker can be activated until the qualification reference is
  created; this is an intentional launch gate.
- Work-session seconds are bounded operational evidence, not a payroll ledger.
  Payroll rules and reconciliation remain undefined.
- Password/MFA recovery and invitation resend/revoke are not yet complete
  operator workflows.
- `npm audit --omit=dev` still reports upstream transitive findings in the
  Next.js/Sharp/PostCSS and Prisma toolchains. Next.js was moved from 15.5.20 to
  15.5.22, but the remaining registry findings have no nonbreaking automated
  resolution and require a dependency follow-up.
- Fable did not return a verdict: one run hit its turn cap and the corrective
  run hit the five-minute wrapper timeout. No Fable conclusion is claimed.

## LINKS / FILES

- Product contract: `docs/specs/worker_ground_truth_portal_v1.md`
- Architecture decision:
  `docs/decisions/0006-supabase-worker-portal-control-and-media-plane.md`
- Worker UI: `console/components/review/review-tally-console.tsx`
- Onboarding UI: `console/components/review/reviewer-onboarding.tsx`
- Ops UI: `console/components/ops/ops-console.tsx`
- Email renderer: `console/lib/reviewerEmail.ts`
- Admin delivery: `console/lib/reviewerAdminServer.ts`
- Database migrations: `supabase/migrations/20260727*.sql`
