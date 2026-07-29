import { Temporal } from "@js-temporal/polyfill";
import {
  derivePlannedLaborCents,
  deriveUnitCents,
  ShiftCalendar,
  workedMillisecondsBetween,
} from "@/lib/ownerEconomics";

type MoneyMode = "per_unit" | "total";

export type OwnerProjectDraft = {
  factoryId: string;
  name: string;
  client: string;
  targetUnits: number | null;
  unitValueCents: number | null;
  unitMaterialCostCents: number | null;
  stationId: string;
  stationSuggested: boolean;
  stationConfirmed: boolean;
  startDate: string;
  startTime: string;
  deadlineDate: string;
  deadlineTime: string;
  timezone: string;
  shiftCalendar: Record<string, unknown>;
  workerIds: string[];
  loadedLaborRateCentsPerHour: number | null;
  loadedLaborRateInputValid: boolean;
  targetMarginBps: number | null;
};

export type OwnerProjectValidation = {
  ok: boolean;
  steps: {
    what: boolean;
    whereWhen: boolean;
    laborGoal: boolean;
  };
  errors: Partial<
    Record<
      | "factoryId"
      | "name"
      | "client"
      | "targetUnits"
      | "unitValueCents"
      | "unitMaterialCostCents"
      | "stationId"
      | "stationConfirmed"
      | "start"
      | "deadline"
      | "shiftCalendar"
      | "workerIds"
      | "loadedLaborRateCentsPerHour"
      | "targetMarginBps",
      string
    >
  >;
};

function stringValue(value: unknown) {
  return typeof value === "string" ? value.trim() : "";
}

function booleanValue(value: unknown) {
  return value === true;
}

function parsePositiveInteger(value: unknown) {
  const text = stringValue(value);
  if (!/^[1-9]\d*$/.test(text)) return null;
  const parsed = Number(text);
  return Number.isSafeInteger(parsed) ? parsed : null;
}

function parseFixedPoint(value: unknown, decimals: number) {
  const text = stringValue(value);
  const match = text.match(/^(\d+)(?:\.(\d+))?$/);
  if (!match || (match[2]?.length ?? 0) > decimals) return null;
  const whole = Number(match[1]);
  const fraction = Number((match[2] ?? "").padEnd(decimals, "0"));
  const scale = 10 ** decimals;
  const result = whole * scale + fraction;
  return Number.isSafeInteger(result) ? result : null;
}

function parseSignedFixedPoint(value: unknown, decimals: number) {
  const text = stringValue(value);
  const match = text.match(/^(-?)(\d+)(?:\.(\d+))?$/);
  if (!match || (match[3]?.length ?? 0) > decimals) return null;
  const whole = Number(match[2]);
  const fraction = Number((match[3] ?? "").padEnd(decimals, "0"));
  const scale = 10 ** decimals;
  const result = (whole * scale + fraction) * (match[1] === "-" ? -1 : 1);
  return Number.isSafeInteger(result) ? result : null;
}

function moneyToUnitCents(
  mode: MoneyMode,
  value: unknown,
  targetUnits: number | null,
) {
  const cents = parseFixedPoint(value, 2);
  if (cents === null || targetUnits === null) return null;
  return mode === "total" ? deriveUnitCents(cents, targetUnits) : cents;
}

function objectValue(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

export function normalizeOwnerProjectDraft(
  body: Record<string, unknown>,
): OwnerProjectDraft {
  const targetUnits = parsePositiveInteger(body.targetUnits);
  const valueMode: MoneyMode = body.valueMode === "total" ? "total" : "per_unit";
  const materialMode: MoneyMode =
    body.materialMode === "total" ? "total" : "per_unit";
  const loadedLaborRateText = stringValue(body.loadedLaborRateUsd);
  const loadedLaborRateCentsPerHour =
    loadedLaborRateText === ""
      ? null
      : parseFixedPoint(loadedLaborRateText, 2);

  return {
    factoryId: stringValue(body.factoryId),
    name: stringValue(body.name),
    client: stringValue(body.client),
    targetUnits,
    unitValueCents: moneyToUnitCents(valueMode, body.valueUsd, targetUnits),
    unitMaterialCostCents: moneyToUnitCents(
      materialMode,
      body.materialUsd,
      targetUnits,
    ),
    stationId: stringValue(body.stationId),
    stationSuggested: booleanValue(body.stationSuggested),
    stationConfirmed: booleanValue(body.stationConfirmed),
    startDate: stringValue(body.startDate),
    startTime: stringValue(body.startTime),
    deadlineDate: stringValue(body.deadlineDate),
    deadlineTime: stringValue(body.deadlineTime),
    timezone: stringValue(body.timezone),
    shiftCalendar: objectValue(body.shiftCalendar),
    workerIds: Array.isArray(body.workerIds)
      ? body.workerIds.map(stringValue).filter(Boolean)
      : [],
    loadedLaborRateCentsPerHour,
    loadedLaborRateInputValid:
      loadedLaborRateText === "" || loadedLaborRateCentsPerHour !== null,
    targetMarginBps:
      stringValue(body.targetMarginPercent) === ""
        ? null
        : parseSignedFixedPoint(body.targetMarginPercent, 2),
  };
}

function projectInstant(date: string, time: string, timezone: string) {
  return Temporal.PlainDateTime.from(`${date}T${time}`)
    .toZonedDateTime(timezone, { disambiguation: "later" })
    .toInstant();
}

function shiftCalendarIsValid(
  calendar: Record<string, unknown>,
  expectedTimezone: string,
) {
  if (
    calendar.timezone !== expectedTimezone ||
    !Array.isArray(calendar.shifts) ||
    calendar.shifts.length === 0
  ) {
    return false;
  }
  try {
    Temporal.ZonedDateTime.from({
      timeZone: expectedTimezone,
      year: 2026,
      month: 1,
      day: 1,
      hour: 0,
    });
  } catch {
    return false;
  }

  const intervals: { start: number; end: number }[] = [];
  for (const value of calendar.shifts) {
    if (!value || typeof value !== "object" || Array.isArray(value)) return false;
    const shift = value as Record<string, unknown>;
    if (
      !Number.isInteger(shift.weekday) ||
      (shift.weekday as number) < 1 ||
      (shift.weekday as number) > 7 ||
      typeof shift.start !== "string" ||
      typeof shift.end !== "string"
    ) {
      return false;
    }
    let start: Temporal.PlainTime;
    let end: Temporal.PlainTime;
    try {
      start = Temporal.PlainTime.from(shift.start);
      end = Temporal.PlainTime.from(shift.end);
    } catch {
      return false;
    }
    const startMinute =
      ((shift.weekday as number) - 1) * 1440 + start.hour * 60 + start.minute;
    let endMinute =
      ((shift.weekday as number) - 1) * 1440 + end.hour * 60 + end.minute;
    if (endMinute === startMinute) return false;
    if (endMinute < startMinute) endMinute += 1440;
    if (endMinute <= 10_080) {
      intervals.push({ start: startMinute, end: endMinute });
    } else {
      intervals.push({ start: startMinute, end: 10_080 });
      intervals.push({ start: 0, end: endMinute - 10_080 });
    }
  }
  intervals.sort((left, right) => left.start - right.start || left.end - right.end);
  return intervals.every(
    (interval, index) => index === 0 || interval.start >= intervals[index - 1].end,
  );
}

export function validateOwnerProjectDraft(
  draft: OwnerProjectDraft,
): OwnerProjectValidation {
  const errors: OwnerProjectValidation["errors"] = {};
  let start: Temporal.Instant | null = null;
  let deadline: Temporal.Instant | null = null;

  if (!draft.factoryId) errors.factoryId = "Factory is required.";
  if (!draft.name) errors.name = "Project name is required.";
  if (!draft.client) errors.client = "Customer is required.";
  if (!draft.targetUnits) errors.targetUnits = "Target units must be greater than 0.";
  if (draft.unitValueCents === null) {
    errors.unitValueCents = "Enter a valid project value.";
  }
  if (draft.unitMaterialCostCents === null) {
    errors.unitMaterialCostCents = "Enter a valid material cost.";
  }

  if (!draft.stationId) errors.stationId = "Station is required.";
  if (draft.stationSuggested && !draft.stationConfirmed) {
    errors.stationConfirmed = "Confirm or change the suggested station.";
  }
  if (!draft.startDate || !draft.startTime || !draft.timezone) {
    errors.start = "Start date and time are required.";
  }
  if (!draft.deadlineDate || !draft.deadlineTime || !draft.timezone) {
    errors.deadline = "Deadline is required.";
  }
  if (!shiftCalendarIsValid(draft.shiftCalendar, draft.timezone)) {
    errors.shiftCalendar = "Enter a valid non-overlapping shift calendar.";
  }
  if (!errors.start && !errors.deadline) {
    try {
      start = projectInstant(
        draft.startDate,
        draft.startTime,
        draft.timezone,
      );
      deadline = projectInstant(
        draft.deadlineDate,
        draft.deadlineTime,
        draft.timezone,
      );
      if (Temporal.Instant.compare(deadline, start) <= 0) {
        errors.deadline = "Deadline must be after the project start.";
      }
    } catch {
      errors.deadline = "Enter valid factory-local dates and times.";
    }
  }
  if (
    start
    && deadline
    && !errors.deadline
    && !errors.shiftCalendar
    && workedMillisecondsBetween(
      start.toString(),
      deadline.toString(),
      draft.shiftCalendar as ShiftCalendar,
      [],
    ) <= 0
  ) {
    errors.shiftCalendar =
      "Project window must include at least one scheduled working shift.";
  }

  if (!draft.workerIds.length) errors.workerIds = "Assign at least one worker.";
  if (!draft.loadedLaborRateInputValid) {
    errors.loadedLaborRateCentsPerHour =
      "Enter a valid non-negative loaded labor rate.";
  }
  if (
    draft.targetMarginBps !== null &&
    (draft.targetMarginBps < -100_000 || draft.targetMarginBps > 10_000)
  ) {
    errors.targetMarginBps = "Target margin must be between -1000% and 100%.";
  }

  const whatKeys = [
    "factoryId",
    "name",
    "client",
    "targetUnits",
    "unitValueCents",
    "unitMaterialCostCents",
  ] as const;
  const whereKeys = [
    "stationId",
    "stationConfirmed",
    "start",
    "deadline",
    "shiftCalendar",
  ] as const;
  const laborKeys = [
    "workerIds",
    "loadedLaborRateCentsPerHour",
    "targetMarginBps",
  ] as const;
  const stepIsValid = (keys: readonly (keyof typeof errors)[]) =>
    keys.every((key) => !errors[key]);
  const steps = {
    what: stepIsValid(whatKeys),
    whereWhen: stepIsValid(whereKeys),
    laborGoal: stepIsValid(laborKeys),
  };

  return {
    ok: steps.what && steps.whereWhen && steps.laborGoal,
    steps,
    errors,
  };
}

export function ownerProjectRpcPayload(
  draft: OwnerProjectDraft,
  status: "draft" | "open",
) {
  const validation = validateOwnerProjectDraft(draft);
  if (!validation.ok || draft.targetUnits === null) {
    throw new Error("Owner project draft is invalid.");
  }
  const start = projectInstant(
    draft.startDate,
    draft.startTime,
    draft.timezone,
  );
  const deadline = projectInstant(
    draft.deadlineDate,
    draft.deadlineTime,
    draft.timezone,
  );
  const plannedWorkedMs = workedMillisecondsBetween(
    start.toString(),
    deadline.toString(),
    draft.shiftCalendar as ShiftCalendar,
    [],
  );
  if (plannedWorkedMs <= 0) {
    throw new Error("Project window must include scheduled working time.");
  }
  return {
    p_factory_id: draft.factoryId,
    p_name: draft.name,
    p_client: draft.client,
    p_target_units: draft.targetUnits,
    p_unit_value_cents: draft.unitValueCents,
    p_unit_material_cost_cents: draft.unitMaterialCostCents,
    p_loaded_labor_rate_cents_per_hour:
      draft.loadedLaborRateCentsPerHour ?? 0,
    p_start_at: start.toString(),
    p_deadline: deadline.toString(),
    p_shift_calendar: draft.shiftCalendar,
    p_target_margin_bps: draft.targetMarginBps,
    p_status: status,
    p_station_id: draft.stationId,
    p_worker_ids: draft.workerIds,
    p_planned_direct_labor_cents: derivePlannedLaborCents({
      loadedRateCentsPerHour:
        draft.loadedLaborRateCentsPerHour ?? 0,
      workerCount: draft.workerIds.length,
      plannedWorkedMs,
    }),
  };
}
