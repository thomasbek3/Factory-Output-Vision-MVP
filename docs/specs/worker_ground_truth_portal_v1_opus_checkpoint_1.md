# Worker Ground Truth Portal V1: Phase 1 Verification Receipt

Date: 2026-07-26

## Scope

This receipt covers the Supabase control and media-plane foundation only. It
does not claim that the Spanish-first worker portal UI, signed-URL API routes,
consensus worker, owner dashboard, or internal ops dashboard are implemented.

The enforced human-truth contract is:

- exactly three blind submissions in each normal review round;
- a two-of-three human majority resolves count and event truth;
- no adjudicator and no AI tie-break;
- no-majority results remain unpublished;
- owners can read only finalized, published human events.

## Independent Checkpoints

The first Opus 5 high-effort review returned `REVISE` and identified three P0
integrity failures: terminal assignments could be reused, consensus could be
fabricated without complete source lineage, and disabled reviewers or invalid
leases could write. Those paths were closed before the first production
migration.

The second Opus 5 high-effort review returned `PASS` on those P0 remediations
and required additional closure checks for cross-tenant reads, append-only
behavior, active owner profiles, immutable assignment identity, media-bucket
binding, source-time tolerance, and publication cardinality. Those requirements
landed in the closure migrations and rollback fixture.

The final high-effort review returned `REVISE` because the fixture marker was
not self-asserting, undone clicks could be cited as lineage, quarantined chunks
could receive assignments, and row triggers did not stop `TRUNCATE`. Migration
`worker_portal_phase1_adversarial_hardening` and the revised live fixture close
all four required findings.

The corrective review independently confirmed those four blockers closed. It
required migration-version parity and executable coverage for two matching
counts plus one problem submission. The local files were renamed to the exact
live versions, their bytes and MD5 values were matched to the SQL retained in
`supabase_migrations.schema_migrations`, and the positive mixed-result path was
added to the live fixture. A sixth migration also permits terminal assignment
cleanup after quarantine and prevents one human click from sourcing two
consensus events.

The final Opus 5 high-effort closure review returned `PASS` with no P0 or P1
blockers. It independently verified the six migration files, mixed-result
fixture, quarantine cleanup, action-lineage uniqueness, ADR boundaries, and
21-test contract.

## Live Supabase Evidence

Project: `jhoshtiffhwsgurntgxp`

Applied migration receipts:

- `20260726183446 worker_portal_phase1_domain`
- `20260726183908 worker_portal_phase1_hardening`
- `20260726191203 worker_portal_phase1_closure_hardening`
- `20260726191349 worker_portal_phase1_finalization_fix`
- `20260726192750 worker_portal_phase1_adversarial_hardening`
- `20260726193947 worker_portal_phase1_final_integrity`

Each local migration filename/version, migration name, byte length, and MD5
matches the corresponding live `schema_migrations.statements` value:

```text
20260726183446  47668  2055456629578f490f66b09b396bfa82
20260726183908   4401  1aedf5c5cf61c708d8a13fd073ae8843
20260726191203  14261  e4b6f5fffb9c848a18449a82302a3cb7
20260726191349   1208  f05585ffa45329ba1e598da4a4186e7c
20260726192750  11672  42784e6d643cc8b091aa394229c6b775
20260726193947    435  fb0cd852f9c76cd6a524e9b35e78188a
```

The stop-on-error, rollback-only fixture returned:

```text
phase1_live_fixture=pass
private_buckets_verified=true
private_schema_denied=true
anon_assignments_denied=true
service_role_truncate_denied=true
```

The fixture exercises:

- valid two-of-three consensus and owner publication;
- valid two-counts-plus-one-problem resolution with the problem retained;
- valid zero-output consensus and finalization;
- disabled reviewer and disabled owner denial;
- cross-factory reviewer and owner isolation;
- reviewer-own action, assignment, and submission RLS;
- server-only table RLS under temporary read grants;
- terminal and immutable assignment guards;
- illegal chunk-state regression and quarantined-assignment denial;
- terminal assignment cleanup after quarantine;
- mismatched submission totals;
- unresolved-run event denial;
- incomplete finalization denial;
- dissenting, out-of-tolerance, and undone-action lineage denial;
- reuse of one human click across consensus events;
- update/delete denial on all nine append-only ledgers;
- `TRUNCATE` denial.

Post-rollback catalog verification returned:

```text
fixture domain rows=0
fixture auth users=0
public tables with RLS and FORCE RLS=17/17
private storage buckets=3/3
service-role TRUNCATE denied=9/9
BEFORE TRUNCATE guards=9/9
unique human-action lineage index=1/1
Supabase security advisor findings=0
```

Static contract verification: `21/21` tests pass.

The live fixture executor was Supabase role `postgres`
(`rolsuper=false`, `rolbypassrls=true`). Authenticated reviewer and owner RLS
checks were executed after `SET LOCAL ROLE authenticated` with explicit JWT
claims; server-only RLS was exercised through rollback-only temporary grants.

The broader repository test receipts captured before the final SQL-only
hardening were:

- backend: `696 passed`;
- console unit tests: `45 passed`;
- console Playwright: `63 passed`;
- console production build: passed;
- console lint: zero errors and 12 pre-existing warnings in audit scripts.

## Actual Footage Boundary

Authorized factory footage exists at:

```text
/Users/thomas/FactoryVisionArtifacts/worker_days/20260709/gate-line/segments/20260709T120800_gate-line_20260709.mkv
```

Recorded SHA-256:

```text
cac1b9796d394be78c54553d9d1c520aa984f6d03c354d04d62b703b0ed4376c
```

The clip has not been uploaded to the live private bucket. The AI Mac Supabase
CLI has no access token or service-role credential, and the available connector
does not expose storage-object upload. Upload, signed download, hash
re-verification, and deletion remain blocked on authenticated service access.

## Remaining Phase 1 Limits

- Interactive practice and qualification assignment flows are deferred.
- Published truth is immutable; append-only retraction/supersession events are a
  later projection feature.
- Corrected overlapping re-ingest requires an explicit future procedure.
- Serial fixture proof does not substitute for a dedicated concurrent race
  harness.
- Cleanup after disabling a reviewer or flipping `assignment_eligible` off
  remains an application-phase operational hardening item.
- Migration hash parity is recorded but not yet enforced by CI.
- Media-object status transitions remain governed by the future retention and
  deletion procedure rather than a dedicated transition trigger.
