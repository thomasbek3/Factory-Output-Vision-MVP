from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = sorted((ROOT / "supabase/migrations").glob("*.sql"))
SPEC = ROOT / "docs/specs/worker_ground_truth_portal_v1.md"
ADR = ROOT / "docs/decisions/0006-supabase-worker-portal-control-and-media-plane.md"
LIVE_FIXTURE = ROOT / "supabase/tests/worker_portal_phase1_live.sql"


class SupabasePhase1ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = "\n".join(
            migration.read_text(encoding="utf-8") for migration in MIGRATIONS
        ).lower()
        cls.spec = SPEC.read_text(encoding="utf-8")
        cls.adr = ADR.read_text(encoding="utf-8")
        cls.live_fixture = LIVE_FIXTURE.read_text(encoding="utf-8").lower()

    def test_owner_amendment_is_explicit(self) -> None:
        amendment = self.spec.split("## 1. Plain-English Summary", maxsplit=1)[0]
        self.assertIn("Two matching human submissions", amendment)
        self.assertIn("No dedicated adjudicator role", amendment)
        self.assertIn("AI never breaks a human tie", amendment)
        self.assertIn("jhoshtiffhwsgurntgxp", amendment)

    def test_required_public_tables_exist(self) -> None:
        required = {
            "factories",
            "profiles",
            "factory_memberships",
            "stations",
            "media_objects",
            "media_renditions",
            "video_chunks",
            "review_assignments",
            "review_actions",
            "review_submissions",
            "consensus_runs",
            "consensus_events",
            "consensus_event_sources",
            "human_finalizations",
            "resolved_human_count_events",
            "internal_review_cases",
            "audit_log",
        }
        created = set(re.findall(r"create table public\.([a-z_]+)", self.sql))
        self.assertTrue(required.issubset(created), required - created)

    def test_reviewer_lifecycle_and_quality_tables_exist(self) -> None:
        required = {
            "reviewer_lifecycles",
            "reviewer_invitations",
            "reviewer_device_registrations",
            "reviewer_training_events",
            "reviewer_work_sessions",
            "review_coverage",
            "reviewer_support_requests",
        }
        created = set(re.findall(r"create table public\.([a-z_]+)", self.sql))
        self.assertTrue(required.issubset(created), required - created)

    def test_every_public_table_enables_rls(self) -> None:
        created = set(re.findall(r"create table public\.([a-z_]+)", self.sql))
        protected = set(
            re.findall(r"alter table public\.([a-z_]+) enable row level security", self.sql)
        )
        self.assertEqual(created, protected)
        forced = set(
            re.findall(r"alter table public\.([a-z_]+) force row level security", self.sql)
        )
        self.assertEqual(created, forced)

    def test_all_storage_buckets_are_private(self) -> None:
        for bucket in ("factory-originals", "review-renditions", "evidence-clips"):
            self.assertRegex(self.sql, rf"\('{bucket}', '{bucket}', false,")
        self.assertNotRegex(self.sql, r"\('(?:factory-originals|review-renditions|evidence-clips)'.*true")

    def test_human_majority_and_no_adjudicator_schema(self) -> None:
        self.assertIn("support_count in (2, 3)", self.sql)
        self.assertIn("'no_majority'", self.sql)
        self.assertNotIn("adjudicator", self.sql)
        self.assertNotIn("adjudication_", self.sql)
        self.assertNotIn("ai_run_id", self.sql.split("create table public.consensus_runs", 1)[1].split(");", 1)[0])

    def test_ai_data_is_private_and_browser_roles_are_revoked(self) -> None:
        for table in ("reference_answers", "ai_runs", "ai_events", "human_ai_comparisons"):
            self.assertIn(f"create table private.{table}", self.sql)
            self.assertIn(f"alter table private.{table} enable row level security", self.sql)
        self.assertIn(
            "revoke all on all tables in schema private from anon, authenticated",
            self.sql,
        )
        self.assertNotRegex(self.sql, r"grant .*private\..* to (?:anon|authenticated)")

    def test_immutable_human_lineage_has_guards(self) -> None:
        for table in (
            "review_actions",
            "review_submissions",
            "consensus_runs",
            "consensus_events",
            "consensus_event_sources",
            "human_finalizations",
            "resolved_human_count_events",
            "internal_review_cases",
            "audit_log",
        ):
            self.assertRegex(
                self.sql,
                rf"before update or delete on public\.{table}",
            )

    def test_protected_source_sets_cannot_be_assignment_eligible(self) -> None:
        self.assertIn(
            "source_set_role in ('production', 'practice', 'qualification', "
            "'resolver_calibration', 'exam', 'holdout')",
            self.sql,
        )
        self.assertIn(
            "source_set_role = 'production'\n    or assignment_eligible = false",
            self.sql,
        )

    def test_browser_grants_are_narrow(self) -> None:
        grants = re.findall(r"grant (.+?) to authenticated;", self.sql)
        joined = "\n".join(grants)
        self.assertNotIn("media_objects", joined)
        self.assertNotIn("media_renditions", joined)
        self.assertNotIn("video_chunks", joined)
        self.assertNotIn("internal_review_cases", joined)
        self.assertNotIn("audit_log", joined)
        self.assertNotIn("consensus_event_sources", joined)
        self.assertNotRegex(joined, r"insert on public\.(?:review_actions|review_submissions)")

    def test_exactly_three_submissions_and_terminal_assignments_are_enforced(self) -> None:
        self.assertIn("review round already holds three submissions", self.sql)
        self.assertIn("unique (chunk_id, review_round, reviewer_id)", self.sql)
        self.assertIn("submitted and problem assignments are terminal", self.sql)
        self.assertIn("counted_count < new.support_count", self.sql)
        self.assertIn(
            "consensus requires exactly three submissions in one round",
            self.sql,
        )
        self.assertIn(
            "two-counts-one-problem fixture accepted",
            self.live_fixture,
        )

    def test_consensus_requires_linked_human_evidence(self) -> None:
        self.assertIn(
            "support_count is not null and support_count in (2, 3)",
            self.sql,
        )
        self.assertIn("consensus event lacks matching human source lineage", self.sql)
        self.assertIn("consensus events require a resolved run", self.sql)
        self.assertIn("is distinct from run_row.resolved_total", self.sql)
        self.assertIn("alignment_tolerance_ms", self.sql)
        self.assertIn("undo.undoes_action_id = ra.id", self.sql)
        self.assertIn(
            "consensus event count does not match resolved total",
            self.sql,
        )
        self.assertIn("deferrable initially deferred", self.sql)
        self.assertIn("consensus_runs_one_resolved_per_chunk_idx", self.sql)
        self.assertIn("consensus_event_sources_unique_action_idx", self.sql)

    def test_disabled_reviewers_and_unbounded_leases_fail_closed(self) -> None:
        self.assertIn(
            "status not in ('leased', 'draft') or lease_expires_at is not null",
            self.sql,
        )
        self.assertGreaterEqual(self.sql.count("p.status = 'active'"), 4)
        self.assertIn("reviewer is not active", self.sql)
        self.assertNotIn("lease_expires_at is null or", self.sql)

    def test_assignment_and_media_identity_are_immutable(self) -> None:
        self.assertIn("assignment identity is immutable", self.sql)
        self.assertIn("media object identity is immutable", self.sql)
        self.assertIn("rendition source must be in factory-originals", self.sql)
        self.assertIn("review media must be in review-renditions", self.sql)

    def test_chunk_state_and_reviewability_fail_closed(self) -> None:
        self.assertIn("invalid chunk state transition from % to %", self.sql)
        self.assertIn("chunk is not reviewable", self.sql)
        self.assertIn("vc.state in ('ready', 'assigned')", self.sql)
        self.assertIn("video_chunks_published_at_required", self.sql)
        assignment_gate = self.sql.rsplit(
            "create trigger review_assignments_chunk_gate", 1
        )[1].split(";", 1)[0]
        self.assertNotIn("status", assignment_gate)
        self.assertIn(
            "quarantined assignment cleanup accepted",
            self.live_fixture,
        )

    def test_finalized_projection_cardinality_is_enforced(self) -> None:
        self.assertIn(
            "published event count does not match finalized consensus",
            self.sql,
        )
        self.assertIn(
            "create constraint trigger human_finalizations_cardinality",
            self.sql,
        )
        self.assertIn(
            "create constraint trigger resolved_human_events_cardinality",
            self.sql,
        )
        self.assertIn("consensus_event_count <> expected_count", self.sql)

    def test_immutable_ledgers_reject_truncate(self) -> None:
        ledgers = (
            "review_actions",
            "review_submissions",
            "consensus_runs",
            "consensus_events",
            "consensus_event_sources",
            "human_finalizations",
            "resolved_human_count_events",
            "internal_review_cases",
            "audit_log",
        )
        for ledger in ledgers:
            self.assertIn(f"{ledger}_reject_truncate", self.sql)
        self.assertRegex(
            self.sql,
            r"revoke truncate on table\s+public\.review_actions,"
            r"[\s\S]*from service_role;",
        )

    def test_default_public_privileges_are_revoked(self) -> None:
        self.assertIn(
            "alter default privileges in schema public revoke all on tables "
            "from anon, authenticated",
            self.sql,
        )

    def test_owner_reads_only_published_projection(self) -> None:
        self.assertIn(
            "grant select on public.resolved_human_count_events to authenticated",
            self.sql,
        )
        self.assertNotRegex(
            self.sql,
            r"grant select on public\.consensus_(?:runs|events) to authenticated",
        )
        self.assertIn("publication_status = 'published'", self.sql)
        self.assertIn("owner projection does not match finalized human event", self.sql)
        owner_policy = self.sql.rsplit(
            "create policy resolved_human_events_read_owner", 1
        )[1].split(");", 1)[0]
        self.assertIn("p.status = 'active'", owner_policy)

    def test_server_only_tables_have_explicit_deny_policies(self) -> None:
        for table in (
            "media_objects",
            "media_renditions",
            "video_chunks",
            "consensus_runs",
            "consensus_events",
            "consensus_event_sources",
            "human_finalizations",
            "internal_review_cases",
            "audit_log",
        ):
            self.assertRegex(
                self.sql,
                rf"on public\.{table} as restrictive for all to anon, authenticated\s+"
                r"using \(false\) with check \(false\)",
            )

    def test_adr_records_storage_and_truth_boundaries(self) -> None:
        self.assertIn("three private buckets", self.adr)
        self.assertIn("Two matching human", self.adr)
        self.assertIn("AI never breaks ties", self.adr)
        self.assertIn("service role", self.adr)
        self.assertIn("interactive practice and qualification assignments are", self.adr)

    def test_live_fixture_is_self_asserting_and_stop_on_error(self) -> None:
        self.assertIn("on_error_stop=1", self.live_fixture)
        self.assertIn("create temporary table phase1_fixture_result", self.live_fixture)
        self.assertIn("insert into phase1_fixture_result", self.live_fixture)
        self.assertIn("values ('pass', true, true, true, true)", self.live_fixture)
        self.assertIn("private bucket invariant failed", self.live_fixture)
        self.assertIn("service_role retained truncate", self.live_fixture)
        self.assertNotIn("'pass' as phase1_live_fixture", self.live_fixture)

    def test_worker_rpcs_derive_identity_and_never_accept_reviewer_id(self) -> None:
        rpc_sql = self.sql.split(
            "-- authenticated worker-loop rpcs. identity always comes from auth.uid().",
            maxsplit=1,
        )[1]
        self.assertGreaterEqual(rpc_sql.count("actor_id uuid := auth.uid()"), 4)
        self.assertNotRegex(rpc_sql, r"\bp_reviewer_id\b")
        self.assertNotRegex(rpc_sql, r"\breviewer_id\s+text\b")
        for function in (
            "claim_worker_assignment",
            "heartbeat_worker_assignment",
            "append_worker_action",
            "submit_worker_assignment",
        ):
            self.assertIn(f"grant execute on function public.{function}", rpc_sql)
            self.assertRegex(
                rpc_sql,
                rf"revoke all on function public\.{function}\([^;]+from public, anon",
            )

    def test_worker_rpcs_hash_leases_and_preserve_lost_response_retry(self) -> None:
        rpc_sql = self.sql.split(
            "-- authenticated worker-loop rpcs. identity always comes from auth.uid().",
            maxsplit=1,
        )[1]
        self.assertIn("digest(lease_token, 'sha256')", rpc_sql)
        self.assertGreaterEqual(
            rpc_sql.count("digest(p_lease_token, 'sha256')"),
            3,
        )
        submit = rpc_sql.split(
            "create or replace function public.submit_worker_assignment",
            maxsplit=1,
        )[1]
        self.assertLess(
            submit.index("if submission_row.id is not null then"),
            submit.index("assignment is not submittable"),
        )
        self.assertIn("'alreadysubmitted', true", submit)

    def test_production_reviewer_gates_fail_closed(self) -> None:
        self.assertIn("coalesce(auth.jwt() ->> 'aal', '') = 'aal2'", self.sql)
        self.assertIn("at least 98 percent of the video must be reviewed", self.sql)
        self.assertIn(
            "review completed faster than the enabled playback speed permits",
            self.sql,
        )
        self.assertIn("reviewer_one_active_account_per_device_idx", self.sql)
        self.assertIn("source_set_role = 'production'", self.sql)

    def test_scheduler_assigns_three_and_never_uses_ai_to_resolve(self) -> None:
        scheduler = self.sql.rsplit(
            "create or replace function public.service_maintain_review_queue",
            maxsplit=1,
        )[1]
        resolver = self.sql.split(
            "create or replace function public.service_resolve_ready_rounds",
            maxsplit=1,
        )[1]
        self.assertIn("for slot in 1..3 loop", scheduler)
        self.assertIn("assignment.review_round = (", scheduler)
        self.assertIn("next_round := round_row.review_round + 1", scheduler)
        self.assertIn("review.round.replaced", scheduler)
        self.assertIn("continue when eligible_count < 3", scheduler)
        self.assertIn("having count(*) = 3", resolver)
        self.assertIn("having count(*) >= 2", resolver)
        self.assertIn("timestamp_ambiguity", resolver)
        self.assertNotRegex(resolver, r"\bai_(?:run|event|count|total)\b")

    def test_new_worker_rpcs_are_narrowly_granted(self) -> None:
        signatures = (
            "public.worker_lifecycle_state()",
            "public.worker_record_onboarding_step(text, text, text, text)",
            "public.save_worker_coverage(uuid, text, uuid, jsonb, bigint)",
            "public.worker_request_support(uuid, text, text)",
            "public.authorize_worker_media(uuid, text)",
            "public.submit_worker_assignment_v2(uuid, text, uuid, text, text, text)",
            "public.worker_touch_work_session(uuid, text, integer)",
            "public.worker_close_work_session(uuid, text)",
        )
        compact = re.sub(r"\s+", " ", self.sql)
        compact = re.sub(r"\s*([(),])\s*", r"\1", compact)
        for signature in signatures:
            signature = re.sub(r"\s*([(),])\s*", r"\1", signature)
            self.assertIn(
                f"revoke all on function {signature}from public,anon",
                compact,
            )
            self.assertIn(
                f"grant execute on function {signature}to authenticated",
                compact,
            )
        self.assertIn(
            "revoke execute on function public.submit_worker_assignment("
            "uuid,text,uuid,text,text,text)from authenticated",
            compact,
        )

    def test_invitation_delivery_and_work_evidence_are_traceable(self) -> None:
        self.assertIn("ops_mark_reviewer_invitation_delivery", self.sql)
        self.assertIn("'delivery_failed'", self.sql)
        self.assertIn("reviewer_one_open_work_session_idx", self.sql)
        self.assertIn("bounded_delta := greatest(0, least(", self.sql)
        self.assertIn("reviewer_work_session_submission_count", self.sql)
        self.assertIn("ops_reviewer_support_requests", self.sql)
        self.assertIn("ops_set_reviewer_support_status", self.sql)
        self.assertIn("service_close_stale_work_sessions", self.sql)
        self.assertIn("factoryvision-work-session-cleanup", self.sql)
        self.assertIn("support request limit reached", self.sql)

    def test_qualification_is_server_scored_and_ready_chunks_are_immediate(self) -> None:
        latest_ops = self.sql.rsplit(
            "create or replace function public.ops_set_reviewer_state",
            maxsplit=1,
        )[1]
        self.assertIn("server-scored qualification is required", latest_ops)
        self.assertNotIn(
            "qualified_at = case when p_state = 'active'",
            latest_ops.split("create or replace function", 1)[0],
        )
        self.assertIn("service_record_reviewer_qualification", self.sql)
        self.assertIn("private.reference_answers", self.sql)
        self.assertIn("source_set_role = 'qualification'", self.sql)
        self.assertIn("factoryvision-ready-chunk-scheduler", self.sql)
        self.assertIn("chunk.source_end_at <= now()", self.sql)


if __name__ == "__main__":
    unittest.main()
