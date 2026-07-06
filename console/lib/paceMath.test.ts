import { describe, expect, it } from "vitest";
import {
  evaluateJobPace,
  jobVerdict,
  moneyStripTotal,
  workMinutesBetween,
} from "@/lib/paceMath";
import type { JobSeed, LaborConfigSeed } from "@/lib/demoData";

const labor: LaborConfigSeed = {
  work_hours: {
    monday: { start: "07:00", end: "17:30" },
    tuesday: { start: "07:00", end: "17:30" },
    wednesday: { start: "07:00", end: "17:30" },
    thursday: { start: "07:00", end: "17:30" },
    friday: { start: "07:00", end: "17:30" },
  },
  hourly_rate_usd: 20,
  workers_per_station: 1,
};

const fixtureJob: JobSeed = {
  id: "job-fixture",
  client: "Fixture",
  title: "100 units",
  units_required: 100,
  quote_usd: 2000,
  cogs_usd: 500,
  labor_budget_usd: 700,
  created_at: "2026-06-26T07:00:00-07:00",
  deadline: "2026-06-26T17:00:00-07:00",
  station_ids: ["pallet-a"],
  status: "active",
};

describe("paceMath", () => {
  it("calculates mid-day pace from the work-hours calendar", () => {
    const snapshot = evaluateJobPace(
      fixtureJob,
      40,
      new Date("2026-06-26T12:00:00-07:00"),
      labor,
    );

    expect(snapshot.elapsed_work_ratio).toBeCloseTo(0.5, 3);
    expect(snapshot.expected_units_by_now).toBeCloseTo(50, 3);
    expect(snapshot.pace_delta).toBeCloseTo(-10, 3);
    expect(snapshot.labor_burned_usd).toBeCloseTo(100, 3);
    expect(snapshot.projected_labor_usd).toBeCloseTo(200, 3);
    expect(snapshot.projected_margin).toBeCloseTo(1300, 3);
  });

  it("uses exact 0.9 and 0.5 planned-margin verdict boundaries", () => {
    expect(jobVerdict(900, 1000)).toBe("IN THE GREEN");
    expect(jobVerdict(899.99, 1000)).toBe("GETTING TIGHT");
    expect(jobVerdict(500, 1000)).toBe("GETTING TIGHT");
    expect(jobVerdict(499.99, 1000)).toBe("LOSING MONEY");
    expect(jobVerdict(-1, 1000)).toBe("LOSING MONEY");
  });

  it("excludes weekend wall-clock time from worked hours", () => {
    const minutes = workMinutesBetween(
      new Date("2026-06-26T16:30:00-07:00"),
      new Date("2026-06-29T08:00:00-07:00"),
      labor,
    );

    expect(minutes).toBe(120);
  });

  it("handles zero-units progress without divide-by-zero failures", () => {
    const snapshot = evaluateJobPace(
      fixtureJob,
      0,
      new Date("2026-06-26T09:00:00-07:00"),
      labor,
    );

    expect(Number.isFinite(snapshot.projected_labor_usd)).toBe(true);
    expect(snapshot.projected_labor_usd).toBeGreaterThan(0);
    expect(snapshot.units_done).toBe(0);
  });

  it("sums projected margin for the money strip", () => {
    const a = evaluateJobPace(fixtureJob, 40, new Date("2026-06-26T12:00:00-07:00"), labor);
    const b = { ...a, projected_margin: -100 };

    expect(moneyStripTotal([a, b])).toBeCloseTo(1200, 3);
  });
});
