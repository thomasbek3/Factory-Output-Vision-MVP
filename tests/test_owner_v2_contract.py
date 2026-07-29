from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT / "supabase/migrations/20260729070000_owner_v2_core.sql"
)
QUERY_BOUNDS_MIGRATION = (
    ROOT / "supabase/migrations/20260729190000_owner_v2_query_bounds.sql"
)
STATION_BOUNDS_MIGRATION = (
    ROOT / "supabase/migrations/20260729193000_owner_v2_station_query_bounds.sql"
)
LIVE_FIXTURE = ROOT / "supabase/tests/owner_v2_live.sql"
WORKER_LIVE_FIXTURE = ROOT / "supabase/tests/worker_portal_phase1_live.sql"


class OwnerV2ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = (
            MIGRATION.read_text(encoding="utf-8").lower()
            if MIGRATION.exists()
            else ""
        )
        cls.fixture = (
            LIVE_FIXTURE.read_text(encoding="utf-8").lower()
            if LIVE_FIXTURE.exists()
            else ""
        )
        cls.query_bounds_sql = QUERY_BOUNDS_MIGRATION.read_text(
            encoding="utf-8"
        ).lower()
        cls.station_bounds_sql = STATION_BOUNDS_MIGRATION.read_text(
            encoding="utf-8"
        ).lower()
        cls.worker_fixture = WORKER_LIVE_FIXTURE.read_text(encoding="utf-8").lower()

    def test_bounded_owner_read_rpcs_are_self_authorizing(self) -> None:
        rpc_contracts = (
            (
                self.query_bounds_sql,
                "owner_dashboard_truth",
                "production_event.occurred_at < p_now_at",
            ),
            (
                self.query_bounds_sql,
                "owner_history_filter_options",
                "limit 500",
            ),
            (
                self.station_bounds_sql,
                "owner_station_event_buckets",
                "interval '36 hours'",
            ),
        )
        for sql, function_name, explicit_bound in rpc_contracts:
            with self.subTest(function=function_name):
                function = sql.split(
                    f"create or replace function public.{function_name}", 1
                )[1].split("$$;", 1)[0]
                self.assertIn("security definer", function)
                self.assertIn("set search_path = ''", function)
                self.assertIn(
                    "public.owner_has_active_role(p_factory_id, 'owner')",
                    function,
                )
                self.assertIn(explicit_bound, function)
                self.assertRegex(
                    sql,
                    rf"revoke all on function public\.{function_name}"
                    r"[\s\S]+from public, anon",
                )
        self.assertIn("recent_good_units", self.query_bounds_sql)
        self.assertRegex(
            self.station_bounds_sql,
            r"date_bin\(\s*interval '15 minutes',\s*"
            r"production_event\.occurred_at,\s*p_window_start\s*\)",
        )

    def test_owner_tables_are_factory_scoped_and_rls_forced(self) -> None:
        tables = {
            "owner_projects",
            "owner_project_drafts",
            "owner_workers",
            "owner_project_station_assignments",
            "owner_worker_station_intervals",
            "owner_station_downtime_intervals",
            "owner_output_adjustments",
            "owner_project_closeouts",
            "owner_project_audit",
            "owner_project_evidence_attachments",
            "owner_closeout_evidence_attachments",
            "owner_production_events",
            "owner_verification_intervals",
            "owner_chunk_publication_locks",
            "owner_test_teardown_receipts",
        }
        for table in tables:
            with self.subTest(table=table):
                body = self.sql.split(f"create table public.{table}", 1)[1].split(
                    ");", 1
                )[0]
                self.assertIn("factory_id uuid not null", body)
                self.assertIn(
                    f"alter table public.{table} enable row level security",
                    self.sql,
                )
                self.assertIn(
                    f"alter table public.{table} force row level security",
                    self.sql,
                )

    def test_money_is_integer_cents_and_percent_is_basis_points(self) -> None:
        project = self.sql.split("create table public.owner_projects", 1)[1].split(
            ");", 1
        )[0]
        self.assertIn("unit_value_cents bigint", project)
        self.assertIn("unit_material_cost_cents bigint", project)
        self.assertIn("loaded_labor_rate_cents_per_hour bigint", project)
        self.assertIn("planned_direct_labor_cents bigint", project)
        self.assertIn("target_margin_bps integer", project)
        self.assertNotIn("_usd", project)

    def test_owner_raw_human_event_policy_is_removed(self) -> None:
        self.assertIn(
            "drop policy if exists resolved_human_events_read_owner",
            self.sql,
        )
        self.assertNotRegex(
            self.sql,
            r"create policy resolved_human_events_read_owner",
        )

    def test_projection_is_production_only_and_timeline_safe(self) -> None:
        self.assertIn("source_set_role = 'production'", self.sql)
        self.assertIn("gap_map <> '[]'::jsonb", self.sql)
        self.assertIn("timeline_untrusted", self.sql)
        self.assertIn("source_time_ms - chunk_row.source_start_ms", self.sql)
        self.assertIn("interval '1 millisecond'", self.sql)

    def test_publication_and_revocation_triggers_are_exact(self) -> None:
        self.assertRegex(
            self.sql,
            r"after update of state on public\.video_chunks[\s\S]+"
            r"owner_project_published_chunk",
        )
        self.assertIn("old.state = 'resolved' and new.state = 'published'", self.sql)
        self.assertIn(
            "old.state = 'published' and new.state = 'quarantined'",
            self.sql,
        )
        self.assertIn("coverage_revoked", self.sql)
        self.assertIn("owner_chunk_publication_locks", self.sql)

    def test_publication_locked_quarantine_cannot_reprocess(self) -> None:
        guard = self.sql.split(
            "create or replace function public.guard_chunk_state_transition", 1
        )[1].split("$$;", 1)[0]
        self.assertIn("owner_chunk_publication_locks", guard)
        self.assertIn("published owner chunk cannot leave quarantine", guard)

    def test_owner_writes_never_require_service_role(self) -> None:
        self.assertIn("owner_authorize_session", self.sql)
        self.assertIn("owner_start_project", self.sql)
        self.assertIn("auth.uid()", self.sql)
        self.assertRegex(
            self.sql,
            r"grant execute on function public\.owner_start_project[\s\S]+"
            r"to authenticated",
        )
        self.assertRegex(
            self.sql,
            r"grant execute on function public\.owner_upsert_worker[\s\S]+"
            r"to authenticated",
        )
        grants = self.sql.split(
            "grant execute on function public.owner_authorize_session", 1
        )[1]
        self.assertNotIn(
            "grant execute on function public.owner_create_project",
            grants,
        )

    def test_audit_and_projection_tables_are_append_only(self) -> None:
        for table in (
            "owner_project_audit",
            "owner_project_evidence_attachments",
            "owner_closeout_evidence_attachments",
            "owner_project_closeouts",
            "owner_output_adjustments",
            "owner_production_events",
            "owner_verification_intervals",
            "owner_chunk_publication_locks",
            "owner_test_teardown_receipts",
        ):
            with self.subTest(table=table):
                self.assertRegex(
                    self.sql,
                    rf"before update or delete on public\.{table}",
                )
                self.assertRegex(
                    self.sql,
                    rf"before truncate on public\.{table}",
                )

    def test_project_start_is_atomic_and_factory_scoped(self) -> None:
        function = self.sql.split(
            "create or replace function public.owner_start_project", 1
        )[1].split("$$;", 1)[0]
        self.assertIn("insert into public.owner_projects", function)
        self.assertIn(
            "insert into public.owner_project_station_assignments",
            function,
        )
        self.assertIn("insert into public.owner_worker_station_intervals", function)
        self.assertIn("p_station_id", function)
        self.assertIn("p_worker_ids", function)
        worker_interval = self.sql.split(
            "create table public.owner_worker_station_intervals", 1
        )[1].split(");", 1)[0]
        self.assertIn(
            "references public.owner_workers(id, factory_id)",
            worker_interval,
        )
        self.assertIn("owner_shift_calendar_is_valid", function)
        self.assertIn("owner_scheduled_work_milliseconds", function)
        self.assertIn(
            "project window must include scheduled working time",
            function,
        )
        self.assertIn(
            "planned direct labor does not match the scheduled plan",
            function,
        )
        self.assertIn("p_test_correlation_id uuid default null", function)
        self.assertIn("factory.is_test = true", function)

    def test_test_teardown_is_correlated_service_only_and_audited(self) -> None:
        function = self.sql.split(
            "create or replace function public.owner_teardown_test_correlation", 1
        )[1].split("$$;", 1)[0]
        self.assertIn("project.test_correlation_id = p_test_correlation_id", function)
        self.assertIn("project.status in ('open', 'closed')", function)
        self.assertIn("factory.is_test = true", function)
        self.assertIn("owner_test_teardown_receipts", function)
        self.assertIn("owner.test_correlation.torn_down", function)
        self.assertIn("deleted_closeout_evidence_count", function)
        self.assertRegex(
            self.sql,
            r"grant execute on function public\.owner_teardown_test_correlation"
            r"\(uuid, uuid\)\s+to service_role",
        )
        self.assertNotRegex(
            self.sql,
            r"grant execute on function public\.owner_teardown_test_correlation"
            r"\(uuid, uuid\)\s+to authenticated",
        )
        self.assertIn("deleted_audit_count =", self.fixture)

    def test_legacy_project_creator_is_absent(self) -> None:
        self.assertNotIn("function public.owner_create_project", self.sql)
        self.assertNotRegex(
            self.sql,
            r"grant execute on function public\.owner_create_project",
        )

    def test_storage_restriction_preserves_assignment_media_reads(self) -> None:
        policy = self.sql.split(
            "create policy factory_vision_media_authenticated_read", 1
        )[1].split(");", 1)[0]
        self.assertIn("bucket_id = 'review-renditions'", policy)
        self.assertIn("public.can_read_assignment_media(bucket_id, name)", policy)
        self.assertIn("public.can_read_qualification_media(bucket_id, name)", policy)
        self.assertIn("bucket_id = 'evidence-clips'", policy)
        self.assertIn("public.can_read_owner_evidence(bucket_id, name)", policy)
        self.assertIn(
            "leased reviewer could not read assigned rendition",
            self.worker_fixture,
        )
        self.assertIn(
            "qualification reviewer could not read qualification media",
            self.worker_fixture,
        )

    def test_owner_workers_have_an_audited_owner_write_path(self) -> None:
        workers = self.sql.split(
            "create table public.owner_workers", 1
        )[1].split(");", 1)[0]
        self.assertIn("unique (factory_id, employee_code)", workers)
        self.assertNotIn("unique nulls not distinct", workers)
        function = self.sql.split(
            "create or replace function public.owner_upsert_worker", 1
        )[1].split("$$;", 1)[0]
        self.assertIn("primary_role text", workers)
        self.assertIn("owner_has_active_role", function)
        self.assertIn("p_primary_role_supplied", function)
        self.assertIn("owner.worker.created", function)
        self.assertIn("owner.worker.updated", function)

    def test_incomplete_project_drafts_are_durable_and_owner_scoped(self) -> None:
        draft = self.sql.split(
            "create table public.owner_project_drafts", 1
        )[1].split(");", 1)[0]
        self.assertIn("payload jsonb not null", draft)
        self.assertIn("unique (factory_id, created_by)", draft)
        function = self.sql.split(
            "create or replace function public.owner_save_project_draft", 1
        )[1].split("$$;", 1)[0]
        self.assertIn("jsonb_typeof(p_payload) <> 'object'", function)
        self.assertIn("on conflict (factory_id, created_by)", function)

    def test_closeout_carries_durable_plan_and_actual_truth(self) -> None:
        closeout = self.sql.split(
            "create table public.owner_project_closeouts", 1
        )[1].split(");", 1)[0]
        for column in (
            "planned_units integer",
            "planned_direct_labor_cents bigint",
            "planned_material_cost_cents bigint",
            "planned_margin_after_direct_costs_cents bigint",
            "deadline_at timestamptz",
            "completed_at timestamptz",
            "factory_timezone text",
            "verified_good_units integer",
            "direct_labor_cents bigint",
            "material_cost_cents bigint",
            "margin_after_direct_costs_cents bigint",
        ):
            with self.subTest(column=column):
                self.assertIn(column, closeout)
        close_function = self.sql.split(
            "create or replace function public.owner_close_project", 1
        )[1].split("$$;", 1)[0]
        self.assertIn("p_actual_material_cost_cents", close_function)
        self.assertIn("actual_material_cost_source", close_function)
        self.assertIn("owner.project.closed", close_function)
        self.assertIn("status = 'closed'", close_function)
        self.assertIn("distinct on (verification.chunk_id)", close_function)
        for snapshot_field in (
            "project_name",
            "customer_name",
            "station_names",
            "shift_names",
            "team_names",
            "planned_schedule_minutes",
            "actual_schedule_minutes",
            "actual_direct_labor_minutes",
            "weekly_output",
            "evidence_clip_count",
            "evidence_retention_until",
        ):
            with self.subTest(snapshot_field=snapshot_field):
                self.assertIn(f"'{snapshot_field}'", close_function)
        self.assertNotIn("'evidence_clip_count', 0", close_function)
        self.assertIn(
            "insert into public.owner_closeout_evidence_attachments",
            close_function,
        )
        correction_function = self.sql.split(
            "create or replace function public.owner_correct_closeout", 1
        )[1].split("$$;", 1)[0]
        self.assertIn("prior_closeout.revision + 1", correction_function)
        self.assertIn("owner.project.closeout_corrected", correction_function)
        self.assertIn("insert into public.owner_output_adjustments", correction_function)
        self.assertIn("supersedes_closeout_id", correction_function)
        self.assertIn(
            "from public.owner_closeout_evidence_attachments",
            correction_function,
        )

    def test_owner_evidence_is_closeout_scoped_and_signed_without_service_role(self) -> None:
        history = self.sql.split(
            "create or replace function public.owner_history_evidence", 1
        )[1].split("$$;", 1)[0]
        self.assertIn("owner_has_active_role", history)
        self.assertIn("attachment.closeout_id = p_closeout_id", history)
        policy = self.sql.split(
            "create policy owner_read_retained_evidence", 1
        )[1].split(");", 1)[0]
        self.assertIn("bucket_id = 'evidence-clips'", policy)
        self.assertIn("can_read_owner_evidence", policy)
        self.assertRegex(
            self.sql,
            r"grant execute on function public\.owner_history_evidence"
            r"\(uuid, uuid\)\s+to authenticated",
        )
        self.assertRegex(
            self.sql,
            r"grant execute on function public\.service_attach_owner_project_evidence"
            r"\([\s\S]+?\)\s+to service_role",
        )

    def test_interval_overlap_constraints_cover_station_and_worker(self) -> None:
        self.assertRegex(
            self.sql,
            r"exclude using gist[\s\S]+station_id with =[\s\S]+tstzrange",
        )
        self.assertRegex(
            self.sql,
            r"exclude using gist[\s\S]+worker_id with =[\s\S]+tstzrange",
        )

    def test_publication_cron_is_independent(self) -> None:
        self.assertIn("factoryvision-owner-publication", self.sql)
        self.assertIn("select public.service_publish_resolved_chunks();", self.sql)
        self.assertNotIn(
            "create or replace function public.service_maintain_review_queue",
            self.sql,
        )

    def test_publication_trigger_checks_cardinality_and_event_bounds(self) -> None:
        trigger = self.sql.split(
            "create or replace function public.owner_project_published_chunk", 1
        )[1].split("$$;", 1)[0]
        self.assertIn("resolved_total", trigger)
        self.assertIn("event_count <> expected_count", trigger)
        self.assertIn("source_time_ms < chunk_row.source_start_ms", trigger)
        self.assertIn("source_time_ms > chunk_row.source_end_ms", trigger)

    def test_assignment_guard_handles_delete_explicitly(self) -> None:
        guard = self.sql.split(
            "create or replace function public.require_open_owner_project", 1
        )[1].split("$$;", 1)[0]
        self.assertIn("if tg_op = 'delete'", guard)

    def test_live_fixture_has_positive_and_negative_identities(self) -> None:
        self.assertIn("entitled owner baseline", self.fixture)
        self.assertIn("cross-tenant owner denied", self.fixture)
        self.assertIn("disabled owner denied", self.fixture)
        self.assertIn("reviewer remains authorized only for reviewer work", self.fixture)
        self.assertIn(
            "ops authorization remains independent from owner authorization",
            self.fixture,
        )
        self.assertIn("owner reached reviewer authorization", self.fixture)
        self.assertIn("owner reached ops authorization", self.fixture)
        self.assertRegex(
            self.worker_fixture,
            r"set state = 'published',\s+published_at = now\(\)",
        )
        self.assertIn("rollback;", self.fixture)
        self.assertIn("multiple code-less workers were not persisted", self.fixture)
        self.assertIn("multi-day actual labor was not shift-clamped", self.fixture)
        self.assertIn("future project completion was accepted", self.fixture)
        self.assertIn("overlapping worker interval was accepted", self.fixture)
        self.assertIn(
            "closeout correction did not append exact revision 2",
            self.fixture,
        )
        self.assertIn(
            "untrusted timeline projected owner events",
            self.worker_fixture,
        )
        self.assertIn(
            "coverage revocation did not append a superseding revision",
            self.worker_fixture,
        )
        self.assertIn(
            "publication-locked chunk reprocessed after quarantine",
            self.worker_fixture,
        )


if __name__ == "__main__":
    unittest.main()
