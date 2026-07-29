import { describe, expect, it } from "vitest";
import { ownerDashboardFromDurableProjects } from "@/lib/ownerDashboardLive";

const factoryId = "10000000-0000-0000-0000-000000000001";
const projectId = "40000000-0000-0000-0000-000000000001";
const stationId = "20000000-0000-0000-0000-000000000001";

function scheduledCoverageDashboard(input: {
  startAt: string;
  deadline: string;
  nowIso: string;
  shifts: { weekday: number; start: string; end: string }[];
  coverage: { start: string; end: string }[];
  downtime?: { start: string; end: string }[];
  adjustments?: {
    stationId: string | null;
    deltaGoodUnits: number;
    occurredAt: string;
  }[];
}) {
  return ownerDashboardFromDurableProjects({
    factoryId,
    timezone: "UTC",
    nowIso: input.nowIso,
    projects: [{
      id: projectId,
      name: "Scheduled run",
      client: "Test customer",
      target_units: 8,
      start_at: input.startAt,
      deadline: input.deadline,
      status: "open",
      shift_calendar: {
        timezone: "UTC",
        shifts: input.shifts,
      },
      unit_value_cents: 10_000,
      unit_material_cost_cents: 2_000,
    }],
    stations: [],
    truth: {
      assignments: [{
        project_id: projectId,
        station_id: stationId,
        effective_start: input.startAt,
        effective_end: null,
      }],
      events: [],
      verifications: input.coverage.map((interval, index) => ({
        station_id: stationId,
        chunk_id: `50000000-0000-0000-0000-${String(index + 1).padStart(12, "0")}`,
        revision: 1,
        source_start_at: interval.start,
        source_end_at: interval.end,
        status: "verified",
      })),
      workerIntervals: [],
      downtime: (input.downtime ?? []).map((interval) => ({
        project_id: projectId,
        station_id: stationId,
        effective_start: interval.start,
        effective_end: interval.end,
      })),
      adjustments: (input.adjustments ?? []).map((adjustment) => ({
        project_id: projectId,
        station_id: adjustment.stationId,
        delta_good_units: adjustment.deltaGoodUnits,
        occurred_at: adjustment.occurredAt,
      })),
    },
  });
}

describe("ownerDashboardFromDurableProjects", () => {
  it("does not invent live production or economics while verification is unavailable", () => {
    const dashboard = ownerDashboardFromDurableProjects({
      factoryId: "10000000-0000-0000-0000-000000000001",
      timezone: "America/New_York",
      nowIso: "2026-07-29T12:00:00Z",
      projects: [
        {
          id: "40000000-0000-0000-0000-000000000001",
          name: "Gate run",
          client: "Test customer",
          target_units: 400,
          deadline: "2026-08-01T21:00:00Z",
          status: "open",
        },
      ],
      stations: [
        {
          id: "20000000-0000-0000-0000-000000000001",
          alias: "Press Bay",
          status: "active",
        },
      ],
    });

    expect(dashboard.projects[0]).toMatchObject({
      status: "DATA_DELAY",
      verifiedGoodUnits: null,
      projectedMarginBps: null,
      projectedMarginStatus: "unavailable",
      chart: null,
      verifiedThroughLabel: "Not yet available",
      deadlineLabel: "Sat, Aug 1",
    });
    expect(dashboard.stations[0]).toMatchObject({
      status: "DATA_DELAY",
      unitsPerHour: null,
      outputPerLaborHour: null,
      projectName: null,
      projectAssignmentKnown: false,
    });
    expect(dashboard.attention[0]?.meta).toBe("No estimate substituted");
    expect(dashboard.exceptionMonitoringAvailable).toBe(false);
  });

  it("keeps date-only deadlines on the factory-local calendar date", () => {
    const dashboard = ownerDashboardFromDurableProjects({
      factoryId: "10000000-0000-0000-0000-000000000001",
      timezone: "America/Los_Angeles",
      nowIso: "2026-07-29T12:00:00Z",
      projects: [
        {
          id: "40000000-0000-0000-0000-000000000001",
          name: "Gate run",
          client: "Test customer",
          target_units: 400,
          deadline: "2026-08-01",
        },
      ],
      stations: [],
    });
    expect(dashboard.projects[0]?.deadlineLabel).toBe("Sat, Aug 1");
  });

  it("turns malformed deadlines and timezones into explicit unavailable values", () => {
    const dashboard = ownerDashboardFromDurableProjects({
      factoryId: "10000000-0000-0000-0000-000000000001",
      timezone: "not/a-zone",
      nowIso: "2026-07-29T12:00:00Z",
      projects: [
        {
          id: "40000000-0000-0000-0000-000000000001",
          name: "Gate run",
          client: "Test customer",
          target_units: 400,
          deadline: "not-a-date",
        },
      ],
      stations: [],
    });
    expect(dashboard.timezone).toBe("UTC");
    expect(dashboard.projects[0]?.deadlineLabel).toBe("Deadline unavailable");
  });

  it("projects owner-safe verified pace, labor, and margin when coverage is contiguous", () => {
    const project = {
      id: "40000000-0000-0000-0000-000000000001",
      name: "Gate run",
      client: "Test customer",
      target_units: 8,
      start_at: "2026-07-29T08:00:00Z",
      deadline: "2026-07-29T12:00:00Z",
      status: "open",
      shift_calendar: {
        timezone: "UTC",
        shifts: [{ weekday: 3, start: "08:00", end: "12:00" }],
      },
      unit_value_cents: 10_000,
      unit_material_cost_cents: 2_000,
      loaded_labor_rate_cents_per_hour: 2_000,
      target_margin_bps: 6_000,
    };
    const dashboard = ownerDashboardFromDurableProjects({
      factoryId: "10000000-0000-0000-0000-000000000001",
      timezone: "UTC",
      nowIso: "2026-07-29T10:00:00Z",
      projects: [project],
      stations: [{
        id: "20000000-0000-0000-0000-000000000001",
        alias: "Press Bay",
        status: "active",
      }],
      verificationLagThresholdMinutes: 30,
      truth: {
        assignments: [{
          project_id: project.id,
          station_id: "20000000-0000-0000-0000-000000000001",
          effective_start: project.start_at,
          effective_end: null,
        }],
        events: [
          "2026-07-29T08:30:00Z",
          "2026-07-29T09:00:00Z",
          "2026-07-29T09:30:00Z",
          "2026-07-29T09:45:00Z",
        ].map((occurred_at) => ({
          station_id: "20000000-0000-0000-0000-000000000001",
          chunk_id: "50000000-0000-0000-0000-000000000001",
          occurred_at,
        })),
        verifications: [{
          station_id: "20000000-0000-0000-0000-000000000001",
          chunk_id: "50000000-0000-0000-0000-000000000001",
          revision: 1,
          source_start_at: project.start_at,
          source_end_at: "2026-07-29T10:00:00Z",
          status: "verified",
        }],
        workerIntervals: [{
          project_id: project.id,
          station_id: "20000000-0000-0000-0000-000000000001",
          effective_start: project.start_at,
          effective_end: null,
          loaded_labor_rate_cents_per_hour: 2_000,
        }],
        downtime: [],
        adjustments: [],
      },
    });

    expect(dashboard.projects[0]).toMatchObject({
      status: "ON_TRACK",
      verifiedGoodUnits: 4,
      projectedMarginBps: 7_000,
      projectedMarginStatus: "healthy",
      verifiedThroughLabel: "10:00 AM",
    });
    expect(dashboard.projects[0]?.chart).toMatchObject({
      actual: [0, 2, 4],
      required: [0, 2, 4, 6, 8],
      requiredToRecover: [],
      nowIndex: 2,
    });
    expect(dashboard.stations[0]).toMatchObject({
      projectName: "Gate run",
      projectProgress: "4 / 8 units",
      projectAssignmentKnown: true,
      status: "ON_TRACK",
      unitsPerHour: 3,
      outputPerLaborHour: 3,
    });
    expect(dashboard.exceptionMonitoringAvailable).toBe(true);
  });

  it("consumes bounded production buckets without expanding per-unit events", () => {
    const dashboard = ownerDashboardFromDurableProjects({
      factoryId,
      timezone: "UTC",
      nowIso: "2026-07-29T10:00:00Z",
      projects: [{
        id: projectId,
        name: "High-volume run",
        client: "Test customer",
        target_units: 240_000,
        start_at: "2026-07-29T08:00:00Z",
        deadline: "2026-07-29T12:00:00Z",
        shift_calendar: {
          timezone: "UTC",
          shifts: [{ weekday: 3, start: "08:00", end: "12:00" }],
        },
        unit_value_cents: 100,
        unit_material_cost_cents: 20,
        loaded_labor_rate_cents_per_hour: 2_000,
      }],
      stations: [],
      truth: {
        assignments: [{
          project_id: projectId,
          station_id: stationId,
          effective_start: "2026-07-29T08:00:00Z",
          effective_end: null,
        }],
        events: [{
          project_id: projectId,
          station_id: stationId,
          occurred_at: "2026-07-29T08:00:00Z",
          good_units: 120_000,
          verified: true,
        }],
        verifications: [{
          station_id: stationId,
          chunk_id: "50000000-0000-0000-0000-000000000001",
          revision: 1,
          source_start_at: "2026-07-29T08:00:00Z",
          source_end_at: "2026-07-29T10:00:00Z",
          status: "verified",
        }],
        workerIntervals: [{
          project_id: projectId,
          station_id: stationId,
          effective_start: "2026-07-29T08:00:00Z",
          effective_end: null,
          loaded_labor_rate_cents_per_hour: 2_000,
        }],
        downtime: [],
        adjustments: [],
      },
    });

    expect(dashboard.projects[0]).toMatchObject({
      verifiedGoodUnits: 120_000,
      projectedMarginStatus: "healthy",
    });
  });

  it("keeps margin and output per labor hour unavailable without a labor rate", () => {
    const dashboard = ownerDashboardFromDurableProjects({
      factoryId,
      timezone: "UTC",
      nowIso: "2026-07-29T10:00:00Z",
      projects: [{
        id: projectId,
        name: "Rate-free run",
        client: "Test customer",
        target_units: 8,
        start_at: "2026-07-29T08:00:00Z",
        deadline: "2026-07-29T12:00:00Z",
        shift_calendar: {
          timezone: "UTC",
          shifts: [{ weekday: 3, start: "08:00", end: "12:00" }],
        },
        unit_value_cents: 10_000,
        unit_material_cost_cents: 2_000,
        loaded_labor_rate_cents_per_hour: 0,
      }],
      stations: [{ id: stationId, alias: "Press Bay", status: "active" }],
      truth: {
        assignments: [{
          project_id: projectId,
          station_id: stationId,
          effective_start: "2026-07-29T08:00:00Z",
          effective_end: null,
        }],
        events: [{
          project_id: projectId,
          station_id: stationId,
          occurred_at: "2026-07-29T08:00:00Z",
          good_units: 4,
          recent_good_units: 4,
          verified: true,
        }],
        verifications: [{
          station_id: stationId,
          chunk_id: "50000000-0000-0000-0000-000000000001",
          revision: 1,
          source_start_at: "2026-07-29T08:00:00Z",
          source_end_at: "2026-07-29T10:00:00Z",
          status: "verified",
        }],
        workerIntervals: [{
          project_id: projectId,
          station_id: stationId,
          effective_start: "2026-07-29T08:00:00Z",
          effective_end: null,
          loaded_labor_rate_cents_per_hour: 0,
        }],
        downtime: [],
        adjustments: [],
      },
    });

    expect(dashboard.projects[0]).toMatchObject({
      projectedMarginBps: null,
      projectedMarginStatus: "unavailable",
    });
    expect(dashboard.stations[0]?.outputPerLaborHour).toBeNull();
  });

  it("bills live labor only inside scheduled shifts across nights and days", () => {
    const coverage = [
      {
        chunk_id: "50000000-0000-0000-0000-000000000001",
        source_start_at: "2026-07-27T08:00:00Z",
        source_end_at: "2026-07-27T12:00:00Z",
      },
      {
        chunk_id: "50000000-0000-0000-0000-000000000002",
        source_start_at: "2026-07-28T08:00:00Z",
        source_end_at: "2026-07-28T12:00:00Z",
      },
      {
        chunk_id: "50000000-0000-0000-0000-000000000003",
        source_start_at: "2026-07-29T08:00:00Z",
        source_end_at: "2026-07-29T10:00:00Z",
      },
    ];
    const eventTimes = [
      "2026-07-27T08:30:00Z",
      "2026-07-27T09:30:00Z",
      "2026-07-27T10:30:00Z",
      "2026-07-27T11:30:00Z",
      "2026-07-28T08:30:00Z",
      "2026-07-28T09:30:00Z",
      "2026-07-28T10:30:00Z",
      "2026-07-28T11:30:00Z",
      "2026-07-29T08:30:00Z",
      "2026-07-29T09:30:00Z",
    ];
    const dashboard = ownerDashboardFromDurableProjects({
      factoryId,
      timezone: "UTC",
      nowIso: "2026-07-29T10:00:00Z",
      projects: [{
        id: projectId,
        name: "Multi-day run",
        client: "Test customer",
        target_units: 20,
        start_at: "2026-07-27T08:00:00Z",
        deadline: "2026-07-31T12:00:00Z",
        status: "open",
        shift_calendar: {
          timezone: "UTC",
          shifts: [1, 2, 3, 4, 5].map((weekday) => ({
            weekday,
            start: "08:00",
            end: "12:00",
          })),
        },
        unit_value_cents: 10_000,
        unit_material_cost_cents: 2_000,
        target_margin_bps: 4_000,
      }],
      stations: [],
      truth: {
        assignments: [{
          project_id: projectId,
          station_id: stationId,
          effective_start: "2026-07-27T08:00:00Z",
          effective_end: null,
        }],
        events: eventTimes.map((occurred_at, index) => ({
          station_id: stationId,
          chunk_id:
            index < 4
              ? coverage[0].chunk_id
              : index < 8
                ? coverage[1].chunk_id
                : coverage[2].chunk_id,
          occurred_at,
        })),
        verifications: coverage.map((row) => ({
          station_id: stationId,
          revision: 1,
          status: "verified",
          ...row,
        })),
        workerIntervals: [{
          project_id: projectId,
          station_id: stationId,
          effective_start: "2026-07-27T08:00:00Z",
          effective_end: null,
          loaded_labor_rate_cents_per_hour: 5_000,
        }],
        downtime: [],
        adjustments: [],
      },
    });

    expect(dashboard.projects[0]).toMatchObject({
      status: "ON_TRACK",
      verifiedGoodUnits: 10,
      projectedMarginBps: 3_000,
      projectedMarginStatus: "at_risk",
      verifiedThroughLabel: "10:00 AM",
    });
  });

  it("keeps pace and economics unavailable across a verification gap", () => {
    const dashboard = ownerDashboardFromDurableProjects({
      factoryId: "10000000-0000-0000-0000-000000000001",
      timezone: "UTC",
      nowIso: "2026-07-29T10:00:00Z",
      projects: [{
        id: "40000000-0000-0000-0000-000000000001",
        name: "Gap run",
        client: "Test customer",
        target_units: 8,
        start_at: "2026-07-29T08:00:00Z",
        deadline: "2026-07-29T12:00:00Z",
        shift_calendar: {
          timezone: "UTC",
          shifts: [{ weekday: 3, start: "08:00", end: "12:00" }],
        },
        unit_value_cents: 10_000,
        unit_material_cost_cents: 2_000,
      }],
      stations: [],
      truth: {
        assignments: [{
          project_id: "40000000-0000-0000-0000-000000000001",
          station_id: "20000000-0000-0000-0000-000000000001",
          effective_start: "2026-07-29T08:00:00Z",
          effective_end: null,
        }],
        events: [],
        verifications: [{
          station_id: "20000000-0000-0000-0000-000000000001",
          chunk_id: "50000000-0000-0000-0000-000000000001",
          revision: 1,
          source_start_at: "2026-07-29T08:15:00Z",
          source_end_at: "2026-07-29T10:00:00Z",
          status: "verified",
        }],
        workerIntervals: [],
        downtime: [],
        adjustments: [],
      },
    });
    expect(dashboard.projects[0]).toMatchObject({
      status: "DATA_DELAY",
      verifiedGoodUnits: null,
      projectedMarginBps: null,
    });
  });

  it("does not treat an overnight off-shift period as missing footage", () => {
    const dashboard = scheduledCoverageDashboard({
      startAt: "2026-07-29T08:00:00Z",
      deadline: "2026-07-30T12:00:00Z",
      nowIso: "2026-07-30T10:00:00Z",
      shifts: [
        { weekday: 3, start: "08:00", end: "12:00" },
        { weekday: 4, start: "08:00", end: "12:00" },
      ],
      coverage: [
        { start: "2026-07-29T08:00:00Z", end: "2026-07-29T12:00:00Z" },
        { start: "2026-07-30T08:00:00Z", end: "2026-07-30T10:00:00Z" },
      ],
    });
    expect(dashboard.projects[0]?.status).not.toBe("DATA_DELAY");
    expect(dashboard.projects[0]?.verifiedThroughLabel).toBe("10:00 AM");
  });

  it("does not treat a weekend as missing footage", () => {
    const dashboard = scheduledCoverageDashboard({
      startAt: "2026-07-31T08:00:00Z",
      deadline: "2026-08-03T12:00:00Z",
      nowIso: "2026-08-03T10:00:00Z",
      shifts: [
        { weekday: 5, start: "08:00", end: "12:00" },
        { weekday: 1, start: "08:00", end: "12:00" },
      ],
      coverage: [
        { start: "2026-07-31T08:00:00Z", end: "2026-07-31T12:00:00Z" },
        { start: "2026-08-03T08:00:00Z", end: "2026-08-03T10:00:00Z" },
      ],
    });
    expect(dashboard.projects[0]?.status).not.toBe("DATA_DELAY");
  });

  it("does not require footage during recorded downtime", () => {
    const dashboard = scheduledCoverageDashboard({
      startAt: "2026-07-29T08:00:00Z",
      deadline: "2026-07-29T12:00:00Z",
      nowIso: "2026-07-29T12:00:00Z",
      shifts: [{ weekday: 3, start: "08:00", end: "12:00" }],
      coverage: [
        { start: "2026-07-29T08:00:00Z", end: "2026-07-29T09:00:00Z" },
        { start: "2026-07-29T10:00:00Z", end: "2026-07-29T12:00:00Z" },
      ],
      downtime: [{
        start: "2026-07-29T09:00:00Z",
        end: "2026-07-29T10:00:00Z",
      }],
    });
    expect(dashboard.projects[0]?.status).not.toBe("DATA_DELAY");
  });

  it("applies project-level adjustments under the same live frontier rule", () => {
    const dashboard = scheduledCoverageDashboard({
      startAt: "2026-07-29T08:00:00Z",
      deadline: "2026-07-29T12:00:00Z",
      nowIso: "2026-07-29T10:00:00Z",
      shifts: [{ weekday: 3, start: "08:00", end: "12:00" }],
      coverage: [{
        start: "2026-07-29T08:00:00Z",
        end: "2026-07-29T10:00:00Z",
      }],
      adjustments: [{
        stationId: null,
        deltaGoodUnits: 1,
        occurredAt: "2026-07-29T09:00:00Z",
      }, {
        stationId: null,
        deltaGoodUnits: 7,
        occurredAt: "2026-07-29T10:30:00Z",
      }],
    });

    expect(dashboard.projects[0]?.verifiedGoodUnits).toBe(1);
  });

  it("still blocks on a gap inside scheduled work", () => {
    const dashboard = scheduledCoverageDashboard({
      startAt: "2026-07-29T08:00:00Z",
      deadline: "2026-07-29T12:00:00Z",
      nowIso: "2026-07-29T12:00:00Z",
      shifts: [{ weekday: 3, start: "08:00", end: "12:00" }],
      coverage: [
        { start: "2026-07-29T08:00:00Z", end: "2026-07-29T09:00:00Z" },
        { start: "2026-07-29T09:30:00Z", end: "2026-07-29T12:00:00Z" },
      ],
    });
    expect(dashboard.projects[0]?.status).toBe("DATA_DELAY");
    expect(dashboard.projects[0]?.verifiedThroughLabel).toBe("9:00 AM");
    expect(dashboard.projects[0]?.verificationGap).toEqual({
      startLabel: "9:00 AM",
      verifiedAfterLabel: "12:00 PM",
    });
    expect(dashboard.attention[0]).toMatchObject({
      kind: "verification_gap",
      title: "Verification gap",
    });
  });

  it("never turns a short permanent hole into a normal pace verdict", () => {
    const dashboard = scheduledCoverageDashboard({
      startAt: "2026-07-29T08:00:00Z",
      deadline: "2026-07-29T12:00:00Z",
      nowIso: "2026-07-29T09:15:00Z",
      shifts: [{ weekday: 3, start: "08:00", end: "12:00" }],
      coverage: [
        { start: "2026-07-29T08:00:00Z", end: "2026-07-29T09:00:00Z" },
        { start: "2026-07-29T09:10:00Z", end: "2026-07-29T09:15:00Z" },
      ],
    });
    expect(dashboard.projects[0]).toMatchObject({
      status: "DATA_DELAY",
      projectedMarginBps: null,
      verificationGap: {
        startLabel: "9:00 AM",
        verifiedAfterLabel: "9:15 AM",
      },
    });
    expect(dashboard.attention[0]?.meta).toContain(
      "Later footage is verified through 9:15 AM",
    );
  });

  it("does not let one verified station mask an unverified project station", () => {
    const secondStationId = "20000000-0000-0000-0000-000000000002";
    const dashboard = ownerDashboardFromDurableProjects({
      factoryId,
      timezone: "UTC",
      nowIso: "2026-07-29T10:00:00Z",
      projects: [{
        id: projectId,
        name: "Two-station run",
        client: "Test customer",
        target_units: 8,
        start_at: "2026-07-29T08:00:00Z",
        deadline: "2026-07-29T12:00:00Z",
        shift_calendar: {
          timezone: "UTC",
          shifts: [{ weekday: 3, start: "08:00", end: "12:00" }],
        },
        unit_value_cents: 10_000,
        unit_material_cost_cents: 2_000,
      }],
      stations: [],
      truth: {
        assignments: [stationId, secondStationId].map((assignedStationId) => ({
          project_id: projectId,
          station_id: assignedStationId,
          effective_start: "2026-07-29T08:00:00Z",
          effective_end: null,
        })),
        events: [],
        verifications: [{
          station_id: stationId,
          chunk_id: "50000000-0000-0000-0000-000000000001",
          revision: 1,
          source_start_at: "2026-07-29T08:00:00Z",
          source_end_at: "2026-07-29T10:00:00Z",
          status: "verified",
        }],
        workerIntervals: [],
        downtime: [],
        adjustments: [],
      },
    });

    expect(dashboard.projects[0]).toMatchObject({
      status: "DATA_DELAY",
      projectedMarginBps: null,
      verifiedThroughLabel: "Not yet available",
    });
  });

  it("uses the same verified window for station output and labor", () => {
    const events = Array.from({ length: 30 }, (_, index) => ({
      station_id: stationId,
      chunk_id: "50000000-0000-0000-0000-000000000001",
      occurred_at: new Date(
        Date.parse("2026-07-29T09:00:00Z") + (index + 1) * 50_000,
      ).toISOString(),
    }));
    const dashboard = ownerDashboardFromDurableProjects({
      factoryId,
      timezone: "UTC",
      nowIso: "2026-07-29T10:00:00Z",
      projects: [{
        id: projectId,
        name: "Verified labor run",
        client: "Test customer",
        target_units: 60,
        start_at: "2026-07-29T09:00:00Z",
        deadline: "2026-07-29T10:00:00Z",
        shift_calendar: {
          timezone: "UTC",
          shifts: [{ weekday: 3, start: "09:00", end: "10:00" }],
        },
        unit_value_cents: 10_000,
        unit_material_cost_cents: 2_000,
      }],
      stations: [{ id: stationId, alias: "Press Bay", status: "active" }],
      truth: {
        assignments: [{
          project_id: projectId,
          station_id: stationId,
          effective_start: "2026-07-29T09:00:00Z",
          effective_end: null,
        }],
        events,
        verifications: [{
          station_id: stationId,
          chunk_id: "50000000-0000-0000-0000-000000000001",
          revision: 1,
          source_start_at: "2026-07-29T09:00:00Z",
          source_end_at: "2026-07-29T09:30:00Z",
          status: "verified",
        }],
        workerIntervals: [{
          project_id: projectId,
          station_id: stationId,
          effective_start: "2026-07-29T09:00:00Z",
          effective_end: "2026-07-29T10:00:00Z",
          loaded_labor_rate_cents_per_hour: 2_000,
        }],
        downtime: [],
        adjustments: [],
      },
    });
    expect(dashboard.stations[0]).toMatchObject({
      unitsPerHour: 60,
      outputPerLaborHour: 60,
    });
  });

  it("excludes aggregate buckets outside the verified station window", () => {
    const dashboard = ownerDashboardFromDurableProjects({
      factoryId,
      timezone: "UTC",
      nowIso: "2026-07-29T10:00:00Z",
      projects: [{
        id: projectId,
        name: "Bounded aggregate run",
        client: "Test customer",
        target_units: 60,
        start_at: "2026-07-29T09:00:00Z",
        deadline: "2026-07-29T10:00:00Z",
        shift_calendar: {
          timezone: "UTC",
          shifts: [{ weekday: 3, start: "09:00", end: "10:00" }],
        },
        unit_value_cents: 10_000,
        unit_material_cost_cents: 2_000,
      }],
      stations: [{ id: stationId, alias: "Press Bay", status: "active" }],
      truth: {
        assignments: [{
          project_id: projectId,
          station_id: stationId,
          effective_start: "2026-07-29T09:00:00Z",
          effective_end: null,
        }],
        events: [
          {
            project_id: projectId,
            station_id: stationId,
            occurred_at: "2026-07-29T09:00:00Z",
            good_units: 15,
            recent_good_units: 15,
            verified: true,
          },
          {
            project_id: projectId,
            station_id: stationId,
            occurred_at: "2026-07-29T09:30:00Z",
            good_units: 30,
            recent_good_units: 0,
            verified: true,
          },
        ],
        verifications: [{
          station_id: stationId,
          chunk_id: "50000000-0000-0000-0000-000000000001",
          revision: 1,
          source_start_at: "2026-07-29T09:00:00Z",
          source_end_at: "2026-07-29T09:30:00Z",
          status: "verified",
        }],
        workerIntervals: [{
          project_id: projectId,
          station_id: stationId,
          effective_start: "2026-07-29T09:00:00Z",
          effective_end: "2026-07-29T10:00:00Z",
          loaded_labor_rate_cents_per_hour: 2_000,
        }],
        downtime: [],
        adjustments: [],
      },
    });

    expect(dashboard.projects[0]?.verifiedGoodUnits).toBe(15);
    expect(dashboard.stations[0]).toMatchObject({
      unitsPerHour: 30,
      outputPerLaborHour: 30,
    });
  });

  it("reconciles a non-aligned project start with raw closeout units", () => {
    const rawCloseoutUnits = 12;
    const dashboard = ownerDashboardFromDurableProjects({
      factoryId,
      timezone: "UTC",
      nowIso: "2026-07-29T10:00:00Z",
      projects: [{
        id: projectId,
        name: "Non-aligned run",
        client: "Test customer",
        target_units: 24,
        start_at: "2026-07-29T09:40:00Z",
        deadline: "2026-07-29T10:40:00Z",
        shift_calendar: {
          timezone: "UTC",
          shifts: [{ weekday: 3, start: "09:40", end: "10:40" }],
        },
        unit_value_cents: 10_000,
        unit_material_cost_cents: 2_000,
      }],
      stations: [{ id: stationId, alias: "Press Bay", status: "active" }],
      truth: {
        assignments: [{
          project_id: projectId,
          station_id: stationId,
          effective_start: "2026-07-29T09:40:00Z",
          effective_end: null,
        }],
        events: [{
          project_id: projectId,
          station_id: stationId,
          occurred_at: "2026-07-29T09:30:00Z",
          good_units: rawCloseoutUnits,
          recent_good_units: rawCloseoutUnits,
          verified: true,
        }],
        verifications: [{
          station_id: stationId,
          chunk_id: "50000000-0000-0000-0000-000000000001",
          revision: 1,
          source_start_at: "2026-07-29T09:40:00Z",
          source_end_at: "2026-07-29T10:00:00Z",
          status: "verified",
        }],
        workerIntervals: [{
          project_id: projectId,
          station_id: stationId,
          effective_start: "2026-07-29T09:40:00Z",
          effective_end: null,
          loaded_labor_rate_cents_per_hour: 2_000,
        }],
        downtime: [],
        adjustments: [],
      },
    });

    expect(dashboard.projects[0]?.verifiedGoodUnits).toBe(rawCloseoutUnits);
    expect(dashboard.stations[0]?.unitsPerHour).toBe(36);
  });

  it("states the verified shortfall when an open project misses its deadline", () => {
    const dashboard = ownerDashboardFromDurableProjects({
      factoryId,
      timezone: "UTC",
      nowIso: "2026-07-29T11:00:00Z",
      projects: [{
        id: projectId,
        name: "Overdue run",
        client: "Test customer",
        target_units: 60,
        start_at: "2026-07-29T09:00:00Z",
        deadline: "2026-07-29T10:00:00Z",
        shift_calendar: {
          timezone: "UTC",
          shifts: [{ weekday: 3, start: "09:00", end: "11:00" }],
        },
        unit_value_cents: 10_000,
        unit_material_cost_cents: 2_000,
      }],
      stations: [{ id: stationId, alias: "Press Bay", status: "active" }],
      truth: {
        assignments: [{
          project_id: projectId,
          station_id: stationId,
          effective_start: "2026-07-29T09:00:00Z",
          effective_end: null,
        }],
        events: [{
          project_id: projectId,
          station_id: stationId,
          occurred_at: "2026-07-29T10:30:00Z",
          good_units: 20,
          recent_good_units: 20,
          verified: true,
        }],
        verifications: [{
          station_id: stationId,
          chunk_id: "50000000-0000-0000-0000-000000000001",
          revision: 1,
          source_start_at: "2026-07-29T09:00:00Z",
          source_end_at: "2026-07-29T11:00:00Z",
          status: "verified",
        }],
        workerIntervals: [{
          project_id: projectId,
          station_id: stationId,
          effective_start: "2026-07-29T09:00:00Z",
          effective_end: null,
          loaded_labor_rate_cents_per_hour: 2_000,
        }],
        downtime: [],
        adjustments: [],
      },
    });

    expect(dashboard.projects[0]).toMatchObject({
      status: "BEHIND",
      verifiedGoodUnits: 20,
      recoverySummary: "Deadline missed by 40 units",
    });
    expect(dashboard.attention).toContainEqual(
      expect.objectContaining({
        title: "Project behind pace",
        meta: "Deadline missed by 40 units",
      }),
    );
  });

  it("clips station throughput to the selected project assignment window", () => {
    const assignmentStart = "2026-07-29T09:40:00Z";
    const events = Array.from({ length: 30 }, (_, index) => ({
      station_id: stationId,
      chunk_id: "50000000-0000-0000-0000-000000000001",
      occurred_at: new Date(
        Date.parse(assignmentStart) + (index + 1) * 38_000,
      ).toISOString(),
    }));
    const dashboard = ownerDashboardFromDurableProjects({
      factoryId,
      timezone: "UTC",
      nowIso: "2026-07-29T10:00:00Z",
      projects: [{
        id: projectId,
        name: "Recent assignment",
        client: "Test customer",
        target_units: 30,
        start_at: assignmentStart,
        deadline: "2026-07-29T10:00:00Z",
        shift_calendar: {
          timezone: "UTC",
          shifts: [{ weekday: 3, start: "09:00", end: "10:00" }],
        },
        unit_value_cents: 10_000,
        unit_material_cost_cents: 2_000,
      }],
      stations: [{ id: stationId, alias: "Press Bay", status: "active" }],
      truth: {
        assignments: [{
          project_id: projectId,
          station_id: stationId,
          effective_start: assignmentStart,
          effective_end: null,
        }],
        events,
        verifications: [{
          station_id: stationId,
          chunk_id: "50000000-0000-0000-0000-000000000001",
          revision: 1,
          source_start_at: "2026-07-29T09:00:00Z",
          source_end_at: "2026-07-29T10:00:00Z",
          status: "verified",
        }],
        workerIntervals: [{
          project_id: projectId,
          station_id: stationId,
          effective_start: assignmentStart,
          effective_end: null,
          loaded_labor_rate_cents_per_hour: 2_000,
        }],
        downtime: [],
        adjustments: [],
      },
    });

    expect(dashboard.stations[0]).toMatchObject({
      unitsPerHour: 90,
      outputPerLaborHour: 90,
    });
  });

  it("does not raise a verification exception before the first scheduled shift", () => {
    const dashboard = scheduledCoverageDashboard({
      startAt: "2026-07-31T13:00:00Z",
      deadline: "2026-08-03T12:00:00Z",
      nowIso: "2026-08-01T12:00:00Z",
      shifts: [{ weekday: 1, start: "08:00", end: "12:00" }],
      coverage: [],
    });
    expect(dashboard.projects[0]).toMatchObject({
      status: "ON_TRACK",
      verifiedGoodUnits: 0,
      recoverySummary: "No scheduled production has elapsed",
      verifiedThroughLabel: "No scheduled work yet",
    });
    expect(dashboard.attention).toEqual([]);
  });

  it("places recovery midpoints at half of remaining scheduled work", () => {
    const dashboard = scheduledCoverageDashboard({
      startAt: "2026-07-31T08:00:00Z",
      deadline: "2026-08-03T12:00:00Z",
      nowIso: "2026-07-31T12:00:00Z",
      shifts: [
        { weekday: 5, start: "08:00", end: "12:00" },
        { weekday: 1, start: "08:00", end: "12:00" },
      ],
      coverage: [{
        start: "2026-07-31T08:00:00Z",
        end: "2026-07-31T12:00:00Z",
      }],
    });
    expect(dashboard.projects[0]?.chart?.labels[3]).toContain("Aug 3");
    expect(dashboard.projects[0]?.chart?.labels[3]).toContain("10 AM");
  });
});
