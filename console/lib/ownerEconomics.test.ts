import { describe, expect, it } from "vitest";
import {
  apportionLaborCents,
  derivePlannedLaborCents,
  deriveUnitCents,
  evaluatePace,
  evaluateProjectFeasibility,
  mergeIntervals,
  ownerLaborAccrualEndMs,
  projectDirectCostMargin,
  workedMillisecondsBetween,
} from "@/lib/ownerEconomics";

const weekdayShift = {
  timezone: "America/Los_Angeles",
  shifts: [
    { weekday: 1, start: "09:00", end: "17:30" },
    { weekday: 2, start: "09:00", end: "17:30" },
    { weekday: 3, start: "09:00", end: "17:30" },
    { weekday: 4, start: "09:00", end: "17:30" },
    { weekday: 5, start: "09:00", end: "17:30" },
  ],
} as const;

describe("ownerEconomics", () => {
  it("derives exact cents per unit", () => {
    expect(deriveUnitCents(100_000, 400)).toBe(250);
  });

  it("rounds half-up only at the currency boundary", () => {
    expect(deriveUnitCents(100, 8)).toBe(13);
    expect(deriveUnitCents(99, 8)).toBe(12);
  });

  it("unions overlapping downtime before subtraction", () => {
    expect(
      mergeIntervals([
        { startMs: 0, endMs: 20 },
        { startMs: 10, endMs: 30 },
        { startMs: 35, endMs: 40 },
      ]),
    ).toEqual([
      { startMs: 0, endMs: 30 },
      { startMs: 35, endMs: 40 },
    ]);
  });

  it("does not double-count overlapping shift windows", () => {
    const overlappingCalendar = {
      timezone: "America/Los_Angeles",
      shifts: [
        { weekday: 2, start: "09:00", end: "17:00" },
        { weekday: 2, start: "12:00", end: "18:00" },
      ],
    } as const;
    expect(
      workedMillisecondsBetween(
        "2026-12-15T17:00:00Z",
        "2026-12-16T02:00:00Z",
        overlappingCalendar,
        [],
      ),
    ).toBe(9 * 60 * 60 * 1000);
  });

  it("uses the correct winter offset independent of process timezone", () => {
    const worked = workedMillisecondsBetween(
      "2026-12-15T16:30:00Z",
      "2026-12-16T01:30:00Z",
      weekdayShift,
      [],
    );
    expect(worked).toBe(8.5 * 60 * 60 * 1000);
  });

  it("is identical when the Node process timezone is Asia/Tokyo", () => {
    const originalTimezone = process.env.TZ;
    try {
      process.env.TZ = "UTC";
      const utcResult = workedMillisecondsBetween(
        "2026-12-15T16:30:00Z",
        "2026-12-16T01:30:00Z",
        weekdayShift,
        [],
      );
      process.env.TZ = "Asia/Tokyo";
      const tokyoResult = workedMillisecondsBetween(
        "2026-12-15T16:30:00Z",
        "2026-12-16T01:30:00Z",
        weekdayShift,
        [],
      );
      expect(tokyoResult).toBe(utcResult);
    } finally {
      process.env.TZ = originalTimezone;
    }
  });

  it("handles spring-forward and fall-back shifts in factory-local time", () => {
    const overnight = {
      timezone: "America/Los_Angeles",
      shifts: [{ weekday: 7, start: "00:00", end: "04:00" }],
    } as const;

    expect(
      workedMillisecondsBetween(
        "2026-03-08T08:00:00Z",
        "2026-03-08T11:00:00Z",
        overnight,
        [],
      ),
    ).toBe(3 * 60 * 60 * 1000);
    expect(
      workedMillisecondsBetween(
        "2026-11-01T07:00:00Z",
        "2026-11-01T12:00:00Z",
        overnight,
        [],
      ),
    ).toBe(5 * 60 * 60 * 1000);
  });

  it("pins ambiguous and nonexistent shift boundaries to the later instant", () => {
    const fallBoundary = {
      timezone: "America/Los_Angeles",
      shifts: [{ weekday: 7, start: "01:00", end: "09:00" }],
    } as const;
    expect(
      workedMillisecondsBetween(
        "2026-11-01T07:00:00Z",
        "2026-11-01T18:00:00Z",
        fallBoundary,
        [],
      ),
    ).toBe(8 * 60 * 60 * 1000);

    const springBoundary = {
      timezone: "America/Los_Angeles",
      shifts: [{ weekday: 7, start: "02:00", end: "09:00" }],
    } as const;
    expect(
      workedMillisecondsBetween(
        "2026-03-08T08:00:00Z",
        "2026-03-08T17:00:00Z",
        springBoundary,
        [],
      ),
    ).toBe(6 * 60 * 60 * 1000);

    const fallInterior = {
      timezone: "America/Los_Angeles",
      shifts: [{ weekday: 7, start: "01:30", end: "09:00" }],
    } as const;
    expect(
      workedMillisecondsBetween(
        "2026-11-01T07:00:00Z",
        "2026-11-01T18:00:00Z",
        fallInterior,
        [],
      ),
    ).toBe(7.5 * 60 * 60 * 1000);

    const springInterior = {
      timezone: "America/Los_Angeles",
      shifts: [{ weekday: 7, start: "02:30", end: "09:00" }],
    } as const;
    expect(
      workedMillisecondsBetween(
        "2026-03-08T08:00:00Z",
        "2026-03-08T17:00:00Z",
        springInterior,
        [],
      ),
    ).toBe(5.5 * 60 * 60 * 1000);
  });

  it("apportions fractional labor cents and reconciles to the project total", () => {
    const result = apportionLaborCents([
      {
        stationId: "station-a",
        rateCentsPerHour: 2_357,
        startMs: 0,
        endMs: 1_234_567,
      },
      {
        stationId: "station-b",
        rateCentsPerHour: 2_357,
        startMs: 0,
        endMs: 2_345_678,
      },
      {
        stationId: "station-c",
        rateCentsPerHour: 2_357,
        startMs: 0,
        endMs: 3_456_789,
      },
    ]);

    expect(
      Object.values(result.byStationCents).reduce((sum, cents) => sum + cents, 0),
    ).toBe(result.projectCents);
  });

  it("derives planned labor cents from team size and scheduled work", () => {
    expect(
      derivePlannedLaborCents({
        loadedRateCentsPerHour: 2_250,
        workerCount: 2,
        plannedWorkedMs: 8.5 * 60 * 60 * 1000,
      }),
    ).toBe(38_250);
  });

  it("uses scheduled shift time rather than raw calendar days for feasibility", () => {
    const result = evaluateProjectFeasibility({
      targetUnits: 400,
      startIso: "2026-12-18T21:00:00Z",
      deadlineIso: "2026-12-21T21:00:00Z",
      calendar: weekdayShift,
      baselineUnitsPerDay: 100,
    });
    expect(result.plannedWorkedMs).toBe(8.5 * 60 * 60 * 1000);
    expect(result.requiredUnitsPerDay).toBe(400);
    expect(result.status).toBe("Not feasible");
  });

  it("uses DATA_DELAY instead of a false behind verdict", () => {
    expect(
      evaluatePace({
        targetUnits: 400,
        goodUnits: 90,
        plannedWorkedMs: 8 * 60 * 60 * 1000,
        verifiedWorkedMs: 3 * 60 * 60 * 1000,
        remainingWorkedMs: 5 * 60 * 60 * 1000,
        verificationLagMs: 45 * 60 * 1000,
        verificationLagThresholdMs: 30 * 60 * 1000,
      }).status,
    ).toBe("DATA_DELAY");
  });

  it("has no recovery rate once an open project is overdue", () => {
    const result = evaluatePace({
      targetUnits: 400,
      goodUnits: 300,
      plannedWorkedMs: 8 * 60 * 60 * 1000,
      verifiedWorkedMs: 8 * 60 * 60 * 1000,
      remainingWorkedMs: 0,
      verificationLagMs: 0,
      verificationLagThresholdMs: 30 * 60 * 1000,
    });
    expect(result.status).toBe("BEHIND");
    expect(result.requiredUnitsPerHour).toBeNull();
  });

  it("keeps labor accruing after the deadline until an open project closes", () => {
    expect(
      ownerLaborAccrualEndMs({
        status: "open",
        deadlineMs: 1_000,
        nowMs: 2_500,
        closedAtMs: null,
      }),
    ).toBe(2_500);
    expect(
      ownerLaborAccrualEndMs({
        status: "closed",
        deadlineMs: 1_000,
        nowMs: 2_500,
        closedAtMs: 2_000,
      }),
    ).toBe(2_000);
  });

  it("keeps projected margin unavailable on a cold start", () => {
    expect(
      projectDirectCostMargin({
        targetUnits: 400,
        verifiedGoodUnits: 0,
        unitValueCents: 250,
        unitMaterialCostCents: 75,
        laborBurnedCents: 0,
        verifiedWorkedMs: 0,
        remainingWorkedMs: 8 * 60 * 60 * 1000,
      }),
    ).toEqual({
      projectedUnits: null,
      projectedLaborCents: null,
      projectedMarginCents: null,
    });
  });

  it("projects margin from verified rate without calling it profit", () => {
    expect(
      projectDirectCostMargin({
        targetUnits: 400,
        verifiedGoodUnits: 100,
        unitValueCents: 250,
        unitMaterialCostCents: 75,
        laborBurnedCents: 5_000,
        verifiedWorkedMs: 2 * 60 * 60 * 1000,
        remainingWorkedMs: 6 * 60 * 60 * 1000,
      }),
    ).toEqual({
      projectedUnits: 400,
      projectedLaborCents: 20_000,
      projectedMarginCents: 50_000,
    });
  });
});
