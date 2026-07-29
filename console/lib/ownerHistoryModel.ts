import type {
  OwnerHistoryAuditEntry,
  OwnerHistoryFilters,
  OwnerHistoryGrade,
  OwnerHistoryRecord,
  OwnerHistorySummary,
} from "@/lib/ownerHistoryTypes";

export type OwnerCloseoutRow = {
  id: string;
  project_id: string;
  revision: number;
  planned_units: number;
  planned_direct_labor_cents: number;
  planned_material_cost_cents: number;
  planned_margin_after_direct_costs_cents: number;
  deadline_at: string;
  completed_at: string;
  factory_timezone?: string;
  verified_good_units: number;
  material_cost_cents: number;
  direct_labor_cents: number;
  margin_after_direct_costs_cents: number;
  snapshot: Record<string, unknown>;
  created_at: string;
};

export type OwnerAuditRow = {
  id: string;
  project_id: string | null;
  actor_type: "user" | "service" | "system";
  action: string;
  metadata: Record<string, unknown>;
  created_at: string;
};

export const defaultOwnerHistoryFilters: OwnerHistoryFilters = {
  range: "90",
  project: "all",
  customer: "all",
  station: "all",
  shift: "all",
  team: "all",
  status: "all",
};

function stringValue(value: unknown) {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function stringArray(value: unknown) {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    const normalized = stringValue(item);
    return normalized ? [normalized] : [];
  });
}

function finiteNumber(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function latestOwnerCloseouts(rows: OwnerCloseoutRow[]) {
  const latest = new Map<string, OwnerCloseoutRow>();
  for (const row of rows) {
    const prior = latest.get(row.project_id);
    if (
      !prior
      || row.revision > prior.revision
      || (
        row.revision === prior.revision
        && Date.parse(row.created_at) > Date.parse(prior.created_at)
      )
    ) {
      latest.set(row.project_id, row);
    }
  }
  return [...latest.values()].sort(
    (left, right) =>
      Date.parse(right.completed_at) - Date.parse(left.completed_at),
  );
}

export function ownerHistoryOnTime(input: {
  plannedUnits: number;
  actualUnits: number;
  deadlineAt: string;
  completedAt: string;
}) {
  return (
    input.actualUnits >= input.plannedUnits
    && Date.parse(input.completedAt) <= Date.parse(input.deadlineAt)
  );
}

export function ownerHistoryGrade(input: {
  onTime: boolean;
  plannedMarginCents: number;
  actualMarginCents: number;
}): OwnerHistoryGrade {
  if (input.actualMarginCents < 0) return "C−";
  if (
    input.onTime
    && input.actualMarginCents >= input.plannedMarginCents
  ) {
    return "A";
  }
  if (
    input.onTime
    || 5 * input.actualMarginCents >= 4 * input.plannedMarginCents
  ) {
    return "B";
  }
  return "C";
}

function auditSummary(row: OwnerAuditRow) {
  if (row.action === "owner.project.closed") {
    return {
      summary: "Project closed",
      detail: "Immutable closeout revision 1 created.",
    };
  }
  if (row.action === "owner.project.closeout_corrected") {
    const prior = finiteNumber(row.metadata.prior_revision);
    const next = finiteNumber(row.metadata.new_revision);
    const priorUnits = finiteNumber(row.metadata.prior_verified_good_units);
    const nextUnits = finiteNumber(row.metadata.new_verified_good_units);
    const priorMaterials = finiteNumber(row.metadata.prior_material_cost_cents);
    const nextMaterials = finiteNumber(row.metadata.new_material_cost_cents);
    const priorMargin = finiteNumber(
      row.metadata.prior_margin_after_direct_costs_cents,
    );
    const nextMargin = finiteNumber(
      row.metadata.new_margin_after_direct_costs_cents,
    );
    const changes = [
      priorUnits !== null && nextUnits !== null
        ? `Units ${priorUnits} → ${nextUnits}`
        : null,
      priorMaterials !== null && nextMaterials !== null
        ? `Materials ${moneyText(priorMaterials)} → ${moneyText(nextMaterials)}`
        : null,
      priorMargin !== null && nextMargin !== null
        ? `Margin after direct costs ${moneyText(priorMargin)} → ${moneyText(nextMargin)}`
        : null,
    ].filter((value): value is string => value !== null);
    return {
      summary: "Closeout corrected",
      detail:
        prior !== null && next !== null && changes.length
          ? `Revision ${prior} → ${next}. ${changes.join(" · ")}.`
          : prior !== null && next !== null
            ? `Revision ${prior} superseded by revision ${next}.`
          : "A new immutable closeout revision was appended.",
    };
  }
  return {
    summary: row.action
      .replace(/^owner\.project\./, "")
      .replaceAll("_", " ")
      .replace(/^\w/, (character) => character.toUpperCase()),
    detail: "Recorded in the append-only project audit.",
  };
}

function moneyText(cents: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  }).format(cents / 100);
}

export function buildOwnerHistoryRecords(input: {
  closeouts: OwnerCloseoutRow[];
  audits: OwnerAuditRow[];
  nowIso: string;
}): OwnerHistoryRecord[] {
  const auditsByProject = new Map<string, OwnerHistoryAuditEntry[]>();
  for (const row of input.audits) {
    if (!row.project_id) continue;
    const copy = auditsByProject.get(row.project_id) ?? [];
    const summary = auditSummary(row);
    copy.push({
      id: row.id,
      createdAt: row.created_at,
      actorType: row.actor_type,
      action: row.action,
      ...summary,
    });
    auditsByProject.set(row.project_id, copy);
  }

  return latestOwnerCloseouts(input.closeouts).map((row) => {
    const snapshot = row.snapshot ?? {};
    const onTime = ownerHistoryOnTime({
      plannedUnits: row.planned_units,
      actualUnits: row.verified_good_units,
      deadlineAt: row.deadline_at,
      completedAt: row.completed_at,
    });
    const evidenceCount = Math.max(
      0,
      Math.trunc(finiteNumber(snapshot.evidence_clip_count) ?? 0),
    );
    const retentionDate = stringValue(snapshot.evidence_retention_until);
    const evidenceExpired =
      snapshot.evidence_expired === true
      || (
        retentionDate !== null
        && Date.parse(retentionDate) <= Date.parse(input.nowIso)
      );
    const rawOutput = Array.isArray(snapshot.weekly_output)
      ? snapshot.weekly_output
      : [];
    const output = rawOutput.flatMap((value, sourceIndex) => {
      if (!value || typeof value !== "object") return [];
      const item = value as Record<string, unknown>;
      const label = stringValue(item.label);
      if (!label) return [];
      return [{
        sourceIndex,
        weekStart: stringValue(item.week_start),
        label,
        plannedUnits: finiteNumber(item.planned_units),
        actualUnits: finiteNumber(item.actual_units),
      }];
    }).sort((left, right) => {
      if (left.weekStart && right.weekStart) {
        return left.weekStart.localeCompare(right.weekStart);
      }
      return left.sourceIndex - right.sourceIndex;
    }).map((bucket) => ({
      weekStart: bucket.weekStart,
      label: bucket.label,
      plannedUnits: bucket.plannedUnits,
      actualUnits: bucket.actualUnits,
    }));
    return {
      id: row.id,
      projectId: row.project_id,
      revision: row.revision,
      projectName:
        stringValue(snapshot.project_name) ?? "Project name unavailable",
      customerName:
        stringValue(snapshot.customer_name) ?? "Customer unavailable",
      factoryTimezone: stringValue(row.factory_timezone),
      completedAt: row.completed_at,
      deadlineAt: row.deadline_at,
      plannedUnits: row.planned_units,
      actualUnits: row.verified_good_units,
      plannedScheduleMinutes: finiteNumber(snapshot.planned_schedule_minutes),
      actualScheduleMinutes: finiteNumber(snapshot.actual_schedule_minutes),
      plannedLaborCents: row.planned_direct_labor_cents,
      actualLaborCents: row.direct_labor_cents,
      actualLaborMinutes: finiteNumber(snapshot.actual_direct_labor_minutes),
      plannedMaterialsCents: row.planned_material_cost_cents,
      actualMaterialsCents: row.material_cost_cents,
      plannedMarginCents: row.planned_margin_after_direct_costs_cents,
      actualMarginCents: row.margin_after_direct_costs_cents,
      onTime,
      verificationHasGap: snapshot.verification_has_gap === true,
      grade: ownerHistoryGrade({
        onTime,
        plannedMarginCents: row.planned_margin_after_direct_costs_cents,
        actualMarginCents: row.margin_after_direct_costs_cents,
      }),
      stationNames: stringArray(snapshot.station_names),
      shiftNames: stringArray(snapshot.shift_names),
      teamNames: stringArray(snapshot.team_names),
      output,
      audit: (auditsByProject.get(row.project_id) ?? []).sort(
        (left, right) =>
          Date.parse(right.createdAt) - Date.parse(left.createdAt),
      ),
      evidence: {
        count: evidenceCount,
        state: evidenceExpired
          ? "expired"
          : evidenceCount > 0
            ? "available"
            : "unavailable",
        retentionDate,
      },
    };
  });
}

function filterRangeStart(
  range: OwnerHistoryFilters["range"],
  nowIso: string,
) {
  if (range === "all") return Number.NEGATIVE_INFINITY;
  return Date.parse(nowIso) - Number(range) * 86_400_000;
}

export function filterOwnerHistoryRecords(
  records: OwnerHistoryRecord[],
  filters: OwnerHistoryFilters,
  nowIso: string,
) {
  const rangeStart = filterRangeStart(filters.range, nowIso);
  return records.filter((record) => {
    if (Date.parse(record.completedAt) < rangeStart) return false;
    if (filters.project !== "all" && record.projectName !== filters.project) {
      return false;
    }
    if (
      filters.customer !== "all"
      && record.customerName !== filters.customer
    ) {
      return false;
    }
    if (
      filters.station !== "all"
      && !record.stationNames.includes(filters.station)
    ) {
      return false;
    }
    if (
      filters.shift !== "all"
      && !record.shiftNames.includes(filters.shift)
    ) {
      return false;
    }
    if (filters.team !== "all" && !record.teamNames.includes(filters.team)) {
      return false;
    }
    if (filters.status === "on_time" && !record.onTime) return false;
    if (filters.status === "late" && record.onTime) return false;
    if (
      filters.status === "positive_margin"
      && record.actualMarginCents <= 0
    ) {
      return false;
    }
    if (
      filters.status === "negative_margin"
      && record.actualMarginCents >= 0
    ) {
      return false;
    }
    return true;
  });
}

export function summarizeOwnerHistory(
  records: OwnerHistoryRecord[],
): OwnerHistorySummary {
  const laborMinutes = records.reduce(
    (total, record) => total + (record.actualLaborMinutes ?? 0),
    0,
  );
  const laborUnits = records.reduce(
    (total, record) =>
      total + (record.actualLaborMinutes === null ? 0 : record.actualUnits),
    0,
  );
  const onTimeCount = records.filter((record) => record.onTime).length;
  return {
    completedProjects: records.length,
    onTimeCount,
    onTimePercent:
      records.length > 0 ? (onTimeCount / records.length) * 100 : null,
    unitsPerLaborHour:
      laborMinutes > 0 ? laborUnits / (laborMinutes / 60) : null,
    laborCoverageCount: records.filter(
      (record) => record.actualLaborMinutes !== null,
    ).length,
    marginAfterDirectCostsCents: records.reduce(
      (total, record) => total + record.actualMarginCents,
      0,
    ),
  };
}

const validRanges = new Set<OwnerHistoryFilters["range"]>([
  "30",
  "90",
  "365",
  "all",
]);
const validStatuses = new Set<OwnerHistoryFilters["status"]>([
  "all",
  "on_time",
  "late",
  "positive_margin",
  "negative_margin",
]);

export function parseOwnerHistoryFilters(
  values: Record<string, string | undefined>,
): OwnerHistoryFilters {
  const range = values.range as OwnerHistoryFilters["range"];
  const status = values.status as OwnerHistoryFilters["status"];
  return {
    range: validRanges.has(range) ? range : defaultOwnerHistoryFilters.range,
    project: stringValue(values.project) ?? "all",
    customer: stringValue(values.customer) ?? "all",
    station: stringValue(values.station) ?? "all",
    shift: stringValue(values.shift) ?? "all",
    team: stringValue(values.team) ?? "all",
    status: validStatuses.has(status)
      ? status
      : defaultOwnerHistoryFilters.status,
  };
}

function csvTextCell(value: string) {
  let text = value;
  if (/^[\t\r\n ]*[=+\-@]/.test(text)) text = `'${text}`;
  return `"${text.replaceAll('"', '""')}"`;
}

function csvNumberCell(value: number) {
  return Number.isFinite(value) ? String(value) : "";
}

function localDateForExport(iso: string, timezone: string) {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date(iso));
  const byType = new Map(parts.map((part) => [part.type, part.value]));
  return `${byType.get("year")}-${byType.get("month")}-${byType.get("day")}`;
}

export function ownerHistoryCsv(
  records: OwnerHistoryRecord[],
  timezone: string,
) {
  const headers = [
    "Project",
    "Customer",
    "Completed",
    "Planned units",
    "Actual verified good units",
    "Planned direct labor",
    "Actual direct labor",
    "Planned materials",
    "Actual materials",
    "Planned margin after direct costs",
    "Actual margin after direct costs",
    "On time",
    "Grade",
    "Revision",
  ];
  return [
    headers.map(csvTextCell).join(","),
    ...records.map((record) =>
      [
        csvTextCell(record.projectName),
        csvTextCell(record.customerName),
        csvTextCell(localDateForExport(
          record.completedAt,
          record.factoryTimezone ?? timezone,
        )),
        csvNumberCell(record.plannedUnits),
        csvNumberCell(record.actualUnits),
        csvNumberCell(record.plannedLaborCents / 100),
        csvNumberCell(record.actualLaborCents / 100),
        csvNumberCell(record.plannedMaterialsCents / 100),
        csvNumberCell(record.actualMaterialsCents / 100),
        csvNumberCell(record.plannedMarginCents / 100),
        csvNumberCell(record.actualMarginCents / 100),
        csvTextCell(record.onTime ? "Yes" : "No"),
        csvTextCell(record.grade),
        csvNumberCell(record.revision),
      ].join(","),
    ),
  ].join("\r\n");
}
