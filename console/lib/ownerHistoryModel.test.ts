import { describe, expect, it } from "vitest";
import {
  buildOwnerHistoryRecords,
  filterOwnerHistoryRecords,
  latestOwnerCloseouts,
  ownerHistoryCsv,
  ownerHistoryGrade,
  ownerHistoryOnTime,
  parseOwnerHistoryFilters,
  summarizeOwnerHistory,
  type OwnerCloseoutRow,
} from "@/lib/ownerHistoryModel";

const baseCloseout: OwnerCloseoutRow = {
  id: "closeout-1",
  project_id: "project-1",
  revision: 1,
  planned_units: 100,
  planned_direct_labor_cents: 40_000,
  planned_material_cost_cents: 20_000,
  planned_margin_after_direct_costs_cents: 40_000,
  deadline_at: "2026-05-12T17:00:00Z",
  completed_at: "2026-05-12T16:00:00Z",
  factory_timezone: "UTC",
  verified_good_units: 102,
  material_cost_cents: 21_000,
  direct_labor_cents: 38_000,
  margin_after_direct_costs_cents: 43_000,
  snapshot: {
    project_name: "Alvarez Gates",
    customer_name: "Alvarez Contracting",
    station_names: ["Press Bay North"],
    shift_names: ["Day shift"],
    team_names: ["Ana Torres"],
    actual_direct_labor_minutes: 480,
  },
  created_at: "2026-05-12T16:01:00Z",
};

describe("owner history immutable closeouts", () => {
  it("uses one highest revision per project", () => {
    const rows = [
      baseCloseout,
      {
        ...baseCloseout,
        id: "closeout-2",
        revision: 2,
        verified_good_units: 99,
        created_at: "2026-05-12T17:00:00Z",
      },
      {
        ...baseCloseout,
        id: "other",
        project_id: "project-2",
      },
    ];
    expect(latestOwnerCloseouts(rows).map((row) => row.id)).toEqual([
      "closeout-2",
      "other",
    ]);
  });

  it("requires both completed quantity and deadline for on-time status", () => {
    expect(ownerHistoryOnTime({
      plannedUnits: 100,
      actualUnits: 100,
      deadlineAt: "2026-05-12T17:00:00Z",
      completedAt: "2026-05-12T17:00:00Z",
    })).toBe(true);
    expect(ownerHistoryOnTime({
      plannedUnits: 100,
      actualUnits: 99,
      deadlineAt: "2026-05-12T17:00:00Z",
      completedAt: "2026-05-12T16:00:00Z",
    })).toBe(false);
    expect(ownerHistoryOnTime({
      plannedUnits: 100,
      actualUnits: 100,
      deadlineAt: "2026-05-12T17:00:00Z",
      completedAt: "2026-05-12T17:00:00.001Z",
    })).toBe(false);
  });

  it("matches the specified grade boundaries", () => {
    expect(ownerHistoryGrade({
      onTime: true,
      plannedMarginCents: 100,
      actualMarginCents: 100,
    })).toBe("A");
    expect(ownerHistoryGrade({
      onTime: false,
      plannedMarginCents: 100,
      actualMarginCents: 80,
    })).toBe("B");
    expect(ownerHistoryGrade({
      onTime: false,
      plannedMarginCents: 505,
      actualMarginCents: 404,
    })).toBe("B");
    expect(ownerHistoryGrade({
      onTime: false,
      plannedMarginCents: 100,
      actualMarginCents: 79,
    })).toBe("C");
    expect(ownerHistoryGrade({
      onTime: true,
      plannedMarginCents: 100,
      actualMarginCents: -1,
    })).toBe("C−");
    expect(ownerHistoryGrade({
      onTime: true,
      plannedMarginCents: 100,
      actualMarginCents: 0,
    })).toBe("B");
    expect(ownerHistoryGrade({
      onTime: false,
      plannedMarginCents: 100,
      actualMarginCents: 0,
    })).toBe("C");
    expect(ownerHistoryGrade({
      onTime: false,
      plannedMarginCents: -100,
      actualMarginCents: 0,
    })).toBe("B");
  });

  it("never substitutes plan values for unavailable actual context", () => {
    const [record] = buildOwnerHistoryRecords({
      closeouts: [{ ...baseCloseout, snapshot: {} }],
      audits: [],
      nowIso: "2026-05-15T00:00:00Z",
    });
    expect(record.projectName).toBe("Project name unavailable");
    expect(record.plannedScheduleMinutes).toBeNull();
    expect(record.actualScheduleMinutes).toBeNull();
    expect(record.actualLaborMinutes).toBeNull();
    expect(record.output).toEqual([]);
    expect(record.actualLaborCents).toBe(baseCloseout.direct_labor_cents);
  });

  it("carries the immutable verification-gap warning into history", () => {
    const [record] = buildOwnerHistoryRecords({
      closeouts: [{
        ...baseCloseout,
        snapshot: {
          ...baseCloseout.snapshot,
          verification_has_gap: true,
        },
      }],
      audits: [],
      nowIso: "2026-05-15T00:00:00Z",
    });
    expect(record.verificationHasGap).toBe(true);
  });

  it("retains the closeout timezone and orders duplicate labels by ISO week", () => {
    const [record] = buildOwnerHistoryRecords({
      closeouts: [{
        ...baseCloseout,
        factory_timezone: "Pacific/Auckland",
        snapshot: {
          ...baseCloseout.snapshot,
          weekly_output: [{
            week_start: "2026-05-04",
            label: "May 04",
            planned_units: null,
            actual_units: 2,
          }, {
            week_start: "2025-05-05",
            label: "May 04",
            planned_units: null,
            actual_units: 1,
          }],
        },
      }],
      audits: [],
      nowIso: "2026-05-15T00:00:00Z",
    });

    expect(record.factoryTimezone).toBe("Pacific/Auckland");
    expect(record.output.map((bucket) => bucket.weekStart)).toEqual([
      "2025-05-05",
      "2026-05-04",
    ]);
  });
});

describe("owner history filtering, summary, and export", () => {
  const records = buildOwnerHistoryRecords({
    closeouts: [baseCloseout],
    audits: [{
      id: "audit-1",
      project_id: "project-1",
      actor_type: "user",
      action: "owner.project.closed",
      metadata: {},
      created_at: "2026-05-12T16:01:00Z",
    }],
    nowIso: "2026-05-15T00:00:00Z",
  });

  it("parses only recognized enum filters", () => {
    expect(parseOwnerHistoryFilters({
      range: "999",
      status: "anything",
      customer: "Alvarez Contracting",
    })).toMatchObject({
      range: "90",
      status: "all",
      customer: "Alvarez Contracting",
    });
  });

  it("filters by URL-addressable dimensions and status", () => {
    const filters = parseOwnerHistoryFilters({
      range: "90",
      station: "Press Bay North",
      team: "Ana Torres",
      status: "on_time",
    });
    expect(filterOwnerHistoryRecords(
      records,
      filters,
      "2026-05-15T00:00:00Z",
    )).toHaveLength(1);
    expect(filterOwnerHistoryRecords(
      records,
      { ...filters, station: "Weld Cell" },
      "2026-05-15T00:00:00Z",
    )).toHaveLength(0);
    expect(filterOwnerHistoryRecords(
      [{ ...records[0], actualMarginCents: 0 }],
      { ...filters, status: "positive_margin" },
      "2026-05-15T00:00:00Z",
    )).toHaveLength(0);
  });

  it("weights units per labor hour by total known labor time", () => {
    const summary = summarizeOwnerHistory(records);
    expect(summary.completedProjects).toBe(1);
    expect(summary.onTimePercent).toBe(100);
    expect(summary.unitsPerLaborHour).toBe(12.75);
    expect(summary.laborCoverageCount).toBe(1);
    expect(summary.marginAfterDirectCostsCents).toBe(43_000);
  });

  it("neutralizes spreadsheet formula injection in CSV text fields", () => {
    const csv = ownerHistoryCsv([
      { ...records[0], projectName: "=HYPERLINK(\"bad\")" },
    ], "America/New_York");
    expect(csv).toContain("\"'=HYPERLINK(\"\"bad\"\")\"");
    expect(csv).toContain("\"Actual verified good units\"");
    expect(csv).toContain("\"2026-05-12\"");
  });

  it("exports completion dates in each immutable closeout timezone", () => {
    const csv = ownerHistoryCsv([{
      ...records[0],
      completedAt: "2026-05-12T23:30:00Z",
      factoryTimezone: "Pacific/Auckland",
    }], "America/New_York");
    expect(csv).toContain("\"2026-05-13\"");
  });

  it("keeps negative currency numeric while guarding dangerous text", () => {
    const csv = ownerHistoryCsv([
      { ...records[0], actualMarginCents: -43_500 },
    ], "America/New_York");
    expect(csv).toContain(",-435,\"Yes\"");
    expect(csv).not.toContain("\"'-435\"");
    const guarded = ownerHistoryCsv([
      { ...records[0], projectName: "\n =2+2" },
    ], "America/New_York");
    expect(guarded).toContain("\"'\n =2+2\"");
  });

  it("expires retained evidence against render time, not closeout time", () => {
    const [record] = buildOwnerHistoryRecords({
      closeouts: [{
        ...baseCloseout,
        snapshot: {
          ...baseCloseout.snapshot,
          evidence_clip_count: 2,
          evidence_retention_until: "2026-05-14T00:00:00Z",
        },
      }],
      audits: [],
      nowIso: "2026-05-15T00:00:00Z",
    });
    expect(record.evidence).toMatchObject({
      count: 2,
      state: "expired",
    });
  });

  it("preserves correction before-and-after values in the audit detail", () => {
    const [record] = buildOwnerHistoryRecords({
      closeouts: [baseCloseout],
      audits: [{
        id: "audit-correction",
        project_id: baseCloseout.project_id,
        actor_type: "user",
        action: "owner.project.closeout_corrected",
        metadata: {
          prior_revision: 1,
          new_revision: 2,
          prior_verified_good_units: 99,
          new_verified_good_units: 102,
          prior_material_cost_cents: 20_000,
          new_material_cost_cents: 21_000,
          prior_margin_after_direct_costs_cents: 40_000,
          new_margin_after_direct_costs_cents: 43_000,
        },
        created_at: "2026-05-12T17:00:00Z",
      }],
      nowIso: "2026-05-15T00:00:00Z",
    });
    expect(record.audit[0].detail).toContain("Units 99 → 102");
    expect(record.audit[0].detail).toContain("Materials $200.00 → $210.00");
    expect(record.audit[0].detail).toContain(
      "Margin after direct costs $400.00 → $430.00",
    );
  });
});
