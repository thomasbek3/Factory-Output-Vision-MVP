import "server-only";

import { Temporal } from "@js-temporal/polyfill";
import { workedMillisecondsBetween, type ShiftCalendar } from "@/lib/ownerEconomics";
import {
  buildOwnerStationData,
  buildOwnerWorkforceData,
} from "@/lib/ownerStationModel";
import type { OwnerStationData, OwnerWorkforceData } from "@/lib/ownerStationTypes";
import { ownerRestAll, ownerRpc } from "@/lib/ownerServer";

type StationRow = {
  id: string;
  alias: string;
  status: string;
};

type ProjectRow = {
  id: string;
  name: string;
  target_units: number;
  start_at: string;
  deadline: string;
  shift_calendar: ShiftCalendar;
  status: string;
};

type AssignmentRow = {
  id: string;
  project_id: string;
  station_id: string;
  effective_start: string;
  effective_end: string | null;
};

type WorkerRow = {
  id: string;
  display_name: string;
  employee_code: string | null;
  primary_role: string | null;
  status: "active" | "inactive";
};

type WorkerIntervalRow = {
  id: string;
  worker_id: string;
  station_id: string;
  project_id: string;
  effective_start: string;
  effective_end: string | null;
  loaded_labor_rate_cents_per_hour: number;
  source: "manual" | "badge" | "schedule" | "import";
};

function validDate(value: string | undefined, timezone: string) {
  try {
    return value
      ? Temporal.PlainDate.from(value)
      : Temporal.Now.instant().toZonedDateTimeISO(timezone).toPlainDate();
  } catch {
    return Temporal.Now.instant().toZonedDateTimeISO(timezone).toPlainDate();
  }
}

function civilDayWindow(date: Temporal.PlainDate, timezone: string) {
  const start = date.toZonedDateTime({
    timeZone: timezone,
    plainTime: Temporal.PlainTime.from("00:00"),
  });
  return {
    startIso: start.toInstant().toString(),
    endIso: start.add({ days: 1 }).toInstant().toString(),
  };
}

function selectedShiftWindow(
  date: Temporal.PlainDate,
  calendar: ShiftCalendar,
) {
  const shift = calendar.shifts
    .filter((candidate) => candidate.weekday === date.dayOfWeek)
    .sort((left, right) => left.start.localeCompare(right.start))[0];
  if (!shift) return null;
  const startTime = Temporal.PlainTime.from(shift.start);
  const endTime = Temporal.PlainTime.from(shift.end);
  const start = date
    .toPlainDateTime(startTime)
    .toZonedDateTime(calendar.timezone, { disambiguation: "later" });
  let endDate = date;
  if (Temporal.PlainTime.compare(endTime, startTime) <= 0) {
    endDate = date.add({ days: 1 });
  }
  const end = endDate
    .toPlainDateTime(endTime)
    .toZonedDateTime(calendar.timezone, { disambiguation: "later" });
  return {
    startIso: start.toInstant().toString(),
    endIso: end.toInstant().toString(),
  };
}

function query(values: Record<string, string>) {
  return new URLSearchParams(values).toString();
}

function queryEntries(values: [string, string][]) {
  return new URLSearchParams(values).toString();
}

export async function loadOwnerStationData(input: {
  accessToken: string;
  factoryId: string;
  timezone: string;
  stationId?: string;
  assignmentId?: string;
  selectedDate?: string;
}): Promise<
  | { kind: "ready"; data: OwnerStationData }
  | { kind: "no_stations" }
  | { kind: "no_assignment"; stationName: string }
> {
  const stations = await ownerRestAll<StationRow>(
    input.accessToken,
    `stations?${query({
      factory_id: `eq.${input.factoryId}`,
      select: "id,alias,status",
      order: "alias.asc,id.asc",
    })}`,
  );
  if (stations.length === 0) return { kind: "no_stations" };
  const station =
    stations.find((candidate) => candidate.id === input.stationId)
    ?? stations[0];
  const date = validDate(input.selectedDate, input.timezone);
  const day = civilDayWindow(date, input.timezone);
  const assignments = await ownerRestAll<AssignmentRow>(
    input.accessToken,
    `owner_project_station_assignments?${query({
      factory_id: `eq.${input.factoryId}`,
      station_id: `eq.${station.id}`,
      effective_start: `lt.${day.endIso}`,
      or: `(effective_end.is.null,effective_end.gt.${day.startIso})`,
      select:
        "id,project_id,station_id,effective_start,effective_end",
      order: "effective_start.desc,id.asc",
    })}`,
  );
  if (assignments.length === 0) {
    return { kind: "no_assignment", stationName: station.alias };
  }
  const projectIds = [...new Set(assignments.map((row) => row.project_id))];
  const projects = await ownerRestAll<ProjectRow>(
    input.accessToken,
    `owner_projects?${query({
      factory_id: `eq.${input.factoryId}`,
      id: `in.(${projectIds.join(",")})`,
      select:
        "id,name,target_units,start_at,deadline,shift_calendar,status",
      order: "id.asc",
    })}`,
  );
  const projectById = new Map(projects.map((project) => [project.id, project]));
  const candidates = assignments.flatMap((assignment) => {
    const project = projectById.get(assignment.project_id);
    if (!project || project.shift_calendar.timezone !== input.timezone) return [];
    const shiftWindow = selectedShiftWindow(date, project.shift_calendar);
    if (!shiftWindow) return [];
    const assignmentStart = Date.parse(assignment.effective_start);
    const assignmentEnd = assignment.effective_end
      ? Date.parse(assignment.effective_end)
      : Number.POSITIVE_INFINITY;
    const shiftStart = Date.parse(shiftWindow.startIso);
    const shiftEnd = Date.parse(shiftWindow.endIso);
    if (
      Number.isFinite(assignmentStart)
      && assignmentEnd > shiftStart
      && assignmentStart < shiftEnd
    ) {
      const selectedStart = Math.max(assignmentStart, shiftStart);
      const selectedEnd = Math.min(assignmentEnd, shiftEnd);
      return [
        {
          assignment,
          project,
          shiftWindow: {
            startIso: new Date(selectedStart).toISOString(),
            endIso: new Date(selectedEnd).toISOString(),
          },
        },
      ];
    }
    return [];
  }).sort(
    (left, right) =>
      Date.parse(left.shiftWindow.startIso) - Date.parse(right.shiftWindow.startIso),
  );
  const nowMs = Date.now();
  const requested = candidates.find(
    (candidate) => candidate.assignment.id === input.assignmentId,
  );
  const selected =
    requested
    ?? candidates.find((candidate) => {
      const start = Date.parse(candidate.shiftWindow.startIso);
      const end = Date.parse(candidate.shiftWindow.endIso);
      return nowMs >= start && nowMs < end;
    })
    ?? candidates[0];
  if (!selected) {
    return { kind: "no_assignment", stationName: station.alias };
  }
  const { project, shiftWindow } = selected;
  const totalScheduledMs = workedMillisecondsBetween(
    project.start_at,
    project.deadline,
    project.shift_calendar,
    [],
  );
  const requiredUnitsPerHour =
    totalScheduledMs > 0
      ? project.target_units / (totalScheduledMs / 3_600_000)
      : null;
  const common = {
    factory_id: `eq.${input.factoryId}`,
    station_id: `eq.${station.id}`,
  };
  const [
    verificationRows,
    eventRows,
    workerRows,
    workerIntervals,
    downtimeRows,
    adjustmentRows,
  ] = await Promise.all([
    ownerRestAll<
      Parameters<typeof buildOwnerStationData>[0]["verificationRows"][number]
    >(
      input.accessToken,
      `owner_verification_intervals?${query({
        ...common,
        source_start_at: `lt.${shiftWindow.endIso}`,
        source_end_at: `gt.${shiftWindow.startIso}`,
        select:
          "id,chunk_id,revision,source_start_at,source_end_at,status",
        order: "source_start_at.asc,id.asc",
      })}`,
    ),
    ownerRpc<Parameters<typeof buildOwnerStationData>[0]["eventRows"]>(
      input.accessToken,
      "owner_station_event_buckets",
      {
        p_factory_id: input.factoryId,
        p_station_id: station.id,
        p_project_id: project.id,
        p_window_start: shiftWindow.startIso,
        p_window_end: shiftWindow.endIso,
      },
    ),
    ownerRestAll<WorkerRow>(
      input.accessToken,
      `owner_workers?${query({
        factory_id: `eq.${input.factoryId}`,
        select: "id,display_name,employee_code,primary_role,status",
        order: "display_name.asc,id.asc",
      })}`,
    ),
    ownerRestAll<WorkerIntervalRow>(
      input.accessToken,
      `owner_worker_station_intervals?${query({
        ...common,
        project_id: `eq.${project.id}`,
        effective_start: `lt.${shiftWindow.endIso}`,
        or: `(effective_end.is.null,effective_end.gt.${shiftWindow.startIso})`,
        select:
          "id,worker_id,station_id,project_id,effective_start,effective_end,loaded_labor_rate_cents_per_hour,source",
        order: "effective_start.asc,id.asc",
      })}`,
    ),
    ownerRestAll<Parameters<typeof buildOwnerStationData>[0]["downtimeRows"][number]>(
      input.accessToken,
      `owner_station_downtime_intervals?${query({
        ...common,
        project_id: `eq.${project.id}`,
        effective_start: `lt.${shiftWindow.endIso}`,
        effective_end: `gt.${shiftWindow.startIso}`,
        select: "id,effective_start,effective_end",
        order: "effective_start.asc,id.asc",
      })}`,
    ),
    ownerRestAll<
      Parameters<typeof buildOwnerStationData>[0]["adjustmentRows"][number]
    >(
      input.accessToken,
      `owner_output_adjustments?${queryEntries([
        ...Object.entries(common),
        ["project_id", `eq.${project.id}`],
        ["occurred_at", `gte.${shiftWindow.startIso}`],
        ["occurred_at", `lt.${shiftWindow.endIso}`],
        ["select", "id,kind,delta_good_units,occurred_at"],
        ["order", "occurred_at.asc,id.asc"],
      ])}`,
    ),
  ]);

  return {
    kind: "ready",
    data: buildOwnerStationData({
      factoryId: input.factoryId,
      timezone: input.timezone,
      selectedDate: date.toString(),
      station: { id: station.id, name: station.alias, status: station.status },
      stationOptions: stations.map((candidate) => ({
        id: candidate.id,
        name: candidate.alias,
      })),
      project: { id: project.id, name: project.name },
      projectAssignmentKnown: true,
      windowStartIso: shiftWindow.startIso,
      windowEndIso: shiftWindow.endIso,
      requiredUnitsPerHour,
      verificationRows,
      eventRows,
      workerRows,
      workerIntervals,
      downtimeRows,
      adjustmentRows,
      nowIso: Temporal.Now.instant().toString(),
      imageSrc: null,
      evidenceLabel: "No owner-safe evidence image attached",
      cycleTimeSeconds: null,
      assignmentId: selected.assignment.id,
      shiftOptions: candidates.map((candidate) => ({
        id: candidate.assignment.id,
        label: `${new Intl.DateTimeFormat("en-US", {
          timeZone: input.timezone,
          hour: "numeric",
          minute: "2-digit",
        }).format(new Date(candidate.shiftWindow.startIso))}–${new Intl.DateTimeFormat(
          "en-US",
          {
            timeZone: input.timezone,
            hour: "numeric",
            minute: "2-digit",
          },
        ).format(new Date(candidate.shiftWindow.endIso))} · ${candidate.project.name}`,
      })),
    }),
  };
}

export async function loadOwnerWorkforceData(input: {
  accessToken: string;
  factoryId: string;
  timezone: string;
}): Promise<OwnerWorkforceData> {
  const date = validDate(undefined, input.timezone);
  const window = civilDayWindow(date, input.timezone);
  const [workers, intervals, stations, projects] = await Promise.all([
    ownerRestAll<WorkerRow>(
      input.accessToken,
      `owner_workers?${query({
        factory_id: `eq.${input.factoryId}`,
        select: "id,display_name,employee_code,primary_role,status",
        order: "display_name.asc,id.asc",
      })}`,
    ),
    ownerRestAll<WorkerIntervalRow>(
      input.accessToken,
      `owner_worker_station_intervals?${query({
        factory_id: `eq.${input.factoryId}`,
        effective_start: `lt.${window.endIso}`,
        or: `(effective_end.is.null,effective_end.gt.${window.startIso})`,
        select:
          "id,worker_id,station_id,project_id,effective_start,effective_end,loaded_labor_rate_cents_per_hour,source",
        order: "effective_start.asc,id.asc",
      })}`,
    ),
    ownerRestAll<StationRow>(
      input.accessToken,
      `stations?${query({
        factory_id: `eq.${input.factoryId}`,
        select: "id,alias,status",
        order: "alias.asc,id.asc",
      })}`,
    ),
    ownerRestAll<ProjectRow>(
      input.accessToken,
      `owner_projects?${query({
        factory_id: `eq.${input.factoryId}`,
        status: "in.(open,paused)",
        select:
          "id,name,target_units,start_at,deadline,shift_calendar,status",
        order: "id.asc",
      })}`,
    ),
  ]);
  return buildOwnerWorkforceData({
    factoryId: input.factoryId,
    workers,
    intervals,
    stationNames: Object.fromEntries(
      stations.map((station) => [station.id, station.alias]),
    ),
    projectNames: Object.fromEntries(
      projects.map((project) => [project.id, project.name]),
    ),
    windowStartIso: window.startIso,
    windowEndIso: window.endIso,
    timezone: input.timezone,
  });
}
