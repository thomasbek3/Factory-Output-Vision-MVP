import { Temporal } from "@js-temporal/polyfill";
import type {
  OwnerAttentionItem,
  OwnerDashboardData,
  OwnerProjectSummary,
  OwnerStationSummary,
} from "@/lib/ownerDashboardTypes";
import {
  apportionLaborCents,
  evaluatePace,
  mergeIntervals,
  projectDirectCostMargin,
  scheduledWorkIntervals,
  workedMillisecondsBetween,
  type ShiftCalendar,
} from "@/lib/ownerEconomics";

type DurableProject = {
  id: string;
  name: string;
  client: string;
  target_units: number;
  deadline: string;
  status?: string;
  start_at?: string;
  shift_calendar?: ShiftCalendar;
  unit_value_cents?: number;
  unit_material_cost_cents?: number;
  loaded_labor_rate_cents_per_hour?: number;
  target_margin_bps?: number | null;
};

export type OwnerDashboardTruth = {
  assignments: {
    project_id: string;
    station_id: string;
    effective_start: string;
    effective_end: string | null;
  }[];
  events: {
    project_id?: string;
    station_id: string;
    chunk_id?: string;
    occurred_at: string;
    good_units?: number;
    recent_good_units?: number;
    verified?: boolean;
  }[];
  verifications: {
    station_id: string;
    chunk_id: string;
    revision: number;
    source_start_at: string;
    source_end_at: string;
    status: string;
  }[];
  workerIntervals: {
    project_id: string;
    station_id: string;
    effective_start: string;
    effective_end: string | null;
    loaded_labor_rate_cents_per_hour: number;
  }[];
  downtime: {
    project_id: string;
    station_id: string;
    effective_start: string;
    effective_end: string;
  }[];
  adjustments: {
    project_id: string;
    station_id: string | null;
    delta_good_units: number;
    occurred_at: string;
  }[];
};

function validTimezone(timezone: string) {
  try {
    Temporal.Instant.from("2026-01-01T00:00:00Z").toZonedDateTimeISO(timezone);
    return timezone;
  } catch {
    return null;
  }
}

function deadlineLabel(deadline: string, timezone: string | null) {
  if (!timezone || typeof deadline !== "string" || !deadline.trim()) {
    return "Deadline unavailable";
  }
  try {
    const zoned = /^\d{4}-\d{2}-\d{2}$/.test(deadline)
      ? Temporal.PlainDate.from(deadline).toZonedDateTime({
          timeZone: timezone,
          plainTime: Temporal.PlainTime.from("12:00"),
        })
      : Temporal.Instant.from(deadline).toZonedDateTimeISO(timezone);
    return new Intl.DateTimeFormat("en", {
      timeZone: timezone,
      weekday: "short",
      month: "short",
      day: "numeric",
    }).format(new Date(zoned.epochMilliseconds));
  } catch {
    return "Deadline unavailable";
  }
}

function timeLabel(iso: string, timezone: string) {
  return new Intl.DateTimeFormat("en", {
    timeZone: timezone,
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(iso));
}

function parsed(value: string | null | undefined) {
  const result = value ? Date.parse(value) : Number.NaN;
  return Number.isFinite(result) ? result : null;
}

function eventUnits(event: OwnerDashboardTruth["events"][number]) {
  return Number.isSafeInteger(event.good_units) && (event.good_units ?? 0) >= 0
    ? event.good_units ?? 0
    : 1;
}

function recentEventUnits(event: OwnerDashboardTruth["events"][number]) {
  return Number.isSafeInteger(event.recent_good_units)
    && (event.recent_good_units ?? 0) >= 0
    ? event.recent_good_units ?? 0
    : 0;
}

function assignmentContains(
  assignment: OwnerDashboardTruth["assignments"][number],
  at: number,
) {
  const start = parsed(assignment.effective_start);
  const end = parsed(assignment.effective_end) ?? Number.POSITIVE_INFINITY;
  return start !== null && start <= at && at < end;
}

function latestVerifications(
  rows: OwnerDashboardTruth["verifications"],
) {
  const byChunk = new Map<string, OwnerDashboardTruth["verifications"][number]>();
  for (const row of rows) {
    const current = byChunk.get(row.chunk_id);
    if (!current || row.revision > current.revision) byChunk.set(row.chunk_id, row);
  }
  return [...byChunk.values()];
}

const AGGREGATE_BUCKET_MS = 15 * 60 * 1_000;

function aggregateBucketOverlapsVerification(
  event: OwnerDashboardTruth["events"][number],
  verifications: OwnerDashboardTruth["verifications"],
) {
  if (!event.project_id || event.verified !== true) return false;
  const bucketStart = parsed(event.occurred_at);
  if (bucketStart === null) return false;
  const bucketEnd = bucketStart + AGGREGATE_BUCKET_MS;
  return verifications.some((verification) => {
    const verificationStart = parsed(verification.source_start_at);
    const verificationEnd = parsed(verification.source_end_at);
    return (
      verification.status === "verified"
      && verification.station_id === event.station_id
      && verificationStart !== null
      && verificationEnd !== null
      && bucketStart < verificationEnd
      && bucketEnd > verificationStart
    );
  });
}

function timestampAtWorkedFraction(input: {
  startMs: number;
  endMs: number;
  fraction: number;
  calendar: ShiftCalendar;
  downtime: { startMs: number; endMs: number }[];
}) {
  if (input.endMs <= input.startMs) return input.startMs;
  const startIso = new Date(input.startMs).toISOString();
  const endIso = new Date(input.endMs).toISOString();
  const totalWorkedMs = workedMillisecondsBetween(
    startIso,
    endIso,
    input.calendar,
    input.downtime,
  );
  if (totalWorkedMs <= 0) {
    return Math.round(
      input.startMs + (input.endMs - input.startMs) * input.fraction,
    );
  }
  const targetWorkedMs = totalWorkedMs * input.fraction;
  let low = input.startMs;
  let high = input.endMs;
  for (let iteration = 0; iteration < 48 && high - low > 1_000; iteration += 1) {
    const middle = Math.floor((low + high) / 2);
    const worked = workedMillisecondsBetween(
      startIso,
      new Date(middle).toISOString(),
      input.calendar,
      input.downtime,
    );
    if (worked < targetWorkedMs) low = middle + 1;
    else high = middle;
  }
  return high;
}

function truthForProject(input: {
  project: DurableProject;
  truth: OwnerDashboardTruth;
  nowMs: number;
  lagThresholdMs: number;
  timezone: string;
}) {
  const { project, truth, nowMs, lagThresholdMs, timezone } = input;
  const startAt = project.start_at;
  const calendar = project.shift_calendar;
  const startMs = parsed(startAt);
  const deadlineMs = parsed(project.deadline);
  if (
    startMs === null
    || deadlineMs === null
    || !startAt
    || !calendar
    || project.unit_value_cents === undefined
    || project.unit_material_cost_cents === undefined
  ) return null;
  const assignments = truth.assignments.filter(
    (row) => row.project_id === project.id,
  );
  if (assignments.length === 0) return null;
  const verifications = latestVerifications(truth.verifications);
  const verifiedByChunk = new Map(
    verifications.map((row) => [row.chunk_id, row]),
  );
  const projectEvents = truth.events.filter((event) => {
    const occurredAt = parsed(event.occurred_at);
    if (event.project_id) {
      return (
        event.project_id === project.id
        && aggregateBucketOverlapsVerification(event, verifications)
        && occurredAt !== null
      );
    }
    if (!event.chunk_id) return false;
    const verification = verifiedByChunk.get(event.chunk_id);
    if (
      occurredAt === null
      || verification?.status !== "verified"
      || verification.station_id !== event.station_id
    ) return false;
    const verificationStart = parsed(verification.source_start_at);
    const verificationEnd = parsed(verification.source_end_at);
    return (
      verificationStart !== null
      && verificationEnd !== null
      && occurredAt >= verificationStart
      && occurredAt < verificationEnd
      && assignments.some(
        (assignment) =>
          assignment.station_id === event.station_id
          && assignmentContains(assignment, occurredAt),
      )
    );
  });
  const verifiedIntervals = verifications.flatMap((row) => {
    if (row.status !== "verified") return [];
    const start = parsed(row.source_start_at);
    const end = parsed(row.source_end_at);
    return start === null || end === null ? [] : [{ row, startMs: start, endMs: end }];
  });
  const projectDowntimeRows = truth.downtime.filter(
    (row) => row.project_id === project.id,
  );
  const candidateAdjustments = truth.adjustments
    .filter((row) => row.project_id === project.id)
    .filter((row) => {
      const occurredAt = parsed(row.occurred_at);
      if (occurredAt === null) return false;
      if (row.station_id === null) return true;
      return verifiedIntervals.some(
        (interval) =>
          interval.row.station_id === row.station_id
          && occurredAt >= interval.startMs
          && occurredAt < interval.endMs,
      ) && assignments.some(
        (assignment) =>
          assignment.station_id === row.station_id
          && assignmentContains(assignment, occurredAt),
      );
    });
  const blockers: {
    frontierMs: number;
    laterVerifiedStartMs: number | null;
    laterVerifiedThroughMs: number | null;
  }[] = [];
  const completedFrontiers: number[] = [];
  for (const assignment of assignments) {
    const assignmentStart = Math.max(
      startMs,
      parsed(assignment.effective_start) ?? startMs,
    );
    const assignmentEnd = Math.min(
      nowMs,
      parsed(assignment.effective_end) ?? nowMs,
    );
    if (assignmentEnd <= assignmentStart) continue;
    const assignmentDowntime = projectDowntimeRows
      .filter((row) => row.station_id === assignment.station_id)
      .flatMap((row) => {
        const start = parsed(row.effective_start);
        const end = parsed(row.effective_end);
        return start === null || end === null
          ? []
          : [{ startMs: start, endMs: end }];
      });
    const required = scheduledWorkIntervals(
      new Date(assignmentStart).toISOString(),
      new Date(assignmentEnd).toISOString(),
      calendar,
      assignmentDowntime,
    );
    const coverage = mergeIntervals(
      verifiedIntervals
        .filter((row) => row.row.station_id === assignment.station_id)
        .map((row) => ({
          startMs: Math.max(assignmentStart, row.startMs),
          endMs: Math.min(assignmentEnd, row.endMs),
        })),
    );
    let blocked = false;
    for (const requiredInterval of required) {
      let frontier = requiredInterval.startMs;
      for (const interval of coverage) {
        if (
          interval.endMs <= requiredInterval.startMs
          || interval.startMs >= requiredInterval.endMs
        ) continue;
        if (interval.startMs > frontier + 1_000) break;
        frontier = Math.max(
          frontier,
          Math.min(requiredInterval.endMs, interval.endMs),
        );
        if (frontier >= requiredInterval.endMs) break;
      }
      if (frontier < requiredInterval.endMs) {
        const laterScheduledCoverage = required.flatMap((scheduled) =>
          coverage.flatMap((interval) => {
            const overlapStart = Math.max(
              scheduled.startMs,
              interval.startMs,
              frontier + 1_001,
            );
            const overlapEnd = Math.min(scheduled.endMs, interval.endMs);
            return overlapEnd > overlapStart
              ? [{ startMs: overlapStart, endMs: overlapEnd }]
              : [];
          }));
        blockers.push({
          frontierMs: frontier,
          laterVerifiedStartMs:
            laterScheduledCoverage.length > 0
              ? Math.min(...laterScheduledCoverage.map((row) => row.startMs))
              : null,
          laterVerifiedThroughMs:
            laterScheduledCoverage.length > 0
              ? Math.max(...laterScheduledCoverage.map((row) => row.endMs))
              : null,
        });
        blocked = true;
        break;
      }
      completedFrontiers.push(requiredInterval.endMs);
    }
    if (!blocked && required.length > 0) {
      completedFrontiers.push(required.at(-1)?.endMs ?? assignmentStart);
    }
  }
  const verifiedThroughMs =
    blockers.length > 0
      ? Math.min(...blockers.map((blocker) => blocker.frontierMs))
      : completedFrontiers.length > 0
        ? Math.max(...completedFrontiers)
        : startMs;
  const gapBlocker = blockers
    .filter((blocker) => blocker.laterVerifiedStartMs !== null)
    .sort((left, right) => left.frontierMs - right.frontierMs)[0] ?? null;
  const verificationGap = gapBlocker
    ? {
        startLabel: timeLabel(
          new Date(gapBlocker.frontierMs).toISOString(),
          timezone,
        ),
        verifiedAfterLabel: timeLabel(
          new Date(
            gapBlocker.laterVerifiedThroughMs
              ?? gapBlocker.laterVerifiedStartMs
              ?? gapBlocker.frontierMs,
          ).toISOString(),
          timezone,
        ),
      }
    : null;
  if (verifiedThroughMs <= startMs) {
    const scheduledWorkElapsed = workedMillisecondsBetween(
      startAt,
      new Date(nowMs).toISOString(),
      calendar,
      [],
    );
    if (!verificationGap && scheduledWorkElapsed === 0) {
      return {
        pace: {
          status: "ON_TRACK" as const,
          expectedUnits: 0,
          requiredUnitsPerHour: null,
        },
        verifiedGoodUnits: 0,
        projectedMarginBps: null,
        recoverySummary: "No scheduled production has elapsed",
        verifiedThroughIso: null,
        verifiedThroughLabel: "No scheduled work yet",
        verificationGap: null,
        chart: null,
      };
    }
    return verificationGap
      ? {
          pace: {
            status: "DATA_DELAY" as const,
            expectedUnits: null,
            requiredUnitsPerHour: null,
          },
          verifiedGoodUnits: null,
          projectedMarginBps: null,
          recoverySummary: "Verification gap in scheduled footage",
          verifiedThroughIso: null,
          verifiedThroughLabel: "No contiguous verified coverage",
          verificationGap,
          chart: null,
        }
      : null;
  }
  const verifiedProjectEvents = projectEvents.filter(
    (event) => (parsed(event.occurred_at) ?? Number.POSITIVE_INFINITY) < verifiedThroughMs,
  );
  const verifiedAdjustments = candidateAdjustments.filter(
    (row) => (parsed(row.occurred_at) ?? Number.POSITIVE_INFINITY) < verifiedThroughMs,
  );
  const adjustmentUnits = verifiedAdjustments.reduce(
    (sum, row) => sum + row.delta_good_units,
    0,
  );
  const verifiedGoodUnits = Math.max(
    0,
    verifiedProjectEvents.reduce((sum, event) => sum + eventUnits(event), 0)
      + adjustmentUnits,
  );
  const plannedWorkedMs = workedMillisecondsBetween(
    startAt,
    project.deadline,
    calendar,
    [],
  );
  const verifiedThroughIso = new Date(verifiedThroughMs).toISOString();
  const verifiedWorkedMs = workedMillisecondsBetween(
    startAt,
    verifiedThroughIso,
    calendar,
    [],
  );
  const remainingWorkedMs =
    verifiedThroughMs < deadlineMs
      ? workedMillisecondsBetween(
          verifiedThroughIso,
          project.deadline,
          calendar,
          [],
        )
      : 0;
  const pace = verificationGap
    ? {
        status: "DATA_DELAY" as const,
        expectedUnits: null,
        requiredUnitsPerHour: null,
      }
    : evaluatePace({
        targetUnits: project.target_units,
        goodUnits: verifiedGoodUnits,
        plannedWorkedMs,
        verifiedWorkedMs,
        remainingWorkedMs,
        verificationLagMs: workedMillisecondsBetween(
          verifiedThroughIso,
          new Date(nowMs).toISOString(),
          calendar,
          [],
        ),
        verificationLagThresholdMs: lagThresholdMs,
      });
  const laborSchedule = scheduledWorkIntervals(
    startAt,
    verifiedThroughIso,
    calendar,
    [],
  );
  const laborIntervals = truth.workerIntervals
    .filter((row) => row.project_id === project.id)
    .flatMap((row) => {
      const rowStart = parsed(row.effective_start);
      const rowEnd = parsed(row.effective_end) ?? verifiedThroughMs;
      if (rowStart === null) return [];
      return laborSchedule.flatMap((scheduled) => {
        const clippedStart = Math.max(startMs, rowStart, scheduled.startMs);
        const clippedEnd = Math.min(
          verifiedThroughMs,
          rowEnd,
          scheduled.endMs,
        );
        return clippedEnd > clippedStart
          ? [{
              stationId: row.station_id,
              rateCentsPerHour: row.loaded_labor_rate_cents_per_hour,
              startMs: clippedStart,
              endMs: clippedEnd,
            }]
          : [];
      });
    });
  const laborBurnedCents = apportionLaborCents(laborIntervals).projectCents;
  const laborRateAvailable =
    (project.loaded_labor_rate_cents_per_hour ?? 0) > 0
    || truth.workerIntervals.some(
      (row) =>
        row.project_id === project.id
        && row.loaded_labor_rate_cents_per_hour > 0,
    );
  const margin = projectDirectCostMargin({
    targetUnits: project.target_units,
    verifiedGoodUnits,
    unitValueCents: project.unit_value_cents,
    unitMaterialCostCents: project.unit_material_cost_cents,
    laborBurnedCents,
    verifiedWorkedMs,
    remainingWorkedMs,
  });
  const projectedRevenueCents =
    margin.projectedUnits === null
      ? null
      : margin.projectedUnits * project.unit_value_cents;
  const projectedMarginBps =
    !laborRateAvailable
    || margin.projectedMarginCents === null
    || projectedRevenueCents === null
    || projectedRevenueCents <= 0
      ? null
      : Math.round((margin.projectedMarginCents * 10_000) / projectedRevenueCents);
  const recoverySummary =
    verificationGap
      ? "Verification gap in scheduled footage"
      : pace.status === "DATA_DELAY"
      ? "Waiting for contiguous verified coverage"
      : pace.status === "BEHIND" && pace.requiredUnitsPerHour !== null
        ? `Need ${pace.requiredUnitsPerHour.toFixed(1)} units/hour to recover`
        : pace.status === "BEHIND"
          ? nowMs >= deadlineMs
            ? `Deadline missed by ${Math.max(
                0,
                project.target_units - verifiedGoodUnits,
              )} units`
            : `No scheduled production time remains; ${Math.max(
                0,
                project.target_units - verifiedGoodUnits,
              )} units short`
        : pace.status === "AHEAD"
          ? "Ahead of required pace"
          : "On pace to meet deadline";
  const chart =
    !verificationGap
    && verifiedThroughMs > startMs
    && verifiedThroughMs < deadlineMs
      ? (() => {
          const anchors = [
            startMs,
            timestampAtWorkedFraction({
              startMs,
              endMs: verifiedThroughMs,
              fraction: 0.5,
              calendar,
              downtime: [],
            }),
            verifiedThroughMs,
            timestampAtWorkedFraction({
              startMs: verifiedThroughMs,
              endMs: deadlineMs,
              fraction: 0.5,
              calendar,
              downtime: [],
            }),
            deadlineMs,
          ];
          const actual = anchors.slice(0, 3).map((anchor) =>
            Math.max(
              0,
              verifiedProjectEvents
                .filter(
                  (event) =>
                    (parsed(event.occurred_at) ?? Number.POSITIVE_INFINITY)
                      <= anchor,
                )
                .reduce((sum, event) => sum + eventUnits(event), 0)
                + verifiedAdjustments
                  .filter(
                    (adjustment) =>
                      (parsed(adjustment.occurred_at)
                        ?? Number.POSITIVE_INFINITY) <= anchor,
                  )
                  .reduce((sum, adjustment) => sum + adjustment.delta_good_units, 0),
            ));
          const required = anchors.map((anchor) => {
            const workedMs = workedMillisecondsBetween(
              startAt,
              new Date(anchor).toISOString(),
              calendar,
              [],
            );
            return plannedWorkedMs > 0
              ? Math.round((project.target_units * workedMs) / plannedWorkedMs)
              : 0;
          });
          return {
            actual,
            required,
            requiredToRecover:
              pace.status === "BEHIND"
                ? [
                    verifiedGoodUnits,
                    Math.round((verifiedGoodUnits + project.target_units) / 2),
                    project.target_units,
                  ]
                : [],
            labels: anchors.map((anchor) =>
              new Intl.DateTimeFormat("en", {
                timeZone: timezone,
                month: "short",
                day: "numeric",
                hour: "numeric",
              }).format(new Date(anchor))),
            nowIndex: 2,
          };
        })()
      : null;
  return {
    pace,
    verifiedGoodUnits,
    projectedMarginBps: verificationGap ? null : projectedMarginBps,
    recoverySummary,
    verifiedThroughIso,
    verifiedThroughLabel: timeLabel(verifiedThroughIso, timezone),
    verificationGap,
    chart,
  };
}

export function ownerDashboardFromDurableProjects(input: {
  factoryId: string;
  timezone: string;
  nowIso: string;
  projects: DurableProject[];
  stations: {
    id: string;
    alias: string;
    status: string;
  }[];
  verificationLagThresholdMinutes?: number;
  truth?: OwnerDashboardTruth;
}): OwnerDashboardData {
  const timezone = validTimezone(input.timezone);
  const nowMs = parsed(input.nowIso);
  const lagThresholdMinutes =
    Number.isInteger(input.verificationLagThresholdMinutes)
    && (input.verificationLagThresholdMinutes ?? 0) > 0
      ? input.verificationLagThresholdMinutes ?? 30
      : 30;
  const projectTruth = new Map(
    input.projects.map((project) => [
      project.id,
      timezone && nowMs !== null && input.truth
        ? truthForProject({
            project,
            truth: input.truth,
            nowMs,
            lagThresholdMs: lagThresholdMinutes * 60_000,
            timezone,
          })
        : null,
    ]),
  );
  const projects: OwnerProjectSummary[] = input.projects.map(
    (project): OwnerProjectSummary => {
    const truth = projectTruth.get(project.id);
    if (!truth) {
      return {
        id: project.id,
        name: project.name,
        client: project.client,
        status: "DATA_DELAY" as const,
        verifiedGoodUnits: null,
        targetUnits: project.target_units,
        recoverySummary: "Waiting for contiguous verified coverage",
        projectedMarginBps: null,
        projectedMarginStatus: "unavailable" as const,
        deadlineLabel: deadlineLabel(project.deadline, timezone),
        verifiedThroughLabel: "Not yet available",
        verificationGap: null,
        chart: null,
      };
    }
    const projectedMarginStatus: OwnerProjectSummary["projectedMarginStatus"] =
      truth.projectedMarginBps === null
        ? "unavailable"
        : truth.projectedMarginBps < 0
          ? "loss"
          : project.target_margin_bps !== null
            && project.target_margin_bps !== undefined
            && truth.projectedMarginBps < project.target_margin_bps
            ? "at_risk"
            : "healthy";
    return {
      id: project.id,
      name: project.name,
      client: project.client,
      status: truth.pace.status as OwnerProjectSummary["status"],
      verifiedGoodUnits: truth.verifiedGoodUnits,
      targetUnits: project.target_units,
      recoverySummary: truth.recoverySummary,
      projectedMarginBps: truth.projectedMarginBps,
      projectedMarginStatus,
      deadlineLabel: deadlineLabel(project.deadline, timezone),
      verifiedThroughLabel: truth.verifiedThroughLabel,
      verificationGap: truth.verificationGap,
      chart: truth.chart,
    };
    },
  );
  const latest = input.truth ? latestVerifications(input.truth.verifications) : [];
  const latestByChunk = new Map(latest.map((row) => [row.chunk_id, row]));
  const attention: OwnerAttentionItem[] = [];
  for (const project of projects) {
    if (project.verificationGap) {
      attention.push({
        id: `verification-gap-${project.id}`,
        tone: "bad",
        kind: "verification_gap",
        title: "Verification gap",
        detail: `${project.name} has missing scheduled footage after ${project.verificationGap.startLabel}`,
        meta: `Later footage is verified through ${project.verificationGap.verifiedAfterLabel}`,
        href: "/alerts?kind=verification_gap",
      });
      continue;
    }
    if (project.status === "DATA_DELAY") {
      attention.push({
        id: `verification-${project.id}`,
        tone: "warn",
        kind: "verification",
        title: "Verification pending",
        detail: `${project.name} is waiting for contiguous coverage`,
        meta: "No estimate substituted",
        href: "/alerts?kind=verification",
      });
      continue;
    }
    if (project.status === "BEHIND") {
      attention.push({
        id: `pace-${project.id}`,
        tone: "bad",
        kind: "pace",
        title: "Project behind pace",
        detail: project.name,
        meta: project.recoverySummary,
        href: `/projects?project_id=${encodeURIComponent(project.id)}`,
      });
    }
  }
  const stations: OwnerStationSummary[] = input.stations.map((station) => {
    const stationAssignments = input.truth?.assignments
      .filter((row) => row.station_id === station.id)
      .sort(
        (left, right) =>
          (parsed(right.effective_start) ?? 0)
          - (parsed(left.effective_start) ?? 0),
      ) ?? [];
    const assignment = nowMs === null
      ? stationAssignments[0]
      : stationAssignments.find((row) => assignmentContains(row, nowMs))
        ?? stationAssignments[0];
    const project = projects.find((row) => row.id === assignment?.project_id);
    const truthProject = input.projects.find(
      (row) => row.id === assignment?.project_id,
    );
    const windowStart = nowMs === null ? null : nowMs - 3_600_000;
    const intervals =
      windowStart === null || !assignment || !truthProject
        ? []
        : mergeIntervals(
            latest
              .filter(
                (row) =>
                  row.station_id === station.id && row.status === "verified",
              )
              .flatMap((row) => {
                const start = parsed(row.source_start_at);
                const end = parsed(row.source_end_at);
                const assignmentStart = parsed(assignment.effective_start);
                const assignmentEnd =
                  parsed(assignment.effective_end)
                  ?? (nowMs ?? Number.POSITIVE_INFINITY);
                return (
                  start === null
                  || end === null
                  || assignmentStart === null
                )
                  ? []
                  : [{
                      startMs: Math.max(windowStart, start, assignmentStart),
                      endMs: Math.min(nowMs ?? end, end, assignmentEnd),
                    }];
              }),
          );
    const coverageMs = intervals.reduce(
      (sum, interval) => sum + Math.max(0, interval.endMs - interval.startMs),
      0,
    );
    const verifiedEvents =
      windowStart === null || !input.truth
        ? []
        : input.truth.events.filter((event) => {
            const occurredAt = parsed(event.occurred_at);
            if (event.project_id) {
              return (
                occurredAt !== null
                && event.station_id === station.id
                && event.project_id === truthProject?.id
                && event.verified === true
                && recentEventUnits(event) > 0
                && assignment?.project_id === truthProject?.id
              );
            }
            if (!event.chunk_id) return false;
            const verification = latestByChunk.get(event.chunk_id);
            const verificationStart = parsed(verification?.source_start_at);
            const verificationEnd = parsed(verification?.source_end_at);
            return (
              occurredAt !== null
              && occurredAt >= windowStart
              && occurredAt < (nowMs ?? occurredAt)
              && event.station_id === station.id
              && verification?.status === "verified"
              && verificationStart !== null
              && verificationEnd !== null
              && occurredAt >= verificationStart
              && occurredAt < verificationEnd
              && assignment?.project_id === truthProject?.id
              && assignmentContains(assignment, occurredAt)
            );
          });
    const verifiedUnits = verifiedEvents.reduce(
      (sum, event) =>
        sum + (event.project_id ? recentEventUnits(event) : eventUnits(event)),
      0,
    );
    const laborRateAvailable =
      (truthProject?.loaded_labor_rate_cents_per_hour ?? 0) > 0
      || (
        input.truth?.workerIntervals.some(
          (row) =>
            row.project_id === truthProject?.id
            && row.station_id === station.id
            && row.loaded_labor_rate_cents_per_hour > 0,
        ) ?? false
      );
    const laborHours =
      windowStart === null || !input.truth || !truthProject
        ? 0
        : input.truth.workerIntervals
            .filter(
              (row) =>
                row.project_id === truthProject.id
                && row.station_id === station.id,
            )
            .reduce((sum, row) => {
              const rowStart = Math.max(
                windowStart,
                parsed(row.effective_start) ?? windowStart,
              );
              const rowEnd = Math.min(
                nowMs ?? windowStart,
                parsed(row.effective_end) ?? (nowMs ?? windowStart),
              );
              const verifiedLaborMs = intervals.reduce(
                (total, interval) =>
                  total
                  + Math.max(
                    0,
                    Math.min(rowEnd, interval.endMs)
                      - Math.max(rowStart, interval.startMs),
                  ),
                0,
              );
              return sum + verifiedLaborMs / 3_600_000;
            }, 0);
    const unitsPerHour =
      coverageMs > 0
        ? verifiedUnits / (coverageMs / 3_600_000)
        : null;
    const outputPerLaborHour =
      laborRateAvailable && laborHours > 0
        ? verifiedUnits / laborHours
        : null;
    return {
      id: station.id,
      name: station.alias,
      cameraCount: null,
      imageSrc: null,
      unitsPerHour,
      outputPerLaborHour,
      projectName: project?.name ?? null,
      projectProgress:
        project?.verifiedGoodUnits === null || !project
          ? null
          : `${project.verifiedGoodUnits} / ${project.targetUnits} units`,
      projectAssignmentKnown: Boolean(assignment),
      status:
        station.status === "active"
          ? project?.status ?? "DATA_DELAY"
          : "DATA_DELAY",
      statusDetail:
        station.status !== "active"
          ? "Station inactive"
          : project?.recoverySummary ?? "Waiting for verified output",
    };
  });
  return {
    factoryId: input.factoryId,
    timezone: timezone ?? "UTC",
    nowIso: input.nowIso,
    projects,
    attention,
    exceptionMonitoringAvailable: projects.some(
      (project) => project.status !== "DATA_DELAY",
    ),
    stations,
  };
}
