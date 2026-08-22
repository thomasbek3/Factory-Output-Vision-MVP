from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = sorted((ROOT / "supabase/migrations").glob("*.sql"))
SPEC = ROOT / "docs/specs/worker_ground_truth_portal_v1.md"
ADR = ROOT / "docs/decisions/0006-supabase-worker-portal-control-and-media-plane.md"
LIVE_FIXTURE = ROOT / "supabase/tests/worker_portal_phase1_live.sql"
WORKFORCE_LIVE_PROOF = (
    ROOT / "supabase/tests/worker_workforce_adversarial_live.sql"
)
OPS_COMMAND_CENTER_LIVE_PROOF = (
    ROOT / "supabase/tests/ops_command_center_live.sql"
)


class SupabasePhase1ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = "\n".join(
            migration.read_text(encoding="utf-8") for migration in MIGRATIONS
        ).lower()
        cls.spec = SPEC.read_text(encoding="utf-8")
        cls.adr = ADR.read_text(encoding="utf-8")
        cls.live_fixture = LIVE_FIXTURE.read_text(encoding="utf-8").lower()
        cls.workforce_live_proof = WORKFORCE_LIVE_PROOF.read_text(
            encoding="utf-8"
        ).lower()
        cls.ops_command_center_live_proof = (
            OPS_COMMAND_CENTER_LIVE_PROOF.read_text(encoding="utf-8").lower()
        )

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

    def test_passwordless_rate_limit_keeps_identity_data_private(self) -> None:
        self.assertIn(
            "create table private.passwordless_login_requests",
            self.sql,
        )
        self.assertIn(
            "alter table private.passwordless_login_requests enable row level security",
            self.sql,
        )
        self.assertIn(
            "alter table private.passwordless_login_requests force row level security",
            self.sql,
        )
        self.assertIn(
            "revoke all on private.passwordless_login_requests from public, anon, authenticated",
            self.sql,
        )
        self.assertIn("p_email_hash text", self.sql)
        self.assertIn("p_ip_hash text", self.sql)
        self.assertIn("interval '60 seconds'", self.sql)
        self.assertIn("interval '1 hour'", self.sql)
        self.assertIn(
            "grant execute on function public.check_passwordless_login_rate(text, text)\n  to anon",
            self.sql,
        )
        self.assertIn(
            "revoke all on function public.check_passwordless_login_rate(text, text)\n  from public, authenticated",
            self.sql,
        )

    def test_owner_approved_20x_speed_keeps_submission_integrity_gates(self) -> None:
        latest_submit = self.sql.rsplit(
            "create or replace function public.submit_worker_assignment_v2",
            1,
        )[1]
        self.assertIn("usable_ms / 20000.0", latest_submit)
        self.assertIn("covered_ms * 100 < usable_ms * 98", latest_submit)
        self.assertIn(
            "coalesce(auth.jwt() ->> 'aal', '') <> 'aal2'",
            latest_submit,
        )
        self.assertIn("active reviewer with mfa required", latest_submit)
        amendment = self.spec.split("## Owner Amendment", maxsplit=1)[0]
        self.assertIn("1x, 2x, 5x, 10x, 15x, and 20x", amendment)
        self.assertIn("real account menu and settings dialog", amendment)

    def test_typed_coverage_gate_error_codes_are_stable(self) -> None:
        # The worker UI branches on these codes (review-tally-console.tsx
        # isCoverageIncomplete / isAssignmentUnavailable); changing them
        # breaks lease/coverage/MFA UX.
        latest_submit = self.sql.rsplit(
            "create or replace function public.submit_worker_assignment_v2",
            1,
        )[1]
        for code, message in (
            ("cv000", "video coverage has not been saved"),
            ("cv001", "at least 98 percent of the video must be reviewed"),
            ("cv002", "faster than the enabled playback speed permits"),
            ("mf000", "active reviewer with mfa required"),
        ):
            raise_at = latest_submit.index(message)
            errcode_at = latest_submit.rindex(f"errcode = '{code}'", 0, raise_at + 400)
            self.assertLess(errcode_at, raise_at + 200)
            self.assertGreater(errcode_at, raise_at - 200)
        # The three coverage gates must no longer share bare 23514.
        self.assertNotIn("errcode = '23514'", latest_submit)

    def test_typed_migration_differs_from_20x_only_in_errcodes(self) -> None:
        # Guard against body drift: strip comments, extract both function
        # bodies, normalize the errcode tokens, and require equality.
        import re

        def body(path: str) -> str:
            text = (ROOT / path).read_text(encoding="utf-8")
            text = "\n".join(
                line for line in text.splitlines()
                if not line.strip().startswith("--")
            )
            start = text.index("create or replace function public.submit_worker_assignment_v2")
            return text[start:].strip().lower()

        typed = re.sub(r"errcode = '(cv00[012]|mf000|42501)'", "errcode = 'X'", body(
            "supabase/migrations/20260821190000_typed_coverage_gate_error_codes.sql"
        ))
        baseline = re.sub(r"errcode = '23514'|errcode = '42501'", "errcode = 'X'", body(
            "supabase/migrations/20260728012044_worker_review_speed_20x.sql"
        ))
        self.assertEqual(typed, baseline)

    def test_client_maps_coverage_gate_codes_without_prose_matching(self) -> None:
        supabase = (ROOT / "console/lib/reviewSupabase.ts").read_text(encoding="utf-8")
        classifiers = (
            ROOT / "console/lib/review-tally-console-classifiers.ts"
        ).read_text(encoding="utf-8")
        component = (
            ROOT / "console/components/review/review-tally-console.tsx"
        ).read_text(encoding="utf-8")
        for domain_code in ("COVERAGE_MISSING", "COVERAGE_INCOMPLETE", "COVERAGE_TOO_FAST"):
            self.assertIn(f'"{domain_code}"', supabase)
            self.assertIn(f'"{domain_code}"', classifiers)
        # The typed branch must not regex prose; only the legacy fallback may.
        self.assertIn('error.domainCode === "COVERAGE_INCOMPLETE"', classifiers)
        # The component must classify through the extracted module.
        self.assertIn("review-tally-console-classifiers", component)

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
        )[1].split("create or replace function", 1)[0]
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
            "public.worker_daily_progress()",
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

    def test_worker_daily_progress_is_personal_and_hides_peer_truth(self) -> None:
        progress = self.sql.rsplit(
            "create or replace function public.worker_daily_progress()",
            maxsplit=1,
        )[1].split("revoke all on function", maxsplit=1)[0]
        self.assertIn("actor_id uuid := auth.uid()", progress)
        self.assertIn("assignment.reviewer_id = actor_id", progress)
        self.assertIn("submission.reviewer_id = actor_id", progress)
        self.assertNotRegex(
            progress,
            r"\b(?:consensus|ai_events|human_finalizations|resolved_human)\b",
        )

    def test_worker_rendition_timeline_and_test_factory_guard_are_explicit(self) -> None:
        claim = self.sql.rsplit(
            "create or replace function public.claim_worker_assignment",
            maxsplit=1,
        )[1].split(
            "create or replace function public.worker_daily_progress",
            maxsplit=1,
        )[0]
        self.assertIn("'renditionsourcestartms', rendition.padded_start_ms", claim)
        self.assertIn("'renditionsourceendms', rendition.padded_end_ms", claim)
        self.assertIn("rendition.mapping_status = 'verified'", claim)
        self.assertIn(
            "(not lifecycle_row.is_test_account or factory.is_test)",
            claim,
        )
        self.assertIn(
            "add column if not exists is_test boolean not null default false",
            self.sql,
        )
        self.assertIn(
            "and not factory.is_test\n  and assignment.status in "
            "('queued', 'leased', 'draft')",
            self.sql,
        )
        latest_picker = self.sql.rsplit(
            "create or replace function public.service_pick_reviewer",
            maxsplit=1,
        )[1].split("revoke all on function", maxsplit=1)[0]
        self.assertIn("join public.factories factory", latest_picker)
        self.assertIn(
            "(not lifecycle.is_test_account or factory.is_test)",
            latest_picker,
        )
        self.assertIn("reviewer_lifecycles_test_factory_guard", self.sql)
        self.assertIn(
            "test accounts require an explicitly marked test factory",
            self.sql,
        )

    def test_qualification_attempt_window_is_consistent(self) -> None:
        claim = self.sql.rsplit(
            "create or replace function public.worker_claim_reviewer_qualification",
            maxsplit=1,
        )[1].split("revoke all on function", maxsplit=1)[0]
        submit = self.sql.rsplit(
            "create or replace function public.worker_submit_reviewer_qualification",
            maxsplit=1,
        )[1].split("create or replace function", maxsplit=1)[0]
        for function_sql in (claim, submit):
            self.assertIn(
                "attempt.submitted_at > now() - interval '24 hours'",
                function_sql,
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

    def test_adversarial_review_security_gates_fail_closed(self) -> None:
        latest_support = self.sql.rsplit(
            "create or replace function public.worker_request_support",
            maxsplit=1,
        )[1].split("create or replace function", 1)[0]
        self.assertIn("assignment.reviewer_id = actor_id", latest_support)
        self.assertIn("assignment.factory_id = lifecycle_row.factory_id", latest_support)
        self.assertIn("support assignment is not available to this reviewer", latest_support)

        self.assertIn("invitation_token_hash", self.sql)
        self.assertIn("worker_accept_reviewer_invitation", self.sql)
        self.assertIn("worker_authorize_reviewer_session", self.sql)
        self.assertIn("ops_revoke_reviewer_invitation", self.sql)
        self.assertIn("reviewer_invitations_request_key_idx", self.sql)
        self.assertIn("ops_reviewer_invitation_request", self.sql)
        self.assertIn("ops_claim_reviewer_invitation_delivery", self.sql)
        self.assertIn("'delivery_unknown'", self.sql)
        acceptance = self.sql.rsplit(
            "create or replace function public.worker_accept_reviewer_invitation",
            maxsplit=1,
        )[1].split("create or replace function", 1)[0]
        self.assertIn("invitation.status = 'sent'", acceptance)
        self.assertIn("invitation.expires_at > now()", acceptance)
        self.assertIn("invitation.revoked_at is null", acceptance)
        self.assertIn("status = 'accepted'", acceptance)

        lifecycle = self.sql.rsplit(
            "create or replace function public.worker_lifecycle_state",
            maxsplit=1,
        )[1].split("create or replace function", 1)[0]
        self.assertNotIn("update public.reviewer_invitations", lifecycle)

        authorization = self.sql.rsplit(
            "create or replace function public.worker_authorize_reviewer_session",
            maxsplit=1,
        )[1].split("create or replace function", 1)[0]
        self.assertIn("lifecycle.state in ('suspended', 'offboarded')", authorization)
        self.assertIn("reviewer access is disabled", authorization)

    def test_workforce_live_proof_is_rerunnable_and_rollback_only(self) -> None:
        proof = self.workforce_live_proof
        self.assertIn("begin;", proof)
        self.assertTrue(proof.rstrip().endswith("rollback;"))
        self.assertIn("service_resolve_ready_rounds", proof)
        self.assertIn("worker_submit_reviewer_qualification", proof)
        self.assertIn("count(distinct source.submission_id)", proof)
        for receipt in (
            "three_reviewers_human_2_of_3_lineage_passed",
            "three_reviewers_no_majority_hold_passed",
            "qualification_claim_score_activate_passed",
            "cross_attempt_invitation_idempotency_passed",
            "suspended_and_offboarded_session_denial_passed",
        ):
            self.assertIn(receipt, proof)

    def test_ops_metrics_and_work_time_use_authenticated_server_data(self) -> None:
        metrics = self.sql.rsplit(
            "create or replace function public.ops_workforce_metrics",
            maxsplit=1,
        )[1].split("create or replace function", 1)[0]
        self.assertIn("if not public.actor_is_ops(null)", metrics)
        self.assertIn("public.review_assignments", metrics)
        self.assertIn("public.review_submissions", metrics)

        touch = self.sql.rsplit(
            "create or replace function public.worker_touch_work_session",
            maxsplit=1,
        )[1].split("create or replace function", 1)[0]
        self.assertIn("clock_timestamp() - session_row.last_seen_at", touch)
        self.assertIn("p_active_seconds_delta > 0", touch)
        self.assertNotIn(
            "least(coalesce(p_active_seconds_delta",
            touch,
        )

        coverage = self.sql.rsplit(
            "create or replace function public.save_worker_coverage",
            maxsplit=1,
        )[1].split("create or replace function", 1)[0]
        self.assertIn("from public.review_coverage", coverage)
        self.assertIn("for update", coverage)
        self.assertIn("coalesce(coverage_row.ranges, '[]'::jsonb)", coverage)
        self.assertIn("merged_ranges", coverage)

    def test_ops_command_center_preserves_truth_and_ai_boundaries(self) -> None:
        projection = self.sql.split(
            "create or replace function public.ops_command_center",
            maxsplit=1,
        )[1].split("revoke all on function", 1)[0]
        self.assertIn("if not public.actor_is_ops(null)", projection)
        self.assertIn("'queue'", projection)
        self.assertIn("'labels'", projection)
        self.assertIn("'humantotals'", projection)
        self.assertIn("public.consensus_runs", projection)
        self.assertIn("private.human_ai_comparisons", projection)
        self.assertNotIn("update public.review_submissions", projection)
        self.assertNotIn("update public.consensus_runs", projection)
        self.assertNotIn("insert into public.human_finalizations", projection)

        safe_projection = self.sql.rsplit(
            "create or replace function public.ops_command_center",
            maxsplit=1,
        )[1].split("revoke all on function", 1)[0]
        self.assertIn("label ->> 'humanfinalat' is null", safe_projection)
        self.assertIn("'locked_until_human_final'", safe_projection)
        self.assertIn("- 'aieventcount'", safe_projection)
        self.assertIn("- 'comparisonmetrics'", safe_projection)
        self.assertIn("public.ops_command_center_internal_v1()", safe_projection)

        access_gate = self.sql.rsplit(
            "create or replace function public.ops_assert_access",
            maxsplit=1,
        )[1].split("revoke all on function", 1)[0]
        self.assertIn("if not public.actor_is_ops(p_factory_id)", access_gate)
        self.assertIn(
            "grant execute on function public.ops_assert_access(uuid) to authenticated",
            self.sql,
        )
        self.assertIn(
            "grant execute on function public.ops_command_center() to authenticated",
            self.sql,
        )
        self.assertIn(
            "non-ops reviewer reached ops_assert_access",
            self.ops_command_center_live_proof,
        )
        self.assertIn(
            "non-ops reviewer reached ops_command_center",
            self.ops_command_center_live_proof,
        )
        self.assertIn(
            "ops_command_center_internal_v1()",
            self.ops_command_center_live_proof,
        )
        self.assertIn(
            "unfinalized ai output was not fully redacted",
            self.ops_command_center_live_proof,
        )
        self.assertIn("rollback;", self.ops_command_center_live_proof)

    def test_service_preview_is_practice_only_and_service_role_only(self) -> None:
        normalized_sql = re.sub(r"\s+", " ", self.sql)
        preview = self.sql.rsplit(
            "create or replace function public.service_latest_practice_preview",
            maxsplit=1,
        )[1].split("revoke all on function", 1)[0]
        self.assertIn("security invoker", preview)
        self.assertIn("chunk.source_set_role = 'practice'", preview)
        self.assertIn("not chunk.assignment_eligible", preview)
        self.assertIn("chunk.state = 'ready'", preview)
        self.assertIn("rendition.mapping_status = 'verified'", preview)
        self.assertIn("media.status = 'verified'", preview)
        self.assertIn(
            "revoke execute on function public.service_latest_practice_preview() "
            "from anon, authenticated",
            normalized_sql,
        )
        self.assertIn(
            "grant execute on function public.service_latest_practice_preview() "
            "to service_role",
            normalized_sql,
        )

    def test_worker_qualification_is_private_server_scored_and_operational(self) -> None:
        self.assertIn("create table public.reviewer_qualification_attempts", self.sql)
        self.assertIn("reviewer_qualification_attempts_immutable", self.sql)
        self.assertIn("reviewer_qualification_attempts_reject_truncate", self.sql)
        self.assertIn("worker_claim_reviewer_qualification", self.sql)
        self.assertIn("worker_submit_reviewer_qualification", self.sql)
        submit = self.sql.rsplit(
            "create or replace function public.worker_submit_reviewer_qualification",
            maxsplit=1,
        )[1].split("create or replace function", 1)[0]
        self.assertIn("private.reference_answers", submit)
        self.assertIn("reference.answer_type = 'qualification'", submit)
        self.assertIn("set state = case when passed then 'active'", submit)
        self.assertNotIn("p_passed", submit)

    def test_resolver_owner_projection_default_matches_insert_guard(self) -> None:
        self.assertIn(
            "alter column publication_status set default 'published'",
            self.sql,
        )
        self.assertIn(
            "owner projection rows must be published at insert",
            self.sql,
        )
        latest_guard = self.sql.rsplit(
            "create or replace function public.guard_chunk_state_transition",
            maxsplit=1,
        )[1].split("create or replace function", 1)[0]
        self.assertIn("old.state = 'assigned'", latest_guard)
        self.assertIn("new.state = 'resolved'", latest_guard)
        self.assertIn("public.human_finalizations", latest_guard)


if __name__ == "__main__":
    unittest.main()
