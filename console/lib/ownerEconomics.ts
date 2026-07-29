import { Temporal } from "@js-temporal/polyfill";

const BIGINT_ZERO = BigInt(0);
const BIGINT_TWO = BigInt(2);

export type MillisecondInterval = {
  startMs: number;
  endMs: number;
};

export type ShiftCalendar = {
  timezone: string;
  shifts: readonly {
    weekday: number;
    start: string;
    end: string;
  }[];
};

function assertFiniteInteger(value: number, label: string) {
  if (!Number.isFinite(value) || !Number.isInteger(value)) {
    throw new Error(`${label} must be a finite integer.`);
  }
}

function roundHalfUp(numerator: bigint, denominator: bigint) {
  if (denominator <= BIGINT_ZERO || numerator < BIGINT_ZERO) {
    throw new Error("roundHalfUp requires a non-negative numerator and positive denominator.");
  }
  return (
    (numerator * BIGINT_TWO + denominator) /
    (denominator * BIGINT_TWO)
  );
}

export function deriveUnitCents(totalCents: number, units: number) {
  assertFiniteInteger(totalCents, "totalCents");
  assertFiniteInteger(units, "units");
  if (totalCents < 0 || units <= 0) {
    throw new Error("totalCents must be non-negative and units must be positive.");
  }
  return Number(roundHalfUp(BigInt(totalCents), BigInt(units)));
}

export function mergeIntervals(
  intervals: readonly MillisecondInterval[],
): MillisecondInterval[] {
  const sorted = intervals
    .filter(({ startMs, endMs }) => endMs > startMs)
    .map((interval) => ({ ...interval }))
    .sort((left, right) => left.startMs - right.startMs || left.endMs - right.endMs);

  const merged: MillisecondInterval[] = [];
  for (const interval of sorted) {
    const tail = merged.at(-1);
    if (!tail || interval.startMs > tail.endMs) {
      merged.push(interval);
      continue;
    }
    tail.endMs = Math.max(tail.endMs, interval.endMs);
  }
  return merged;
}

export function scheduledWorkIntervals(
  startIso: string,
  endIso: string,
  calendar: ShiftCalendar,
  downtime: readonly MillisecondInterval[],
): MillisecondInterval[] {
  const rangeStart = Temporal.Instant.from(startIso);
  const rangeEnd = Temporal.Instant.from(endIso);
  if (Temporal.Instant.compare(rangeEnd, rangeStart) <= 0) return [];

  const firstDate = rangeStart
    .toZonedDateTimeISO(calendar.timezone)
    .toPlainDate()
    .subtract({ days: 1 });
  const lastDate = rangeEnd.toZonedDateTimeISO(calendar.timezone).toPlainDate();
  const rangeStartMs = rangeStart.epochMilliseconds;
  const rangeEndMs = rangeEnd.epochMilliseconds;
  const mergedDowntime = mergeIntervals(downtime);
  const shiftIntervals: MillisecondInterval[] = [];

  for (
    let date = firstDate;
    Temporal.PlainDate.compare(date, lastDate) <= 0;
    date = date.add({ days: 1 })
  ) {
    for (const shift of calendar.shifts) {
      if (shift.weekday !== date.dayOfWeek) continue;
      const shiftStart = date
        .toPlainDateTime(Temporal.PlainTime.from(shift.start))
        .toZonedDateTime(calendar.timezone, { disambiguation: "later" });
      let shiftEndDate = date;
      if (
        Temporal.PlainTime.compare(
          Temporal.PlainTime.from(shift.end),
          Temporal.PlainTime.from(shift.start),
        ) <= 0
      ) {
        shiftEndDate = date.add({ days: 1 });
      }
      const shiftEnd = shiftEndDate
        .toPlainDateTime(Temporal.PlainTime.from(shift.end))
        .toZonedDateTime(calendar.timezone, { disambiguation: "later" });
      const clipped = {
        startMs: Math.max(rangeStartMs, shiftStart.epochMilliseconds),
        endMs: Math.min(rangeEndMs, shiftEnd.epochMilliseconds),
      };
      if (clipped.endMs > clipped.startMs) {
        shiftIntervals.push(clipped);
      }
    }
  }

  const scheduled: MillisecondInterval[] = [];
  for (const shift of mergeIntervals(shiftIntervals)) {
    let fragments = [shift];
    for (const gap of mergedDowntime) {
      if (gap.endMs <= shift.startMs) continue;
      if (gap.startMs >= shift.endMs) break;
      fragments = fragments.flatMap((fragment) => {
        if (gap.endMs <= fragment.startMs || gap.startMs >= fragment.endMs) {
          return [fragment];
        }
        const remainder: MillisecondInterval[] = [];
        if (gap.startMs > fragment.startMs) {
          remainder.push({
            startMs: fragment.startMs,
            endMs: Math.min(gap.startMs, fragment.endMs),
          });
        }
        if (gap.endMs < fragment.endMs) {
          remainder.push({
            startMs: Math.max(gap.endMs, fragment.startMs),
            endMs: fragment.endMs,
          });
        }
        return remainder;
      });
      if (fragments.length === 0) break;
    }
    scheduled.push(...fragments);
  }
  return scheduled;
}

export function workedMillisecondsBetween(
  startIso: string,
  endIso: string,
  calendar: ShiftCalendar,
  downtime: readonly MillisecondInterval[],
) {
  return scheduledWorkIntervals(startIso, endIso, calendar, downtime).reduce(
    (workedMs, interval) => workedMs + interval.endMs - interval.startMs,
    0,
  );
}

function nominalShiftMilliseconds(calendar: ShiftCalendar) {
  if (!calendar.shifts.length) return 0;
  const durations = calendar.shifts.map((shift) => {
    const start = Temporal.PlainTime.from(shift.start);
    const end = Temporal.PlainTime.from(shift.end);
    const startMinute = start.hour * 60 + start.minute;
    let endMinute = end.hour * 60 + end.minute;
    if (endMinute <= startMinute) endMinute += 24 * 60;
    return (endMinute - startMinute) * 60_000;
  });
  return Math.round(
    durations.reduce((sum, duration) => sum + duration, 0) / durations.length,
  );
}

export function evaluateProjectFeasibility(input: {
  targetUnits: number;
  startIso: string;
  deadlineIso: string;
  calendar: ShiftCalendar;
  baselineUnitsPerDay: number | null;
}) {
  const plannedWorkedMs = workedMillisecondsBetween(
    input.startIso,
    input.deadlineIso,
    input.calendar,
    [],
  );
  const nominalDayMs = nominalShiftMilliseconds(input.calendar);
  const workedDayEquivalents =
    nominalDayMs > 0 ? plannedWorkedMs / nominalDayMs : 0;
  const requiredUnitsPerDay =
    workedDayEquivalents > 0
      ? input.targetUnits / workedDayEquivalents
      : null;
  const requiredUnitsPerHour =
    plannedWorkedMs > 0
      ? (input.targetUnits * 3_600_000) / plannedWorkedMs
      : null;
  const baseline = input.baselineUnitsPerDay;
  const status =
    requiredUnitsPerDay === null || baseline === null
      ? "Unavailable"
      : requiredUnitsPerDay <= baseline * 0.85
        ? "Feasible"
        : requiredUnitsPerDay <= baseline
          ? "Tight"
          : "Not feasible";
  return {
    plannedWorkedMs,
    workedDayEquivalents,
    requiredUnitsPerDay,
    requiredUnitsPerHour,
    baselineUnitsPerDay: baseline,
    status,
  } as const;
}

export type LaborInterval = {
  stationId: string;
  rateCentsPerHour: number;
  startMs: number;
  endMs: number;
};

export function apportionLaborCents(intervals: readonly LaborInterval[]) {
  const denominator = BigInt(3_600_000);
  const stationNumerators = new Map<string, bigint>();

  for (const interval of intervals) {
    assertFiniteInteger(interval.rateCentsPerHour, "rateCentsPerHour");
    assertFiniteInteger(interval.startMs, "startMs");
    assertFiniteInteger(interval.endMs, "endMs");
    if (interval.rateCentsPerHour < 0 || interval.endMs < interval.startMs) {
      throw new Error("Labor intervals require non-negative rates and ordered times.");
    }
    const numerator =
      BigInt(interval.rateCentsPerHour) * BigInt(interval.endMs - interval.startMs);
    stationNumerators.set(
      interval.stationId,
      (stationNumerators.get(interval.stationId) ?? BIGINT_ZERO) + numerator,
    );
  }

  const totalNumerator = [...stationNumerators.values()].reduce(
    (sum, numerator) => sum + numerator,
    BIGINT_ZERO,
  );
  const projectCents = Number(roundHalfUp(totalNumerator, denominator));
  const rows = [...stationNumerators.entries()].map(([stationId, numerator]) => ({
    stationId,
    cents: Number(numerator / denominator),
    remainder: numerator % denominator,
  }));
  const remaining = projectCents - rows.reduce((sum, row) => sum + row.cents, 0);
  rows.sort(
    (left, right) => {
      if (right.remainder !== left.remainder) {
        return right.remainder > left.remainder ? 1 : -1;
      }
      return left.stationId < right.stationId
        ? -1
        : left.stationId > right.stationId
          ? 1
          : 0;
    },
  );
  for (let index = 0; index < remaining; index += 1) {
    rows[index].cents += 1;
  }

  return {
    projectCents,
    byStationCents: Object.fromEntries(
      rows
        .sort((left, right) =>
          left.stationId < right.stationId
            ? -1
            : left.stationId > right.stationId
              ? 1
              : 0,
        )
        .map(({ stationId, cents }) => [stationId, cents]),
    ),
  };
}

export function derivePlannedLaborCents(input: {
  loadedRateCentsPerHour: number;
  workerCount: number;
  plannedWorkedMs: number;
}) {
  assertFiniteInteger(
    input.loadedRateCentsPerHour,
    "loadedRateCentsPerHour",
  );
  assertFiniteInteger(input.workerCount, "workerCount");
  assertFiniteInteger(input.plannedWorkedMs, "plannedWorkedMs");
  if (
    input.loadedRateCentsPerHour < 0 ||
    input.workerCount < 0 ||
    input.plannedWorkedMs < 0
  ) {
    throw new Error("Planned labor inputs must be non-negative.");
  }
  return Number(
    roundHalfUp(
      BigInt(input.loadedRateCentsPerHour) *
        BigInt(input.workerCount) *
        BigInt(input.plannedWorkedMs),
      BigInt(3_600_000),
    ),
  );
}

export function ownerLaborAccrualEndMs(input: {
  status: "open" | "closed";
  deadlineMs: number;
  nowMs: number;
  closedAtMs: number | null;
}) {
  assertFiniteInteger(input.deadlineMs, "deadlineMs");
  assertFiniteInteger(input.nowMs, "nowMs");
  if (input.status === "open") return input.nowMs;
  if (input.closedAtMs === null) {
    throw new Error("Closed projects require a closedAtMs value.");
  }
  assertFiniteInteger(input.closedAtMs, "closedAtMs");
  return input.closedAtMs;
}

type PaceInput = {
  targetUnits: number;
  goodUnits: number;
  plannedWorkedMs: number;
  verifiedWorkedMs: number;
  remainingWorkedMs: number;
  verificationLagMs: number;
  verificationLagThresholdMs: number;
};

export function evaluatePace(input: PaceInput) {
  if (input.verificationLagMs > input.verificationLagThresholdMs) {
    return {
      status: "DATA_DELAY" as const,
      expectedUnits: null,
      requiredUnitsPerHour: null,
    };
  }

  const expectedUnits =
    input.plannedWorkedMs > 0
      ? (input.targetUnits * input.verifiedWorkedMs) / input.plannedWorkedMs
      : 0;
  const ratio = expectedUnits > 0 ? input.goodUnits / expectedUnits : 1;
  const status = ratio < 0.95 ? "BEHIND" : ratio > 1.05 ? "AHEAD" : "ON_TRACK";
  const requiredUnitsPerHour =
    input.remainingWorkedMs > 0
      ? ((input.targetUnits - input.goodUnits) * 3_600_000) /
        input.remainingWorkedMs
      : null;

  return {
    status,
    expectedUnits,
    requiredUnitsPerHour:
      requiredUnitsPerHour === null ? null : Math.max(0, requiredUnitsPerHour),
  };
}

type MarginProjectionInput = {
  targetUnits: number;
  verifiedGoodUnits: number;
  unitValueCents: number;
  unitMaterialCostCents: number;
  laborBurnedCents: number;
  verifiedWorkedMs: number;
  remainingWorkedMs: number;
};

export function projectDirectCostMargin(input: MarginProjectionInput) {
  for (const [label, value] of Object.entries(input)) {
    assertFiniteInteger(value, label);
  }
  if (input.verifiedGoodUnits <= 0 || input.verifiedWorkedMs <= 0) {
    return {
      projectedUnits: null,
      projectedLaborCents: null,
      projectedMarginCents: null,
    };
  }

  const totalWorkedMs = input.verifiedWorkedMs + input.remainingWorkedMs;
  const projectedUnits = Math.min(
    input.targetUnits,
    Number(
      roundHalfUp(
        BigInt(input.verifiedGoodUnits) * BigInt(totalWorkedMs),
        BigInt(input.verifiedWorkedMs),
      ),
    ),
  );
  const projectedLaborCents = Number(
    roundHalfUp(
      BigInt(input.laborBurnedCents) * BigInt(totalWorkedMs),
      BigInt(input.verifiedWorkedMs),
    ),
  );
  const projectedMarginCents =
    projectedUnits * (input.unitValueCents - input.unitMaterialCostCents) -
    projectedLaborCents;

  return { projectedUnits, projectedLaborCents, projectedMarginCents };
}
