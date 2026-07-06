import { describe, expect, it } from "vitest";
import {
  evaluateJobPace,
  jobVerdict,
  moneyStripTotal,
  pacePillLabel,
  workMinutesBetween,
} from "@/lib/paceMath";
import { demoNowIso, jobs } from "@/lib/demoData";
import { validateNewJobInput } from "@/lib/jobForm";
import {
  jobPaceSentence,
  selectMoneyStripTotal,
  selectRunningJobSnapshots,
} from "@/lib/jobSelectors";
import { selectStationCountSnapshots } from "@/lib/stationSelectors";
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

  it("uses exact 0.9 planned-margin and zero-dollar verdict boundaries", () => {
    expect(jobVerdict(900, 1000)).toBe("IN THE GREEN");
    expect(jobVerdict(899.99, 1000)).toBe("GETTING TIGHT");
    expect(jobVerdict(0, 1000)).toBe("GETTING TIGHT");
    expect(jobVerdict(-0.01, 1000)).toBe("LOSING MONEY");
    expect(jobVerdict(-1, 1000)).toBe("LOSING MONEY");
  });

  it("labels a rounded zero pace delta as on pace, not behind", () => {
    expect(pacePillLabel(-0.2)).toBe("ON PACE");
    expect(pacePillLabel(18)).toBe("18 AHEAD");
    expect(pacePillLabel(-21)).toBe("21 BEHIND");
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

  it("holds the demo-day 14:32 narrative exactly", () => {
    const now = new Date(demoNowIso);
    const snapshots = selectRunningJobSnapshots(now, jobs);
    const byClient = new Map(snapshots.map((snapshot) => [snapshot.job.client, snapshot]));
    const stationSnapshots = selectStationCountSnapshots(now, jobs);
    const byStation = new Map(stationSnapshots.map((snapshot) => [snapshot.station.name, snapshot]));

    expect(snapshots).toHaveLength(3);
    expect(byClient.get("Ramirez Fencing")?.snapshot.verdict).toBe("IN THE GREEN");
    expect(byClient.get("Delgado HVAC")?.snapshot.verdict).toBe("GETTING TIGHT");
    expect(byClient.get("Alvarez Gates")?.snapshot.verdict).toBe("LOSING MONEY");
    expect(byClient.get("Ramirez Fencing")?.unitsDone).toBe(208);
    expect(Math.round(byClient.get("Ramirez Fencing")?.snapshot.expected_units_by_now ?? 0)).toBe(208);
    expect(byClient.get("Alvarez Gates")?.snapshot.projected_margin).toBeLessThan(0);
    expect(byStation.get("Pallet A")?.unitsToday).toBe(142);
    expect(pacePillLabel(byStation.get("Pallet A")?.pace.pace_delta ?? 0)).toBe("18 AHEAD");
    expect(byStation.get("Gate line")?.unitsToday).toBe(58);
    expect(pacePillLabel(byStation.get("Gate line")?.pace.pace_delta ?? 0)).toBe("21 BEHIND");
    expect(selectMoneyStripTotal(snapshots)).toBeCloseTo(532, 0);
  });

  it("writes an ahead sentence with the finish-day driver", () => {
    const now = new Date("2026-06-26T12:00:00-07:00");
    const ahead = evaluateJobPace(fixtureJob, 60, now, labor);

    expect(jobPaceSentence(fixtureJob, ahead, now)).toMatch(
      /^60 of 100 done — ahead\. Finishes Friday morning\.$/,
    );
  });

  it("writes a behind-pace sentence with needed and actual rates", () => {
    const now = new Date("2026-06-26T12:00:00-07:00");
    const behind = evaluateJobPace(fixtureJob, 35, now, labor);

    expect(jobPaceSentence(fixtureJob, behind, now)).toBe(
      "35 of 100 done — needs 137/day, doing 74. Watch it tomorrow.",
    );
  });

  it("writes a losing-money labor-overrun sentence when the job is still on pace", () => {
    const now = new Date("2026-06-26T12:00:00-07:00");
    const onPace = evaluateJobPace(fixtureJob, 55, now, labor);
    const laborOverrun = {
      ...onPace,
      verdict: "LOSING MONEY" as const,
      pace_delta: 0,
      projected_labor_usd: fixtureJob.labor_budget_usd + 143,
    };

    expect(jobPaceSentence(fixtureJob, laborOverrun, now)).toBe(
      "55 of 100 done — on pace, but labor is eating the margin — projected $143 over budget.",
    );
  });

  it("writes an overdue sentence with the margin warning", () => {
    const overdue = evaluateJobPace(fixtureJob, 80, new Date("2026-06-26T18:00:00-07:00"), labor);

    expect(jobPaceSentence(fixtureJob, overdue, new Date("2026-06-26T18:00:00-07:00"))).toBe(
      "80 of 100 done — Overdue — at this pace labor eats the whole margin.",
    );
  });

  it("writes three different verdict-explaining sentences for the demo jobs", () => {
    const now = new Date(demoNowIso);
    const snapshots = selectRunningJobSnapshots(now, jobs);
    const sentences = snapshots.map(({ job, snapshot }) => jobPaceSentence(job, snapshot, now));

    expect(new Set(sentences).size).toBe(3);
    expect(sentences.some((sentence) => sentence.includes("ahead. Finishes"))).toBe(true);
    expect(sentences.some((sentence) => sentence.includes("labor is tightening the margin"))).toBe(true);
    expect(sentences.some((sentence) => sentence.includes("labor is eating the margin"))).toBe(true);
  });

  it("validates new-job form input as a pure function", () => {
    expect(
      validateNewJobInput({
        client: "",
        title: "",
        units_required: 0,
        quote_usd: 0,
        cogs_usd: 0,
        labor_budget_usd: 0,
        deadline: "",
        station_ids: [],
      }).ok,
    ).toBe(false);

    expect(
      validateNewJobInput({
        client: "Northline",
        title: "300 brackets",
        units_required: 300,
        quote_usd: 2400,
        cogs_usd: 900,
        labor_budget_usd: 600,
        deadline: "2026-06-30",
        station_ids: ["pallet-a"],
      }).ok,
    ).toBe(true);
  });
});
