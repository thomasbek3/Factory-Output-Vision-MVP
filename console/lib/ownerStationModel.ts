import type {
  OwnerStationData,
  OwnerStationOption,
  OwnerWorkforceData,
} from "@/lib/ownerStationTypes";

type VerificationRow = {
  id: string;
  chunk_id: string;
  revision: number;
  source_start_at: string;
  source_end_at: string;
  status:
    | "verified"
    | "timeline_untrusted"
    | "no_published_coverage"
    | "coverage_revoked";
};

type EventRow = {
  id?: string;
  chunk_id?: string;
  occurred_at: string;
  good_units?: number;
  verified?: boolean;
};

type WorkerRow = {
  id: string;
  display_name: string;
  employee_code?: string | null;
  primary_role?: string | null;
  status?: "active" | "inactive";
};

type WorkerIntervalRow = {
  id: string;
  worker_id: string;
  station_id: string;
  project_id: string;
  effective_start: string;
  effective_end: string | null;
  loaded_labor_rate_cents_per_hour?: number;
  source: "manual" | "badge" | "schedule" | "import";
};

type DowntimeRow = {
  effective_start: string;
  effective_end: string;
};

type AdjustmentRow = {
  kind: "scrap" | "rework" | "correction";
  delta_good_units: number;
  occurred_at: string;
};

type Interval = { start: number; end: number };

function finiteTime(value: string) {
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function clampInterval(
  startValue: string,
  endValue: string | null,
  windowStart: number,
  windowEnd: number,
) {
  const start = finiteTime(startValue);
  const end = endValue ? finiteTime(endValue) : windowEnd;
  if (start === null || end === null) return null;
  const clipped = {
    start: Math.max(start, windowStart),
    end: Math.min(end, windowEnd),
  };
  return clipped.end > clipped.start ? clipped : null;
}

function mergeIntervals(intervals: Interval[]) {
  const sorted = [...intervals].sort(
    (left, right) => left.start - right.start || left.end - right.end,
  );
  const merged: Interval[] = [];
  for (const interval of sorted) {
    const previous = merged.at(-1);
    if (!previous || interval.start > previous.end) {
      merged.push({ ...interval });
    } else {
      previous.end = Math.max(previous.end, interval.end);
    }
  }
  return merged;
}

function overlapMilliseconds(
  interval: Interval,
  start: number,
  end: number,
) {
  return Math.max(0, Math.min(interval.end, end) - Math.max(interval.start, start));
}

function coveredMilliseconds(intervals: Interval[], start: number, end: number) {
  return intervals.reduce(
    (total, interval) => total + overlapMilliseconds(interval, start, end),
    0,
  );
}

function latestVerificationRows(rows: VerificationRow[]) {
  const latest = new Map<string, VerificationRow>();
  for (const row of rows) {
    const current = latest.get(row.chunk_id);
    if (
      !current
      || row.revision > current.revision
      || (row.revision === current.revision && row.id > current.id)
    ) {
      latest.set(row.chunk_id, row);
    }
  }
  return [...latest.values()];
}

function formatTime(value: number, timezone: string) {
  return new Intl.DateTimeFormat("en-US", {
    timeZone: timezone,
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function round(value: number, decimals: number) {
  const scale = 10 ** decimals;
  return Math.round(value * scale) / scale;
}

function safeDivide(numerator: number, denominator: number) {
  return denominator > 0 ? numerator / denominator : null;
}

function eventUnits(event: EventRow) {
  return Number.isSafeInteger(event.good_units) && (event.good_units ?? 0) >= 0
    ? event.good_units ?? 0
    : 1;
}

function workerAttribution(
  target: WorkerIntervalRow,
  intervals: WorkerIntervalRow[],
  coverageSufficient: boolean,
) {
  if (target.source !== "badge" || !coverageSufficient) {
    return {
      attribution: "team_only" as const,
      attributionDetail: "Shared or unconfirmed interval on station",
    };
  }
  const targetStart = finiteTime(target.effective_start);
  const targetEnd = target.effective_end
    ? finiteTime(target.effective_end)
    : Number.POSITIVE_INFINITY;
  if (targetStart === null || targetEnd === null) {
    return {
      attribution: "unavailable" as const,
      attributionDetail: "Interval timing unavailable",
    };
  }
  const overlapsAnotherWorker = intervals.some((candidate) => {
    if (candidate.id === target.id || candidate.station_id !== target.station_id) {
      return false;
    }
    const candidateStart = finiteTime(candidate.effective_start);
    const candidateEnd = candidate.effective_end
      ? finiteTime(candidate.effective_end)
      : Number.POSITIVE_INFINITY;
    return (
      candidateStart !== null
      && candidateEnd !== null
      && candidateStart < targetEnd
      && candidateEnd > targetStart
    );
  });
  return overlapsAnotherWorker
    ? {
        attribution: "team_only" as const,
        attributionDetail: "Shared interval on station",
      }
    : {
        attribution: "solo_high_confidence" as const,
        attributionDetail: "Alone, checked in, coverage confirmed",
      };
}

export function buildOwnerStationData(input: {
  factoryId: string;
  timezone: string;
  selectedDate: string;
  station: OwnerStationOption & { status: string };
  stationOptions: OwnerStationOption[];
  project: { id: string; name: string } | null;
  projectAssignmentKnown: boolean;
  windowStartIso: string;
  windowEndIso: string;
  requiredUnitsPerHour: number | null;
  verificationRows: VerificationRow[];
  eventRows: EventRow[];
  workerRows: WorkerRow[];
  workerIntervals: WorkerIntervalRow[];
  downtimeRows: DowntimeRow[];
  adjustmentRows: AdjustmentRow[];
  nowIso: string;
  imageSrc?: string | null;
  evidenceLabel?: string;
  cycleTimeSeconds?: number | null;
  assignmentId?: string;
  shiftOptions?: { id: string; label: string }[];
  comparisonBps?: Partial<
    Record<
      "verifiedGoodUnits" | "unitsPerHour" | "laborHours" | "outputPerLaborHour",
      number
    >
  >;
}): OwnerStationData {
  const windowStart = finiteTime(input.windowStartIso);
  const windowEnd = finiteTime(input.windowEndIso);
  const now = finiteTime(input.nowIso);
  if (
    windowStart === null
    || windowEnd === null
    || now === null
    || windowEnd <= windowStart
  ) {
    throw new Error("Invalid station window.");
  }
  const effectiveEnd = Math.min(windowEnd, now);
  const latestVerifications = latestVerificationRows(input.verificationRows);
  const verifiedByChunk = new Map(
    latestVerifications.map((row) => [row.chunk_id, row]),
  );
  const verifiedIntervals = mergeIntervals(
    latestVerifications.flatMap((row) => {
      if (row.status !== "verified") return [];
      const interval = clampInterval(
        row.source_start_at,
        row.source_end_at,
        windowStart,
        effectiveEnd,
      );
      return interval ? [interval] : [];
    }),
  );
  const downtimeIntervals = mergeIntervals(
    input.downtimeRows.flatMap((row) => {
      const interval = clampInterval(
        row.effective_start,
        row.effective_end,
        windowStart,
        effectiveEnd,
      );
      return interval ? [interval] : [];
    }),
  );
  const verifiedEvents = input.eventRows.filter((event) => {
    const occurredAt = finiteTime(event.occurred_at);
    if (event.good_units !== undefined) {
      return (
        occurredAt !== null
        && event.verified === true
        && occurredAt >= windowStart
        && occurredAt < effectiveEnd
      );
    }
    if (!event.chunk_id) return false;
    const verification = verifiedByChunk.get(event.chunk_id);
    if (occurredAt === null || verification?.status !== "verified") return false;
    const verificationStart = finiteTime(verification.source_start_at);
    const verificationEnd = finiteTime(verification.source_end_at);
    return (
      verificationStart !== null
      && verificationEnd !== null
      && occurredAt >= windowStart
      && occurredAt < effectiveEnd
      && occurredAt >= verificationStart
      && occurredAt < verificationEnd
    );
  });

  const bucketMs = 15 * 60 * 1000;
  const verifiedAdjustments = input.adjustmentRows.flatMap((adjustment) => {
    if (adjustment.kind !== "scrap" && adjustment.kind !== "rework") return [];
    const occurredAt = finiteTime(adjustment.occurred_at);
    if (
      occurredAt === null
      || occurredAt < windowStart
      || occurredAt >= effectiveEnd
      || coveredMilliseconds(verifiedIntervals, occurredAt, occurredAt + 1) < 1
    ) {
      return [];
    }
    return [{ ...adjustment, occurredAt }];
  });
  const production = [];
  for (let start = windowStart; start < windowEnd; start += bucketMs) {
    const end = Math.min(start + bucketMs, windowEnd);
    const requiredUnits =
      input.requiredUnitsPerHour === null
        ? null
        : round(input.requiredUnitsPerHour * ((end - start) / 3_600_000), 1);
    const fullyVerified =
      end <= effectiveEnd
      && coveredMilliseconds(verifiedIntervals, start, end) >= end - start;
    const rawUnits = verifiedEvents
      .filter((event) => {
        const occurredAt = finiteTime(event.occurred_at) ?? -1;
        return occurredAt >= start && occurredAt < end;
      })
      .reduce((total, event) => total + eventUnits(event), 0);
    const adjustmentUnits = verifiedAdjustments
      .filter(
        (adjustment) =>
          adjustment.occurredAt >= start && adjustment.occurredAt < end,
      )
      .reduce((total, adjustment) => total + adjustment.delta_good_units, 0);
    production.push({
      startIso: new Date(start).toISOString(),
      label: formatTime(start, input.timezone),
      verifiedGoodUnits: fullyVerified
        ? Math.max(0, rawUnits + adjustmentUnits)
        : null,
      requiredUnits,
      downtimeMinutes: Math.round(
        coveredMilliseconds(downtimeIntervals, start, end) / 60_000,
      ),
    });
  }

  const verifiedCoverageMs = coveredMilliseconds(
    verifiedIntervals,
    windowStart,
    effectiveEnd,
  );
  const productiveVerifiedMs = production.reduce((total, bucket, index) => {
    if (bucket.verifiedGoodUnits === null) return total;
    const start = windowStart + index * bucketMs;
    const end = Math.min(start + bucketMs, windowEnd, effectiveEnd);
    return total + Math.max(0, end - start - bucket.downtimeMinutes * 60_000);
  }, 0);
  const verifiedGoodUnits = production.reduce(
    (total, bucket) => total + (bucket.verifiedGoodUnits ?? 0),
    0,
  );
  const workerIntervals = input.workerIntervals.flatMap((row) => {
    const interval = clampInterval(
      row.effective_start,
      row.effective_end,
      windowStart,
      effectiveEnd,
    );
    return interval ? [{ row, interval }] : [];
  });
  const laborHours =
    effectiveEnd > windowStart
      ? workerIntervals.reduce(
          (total, item) => total + (item.interval.end - item.interval.start),
          0,
        ) / 3_600_000
      : null;
  const unitsPerHour = safeDivide(
    verifiedGoodUnits,
    productiveVerifiedMs / 3_600_000,
  );
  const outputPerLaborHour =
    workerIntervals.some(
      ({ row }) => (row.loaded_labor_rate_cents_per_hour ?? 0) > 0,
    ) && laborHours !== null
      ? safeDivide(verifiedGoodUnits, laborHours)
      : null;
  const workerById = new Map(input.workerRows.map((row) => [row.id, row]));
  const team = workerIntervals.map(({ row, interval }) => {
    const coverageSufficient =
      coveredMilliseconds(
        verifiedIntervals,
        interval.start,
        interval.end,
      ) >= interval.end - interval.start;
    const attribution = workerAttribution(
      row,
      input.workerIntervals,
      coverageSufficient,
    );
    return {
      id: row.id,
      name: workerById.get(row.worker_id)?.display_name ?? "Worker unavailable",
      scheduledInterval: `${formatTime(interval.start, input.timezone)}–${formatTime(
        interval.end,
        input.timezone,
      )}`,
      laborHours: round((interval.end - interval.start) / 3_600_000, 2),
      primaryRole: workerById.get(row.worker_id)?.primary_role ?? null,
      ...attribution,
    };
  });
  const scrapUnits = verifiedAdjustments
    .filter((row) => row.kind === "scrap")
    .reduce((total, row) => total + Math.abs(row.delta_good_units), 0);
  const reworkUnits = verifiedAdjustments
    .filter((row) => row.kind === "rework")
    .reduce((total, row) => total + Math.abs(row.delta_good_units), 0);
  let verifiedFrontier = windowStart;
  for (const interval of verifiedIntervals) {
    if (interval.start > verifiedFrontier) break;
    verifiedFrontier = Math.max(verifiedFrontier, interval.end);
  }
  const verifiedThrough =
    verifiedFrontier > windowStart ? verifiedFrontier : null;
  const hasCoverageGap =
    verifiedCoverageMs < Math.max(0, effectiveEnd - windowStart);

  return {
    factoryId: input.factoryId,
    timezone: input.timezone,
    selectedDate: input.selectedDate,
    station: {
      id: input.station.id,
      name: input.station.name,
      status: input.station.status === "active" ? "active" : "inactive",
      imageSrc: input.imageSrc ?? null,
      evidenceLabel: input.evidenceLabel ?? "Station evidence unavailable",
      cycleTimeSeconds: input.cycleTimeSeconds ?? null,
    },
    stationOptions: input.stationOptions,
    project: input.project,
    projectAssignmentKnown: input.projectAssignmentKnown,
    verifiedThroughLabel:
      verifiedThrough === null
        ? "Not yet available"
        : formatTime(verifiedThrough, input.timezone),
    verifiedThroughIso:
      verifiedThrough === null
        ? null
        : new Date(verifiedThrough).toISOString(),
    nowIso: new Date(now).toISOString(),
    windowStartIso: new Date(windowStart).toISOString(),
    windowEndIso: new Date(windowEnd).toISOString(),
    verificationState:
      verifiedCoverageMs === 0
        ? "unavailable"
        : hasCoverageGap
          ? "delayed"
          : "verified",
    shiftLabel: `${formatTime(windowStart, input.timezone)}–${formatTime(
      windowEnd,
      input.timezone,
    )}`,
    selectedAssignmentId: input.assignmentId ?? "current-assignment",
    shiftOptions:
      input.shiftOptions
      ?? [
        {
          id: input.assignmentId ?? "current-assignment",
          label: `${formatTime(windowStart, input.timezone)}–${formatTime(
            windowEnd,
            input.timezone,
          )}`,
        },
      ],
    kpis: {
      verifiedGoodUnits: {
        value: verifiedCoverageMs > 0 ? verifiedGoodUnits : null,
        decimals: 0,
        comparisonBps: input.comparisonBps?.verifiedGoodUnits ?? null,
      },
      unitsPerHour: {
        value: unitsPerHour === null ? null : round(unitsPerHour, 1),
        decimals: 1,
        comparisonBps: input.comparisonBps?.unitsPerHour ?? null,
      },
      laborHours: {
        value: laborHours === null ? null : round(laborHours, 1),
        decimals: 1,
        comparisonBps: input.comparisonBps?.laborHours ?? null,
      },
      outputPerLaborHour: {
        value:
          outputPerLaborHour === null ? null : round(outputPerLaborHour, 1),
        decimals: 1,
        comparisonBps: input.comparisonBps?.outputPerLaborHour ?? null,
      },
    },
    production,
    team,
    summary: {
      scrapUnits: verifiedCoverageMs > 0 ? scrapUnits : null,
      reworkUnits: verifiedCoverageMs > 0 ? reworkUnits : null,
      downtimeMinutes: Math.round(
        coveredMilliseconds(downtimeIntervals, windowStart, effectiveEnd)
          / 60_000,
      ),
    },
  };
}

export function buildOwnerWorkforceData(input: {
  factoryId: string;
  workers: WorkerRow[];
  intervals: WorkerIntervalRow[];
  stationNames: Record<string, string>;
  projectNames: Record<string, string>;
  windowStartIso: string;
  windowEndIso: string;
  timezone: string;
}): OwnerWorkforceData {
  const windowStart = finiteTime(input.windowStartIso);
  const windowEnd = finiteTime(input.windowEndIso);
  if (windowStart === null || windowEnd === null || windowEnd <= windowStart) {
    throw new Error("Invalid workforce window.");
  }
  const intervalsByWorker = new Map<
    string,
    { row: WorkerIntervalRow; clipped: Interval }[]
  >();
  for (const interval of input.intervals) {
    const clipped = clampInterval(
      interval.effective_start,
      interval.effective_end,
      windowStart,
      windowEnd,
    );
    if (clipped) {
      const existing = intervalsByWorker.get(interval.worker_id) ?? [];
      existing.push({ row: interval, clipped });
      intervalsByWorker.set(interval.worker_id, existing);
    }
  }
  const members = input.workers.map((worker) => {
    const assignments = (intervalsByWorker.get(worker.id) ?? []).sort(
      (left, right) => left.clipped.start - right.clipped.start,
    );
    const stationNames = [
      ...new Set(
        assignments.map(
          ({ row }) =>
            input.stationNames[row.station_id] ?? "Station unavailable",
        ),
      ),
    ];
    const projectNames = [
      ...new Set(
        assignments.map(
          ({ row }) =>
            input.projectNames[row.project_id] ?? "Project unavailable",
        ),
      ),
    ];
    return {
      id: worker.id,
      name: worker.display_name,
      employeeCode: worker.employee_code ?? null,
      status: worker.status === "inactive" ? "inactive" as const : "active" as const,
      stationName: stationNames.length ? stationNames.join(", ") : null,
      projectName: projectNames.length ? projectNames.join(", ") : null,
      scheduledInterval: assignments.length
        ? assignments
            .map(
              ({ clipped }) =>
                `${formatTime(clipped.start, input.timezone)}–${formatTime(
                  clipped.end,
                  input.timezone,
                )}`,
            )
            .join(", ")
        : null,
      primaryRole: worker.primary_role ?? null,
      attribution: assignments.length
        ? "team_only" as const
        : "unassigned" as const,
    };
  });
  const assigned = members.filter((member) => member.stationName !== null);
  return {
    factoryId: input.factoryId,
    members,
    activeCount: members.filter((member) => member.status === "active").length,
    assignedCount: assigned.length,
    stationCount: new Set(
      [...intervalsByWorker.values()].flatMap((assignments) =>
        assignments.map(({ row }) => row.station_id),
      ),
    ).size,
  };
}
