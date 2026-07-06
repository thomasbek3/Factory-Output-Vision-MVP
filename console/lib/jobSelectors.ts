import type { CountEventShape } from "@/lib/demoEvents";
import { countEventsThrough, jobs, laborConfig, type JobSeed } from "@/lib/demoData";
import {
  evaluateJobPace,
  moneyStripTotal,
  pacePillLabel,
  workMinutesBetween,
  type PaceSnapshot,
} from "@/lib/paceMath";

export type JobWithPace = {
  job: JobSeed;
  unitsDone: number;
  snapshot: PaceSnapshot;
};

export type HourPoint = {
  hour: string;
  units: number;
};

function formatHourLabel(hour: number) {
  const suffix = hour >= 12 ? "p" : "a";
  const display = hour > 12 ? hour - 12 : hour;
  return `${display}${suffix}`;
}

function hourInPacific(date: Date) {
  return Number(
    new Intl.DateTimeFormat("en-US", {
      timeZone: "America/Los_Angeles",
      hour: "2-digit",
      hour12: false,
    }).format(date),
  );
}

function formatFinishDay(date: Date) {
  return new Intl.DateTimeFormat("en-US", {
    timeZone: "America/Los_Angeles",
    weekday: "long",
  }).format(date);
}

function projectedFinishDate(job: JobSeed, snapshot: PaceSnapshot, now: Date) {
  const elapsedMinutes = Math.max(
    workMinutesBetween(new Date(job.created_at), now, laborConfig),
    1,
  );
  const unitsPerMinute = snapshot.units_done / elapsedMinutes;
  if (unitsPerMinute <= 0) return new Date(job.deadline);

  const remaining = Math.max(job.units_required - snapshot.units_done, 0);
  return new Date(now.getTime() + (remaining / unitsPerMinute) * 60_000);
}

export function jobUnits(jobId: string, now: Date, events = countEventsThrough(now)) {
  return events.filter((event) => event.job_id === jobId).length;
}

export function selectRunningJobSnapshots(
  now: Date,
  sourceJobs: JobSeed[] = jobs,
  events = countEventsThrough(now),
): JobWithPace[] {
  return sourceJobs
    .filter((job) => job.status === "active")
    .map((job) => {
      const unitsDone = jobUnits(job.id, now, events);
      return {
        job,
        unitsDone,
        snapshot: evaluateJobPace(job, unitsDone, now, laborConfig),
      };
    });
}

export function selectMoneyStripTotal(jobSnapshots: JobWithPace[]) {
  return moneyStripTotal(jobSnapshots.map(({ snapshot }) => snapshot));
}

export function eventsByHour(events: CountEventShape[]): HourPoint[] {
  return Array.from({ length: 11 }, (_, index) => {
    const hour = index + 7;
    return {
      hour: formatHourLabel(hour),
      units: events.filter((event) => hourInPacific(new Date(event.ts)) === hour).length,
    };
  });
}

export function proratedBaselineUnits(now: Date, fullDayBaselineUnits: number) {
  const dayStart = new Date(now);
  dayStart.setHours(0, 0, 0, 0);
  const elapsed = workMinutesBetween(dayStart, now, laborConfig);
  const dayEnd = new Date(now);
  dayEnd.setHours(23, 59, 59, 999);
  const total = workMinutesBetween(dayStart, dayEnd, laborConfig);
  if (total === 0) return 0;
  return fullDayBaselineUnits * Math.min(1, elapsed / total);
}

export function moneySentence(jobSnapshots: JobWithPace[]) {
  const worst = [...jobSnapshots].sort((a, b) => a.snapshot.projected_margin - b.snapshot.projected_margin)[0];
  const atRisk = jobSnapshots.find(({ snapshot }) => snapshot.verdict !== "IN THE GREEN");
  if (!worst || !atRisk) return `All ${jobSnapshots.length} jobs on pace.`;

  const verdict = worst.snapshot.verdict === "LOSING MONEY" ? "losing money" : "getting tight";
  return `You're in the green - but ${worst.job.client} is ${verdict}.`;
}

export function cumulativeMarginSeries(jobSnapshots: JobWithPace[], events: CountEventShape[]) {
  const totalMargin = selectMoneyStripTotal(jobSnapshots);
  const chartData = eventsByHour(events);
  let runningUnits = 0;
  const totalUnits = Math.max(
    chartData.reduce((total, point) => total + point.units, 0),
    1,
  );

  return chartData.map((point) => {
    runningUnits += point.units;
    return {
      hour: point.hour,
      margin: Math.round(totalMargin * (runningUnits / totalUnits)),
    };
  });
}

export function jobPaceSentence(job: JobSeed, snapshot: PaceSnapshot, now: Date) {
  const done = Math.round(snapshot.units_done);
  const remaining = Math.max(job.units_required - snapshot.units_done, 0);
  const elapsedMinutes = Math.max(
    workMinutesBetween(new Date(job.created_at), now, laborConfig),
    1,
  );
  const actualPerDay = Math.round((snapshot.units_done / elapsedMinutes) * 60 * 10.5);
  const remainingWorkMinutes = Math.max(workMinutesBetween(now, new Date(job.deadline), laborConfig), 0);
  const neededPerDay =
    remainingWorkMinutes > 0 ? Math.ceil((remaining / remainingWorkMinutes) * 60 * 10.5) : remaining;
  const isBehindPace = snapshot.pace_delta < -0.05 * Math.max(snapshot.expected_units_by_now, 1);
  const isOverdue = now > new Date(job.deadline);
  const overBudget = Math.max(0, Math.round(snapshot.projected_labor_usd - job.labor_budget_usd));

  if (isOverdue) {
    return `${done} of ${job.units_required} done - Overdue — at this pace labor eats the whole margin.`;
  }
  if (snapshot.verdict === "LOSING MONEY" && !isBehindPace) {
    return `${done} of ${job.units_required} done - on pace, but labor is eating the margin — projected $${overBudget.toLocaleString("en-US")} over budget.`;
  }
  if (snapshot.verdict === "GETTING TIGHT" && !isBehindPace && overBudget > 0) {
    return `${done} of ${job.units_required} done - on pace, but labor is tightening the margin — projected $${overBudget.toLocaleString("en-US")} over budget.`;
  }
  if (isBehindPace) {
    return `${done} of ${job.units_required} done - needs ${neededPerDay}/day, doing ${actualPerDay}. Watch it tomorrow.`;
  }

  return `${done} of ${job.units_required} done — ahead. Finishes ${formatFinishDay(projectedFinishDate(job, snapshot, now))} morning.`;
}

export function pacePercent(snapshot: PaceSnapshot, unitsRequired: number) {
  return Math.round((snapshot.units_done / Math.max(unitsRequired, 1)) * 100);
}

export { pacePillLabel };
