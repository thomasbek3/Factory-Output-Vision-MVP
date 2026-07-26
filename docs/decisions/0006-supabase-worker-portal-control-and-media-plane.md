# ADR 0006: Supabase Worker Portal Control And Media Plane

Status: Accepted

Date: 2026-07-26

## Context

The worker portal needs durable identity, tenant isolation, private delivery of
factory footage, immutable human labels, and a clean boundary between human
ground truth and AI output. The pilot has three reviewers but no separate
adjudicator or backup team.

The dedicated Supabase project is `jhoshtiffhwsgurntgxp` in `us-east-1`.

## Decision

Use Supabase Auth, PostgreSQL, row-level security, and private Supabase Storage
for the pilot control and media plane.

Use three private buckets:

- `factory-originals` for immutable original uploads;
- `review-renditions` for browser-ready 15-minute review media;
- `evidence-clips` for short diagnostic excerpts.

Reviewers never receive direct access to originals. The application validates
an active assignment and issues a short-lived signed URL for its review
rendition. Object keys contain opaque IDs rather than customer names.

Every normal chunk receives three blind human reviews. Two matching human
submissions resolve a count or event. A case with no two-person majority remains
unpublished in an internal exception queue. Ops may request a new independent
three-review round or mark footage unusable, but cannot manually create or edit
ground truth. AI never breaks ties or participates in human consensus.

Two matching counted submissions still resolve when the third reviewer submits
a footage/problem result. The problem report remains available for ops triage;
it does not erase the two-person human majority.

AI runs and comparisons live in a private database schema with no browser-role
access. They become available only through a server path after
the append-only `human_finalizations.human_final_at` record exists.

Ops exception and audit data is also API-only. The browser session never gets
direct table grants for raw submissions, internal cases, audit logs, media
metadata, or consensus lineage; an authenticated server route applies the
capability check and returns a purpose-built projection.

## Consequences

- Video bytes live in private object storage; metadata, assignments, labels,
  consensus lineage, and audit records live in PostgreSQL.
- Raw reviewer submissions remain immutable even when only two agree.
- Unresolved intervals block the owner's contiguous verified-through frontier.
- The service role handles ingest, assignment, signed URLs, consensus jobs, and
  internal AI data. It is never shipped to a browser.
- Original uploads require resumable transfer and content-hash verification.
- Retention and deletion must cover database lineage and all three buckets.

## Phase 1 Scope Boundaries

As of 2026-07-26, interactive practice and qualification assignments are
deferred to the worker-portal application phase. The private
`reference_answers` schema is reserved for that future flow; protected practice,
qualification, exam, calibration, and holdout chunks cannot enter the production
assignment queue.

Published human event rows are an immutable Phase 1 ledger. A later dispute
creates a new three-review round and internal case rather than editing existing
truth. The replacement result remains internal in Phase 1 because the one
finalization-per-chunk constraint prevents it from silently replacing
owner-visible truth. A future owner projection may add an append-only
retraction/supersession event, but the current `pending` and `retracted` enum
values are not active write paths.

Corrected re-ingest for an overlapping quarantined interval is also deferred.
The current overlap exclusion fails closed and requires an explicit migration or
replacement-media procedure instead of silently creating competing canonical
chunks.

## Verification Gate

Phase 1 is proved only when the migration applies to the dedicated project,
every exposed table has RLS, browser roles cannot access private media or AI
tables, cross-tenant reads are denied, append-only records reject update/delete,
the service role cannot truncate immutable ledgers, quarantined chunks cannot
receive review work, undone clicks cannot become consensus lineage, and a 2-of-3
fixture resolves without exposing the dissenting review.
