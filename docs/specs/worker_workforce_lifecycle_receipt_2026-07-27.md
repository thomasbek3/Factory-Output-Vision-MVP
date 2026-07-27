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
- The AI Mac server has the Supabase secret key configured in its private
  environment. `thomas@paverturf.com` is provisioned as the first permanent
  active `ops` membership and is awaiting email verification.
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
  or delivery_failed from the provider receipt. One ops action has a stable
  request key and provider idempotency key, so a browser retry cannot create a
  second invitation or send the same invitation twice. An ambiguous provider
  outcome is held for explicit reissue instead of guessed.
- Invitation acceptance is bound to a hashed, one-time, expiring token. Expired,
  revoked, replayed, and unaccepted password sessions fail closed. Ops can
  revoke an open invitation.
- Production activation requires a server-recorded result against a private
  qualification reference. The worker qualification player now collects event
  timestamps, scores them without exposing the gold answer, records an
  append-only attempt, and activates only a passing reviewer. Ops cannot convert
  the conceptual quiz into a passing qualification.
- Ops queue metrics now come from authenticated live Supabase data. The former
  public demo snapshot is no longer rendered or accessible without ops auth.
- Support requests verify assignment ownership and factory scope. Work-session
  time is derived from elapsed server time rather than a caller-supplied amount.
- Coverage writes merge monotonically under a row lock, so a stale browser tab
  cannot erase already observed video ranges.
- Suspended and offboarded reviewers are rejected by session restore, password
  login, MFA, onboarding, and worker RPC routes. Existing reviewer cookies are
  cleared on failed session restore.

## VERIFIED

- Live Supabase project: `jhoshtiffhwsgurntgxp`.
- Applied migrations: reviewer lifecycle, quality/scheduler, terminal round
  replacement, invitation delivery, work sessions, support inbox, stale-session
  cleanup, support rate limit, qualification gate, immediate ready scheduler,
  adversarial hardening, invitation/session follow-up, and resolver fixes.
- Static gates: 33 Supabase contract tests, 50 Vitest tests, ESLint, and a clean
  Next.js production build.
- GitHub CI now runs console lint, unit tests, production build, and the
  unauthenticated/mocked Playwright suite. `npm run e2e:release` fails closed
  unless live worker and ops QA credentials are supplied.
- Live Playwright: three isolated QA reviewer accounts shared one real
  15-minute factory chunk through distinct assignments. The run covered private
  signed media, actual playback, desktop/mobile layouts, durable tally/undo,
  reload recovery, offline recovery, a dropped committed response, idempotent
  retry, support creation, active-device registration, and work-session
  submission evidence.
- Live Playwright: authenticated ops roster, stored support request,
  acknowledgement, invitation dialog, and rendered Spanish invitation email.
- Live database adversarial proof:
  - cross-user support request denied with no durable row;
  - valid invitation accepted once, then replay denied;
  - expired and revoked invitations denied;
  - unaccepted invited session denied and active session allowed;
  - missing qualification gold answer denied activation;
  - gold-answer qualification claim, score, and activation passed in a
    rollback-isolated fixture;
  - three independent reviewer submissions resolved a human two-of-three
    majority with two-source lineage and a published owner projection;
  - three disagreeing submissions produced `no_majority`, an internal review
    case, and no human finalization.
  - stale-page coverage writes merged both ranges and retained the greater
    active-time value.
  - repeated invite delivery attempts with one request key returned one
    invitation, and a suspended/offboarded reviewer could not authorize a
    session.
- The rollback-only live proof can be rerun from
  `supabase/tests/worker_workforce_adversarial_live.sql`; the machine-readable
  receipt is `docs/specs/worker_workforce_live_proof_receipt_2026-07-27.json`.
- The three-person proof caught and fixed two resolver/schema contradictions:
  owner projections now default to `published`, and assigned chunks can become
  resolved only after a durable human finalization exists.
- Visual evidence:
  - `console/e2e-audit/shots/worker-review-desktop.png`
  - `console/e2e-audit/shots/worker-review-mobile.png`
  - `console/e2e-audit/shots/ops-worker-support.png`
  - `console/e2e-audit/shots/reviewer-invitation-email.png`
  - `console/e2e-audit/shots/reviewer-qualification.png`
  - `console/e2e-audit/shots/reviewer-qualification-mobile.png`

## NEXT 3

1. Curate and approve a disjoint 90-second qualification video, upload it as a
   `qualification` chunk, and add its private gold reference answer.
2. Configure the production host and email delivery values, send a real
   invitation to a controlled inbox, and prove its activate-account link.
3. Accept Thomas's Supabase verification email, then run one full first-worker
   rehearsal from received email through qualification and three-person
   production resolution.

## WAITING ON THOMAS

- Verified sending domain, sender name/address, Resend credential, Supabase
  server key, public review URL, and staffed support address.
- Accept the pending Supabase invitation for `thomas@paverturf.com`. The Auth
  user and permanent `ops` membership are already created.
- Final worker country/classification, pay basis and rate, time-rounding policy,
  privacy/data-handling terms, support SLA, and owner for payroll disputes.
- Approval of the gold qualification clip and pass thresholds.
- Hiring at least three qualified reviewers. The scheduler intentionally does
  not create partial production rounds with fewer than three.

## OPEN RISKS

- No production email was sent because no verified sender configuration exists.
- The permanent ops account is provisioned but cannot sign in until Thomas
  accepts Supabase's verification email.
- No normal worker can be activated until the qualification reference is
  created; this is an intentional launch gate.
- Work-session seconds are bounded operational evidence, not a payroll ledger.
  Payroll rules and reconciliation remain undefined.
- Password/MFA recovery is not yet a complete operator workflow. Reissuing an
  invitation is supported by creating a new invite, which revokes the old link,
  but it does not yet have a dedicated one-click roster action.
- `npm audit --omit=dev` still reports upstream transitive findings in the
  Next.js/Sharp/PostCSS and Prisma toolchains. Next.js was moved from 15.5.20 to
  15.5.22, but the remaining registry findings have no nonbreaking automated
  resolution and require a dependency follow-up.
- Fable did not return a verdict: one run hit its turn cap and the corrective
  run hit the five-minute wrapper timeout. No Fable conclusion is claimed.
- The independent adversarial reviewer first returned `BLOCK` on support
  ownership, invitation consumption, public demo metrics, qualification, and
  three-person proof. Its second pass found two remaining P1 issues: invite
  retry idempotency and suspended-session authorization. Both are now fixed and
  regression-covered. Its final scoped review returned `PASS` with no remaining
  P0 or P1 findings.

## LINKS / FILES

- Product contract: `docs/specs/worker_ground_truth_portal_v1.md`
- Architecture decision:
  `docs/decisions/0006-supabase-worker-portal-control-and-media-plane.md`
- Worker UI: `console/components/review/review-tally-console.tsx`
- Onboarding UI: `console/components/review/reviewer-onboarding.tsx`
- Qualification UI: `console/components/review/reviewer-qualification.tsx`
- Ops UI: `console/components/ops/ops-console.tsx`
- Email renderer: `console/lib/reviewerEmail.ts`
- Admin delivery: `console/lib/reviewerAdminServer.ts`
- Database migrations: `supabase/migrations/20260727*.sql`
- Executable live proof:
  `supabase/tests/worker_workforce_adversarial_live.sql`
- Live proof receipt:
  `docs/specs/worker_workforce_live_proof_receipt_2026-07-27.json`
