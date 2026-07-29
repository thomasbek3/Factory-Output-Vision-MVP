import {
  buildOwnerHistoryRecords,
  filterOwnerHistoryRecords,
  summarizeOwnerHistory,
  type OwnerAuditRow,
  type OwnerCloseoutRow,
} from "@/lib/ownerHistoryModel";
import type {
  OwnerHistoryData,
  OwnerHistoryFilters,
  OwnerHistoryRecord,
} from "@/lib/ownerHistoryTypes";
import { ownerPreviewDashboard } from "@/lib/preview/ownerDashboard";

const projects = [
  {
    id: "alvarez",
    name: "Alvarez Gates",
    customer: "Alvarez Contracting",
    completed: "2026-05-12T14:42:00-04:00",
    deadline: "2026-05-12T17:00:00-04:00",
    units: [400, 407],
    labor: [320_000, 306_000],
    laborMinutes: 1_344,
    materials: [480_000, 491_000],
    margin: [240_000, 253_000],
    schedule: [1_440, 1_344],
    station: "Press Bay North",
    team: ["Ana Torres", "Luis Mendoza"],
    output: [76, 82, 84, 79, 86],
  },
  {
    id: "omega",
    name: "Omega Railings",
    customer: "Omega Industrial",
    completed: "2026-05-09T15:10:00-04:00",
    deadline: "2026-05-09T17:00:00-04:00",
    units: [300, 298],
    labor: [250_000, 260_000],
    laborMinutes: 1_248,
    materials: [360_000, 355_000],
    margin: [180_000, 185_000],
    schedule: [1_200, 1_248],
    station: "Weld Cell West",
    team: ["Rosa Castillo"],
    output: [68, 71, 81, 78],
  },
  {
    id: "summit",
    name: "Summit Frames",
    customer: "Summit Supply",
    completed: "2026-05-07T18:06:00-04:00",
    deadline: "2026-05-07T17:00:00-04:00",
    units: [250, 247],
    labor: [220_000, 232_000],
    laborMinutes: 1_008,
    materials: [320_000, 328_000],
    margin: [150_000, 147_000],
    schedule: [960, 1_008],
    station: "Assembly Line 1",
    team: ["Ana Torres"],
    output: [55, 64, 61, 67],
  },
  {
    id: "northfield",
    name: "Northfield Panels",
    customer: "Northfield Builders",
    completed: "2026-05-03T13:25:00-04:00",
    deadline: "2026-05-03T17:00:00-04:00",
    units: [180, 183],
    labor: [170_000, 158_000],
    laborMinutes: 672,
    materials: [240_000, 236_000],
    margin: [90_000, 94_000],
    schedule: [720, 672],
    station: "Paint Booth",
    team: ["Luis Mendoza"],
    output: [42, 47, 44, 50],
  },
  {
    id: "ironwood",
    name: "Ironwood Balusters",
    customer: "Ironwood Metalworks",
    completed: "2026-04-30T18:30:00-04:00",
    deadline: "2026-04-30T17:00:00-04:00",
    units: [350, 341],
    labor: [290_000, 315_000],
    laborMinutes: 1_440,
    materials: [420_000, 435_000],
    margin: [160_000, 145_000],
    schedule: [1_344, 1_440],
    station: "Weld Cell East",
    team: ["Ana Torres", "Rosa Castillo"],
    output: [100, 100, 150, -9],
  },
  {
    id: "pioneer",
    name: "Pioneer Brackets",
    customer: "Pioneer Equipment",
    completed: "2026-04-28T14:00:00-04:00",
    deadline: "2026-04-28T17:00:00-04:00",
    units: [500, 512],
    labor: [380_000, 360_000],
    laborMinutes: 1_776,
    materials: [600_000, 587_000],
    margin: [300_000, 321_000],
    schedule: [1_920, 1_776],
    station: "Press Bay North",
    team: ["Luis Mendoza", "Rosa Castillo"],
    output: [118, 126, 133, 135],
  },
] as const;

const closeouts: OwnerCloseoutRow[] = projects.flatMap((project, index) => {
  const base: OwnerCloseoutRow = {
    id: `preview-closeout-${project.id}`,
    project_id: `preview-project-${project.id}`,
    revision: 1,
    planned_units: project.units[0],
    planned_direct_labor_cents: project.labor[0],
    planned_material_cost_cents: project.materials[0],
    planned_margin_after_direct_costs_cents: project.margin[0],
    deadline_at: project.deadline,
    completed_at: project.completed,
    verified_good_units: project.units[1],
    material_cost_cents: project.materials[1],
    direct_labor_cents: project.labor[1],
    margin_after_direct_costs_cents: project.margin[1],
    snapshot: {
      project_name: project.name,
      customer_name: project.customer,
      station_names: [project.station],
      shift_names: ["06:00-14:00"],
      team_names: project.team,
      planned_schedule_minutes: project.schedule[0],
      actual_schedule_minutes: project.schedule[1],
      actual_direct_labor_minutes: project.laborMinutes,
      weekly_output: project.output.map((actual, bucket) => ({
        label: ["Apr 14", "Apr 21", "Apr 28", "May 5", "May 12"][bucket]
          ?? `Week ${bucket + 1}`,
        planned_units: null,
        actual_units: actual,
      })),
      evidence_clip_count: index === 0 ? 12 : index % 2 === 0 ? 0 : 4,
      evidence_retention_until:
        index === 2 ? "2026-05-20T00:00:00Z" : "2026-08-12T00:00:00Z",
      evidence_expired: index === 2,
    },
    created_at: new Date(
      Date.parse(project.completed) + 60_000,
    ).toISOString(),
  };
  if (index !== 0) return [base];
  return [
    {
      ...base,
      verified_good_units: 404,
      material_cost_cents: 488_000,
      margin_after_direct_costs_cents: 250_000,
      snapshot: {
        ...base.snapshot,
        weekly_output: [75, 82, 83, 79, 85].map((actual, bucket) => ({
          label: ["Apr 14", "Apr 21", "Apr 28", "May 5", "May 12"][bucket],
          planned_units: null,
          actual_units: actual,
        })),
      },
    },
    {
      ...base,
      id: "preview-closeout-alvarez-r2",
      revision: 2,
      verified_good_units: 407,
      created_at: new Date(
        Date.parse(project.completed) + 3_600_000,
      ).toISOString(),
    },
  ];
});

const audits: OwnerAuditRow[] = projects.flatMap((project, index) => {
  const closedAt = new Date(
    Date.parse(project.completed) + 60_000,
  ).toISOString();
  const rows: OwnerAuditRow[] = [{
    id: `preview-audit-${project.id}-closed`,
    project_id: `preview-project-${project.id}`,
    actor_type: "system",
    action: "owner.project.closed",
    metadata: { revision: 1 },
    created_at: closedAt,
  }];
  if (index === 0) {
    rows.push({
      id: "preview-audit-alvarez-correction",
      project_id: "preview-project-alvarez",
      actor_type: "user",
      action: "owner.project.closeout_corrected",
      metadata: {
        prior_revision: 1,
        new_revision: 2,
        prior_verified_good_units: 404,
        new_verified_good_units: 407,
        prior_material_cost_cents: 488_000,
        new_material_cost_cents: 491_000,
        prior_margin_after_direct_costs_cents: 250_000,
        new_margin_after_direct_costs_cents: 253_000,
      },
      created_at: new Date(Date.parse(closedAt) + 3_540_000).toISOString(),
    });
  }
  return rows;
});

const allRecords = buildOwnerHistoryRecords({
  closeouts,
  audits,
  nowIso: ownerPreviewDashboard.nowIso,
});

function uniqueValues(
  records: OwnerHistoryRecord[],
  selector: (record: OwnerHistoryRecord) => string[],
) {
  return [...new Set(records.flatMap(selector))].sort();
}

export function ownerPreviewHistory(
  filters: OwnerHistoryFilters,
): OwnerHistoryData {
  const records = filterOwnerHistoryRecords(
    allRecords,
    filters,
    ownerPreviewDashboard.nowIso,
  );
  return {
    factoryId: ownerPreviewDashboard.factoryId,
    timezone: ownerPreviewDashboard.timezone,
    filters,
    records,
    summary: summarizeOwnerHistory(records),
    options: {
      projects: uniqueValues(allRecords, (record) => [record.projectName]),
      customers: uniqueValues(allRecords, (record) => [record.customerName]),
      stations: uniqueValues(allRecords, (record) => record.stationNames),
      shifts: uniqueValues(allRecords, (record) => record.shiftNames),
      teams: uniqueValues(allRecords, (record) => record.teamNames),
    },
  };
}
