import { describe, expect, it } from "vitest";
import {
  buildOwnerStationData,
  buildOwnerWorkforceData,
} from "@/lib/ownerStationModel";

const base = {
  factoryId: "factory-1",
  timezone: "UTC",
  selectedDate: "2026-05-07",
  station: { id: "station-1", name: "Press Bay", status: "active" },
  stationOptions: [{ id: "station-1", name: "Press Bay" }],
  project: { id: "project-1", name: "Alvarez Gates" },
  projectAssignmentKnown: true,
  windowStartIso: "2026-05-07T06:00:00Z",
  windowEndIso: "2026-05-07T07:00:00Z",
  requiredUnitsPerHour: 20,
  workerRows: [
    { id: "worker-1", display_name: "Ana", status: "active" as const },
    { id: "worker-2", display_name: "Luis", status: "active" as const },
  ],
  downtimeRows: [],
  adjustmentRows: [],
  nowIso: "2026-05-07T07:00:00Z",
};

describe("owner station truth aggregation", () => {
  it("counts only events covered by the latest verified chunk revision", () => {
    const result = buildOwnerStationData({
      ...base,
      verificationRows: [
        {
          id: "v1",
          chunk_id: "chunk-a",
          revision: 1,
          source_start_at: "2026-05-07T06:00:00Z",
          source_end_at: "2026-05-07T06:30:00Z",
          status: "verified",
        },
        {
          id: "v2",
          chunk_id: "chunk-a",
          revision: 2,
          source_start_at: "2026-05-07T06:00:00Z",
          source_end_at: "2026-05-07T06:30:00Z",
          status: "coverage_revoked",
        },
        {
          id: "v3",
          chunk_id: "chunk-b",
          revision: 1,
          source_start_at: "2026-05-07T06:30:00Z",
          source_end_at: "2026-05-07T07:00:00Z",
          status: "verified",
        },
      ],
      eventRows: [
        { id: "e1", chunk_id: "chunk-a", occurred_at: "2026-05-07T06:10:00Z" },
        { id: "e2", chunk_id: "chunk-b", occurred_at: "2026-05-07T06:35:00Z" },
      ],
      workerIntervals: [],
    });
    expect(result.kpis.verifiedGoodUnits.value).toBe(1);
    expect(result.production.map((bucket) => bucket.verifiedGoodUnits)).toEqual([
      null,
      null,
      1,
      0,
    ]);
    expect(result.verificationState).toBe("delayed");
  });

  it("subtracts downtime from the verified production-rate denominator", () => {
    const result = buildOwnerStationData({
      ...base,
      verificationRows: [
        {
          id: "v1",
          chunk_id: "chunk-a",
          revision: 1,
          source_start_at: base.windowStartIso,
          source_end_at: base.windowEndIso,
          status: "verified",
        },
      ],
      eventRows: Array.from({ length: 15 }, (_, index) => ({
        id: `e${index}`,
        chunk_id: "chunk-a",
        occurred_at: `2026-05-07T06:${String(index).padStart(2, "0")}:00Z`,
      })),
      workerIntervals: [],
      downtimeRows: [
        {
          effective_start: "2026-05-07T06:15:00Z",
          effective_end: "2026-05-07T06:30:00Z",
        },
      ],
    });
    expect(result.kpis.unitsPerHour.value).toBe(20);
    expect(result.summary.downtimeMinutes).toBe(15);
    expect(result.production[1].downtimeMinutes).toBe(15);
  });

  it("never grants solo attribution without badge, confirmed coverage, and no overlap", () => {
    const manual = {
      id: "i1",
      worker_id: "worker-1",
      station_id: "station-1",
      project_id: "project-1",
      effective_start: base.windowStartIso,
      effective_end: base.windowEndIso,
      source: "manual" as const,
    };
    const badge = { ...manual, id: "i2", source: "badge" as const };
    const common = {
      ...base,
      verificationRows: [
        {
          id: "v1",
          chunk_id: "chunk-a",
          revision: 1,
          source_start_at: base.windowStartIso,
          source_end_at: base.windowEndIso,
          status: "verified" as const,
        },
      ],
      eventRows: [],
    };
    expect(
      buildOwnerStationData({ ...common, workerIntervals: [manual] }).team[0]
        .attribution,
    ).toBe("team_only");
    expect(
      buildOwnerStationData({ ...common, workerIntervals: [badge] }).team[0]
        .attribution,
    ).toBe("solo_high_confidence");
    expect(
      buildOwnerStationData({
        ...common,
        workerIntervals: [
          badge,
          {
            ...badge,
            id: "i3",
            worker_id: "worker-2",
            source: "badge",
          },
        ],
      }).team[0].attribution,
    ).toBe("team_only");
  });

  it("subtracts verified scrap and rework from each bucket and every rate", () => {
    const events = Array.from({ length: 10 }, (_, index) => ({
      id: `e${index}`,
      chunk_id: "chunk-a",
      occurred_at: `2026-05-07T06:${String(index).padStart(2, "0")}:00Z`,
    }));
    const result = buildOwnerStationData({
      ...base,
      verificationRows: [
        {
          id: "v1",
          chunk_id: "chunk-a",
          revision: 1,
          source_start_at: base.windowStartIso,
          source_end_at: base.windowEndIso,
          status: "verified",
        },
      ],
      eventRows: events,
      workerIntervals: [
        {
          id: "i1",
          worker_id: "worker-1",
          station_id: "station-1",
          project_id: "project-1",
          effective_start: base.windowStartIso,
          effective_end: base.windowEndIso,
          loaded_labor_rate_cents_per_hour: 2_000,
          source: "schedule",
        },
      ],
      adjustmentRows: [
        {
          kind: "scrap",
          delta_good_units: -2,
          occurred_at: "2026-05-07T06:10:00Z",
        },
        {
          kind: "rework",
          delta_good_units: -1,
          occurred_at: "2026-05-07T06:12:00Z",
        },
      ],
    });
    expect(result.production[0].verifiedGoodUnits).toBe(7);
    expect(result.kpis.verifiedGoodUnits.value).toBe(7);
    expect(result.kpis.unitsPerHour.value).toBe(7);
    expect(result.kpis.outputPerLaborHour.value).toBe(7);
    expect(result.summary).toMatchObject({
      scrapUnits: 2,
      reworkUnits: 1,
    });
  });

  it("does not imply labor economics when every loaded labor rate is zero", () => {
    const result = buildOwnerStationData({
      ...base,
      verificationRows: [{
        id: "v1",
        chunk_id: "chunk-a",
        revision: 1,
        source_start_at: base.windowStartIso,
        source_end_at: base.windowEndIso,
        status: "verified",
      }],
      eventRows: [{
        id: "e1",
        chunk_id: "chunk-a",
        occurred_at: "2026-05-07T06:10:00Z",
      }],
      workerIntervals: [{
        id: "i1",
        worker_id: "worker-1",
        station_id: "station-1",
        project_id: "project-1",
        effective_start: base.windowStartIso,
        effective_end: base.windowEndIso,
        loaded_labor_rate_cents_per_hour: 0,
        source: "schedule",
      }],
    });

    expect(result.kpis.laborHours.value).toBe(1);
    expect(result.kpis.outputPerLaborHour.value).toBeNull();
  });

  it("uses the same fully verified buckets for units and rate denominator", () => {
    const result = buildOwnerStationData({
      ...base,
      verificationRows: [{
        id: "v1",
        chunk_id: "chunk-a",
        revision: 1,
        source_start_at: "2026-05-07T06:00:00Z",
        source_end_at: "2026-05-07T06:20:00Z",
        status: "verified",
      }],
      eventRows: Array.from({ length: 15 }, (_, index) => ({
        id: `e${index}`,
        chunk_id: "chunk-a",
        occurred_at: `2026-05-07T06:${String(index).padStart(2, "0")}:00Z`,
      })),
      workerIntervals: [],
    });

    expect(result.production.map((bucket) => bucket.verifiedGoodUnits)).toEqual([
      15,
      null,
      null,
      null,
    ]);
    expect(result.kpis.unitsPerHour.value).toBe(60);
  });

  it("consumes station production buckets without expanding high-volume events", () => {
    const result = buildOwnerStationData({
      ...base,
      verificationRows: [{
        id: "v1",
        chunk_id: "chunk-a",
        revision: 1,
        source_start_at: base.windowStartIso,
        source_end_at: base.windowEndIso,
        status: "verified",
      }],
      eventRows: [{
        occurred_at: "2026-05-07T06:00:00Z",
        good_units: 120_000,
        verified: true,
      }],
      workerIntervals: [],
    });

    expect(result.kpis.verifiedGoodUnits.value).toBe(120_000);
    expect(result.production[0]?.verifiedGoodUnits).toBe(120_000);
  });

  it("keeps the first bucket when a shift starts off the quarter hour", () => {
    const result = buildOwnerStationData({
      ...base,
      windowStartIso: "2026-05-07T06:05:00Z",
      windowEndIso: "2026-05-07T07:05:00Z",
      nowIso: "2026-05-07T07:05:00Z",
      verificationRows: [{
        id: "v1",
        chunk_id: "chunk-a",
        revision: 1,
        source_start_at: "2026-05-07T06:05:00Z",
        source_end_at: "2026-05-07T07:05:00Z",
        status: "verified",
      }],
      eventRows: [{
        occurred_at: "2026-05-07T06:05:00Z",
        good_units: 12,
        verified: true,
      }],
      workerIntervals: [],
    });

    expect(result.production[0]?.verifiedGoodUnits).toBe(12);
    expect(result.kpis.verifiedGoodUnits.value).toBe(12);
    expect(result.kpis.unitsPerHour.value).toBe(12);
  });

  it("stops the verified-through frontier at the first coverage gap", () => {
    const result = buildOwnerStationData({
      ...base,
      verificationRows: [
        {
          id: "v1",
          chunk_id: "chunk-a",
          revision: 1,
          source_start_at: "2026-05-07T06:00:00Z",
          source_end_at: "2026-05-07T06:15:00Z",
          status: "verified",
        },
        {
          id: "v2",
          chunk_id: "chunk-b",
          revision: 1,
          source_start_at: "2026-05-07T06:30:00Z",
          source_end_at: "2026-05-07T07:00:00Z",
          status: "verified",
        },
      ],
      eventRows: [],
      workerIntervals: [],
    });
    expect(result.verifiedThroughIso).toBe("2026-05-07T06:15:00.000Z");
    expect(result.nowIso).toBe("2026-05-07T07:00:00.000Z");
    expect(result.verificationState).toBe("delayed");
  });

  it("keeps planned pace separate from unavailable verified output", () => {
    const result = buildOwnerStationData({
      ...base,
      verificationRows: [],
      eventRows: [],
      workerIntervals: [],
    });
    expect(result.kpis.verifiedGoodUnits.value).toBeNull();
    expect(result.production[0]).toMatchObject({
      verifiedGoodUnits: null,
      requiredUnits: 5,
    });
  });
});

describe("owner workforce mapping", () => {
  it("does not create rankings or individual output totals", () => {
    const result = buildOwnerWorkforceData({
      factoryId: "factory-1",
      workers: base.workerRows,
      intervals: [],
      stationNames: {},
      projectNames: {},
      windowStartIso: base.windowStartIso,
      windowEndIso: base.windowEndIso,
      timezone: "UTC",
    });
    expect(result.activeCount).toBe(2);
    expect(result.assignedCount).toBe(0);
    expect(result.members[0]).not.toHaveProperty("verifiedGoodUnits");
    expect(result.members[0].attribution).toBe("unassigned");
  });
});
