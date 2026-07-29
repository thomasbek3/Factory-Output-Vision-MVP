# FactoryVision Owner V2 Implementation Plan

Status: active  
Design authority: `DESIGN.md` §9  
Golden references: `docs/design/owner-v2/*.png`  
Branch: `day5-human-trigger`

## Objective

Build the approved owner product as a truthful, role-separated production
economics application. The owner must be able to create a project in under one
minute, see whether verified production is ahead/on-track/behind, understand
direct-cost margin and the recovery pace needed, inspect station/team
productivity, and reconcile completed work from permanent historical records.

Reviewer `/review` and internal `/ops` remain separate products. Owner routes
must never expose reviewer identity, votes, qualification, or labeling controls.

## Fixed decisions

- Production owner data lives in the existing Supabase Postgres project.
  Production owner routes never read or write Prisma SQLite.
- Every owner request is executed with that owner's Supabase access token.
  Postgres RLS is the final tenant boundary; owner request paths never use the
  Supabase service-role key.
- Owner authentication uses dedicated HttpOnly `fv_owner_access` and
  `fv_owner_refresh` cookies plus an owner-authorization RPC. Existing
  `fv_review_*` cookies and reviewer RPCs remain unchanged. Route/API guards
  authorize the required role per request; deployment-wide role switches are
  removed.
- Ops uses dedicated `fv_ops_access`/`fv_ops_refresh` cookies, `/ops/sign-in`,
  and the existing ops membership assertions. The ops shell and APIs fail
  closed before rendering data. The current fixture-backed ops page moves to a
  visibly labeled public `/ops-preview`; production `/ops` never uses fixtures.
- Owner cookies are `HttpOnly`, `SameSite=Strict`, path `/`, and `Secure` in
  production. Access cookies use the Supabase token TTL; refresh cookies expire
  after 30 days and rotate through the owner session endpoint.
- Every owner API requires an explicit `factory_id`. The authorization layer
  verifies that exact active factory membership before data access. `/` selects
  the sole active factory or shows a factory chooser; it never unions multiple
  memberships.
- Owner API errors are semantic: `401` missing/expired session, `403` role or
  cross-factory denial, `409` exclusion/closed-record conflict, `422` domain
  constraint failure, and `503 OWNER_DATA_UNAVAILABLE` only for network or
  Supabase 5xx outage. PostgREST error codes are preserved internally for this
  mapping and never collapsed into a generic availability error.
- Middleware becomes a coarse default-deny router, not the source of truth:
  anonymous `/` redirects to owner sign-in, anonymous `/ops` redirects to its
  sign-in, and anonymous legacy/owner APIs return `401` or `404`. Public auth
  endpoints, `/review`, `/review/welcome`, `/api/review/**`, and the visibly
  labeled preview surfaces are explicitly routable. Only
  `/api/review/preview` and `/api/review/preview-access` return anonymous
  practice data; session, password, MFA, onboarding, and RPC handlers enforce
  their own token/capability checks. Every page loader and API performs its own
  required-role authorization.
- Legacy `/tv` is removed from the production surface and returns `404`.
  Its fixture wallboard moves to `/owner-preview/tv` until an authenticated
  display-device token product is separately scoped.
- Owner Playwright uses a dedicated Supabase identity in an `is_test = true`
  factory. Release runs require `FV_OWNER_QA_EMAIL`, `FV_OWNER_QA_PASSWORD`, and
  `FV_OWNER_QA_FACTORY_ID`; setup authenticates through Supabase and
  `/api/owner/session`, then saves `storageState`. Missing/invalid QA credentials
  fail the owner release suite; they never skip it.
- Golden-overlay acceptance for `DESIGN.md` section 9.10 runs on
  `/owner-preview` (Today and the New Project drawer),
  `/owner-preview/stations`, `/owner-preview/history`, and
  `/owner-preview/tv`. These routes render the same `components/owner-v2/**`
  components as production with static fixture data and an injected fixed
  clock. Every preview is visibly marked `Preview data`, is read-only, and
  never calls live owner APIs. Owner V2 components accept data and a clock as
  inputs; components used by overlay specs never call `Date.now()` or fetch
  directly. Authenticated owner specs cover behavior, authorization, and
  durable truth but do not perform pixel overlays. Live owner routes fail
  closed when authentication or storage is unavailable.
- Visual acceptance captures at 1536×1024 with device scale factor 1. Playwright
  asserts bounding boxes within four CSS pixels for the shell navigation,
  context/date bar, summary KPI row, primary chart bounds, table header and
  first data row, plus the New Project drawer and each step header. It also
  asserts their computed color, font, padding, border, and radius tokens before
  generating a 50%-opacity overlay artifact. The static fixtures have no
  allowed dynamic mask regions. Two captures at least 90 seconds apart must be
  byte-identical, so update-snapshot is never an acceptance mechanism.
- Every owner-owned row includes `factory_id`; composite foreign keys prevent a
  child row from referencing records in another factory.
- Money is stored as integer cents, percentages as integer basis points, and
  timestamps as `timestamptz`. Intermediate calculations retain integer/rational
  precision and round half-up to cents only at an explicit currency boundary.
- `Margin after direct costs` means production value minus material cost minus
  direct labor. The UI never calls this profit.
- A closeout snapshots planned units, planned direct labor/material/margin
  cents, deadline, actual completion instant, verified actual units, actual
  direct labor/material/margin cents, and the factory timezone. `On time`
  means the snapshot reached its planned unit count and its completion instant
  is at or before the deadline instant; comparison is between stored
  `timestamptz` instants, while display uses the snapshotted IANA timezone.
  History's on-time percentage is on-time closeouts divided by all filtered
  completed closeouts.
- History grades are deterministic closeout results: `C−` when actual margin
  after direct costs is negative; otherwise `A` when the project is on time and
  actual margin is at least planned margin; `B` when either the project is on
  time or actual margin is at least 80% of planned margin; otherwise `C`.
  Integer cross-multiplication defines the 80% boundary. Grades and on-time
  results are derived only from immutable closeout fields, never current project
  rows, synthetic output, or plan-for-actual substitution.
- History selects the highest `owner_project_closeouts.revision` per project.
  The row, grade, on-time result, and every summary metric derive from that
  latest revision only. Superseded revisions never create another row or
  denominator entry and are visible only in the expanded audit trail. On-time
  percentage is therefore on-time latest revisions divided by filtered
  completed projects, not divided by revision rows.
- Pace is evaluated through each station's contiguous
  `verified_through_at`, not wall-clock now. A project rollup uses the oldest
  relevant station watermark across its active assignment intervals and shows
  station-specific freshness.
- Published human events are copied by a server-side trigger into an immutable,
  owner-safe production projection containing `factory_id`, `station_id`,
  `occurred_at`, opaque source references, and no reviewer identity. Only
  `source_set_role = 'production'` is projected. Owners never receive direct
  access to `video_chunks`.
- Wall-clock mapping is linear only when `gap_map = []` and the absolute
  difference between wall-clock chunk span and media-offset span is at most
  1,000ms. Then `occurred_at = source_start_at +
  (source_time_ms - source_start_ms) * 1ms`. A non-empty gap map or larger span
  mismatch projects no events and creates a `TIMELINE_UNTRUSTED` verification
  gap. There is no interpolation across missing media.
- Human event `publication_status = 'published'` and chunk
  `state = 'published'` are distinct. The resolver creates finalized,
  event-published rows while the chunk is `resolved`. A service-only publication
  producer then validates the complete finalization and timeline and moves the
  chunk to `published`; owner projection occurs only on that chunk transition.
- An immutable owner-safe verification-interval projection records published
  production chunk coverage even when a chunk contains zero output events.
  A quarantined or missing interval creates a visible permanent
  `VERIFICATION_GAP`; it stops the contiguous frontier, while later intervals
  are shown separately as `verified after a gap`. An audited ops correction may
  resolve the source interval, but no process silently advances across a hole.
- Provisional AI counts are visually separate and never silently included in
  verified totals.
- Good units include only owner-projected, published human-resolved production
  events assigned to the project at event time, less verified scrap, duplicate
  rework, and corrections. Pending, retracted, non-production, and AI-only
  events are excluded. Open disagreement is a verification gap, not a count.
- Non-working shift hours pause expected-production accumulation. Recorded
  downtime is excluded from required footage continuity, but it does not move
  the fixed deadline or retarget expected production.
- Project/station assignments may not overlap for the same station. A worker
  check-in interval therefore maps to at most one active project, so one hour
  of payroll is never charged twice. The new tables start empty and constraints
  reject overlap. Any later import has its own preflight overlap audit and fails
  loudly before inserting a violating interval.
- A worker may not hold overlapping station check-in intervals. Postgres
  exclusion constraints enforce both worker/time and station-project/time
  uniqueness.
- Expected output is evaluated at the verified watermark. Actual labor accrues
  only where worker intervals overlap scheduled shifts, including scheduled
  downtime and scheduled time after the deadline; it never accrues through
  off-shift nights or weekends. An overdue open project has zero remaining
  scheduled time and no fabricated recovery rate.
- If a station watermark exceeds the configured freshness threshold, verdict
  is `DATA_DELAY`, never `BEHIND`; the UI states which station is stale.
- When no verified trailing production rate exists, forecast units, forecast
  labor, and projected margin are unavailable. Planned pace remains visible but
  is never relabeled as a forecast.
- The New Project drawer shows `Planned margin after direct costs`, calculated
  from target units, value/material cents, and budgeted labor. Today shows
  `Projected margin` only after a verified trailing rate exists.
- Individual worker output is shown only for an explicit solo checked-in
  interval with sufficient camera coverage. Otherwise output belongs to the
  station team.
- Owner history is an append-only operational/financial record. Corrections add
  audit entries rather than rewriting closed records without trace. Database
  triggers deny audit and closeout update/delete/truncate.
- Station assignments and worker intervals are editable only while a project is
  draft or open, and every change appends an audit event. Close makes the
  assignments, labor ledger, output snapshot, and economics immutable.
  Post-close corrections append adjustment/audit rows and a new closeout
  revision; they never silently restate an earlier closeout.
- Owner production events, verification intervals, closeouts, and audit records
  outlive raw-video retention. Retained/deleted source transitions never retract
  published owner truth. An expired evidence link shows its recorded expiry and
  hash metadata but not missing media.
- If published coverage is later quarantined, projection rows and closed
  closeouts are never deleted. An append-only `COVERAGE_REVOKED` interval
  revision and audit event supersede the prior coverage. Open-dashboard totals
  exclude events inside the latest revoked revision; closed History preserves
  its snapshot and displays the later integrity warning. The same finalized
  chunk cannot be republished or re-reviewed. Restoring coverage requires a
  separately scoped future replacement-source workflow; an ops note or
  correction cannot reactivate revoked event ids.
- First publication inserts an immutable
  `owner_chunk_publication_locks(factory_id, chunk_id, published_at)` row.
  `guard_chunk_state_transition()` rejects a publication-locked
  `quarantined → transcoding` reprocessing transition while still permitting
  terminal retention/deletion. Pre-publication quarantines remain
  reprocessable.
- All visual implementation is semantic React/CSS. Golden PNGs are test
  references, never page backgrounds.

## Persistence and compatibility boundary

The Owner V2 migration extends the existing Supabase domain with new
factory-scoped tables:

- `owner_projects`
- `owner_project_drafts`
- `owner_workers`
- `owner_project_station_assignments`
- `owner_worker_station_intervals`
- `owner_station_downtime_intervals`
- `owner_output_adjustments`
- `owner_project_closeouts`
- `owner_project_audit`
- `owner_production_events`
- `owner_verification_intervals`
- `owner_chunk_publication_locks`

Factory workers are independent factory-scoped operational records, not
reviewer/authentication `profiles`; a factory employee does not need a login to
be scheduled or included in labor attribution. Owners manage those records
through the audited `owner_upsert_worker` RPC; direct table writes remain
unavailable to owner JWTs. Shared `factories`,
`factory_memberships`, `stations`,
`resolved_human_count_events`, `video_chunks`, and the authenticated Supabase
identity are referenced, not duplicated. Additive server-only triggers may read
published production chunk metadata to populate owner-safe projections; owners
receive no chunk grant or policy. The migration does not drop, rename, or change
the signature of reviewer contracts, including media/rendition/chunk, review
assignment/action/submission, consensus/resolution, qualification, invitation,
scheduler, worker session, and daily-progress tables, policies, triggers, or
RPCs.

One intentional owner-publication hardening is outside that compatibility
promise: the existing `resolved_human_events_read_owner` policy is dropped so
authenticated users can no longer select the raw projection. The browser grant
may remain but returns zero rows under RLS. Owner publication moves exclusively
to `owner_production_events` and `owner_verification_intervals`. The existing
live SQL fixture's owner-publication assertion is updated to the new projection;
all reviewer assertions and RPC contracts remain unchanged.

A second intentional hardening extends `guard_chunk_state_transition()` without
changing its signature: a chunk carrying an owner publication lock may enter
`quarantined` but may never leave it. This additive rejection prevents revoked
owner truth from being silently republished. Chunks quarantined before first
publication retain the existing reviewer reprocessing path, which must remain
green in the unchanged reviewer state-machine suite.

`console/prisma/dev.db` remains a deterministic local legacy/demo fixture until
the V2 route cutover, then is removed from production owner imports. It is not a
migration source and is never deployed as writable production storage.
`paceMath.ts` remains under its existing regression tests until
`ownerEconomics.ts` passes the replacement suite and all owner callers move;
then `paceMath.ts`, `jobSelectors.ts`, `alerts.ts`, `stationSelectors.ts`,
`pinnedJobs.ts`, `pinnedJobs.test.ts`, and every `$532` narrative assertion in
`paceMath.test.ts` and `e2e/live.spec.ts` leave production owner paths in the
same reviewed change. Preview-only code may retain fixture math under
`owner-preview` imports.

The legacy `/api/jobs` Prisma implementation is replaced at cutover. Its
seed-on-error `200` fallback is deleted, and `ownerJobs.ts` regex filtering is
deleted. Preview/live separation uses an explicit data-source flag, never
customer or project names. `use-console-jobs.ts` stops initializing from
`seedJobs` and stops calling `pinDemoNarrative`; live API records are returned
unchanged. `pinnedJobs.ts` is deleted or imported only by `/owner-preview`.
No module reachable from a production owner route may import `demoData`,
`paceMath`, or `pinnedJobs`. Reviewer practice code (`reviewChunks.ts` and
`reviewStore.ts`) may continue using `demoData` until a separately scoped
reviewer-fixture extraction; this exemption never reaches owner routes.

## Test seams

These are the public behaviors under test:

1. `ownerEconomics` pure functions: worked-time pace, verification lag,
   downtime, scrap/rework, labor burn, projected direct-cost margin, recovery
   rate, and status.
2. `jobForm` normalization/validation: the three project-setup steps and their
   server payload.
3. Owner jobs/history API routes: create, edit, start, close, correct, and read
   durable records through HTTP.
4. Owner browser workflows: Today selection, New Project, station detail,
   workforce attribution copy, History filters/expansion, audit records, and
   evidence links.
5. Role boundary: owner navigation and APIs never expose `/review`, `/ops`, or
   reviewer-only fields.
6. Supabase migration/publication: chunk publication, timeline invariant,
   owner-safe projection, interval revisions, RLS, and cron reachability.

Each capability is implemented as a vertical red→green slice.

## Checkpoint 0 — Architecture and adversarial plan review

Deliverables:

- This resolved plan.
- File and migration map.
- Opus 5 high-effort read-only adversarial verdict.
- Incorporated fixes for every P0/P1 finding before implementation.

Proposed file map:

- `console/lib/ownerEconomics.ts`
- `console/lib/ownerEconomics.test.ts`
- `console/lib/ownerDomain.ts`
- `console/lib/ownerServer.ts`
- `console/lib/opsServer.ts`
- `console/lib/ownerSupabase.ts`
- `console/lib/ownerProjectForm.ts`
- `console/lib/ownerProjectForm.test.ts`
- `console/package.json` (`@js-temporal/polyfill`)
- `console/middleware.ts`
- `console/app/(owner)/**`
- `console/app/sign-in/**`
- `console/app/ops/page.tsx`
- `console/app/ops/sign-in/**`
- `console/app/ops-preview/**`
- `console/app/api/ops/session/**`
- `console/app/api/jobs/route.ts` — delete
- `console/app/api/jobs/[id]/route.ts` — delete
- `console/app/api/owner/**`
- `console/app/owner-preview/**`
- `console/app/owner-preview/tv/**`
- `console/components/owner-v2/**`
- `console/components/jobs/use-console-jobs.ts`
- `console/components/chrome/owner-chrome.tsx` — rewrite
- `console/components/chrome/command-palette.tsx` — rewrite without seeds
- `console/components/jobs/jobs-dashboard.tsx` — replace with Projects V2
- `console/components/alerts/alerts-dashboard.tsx` — rewrite
- `console/components/history/history-dashboard.tsx` — rewrite
- `console/components/live/live-dashboard.tsx` — replace with Today V2
- `console/components/tv/tv-dashboard.tsx` — move to preview imports only
- `console/components/replay/replay-dashboard.tsx` — delete
- `console/components/replay/replay-archive.tsx` — delete
- `console/components/providers/time-provider.tsx` — rewrite owner time from
  real clock; preview owns any fixed clock
- `console/components/live/camera-tile-menu.tsx` — replace Replay link with
  authenticated evidence action
- `console/components/live/clip-drawer-provider.tsx` — rewrite for durable
  owner evidence
- `console/lib/pinnedJobs.ts`
- `console/lib/pinnedJobs.test.ts`
- `console/lib/jobSelectors.ts`
- `console/lib/alerts.ts`
- `console/lib/stationSelectors.ts`
- `console/lib/jobRecords.ts` — delete after API cutover
- `console/lib/ownerJobs.ts` — delete
- `console/lib/demoData.ts` — preview-only imports
- `console/lib/historyRecords.ts` — replace fixtures with durable closeouts
- `console/lib/historyRecords.test.ts` — rewrite against durable closeouts
- `console/lib/replayTimeline.ts` — delete
- `console/lib/replayTimeline.test.ts` — delete
- `console/components/replay/use-saved-clips.ts` — delete
- `console/lib/jobForm.ts` — delete after legacy jobs API removal
- `console/app/tv/page.tsx` — delete; preview route owns wallboard
- `console/app/(owner)/replay/page.tsx` — delete
- `console/app/(owner)/jobs/page.tsx` — rewrite as `/projects` redirect only
- `console/app/api/clips/route.ts` — delete after owner evidence cutover
- `console/app/api/clip/[eventId]/download/route.ts` — delete after owner
  evidence cutover
- `console/app/api/owner/evidence/**` — authenticated owner evidence metadata
  and retained-media access
- `console/e2e/owner-v2.spec.ts`
- `console/e2e/tv.spec.ts` — target `/owner-preview/tv`
- `console/e2e/flow.spec.ts` — remove legacy `/tv` production expectation
- `console/e2e/live.spec.ts` — replace `$532` narrative with Owner V2 truth
- `console/e2e/replay.spec.ts` — delete
- `console/e2e/archive.spec.ts` — rewrite for History closeouts
- `console/e2e/chrome.spec.ts` — update exact V2 navigation
- `console/e2e/mobile.spec.ts` — update surviving responsive routes
- `console/e2e/language.spec.ts` — keep reviewer language coverage; remove
  legacy owner assumptions
- `console/e2e/jobs.spec.ts` — replace with Projects V2 workflow
- `console/e2e/alerts.spec.ts` — rewrite against durable alerts
- `console/e2e/history.spec.ts` — rewrite against durable closeouts
- `console/playwright.config.ts` — owner QA setup/storage state
- `supabase/migrations/*_owner_v2.sql`
- `supabase/tests/owner_v2_live.sql`

## Checkpoint 1 — Durable model, tenancy, authorization, and calculations

Add durable project fields:

- `start_at`
- `unit_value_cents`
- `unit_material_cost_cents`
- `target_margin_bps`
- `loaded_labor_rate_cents_per_hour`
- `shift_calendar`
- `status`, close metadata, and immutable closeout snapshot references

The shared `factories` table adds
`verification_lag_threshold_minutes integer not null default 30`.

Add first-class records:

- project/station assignments with effective intervals
- worker station check-ins
- downtime intervals
- output adjustments (`scrap`, `rework`, `correction`)
- append-only project audit entries
- owner-safe event and verification-interval projections
- service-only chunk publication producer and cron invocation

Calculation requirements:

- worked minutes use the factory's IANA timezone through
  `@js-temporal/polyfill`; no fixed UTC offset and no process-local date
  arithmetic. A migration trigger rejects names absent from
  `pg_timezone_names`.
- downtime is subtracted from required verification coverage without double
  counting overlapping intervals; it is not subtracted from fixed-deadline pace
  or scheduled direct labor
- expected units and pace status use verified-through time
- pace thresholds are ±5% of expected units
- recovery rate uses remaining worked time
- labor burned uses effective worker/station intervals and snapshotted loaded
  rates intersected with scheduled shifts, includes scheduled downtime,
  continues after deadline when a shift is scheduled, and cannot be
  double-counted
- projected labor uses a trailing verified rate with safe cold-start behavior
- direct-cost margin carries explicit exclusions
- verification lag can suppress a false behind verdict
- labor is accumulated as exact `rate_cents_per_hour × milliseconds / 3,600,000`
  rationals. The project total is rounded half-up once; station cents are
  apportioned by largest fractional remainder with stable station-id
  tie-breaking, so station labor sums exactly to project labor

Migration requirements:

- A single transactional, additive Supabase migration creates all Owner V2
  tables, constraints, indexes, triggers, grants, RLS policies, and
  authorization RPCs.
- New rows carry `factory_id`; same-factory composite foreign keys and a
  station/time exclusion constraint reject cross-tenant references and
  overlapping project assignments.
- GiST exclusion constraints use the already-installed
  `extensions.btree_gist` operators and reject overlapping intervals for the
  same worker as well as the same station/project slot.
- Owner policies require active profile plus active `owner` membership.
  Positive and negative tests run as two actual authenticated identities.
- `owner_project_audit` and `owner_project_closeouts` are append-only at the
  database layer for authenticated, service-role, and table-owner mutation
  paths.
- Existing SQLite jobs are not silently imported into production. If a
  one-time import is later approved, it uses an idempotent, receipt-producing
  script with explicit factory mapping.
- Preview fixtures are separate static data and contain conspicuous fixture
  identifiers. They cannot be returned from API error handling.
- `owner_production_events` is populated only from published human events on
  production chunks and stores station plus wall-clock occurrence time.
  `owner_verification_intervals` is populated from production chunk terminal
  transitions and represents published coverage or explicit gaps. Both are
  immutable, owner-selectable under factory RLS, and reveal no reviewer data.
- A published production chunk is `verified` coverage only when its source
  timeline passes the linear mapping invariant. `quarantined`, missing, or
  timeline-untrusted chunks become gaps. `retained` and `deleted` are retention
  lifecycle states and never mutate earlier owner coverage.
- Project watermarks consider only each assignment's effective interval. For an
  ended assignment, required coverage is clamped at `effective_end`; an
  unresolved hole before that end remains a verification gap.
- `service_publish_resolved_chunks()` is `SECURITY DEFINER`, executable only by
  `service_role`/database maintenance, and runs from a new independent
  `factoryvision-owner-publication` pg_cron job every minute. It does not replace
  or alter `service_maintain_review_queue()`. It selects `resolved` production
  chunks with complete finalization cardinality. Trusted timelines transition
  to `published`; untrusted timelines transition to `quarantined` and append a
  gap.
- The projection trigger contract is `AFTER UPDATE OF state ON video_chunks`
  when `OLD.state = 'resolved' AND NEW.state = 'published'`. In the same
  transaction it inserts the immutable publication lock, verified interval, and
  all finalized event projections. `resolved_event_id` is the event idempotency
  key.
  Verification intervals use
  `(factory_id, chunk_id, revision)` plus `supersedes_id`; state transitions to
  quarantine append, never update, a higher revision.
- The revocation trigger contract is `AFTER UPDATE OF state ON video_chunks`
  when `OLD.state = 'published' AND NEW.state = 'quarantined'`. It appends
  exactly one `COVERAGE_REVOKED` revision and one audit event. Existing
  projection/event rows are not updated. `quarantined → published` remains an
  invalid state transition, and the hardened state guard also rejects the
  currently legal multi-hop path from a publication-locked quarantine back to
  `transcoding`.

Gate:

- Red→green unit tests for calculation and validation examples.
- Supabase migration applies to a fresh database and a copy of the current
  schema without destructive drift.
- HTTP create→read proof under owner JWT and cross-factory denial under a second
  owner JWT.
- Simulated production persistence proof: create, restart/redeploy boundary,
  then GET returns the same record.
- Network/Supabase 5xx failure returns structured
  `503 OWNER_DATA_UNAVAILABLE`; denial and domain conflicts retain their
  distinct `401`/`403`/`409`/`422` status and never return fixtures with `200`.
- Owner is denied reviewer/ops pages and APIs; reviewer behavior remains green
  in the same deployment.
- Anonymous `/`, `/ops`, `/api/jobs`, and owner mutation endpoints are denied
  after the deployment-global flag is removed.
- Anonymous `/review`, `/review/welcome`, `/api/review/preview`, and
  `/api/review/preview-access` preserve the shipped no-login practice flow.
- `/ops/sign-in` is real and public; anonymous `/ops` redirects there, an owner
  is denied, and only an active ops membership can establish ops cookies.
- `/owner-preview`, `/owner-preview/stations`, `/owner-preview/history`,
  `/owner-preview/tv`, and `/ops-preview` each have a render test requiring
  HTTP `200`, a visible `Preview data` label, read-only behavior, and zero live
  owner/ops API calls.
- The legacy seed fallback and name-based `probe|smoke` suppression are absent;
  a real client named `Smoke Test Fixtures Inc.` remains visible.
- Opus 5 adversarial review of persistence, auth, model, math, migration, and
  tests.

## Checkpoint 2 — Today and New Project

Today:

- Owner V2 shell and navigation.
- Navigation order is exactly `Today`, `Projects`, `Stations`, `Workforce`,
  `History`, `Alerts`, `Settings`.
- Routes are `/`, `/projects`, `/stations`, `/workforce`, `/history`,
  `/alerts`, and `/settings`. Legacy `/jobs` redirects to `/projects`;
  `/replay` returns `404` and is removed from navigation.
- Three active-project verdict rows.
- Selected-project actual/required/recovery chart.
- Verification-lag attention rail.
- Station performance table.
- No giant profit hero and no synthetic chart values.

New Project:

- Three-step 640px desktop drawer.
- Step summaries with Edit actions.
- Station suggestion requires explicit confirmation.
- Feasibility calculation before Start.
- Draft persistence.
- Mobile full-screen step flow.

Gate:

- Component/unit tests for state and validation.
- Playwright workflows at desktop/tablet/mobile.
- 1536×1024 screenshot overlay against references 01 and 02.
- Computed-token assertions for named golden elements cover color, typography,
  padding, border, and radius in addition to bounding-box geometry.
- Accessibility and console-error checks.
- Opus 5 adversarial review of UX, truthfulness, and drift.

## Checkpoint 3 — Stations and Workforce

- Station selector/context bar.
- Verified units, units/hour, labor hours, output/labor hour.
- Real 15-minute production series, required pace, NOW, and downtime bands.
- Camera/evidence panel.
- Team-on-station table.
- Scrap/rework/downtime summary.
- Explicit team-versus-solo attribution states.
- Alerts presents durable verification lag, coverage revocation, and project
  pacing exceptions. It has no synthetic alerts.
- Settings owns the factory-local IANA timezone and
  `verification_lag_threshold_minutes`; updates require owner authorization,
  validation, and audit.

Gate:

- Attribution and aggregation tests.
- Browser interaction and responsive screenshots.
- Overlay against reference 03.
- Opus 5 adversarial privacy, fairness, and data-integrity review.

## Checkpoint 4 — History and audit

- Filter bar and export.
- Summary metrics.
- Dense completed-project table.
- Inline closeout comparison.
- Real weekly output chart.
- Append-only audit timeline.
- Evidence links attached to records, not raw-footage browsing.

Gate:

- Closeout snapshot and correction tests.
- HTTP and browser tests for filters, expansion, export, and evidence.
- Overlay against reference 04.
- Closeout grade/on-time boundary tests and an explicit plan-versus-actual
  substitution failure test.
- Opus 5 adversarial reconciliation and audit review.

## Checkpoint 5 — Integration and release hardening

- All owner views use the reviewed durable APIs from Checkpoint 1.
- Owners can see only their factory records and published owner-safe evidence.
- Owner, reviewer, and ops authorization is enforced independently per surface,
  not inferred from hidden navigation or a deployment-wide environment flag.
- Existing reviewer Supabase contracts remain intact.
- Demo fixtures are visibly labeled and cannot leak into live owner totals.

Gate:

- RLS contract tests with positive and negative authenticated identities plus
  rollback-only live receipts for mutation-free checks.
- Committed create→restart→read proofs run only in an `is_test = true` factory,
  tag rows with a unique correlation id, and delete them through an audited
  teardown RPC after receipt capture.
- Cross-factory denial tests.
- Owner/reviewer/ops route-boundary tests.
- Full Opus 5 adversarial release review.

## Checkpoint 6 — Release proof

- Full unit, contract, lint, build, and end-to-end suites green.
- Desktop/tablet/mobile screenshots visually inspected.
- Canonical AI Mac checkout and GitHub branch synchronized.
- Force `vercel --prod` from `console/`.
- Browse the production alias, exercise all owner workflows, capture
  screenshots, and inspect console/network errors.
- Verify `/review` still works and remains owner-inaccessible.
- Close the goal only after production evidence is complete.

## Opus 5 checkpoint protocol

Every checkpoint is reviewed in Claude Code print mode with:

- model alias `opus` (latest Opus 5)
- high effort
- read-only tools (`Read`, `Grep`, `Glob`)
- Chrome disabled
- no session persistence
- no implementation permission

Each prompt requires:

- `PASS`, `REVISE`, or `BLOCK`
- ranked findings with file/line evidence
- missing evidence
- failure tests
- minimum changes

P0/P1 findings must be independently verified and resolved. The next checkpoint
does not begin until the current checkpoint has a PASS or all blocking findings
are demonstrably closed.

Checkpoint 1 artifacts created after the six successful plan passes are
provisional vertical red→green slices, not accepted checkpoint output. Their
failing and passing receipts are preserved, and they remain subject to the
Checkpoint 1 Opus review and database execution proof before integration.

## Checkpoint 0 live evidence

A read-only query against Supabase project `jhoshtiffhwsgurntgxp` on
2026-07-29 found:

- one production chunk in `assigned`
- one practice chunk in `ready`
- zero resolved/published human events
- zero chunks with non-empty `gap_map`
- zero chunks whose media and wall-clock spans differ by more than 1,000ms

Therefore the Owner V2 publication migration has no historical owner totals to
backfill and no ambiguous source timeline to reinterpret. This snapshot is
evidence for migration planning, not a substitute for the post-migration live
tests.

## Mandatory failure tests

Each numbered regression has an owning checkpoint:

- Checkpoint 1: 1–31, 33–46, 55, and 57.
- Checkpoint 2: 32, 41–42, 47–50, 52–54, 56, and 58–60.
- Checkpoint 3: station/workforce applications of 4, 10, 13, 18, and 21.
- Checkpoint 4: 51, 61–65, plus history/audit applications of 12, 31, 33, 37,
  and 43.
- Checkpoint 5 reruns all 65 as the integration gate.

Named regressions:

1. A production-created project survives a process/redeploy boundary.
2. Owner A cannot read, write, or infer Owner B's rows.
3. Labor continues accruing on an overdue open project.
4. Concurrent project labor cannot exceed the underlying payroll interval.
5. A winter date in `America/Los_Angeles` uses PST, not a hard-coded PDT
   offset.
6. Results are identical when the Node process runs with `TZ=Asia/Tokyo`.
7. `$1,000 / 400` derives exactly `$2.50` per unit.
8. Storage errors produce a degraded/503 response, never demo fixtures.
9. Excess verification lag produces `DATA_DELAY`, not a false `BEHIND`.
10. Overlapping downtime intervals are unioned before subtraction.
11. Good units exclude scrap, duplicate rework, provisional, retracted, and
    non-production output.
12. Audit and closeout update, delete, and truncate are denied by Postgres.
13. Two checked-in workers produce team attribution only.
14. An owner is denied `/review`, `/ops`, and their APIs while a reviewer still
    accesses `/review` in the same deployment.
15. The additive migration preserves current reviewer data and contracts.
16. An owner JWT receives station-attributed production and verification
    intervals without any service-role key on the request path.
17. Practice, qualification, resolver-calibration, exam, and holdout chunks
    never enter owner totals.
18. Postgres rejects one worker checked into two stations at overlapping times.
19. Anonymous `/`, `/ops`, `/api/jobs`, and owner mutations fail closed.
20. A real `Smoke Test Fixtures Inc.` project remains visible.
21. Per-station labor cents sum exactly to project labor cents for fractional
    multi-worker intervals.
22. Spring-forward and fall-back shift fixtures use the correct factory-local
    duration.
23. An owner with two memberships sees only the explicitly requested factory;
    an omitted `factory_id` returns `400`.
24. A verification hole keeps a contiguous frontier, exposes later intervals as
    `verified after a gap`, and does not remain mislabeled as ordinary lag.
25. `worker_portal_phase1_live.sql` drives its fixture chunk through
    `resolved → published`, setting `published_at` in the same update, and
    migrates all three owner-publication assertions (entitled, cross-tenant, and
    disabled) to the owner-safe projections. The entitled baseline must be
    non-zero so negative checks cannot pass vacuously;
    `worker_workforce_adversarial_live.sql` and
    `ops_command_center_live.sql` pass unchanged, and a before/after schema diff
    shows only the named additive objects plus the explicitly removed legacy
    owner policy.
26. A non-empty `gap_map` projects no owner event timestamps and creates a
    `TIMELINE_UNTRUSTED` gap; linear interpolation across it fails.
27. A wall-clock/media span mismatch over 1,000ms projects no shifted events and
    creates a verification gap.
28. An owner JWT selecting `resolved_human_count_events` directly receives zero
    rows.
29. An owner JWT is denied direct reads of `video_chunks`,
    `review_submissions`, and `consensus_events`.
30. A violating interval insert and a later import preflight both fail loudly;
    no row is silently dropped or quarantined.
31. `retained` or `deleted` source transitions leave prior owner coverage,
    owner events, and closeout totals unchanged.
32. Anonymous `/review/welcome`, `/api/review/preview`, and
    `/api/review/preview-access` still succeed after default-deny lands.
33. Editing an assignment on a closed project is denied; a post-close
    correction creates an immutable audit/closeout revision.
34. `resolver_calibration` chunks never enter owner totals.
35. A chunk left at `resolved` yields no owner events and an explicit
    `NO_PUBLISHED_COVERAGE` operational condition rather than a silent empty
    dashboard.
36. Finalized event-published rows project nothing while their chunk is
    `resolved`; the later `resolved → published` transition projects every event
    exactly once, and retries are idempotent.
37. `published → quarantined` after closeout preserves closeout cents, appends a
    `COVERAGE_REVOKED` interval/audit event, and excludes the interval from live
    current totals.
38. Reprocessing or republishing the same revoked chunk is rejected. An ops
    correction may annotate the permanent gap but cannot reactivate immutable
    event ids or mutate prior revisions.
39. Anonymous `/ops` redirects to the real `/ops/sign-in`; an authenticated
    owner and a reviewer carrying only `fv_review_*` cookies are denied, and an
    active ops identity succeeds.
40. Creating or editing a December 15, 2026 5:30 PM deadline through the owner
    project API stores the correct PST instant in `America/Los_Angeles`; the
    deleted legacy jobs routes and their fixed `-07:00` conversion are absent.
41. No seed or pinned job appears in a live owner API response or dashboard;
    a database row whose id matches an old seed id is returned unmodified.
42. Production `/tv` returns `404`; `/owner-preview/tv` remains a clearly
    labeled fixture surface.
43. `published → quarantined` appends exactly one `COVERAGE_REVOKED` revision
    and performs zero updates/deletes against prior revisions.
44. The deployed `factoryvision-owner-publication` cron job calls the
    publication producer within one minute without changing the reviewer
    maintenance job.
45. A publication-locked revoked chunk is rejected when driven
    `quarantined → transcoding`; owner totals and interval revision count remain
    unchanged.
46. A chunk quarantined before first publication still follows the existing
    reviewer reprocessing path.
47. `tsc --noEmit` and `next build` pass after legacy deletion with no
    production owner import of `paceMath`, `pinnedJobs`, or `demoData`.
48. Owner command search returns no seed jobs while a durable live project
    remains findable.
49. The full e2e suite is green after `/tv` removal; no production test
    navigates to the removed route.
50. Owner navigation renders exactly `Today`, `Projects`, `Stations`,
    `Workforce`, `History`, `Alerts`, `Settings`; no Replay item remains.
51. Owner evidence APIs use authenticated durable records and never return
    `demoData` clips.
52. A route-graph check proves no module reachable from a production owner page
    imports `demoData`, `paceMath`, or `pinnedJobs`; reviewer practice imports
    remain explicitly exempt.
53. `/review` and `/api/review/preview` remain green after owner fixture
    isolation.
54. An authenticated owner Playwright session loads all seven owner routes and
    fails, rather than skips, when required QA credentials are absent.
55. Cross-factory denial returns `403`; overlap returns `409`; check/domain
    rejection returns `422`; none return `503 OWNER_DATA_UNAVAILABLE`.
56. `/ops-preview`, `/owner-preview`, `/owner-preview/stations`,
    `/owner-preview/history`, and `/owner-preview/tv` return `200`, display
    `Preview data`, are read-only, and issue no live ops/owner requests.
57. Anonymous calls to reviewer RPC/password/MFA/onboarding handlers are denied
    by those handlers even though middleware routes `/api/review/**`.
58. A static e2e route audit rejects navigation to removed `/tv` or `/replay`
    and requires every authenticated owner spec to use authenticated storage
    state; preview render specs are explicitly excluded.
59. The visual-acceptance spec renders references 01–04 at 1536×1024 and
    device scale factor 1, producing byte-identical screenshots across two runs
    separated by at least 90 seconds of wall-clock time. A moving NOW line or
    relative timestamp fails rather than being silently re-baselined. Named
    golden elements also assert computed color, font, padding, border, and
    radius tokens.
60. A static import audit proves no `components/owner-v2/**` module used by an
    overlay spec reads `Date.now()` or fetches directly.
61. History filter state round-trips through the URL and survives browser back
    navigation.
62. `tsc --noEmit` and the unit suite pass after `historyRecords.ts` is
    replaced, with no orphaned import of the deleted grading helpers.
63. History grade and on-time result derive only from immutable closeout fields.
    A project whose actual labor or margin differs from plan renders the actual;
    substituting any planned value for an actual fails.
64. Grade thresholds are asserted at exact A/B/C/C− boundaries, including
    negative margin and the integer 80% margin boundary.
65. A project with two closeout revisions renders exactly one History row;
    grade, on-time result, and every summary use revision 2; the denominator
    counts the project once; revision 1 is reachable only through the audit
    trail.

The `/` page-load path is the sole factory-id exception: it resolves one active
membership or shows a chooser. All owner data APIs require `factory_id` and
return `400` when it is omitted.
