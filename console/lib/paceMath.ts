import type { JobSeed, LaborConfigSeed, WorkDayKey } from "@/lib/demoData";

export type PaceSnapshot = {
  elapsed_work_ratio: number;
  expected_units_by_now: number;
  units_done: number;
  pace_delta: number;
  labor_burned_usd: number;
  projected_labor_usd: number;
  projected_margin: number;
  planned_margin: number;
  verdict: "IN THE GREEN" | "GETTING TIGHT" | "LOSING MONEY";
};

const weekdayKeys: WorkDayKey[] = [
  "sunday",
  "monday",
  "tuesday",
  "wednesday",
  "thursday",
  "friday",
  "saturday",
];

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function pacificParts(date: Date) {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/Los_Angeles",
    weekday: "long",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(date);

  const value = (type: string) => parts.find((part) => part.type === type)?.value ?? "";
  return {
    weekday: value("weekday").toLowerCase() as WorkDayKey,
    dateKey: `${value("year")}-${value("month")}-${value("day")}`,
    minutes: Number(value("hour")) * 60 + Number(value("minute")),
  };
}

function parseClock(value: string) {
  const [hours, minutes] = value.split(":").map(Number);
  return hours * 60 + minutes;
}

function dateKeyAfter(dateKey: string, days: number) {
  const date = new Date(`${dateKey}T12:00:00-07:00`);
  date.setDate(date.getDate() + days);
  return pacificParts(date).dateKey;
}

function dateForPacificMinute(dateKey: string, minute: number) {
  const hours = Math.floor(minute / 60);
  const minutes = minute % 60;
  return new Date(
    `${dateKey}T${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:00-07:00`,
  );
}

export function workMinutesBetween(start: Date, end: Date, labor: LaborConfigSeed) {
  if (end <= start) return 0;

  let minutes = 0;
  let dateKey = pacificParts(start).dateKey;
  const endDateKey = pacificParts(end).dateKey;

  while (dateKey <= endDateKey) {
    const dayMidpoint = new Date(`${dateKey}T12:00:00-07:00`);
    const parts = pacificParts(dayMidpoint);
    const window = labor.work_hours[parts.weekday];
    if (window) {
      const startMinute = parseClock(window.start);
      const endMinute = parseClock(window.end);
      const windowStart = dateForPacificMinute(dateKey, startMinute);
      const windowEnd = dateForPacificMinute(dateKey, endMinute);
      const segmentStart = new Date(Math.max(start.getTime(), windowStart.getTime()));
      const segmentEnd = new Date(Math.min(end.getTime(), windowEnd.getTime()));
      minutes += Math.max(0, (segmentEnd.getTime() - segmentStart.getTime()) / 60_000);
    }
    dateKey = dateKeyAfter(dateKey, 1);
  }

  return minutes;
}

export function elapsedWorkRatio(job: JobSeed, now: Date, labor: LaborConfigSeed) {
  const start = new Date(job.created_at);
  const deadline = new Date(job.deadline);
  const total = workMinutesBetween(start, deadline, labor);
  const elapsed = workMinutesBetween(start, new Date(Math.min(now.getTime(), deadline.getTime())), labor);
  return total === 0 ? 0 : clamp(elapsed / total, 0, 1);
}

export function expectedUnitsByNow(job: JobSeed, now: Date, labor: LaborConfigSeed) {
  return job.units_required * elapsedWorkRatio(job, now, labor);
}

export function paceDelta(job: JobSeed, unitsDone: number, now: Date, labor: LaborConfigSeed) {
  return unitsDone - expectedUnitsByNow(job, now, labor);
}

export function laborBurnedUsd(job: JobSeed, now: Date, labor: LaborConfigSeed) {
  const activeMinutes = workMinutesBetween(
    new Date(job.created_at),
    new Date(Math.min(now.getTime(), new Date(job.deadline).getTime())),
    labor,
  );
  const stationCount = Math.max(job.station_ids.length, 1);
  return (activeMinutes / 60) * labor.hourly_rate_usd * labor.workers_per_station * stationCount;
}

export function projectedLaborUsd(job: JobSeed, unitsDone: number, now: Date, labor: LaborConfigSeed) {
  const burned = laborBurnedUsd(job, now, labor);
  const unitsBased = (burned / Math.max(unitsDone, 1)) * job.units_required;
  const totalScheduledLabor =
    (workMinutesBetween(new Date(job.created_at), new Date(job.deadline), labor) / 60) *
    labor.hourly_rate_usd *
    labor.workers_per_station *
    Math.max(job.station_ids.length, 1);

  return Math.min(unitsBased, totalScheduledLabor);
}

export function projectedMargin(job: JobSeed, unitsDone: number, now: Date, labor: LaborConfigSeed) {
  return job.quote_usd - job.cogs_usd - projectedLaborUsd(job, unitsDone, now, labor);
}

export function jobVerdict(projected_margin: number, planned_margin: number): PaceSnapshot["verdict"] {
  if (projected_margin >= 0.9 * planned_margin) return "IN THE GREEN";
  if (projected_margin >= 0) return "GETTING TIGHT";
  return "LOSING MONEY";
}

export function evaluateJobPace(
  job: JobSeed,
  unitsDone: number,
  now: Date,
  labor: LaborConfigSeed,
): PaceSnapshot {
  const planned_margin = job.quote_usd - job.cogs_usd - job.labor_budget_usd;
  const projected_margin = projectedMargin(job, unitsDone, now, labor);

  return {
    elapsed_work_ratio: elapsedWorkRatio(job, now, labor),
    expected_units_by_now: expectedUnitsByNow(job, now, labor),
    units_done: unitsDone,
    pace_delta: paceDelta(job, unitsDone, now, labor),
    labor_burned_usd: laborBurnedUsd(job, now, labor),
    projected_labor_usd: projectedLaborUsd(job, unitsDone, now, labor),
    projected_margin,
    planned_margin,
    verdict: jobVerdict(projected_margin, planned_margin),
  };
}

export function moneyStripTotal(snapshots: PaceSnapshot[]) {
  return snapshots.reduce((total, snapshot) => total + snapshot.projected_margin, 0);
}

export function pacePillLabel(delta: number) {
  const rounded = Math.round(Math.abs(delta));
  return `${rounded} ${delta >= 0 ? "AHEAD" : "BEHIND"}`;
}

export function weekdayForDate(date: Date) {
  return weekdayKeys[date.getUTCDay()];
}
