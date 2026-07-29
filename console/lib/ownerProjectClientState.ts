export type OwnerProjectFormState = {
  name: string;
  client: string;
  targetUnits: string;
  valueMode: "per_unit" | "total";
  valueUsd: string;
  materialMode: "per_unit" | "total";
  materialUsd: string;
  stationId: string;
  stationSuggested: boolean;
  stationConfirmed: boolean;
  projectStartDate: string;
  projectStartTime: string;
  deadlineDate: string;
  deadlineTime: string;
  shiftStartTime: string;
  shiftEndTime: string;
  shiftDays: number[];
  workerIds: string[];
  loadedLaborRateUsd: string;
  targetMarginPercent: string;
};

function stringValue(value: unknown, fallback: string) {
  return typeof value === "string" ? value : fallback;
}

export function mergeOwnerProjectFormState(
  value: unknown,
  fallback: OwnerProjectFormState,
): OwnerProjectFormState {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return fallback;
  }
  const input = value as Record<string, unknown>;
  const string = (key: keyof OwnerProjectFormState) =>
    stringValue(input[key], fallback[key] as string);
  const legacyStartDate = stringValue(input.startDate, fallback.projectStartDate);
  const legacyStartTime = stringValue(input.startTime, fallback.projectStartTime);
  return {
    name: string("name"),
    client: string("client"),
    targetUnits: string("targetUnits"),
    valueMode: input.valueMode === "total" ? "total" : "per_unit",
    valueUsd: string("valueUsd"),
    materialMode: input.materialMode === "total" ? "total" : "per_unit",
    materialUsd: string("materialUsd"),
    stationId: string("stationId"),
    stationSuggested:
      typeof input.stationSuggested === "boolean"
        ? input.stationSuggested
        : fallback.stationSuggested,
    stationConfirmed:
      typeof input.stationConfirmed === "boolean"
        ? input.stationConfirmed
        : fallback.stationConfirmed,
    projectStartDate: stringValue(input.projectStartDate, legacyStartDate),
    projectStartTime: stringValue(input.projectStartTime, legacyStartTime),
    deadlineDate: string("deadlineDate"),
    deadlineTime: string("deadlineTime"),
    shiftStartTime: stringValue(input.shiftStartTime, legacyStartTime),
    shiftEndTime: string("shiftEndTime"),
    shiftDays: Array.isArray(input.shiftDays)
      ? input.shiftDays.filter(
          (day): day is number =>
            Number.isInteger(day) && Number(day) >= 1 && Number(day) <= 7,
        )
      : fallback.shiftDays,
    workerIds: Array.isArray(input.workerIds)
      ? input.workerIds.filter(
          (workerId): workerId is string =>
            typeof workerId === "string" && workerId.length > 0,
        )
      : fallback.workerIds,
    loadedLaborRateUsd: string("loadedLaborRateUsd"),
    targetMarginPercent: string("targetMarginPercent"),
  };
}
