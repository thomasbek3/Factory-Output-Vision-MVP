import type { OwnerDashboardData } from "@/lib/ownerDashboardTypes";
import {
  buildOwnerStationData,
  buildOwnerWorkforceData,
} from "@/lib/ownerStationModel";

export const PREVIEW_ONLY_OWNER_FIXTURE = true;

export const ownerPreviewWorkers = [
  {
    id: "30000000-0000-0000-0000-000000000001",
    name: "Ana Torres",
    primaryRole: "Operator",
  },
  {
    id: "30000000-0000-0000-0000-000000000002",
    name: "Luis Mendoza",
    primaryRole: "Operator",
  },
  {
    id: "30000000-0000-0000-0000-000000000003",
    name: "Rosa Castillo",
    primaryRole: "Material handler",
  },
] as const;

export const ownerPreviewDashboard: OwnerDashboardData = {
  factoryId: "10000000-0000-0000-0000-000000000001",
  timezone: "America/New_York",
  nowIso: "2026-05-15T18:31:00Z",
  projects: [
    {
      id: "40000000-0000-0000-0000-000000000001",
      name: "Alvarez Gates",
      client: "Alvarez Contracting",
      status: "BEHIND",
      verifiedGoodUnits: 212,
      targetUnits: 400,
      recoverySummary: "Need 63 units/day to recover",
      projectedMarginBps: 1870,
      projectedMarginStatus: "at_risk",
      deadlineLabel: "Thu, May 16",
      verifiedThroughLabel: "2:31 PM",
      verificationGap: null,
      chart: {
        actual: [0, 54, 118, 168, 212],
        required: [0, 40, 88, 137, 185, 233, 282, 330],
        requiredToRecover: [212, 262, 325, 400],
        labels: ["Day 1", "", "Day 2", "", "Now", "", "Day 3", "Deadline"],
        nowIndex: 4,
      },
    },
    {
      id: "40000000-0000-0000-0000-000000000002",
      name: "Omega Railings",
      client: "Omega Industrial",
      status: "ON_TRACK",
      verifiedGoodUnits: 315,
      targetUnits: 600,
      recoverySummary: "On pace to meet deadline",
      projectedMarginBps: 2340,
      projectedMarginStatus: "healthy",
      deadlineLabel: "Fri, May 17",
      verifiedThroughLabel: "2:31 PM",
      verificationGap: null,
      chart: {
        actual: [0, 71, 154, 237, 315],
        required: [0, 50, 100, 150, 220, 270, 320],
        requiredToRecover: [],
        labels: ["Day 1", "", "Day 2", "", "Today", "", "Deadline"],
        nowIndex: 4,
      },
    },
    {
      id: "40000000-0000-0000-0000-000000000003",
      name: "Summit Frames",
      client: "Summit Supply",
      status: "AHEAD",
      verifiedGoodUnits: 487,
      targetUnits: 500,
      recoverySummary: "Ahead by 1.6 days",
      projectedMarginBps: 2610,
      projectedMarginStatus: "healthy",
      deadlineLabel: "Mon, May 20",
      verifiedThroughLabel: "2:31 PM",
      verificationGap: null,
      chart: {
        actual: [0, 118, 243, 369, 487],
        required: [0, 55, 120, 190, 270, 350, 430],
        requiredToRecover: [],
        labels: ["Day 1", "", "Day 2", "", "Today", "", "Deadline"],
        nowIndex: 4,
      },
    },
  ],
  attention: [
    {
      id: "verification-lag",
      tone: "bad",
      kind: "verification",
      title: "Verification lag",
      detail: "Data behind by 18 min",
      meta: "Verified through 2:31 PM",
      href: "/alerts?kind=verification",
    },
    {
      id: "station-behind",
      tone: "warn",
      kind: "pace",
      title: "Station behind pace",
      detail: "Press Bay North",
      meta: "58 units behind required",
      href: "/stations?station_id=20000000-0000-0000-0000-000000000001",
    },
    {
      id: "camera-offline",
      tone: "warn",
      kind: "camera",
      title: "Camera offline",
      detail: "CAM-04 · Weld Cell East",
      meta: "Offline for 41 min",
      href: "/stations?camera_id=CAM-04",
    },
  ],
  exceptionMonitoringAvailable: true,
  stations: [
    {
      id: "20000000-0000-0000-0000-000000000001",
      name: "Press Bay North",
      cameraCount: 2,
      imageSrc: "/owner-preview/press-bay.jpg",
      unitsPerHour: 24,
      outputPerLaborHour: 12.6,
      projectName: "Alvarez Gates",
      projectProgress: "212 / 400 units",
      projectAssignmentKnown: true,
      status: "BEHIND",
      statusDetail: "58 units behind",
    },
    {
      id: "20000000-0000-0000-0000-000000000002",
      name: "Weld Cell West",
      cameraCount: 3,
      imageSrc: "/owner-preview/weld-cell-west.jpg",
      unitsPerHour: 31,
      outputPerLaborHour: 15.8,
      projectName: "Omega Railings",
      projectProgress: "315 / 600 units",
      projectAssignmentKnown: true,
      status: "ON_TRACK",
      statusDetail: "On pace",
    },
    {
      id: "20000000-0000-0000-0000-000000000003",
      name: "Weld Cell East",
      cameraCount: 3,
      imageSrc: "/owner-preview/weld-cell-east.jpg",
      unitsPerHour: 28,
      outputPerLaborHour: 13.2,
      projectName: "Alvarez Gates",
      projectProgress: "212 / 400 units",
      projectAssignmentKnown: true,
      status: "BEHIND",
      statusDetail: "37 units behind",
    },
    {
      id: "20000000-0000-0000-0000-000000000004",
      name: "Paint Booth",
      cameraCount: 2,
      imageSrc: "/owner-preview/paint-booth.jpg",
      unitsPerHour: 18,
      outputPerLaborHour: 9.4,
      projectName: "Summit Frames",
      projectProgress: "487 / 500 units",
      projectAssignmentKnown: true,
      status: "AHEAD",
      statusDetail: "Ahead by 1.2 days",
    },
    {
      id: "20000000-0000-0000-0000-000000000005",
      name: "Assembly Line 1",
      cameraCount: 2,
      imageSrc: "/owner-preview/assembly-line.jpg",
      unitsPerHour: 22,
      outputPerLaborHour: 11.9,
      projectName: "Omega Railings",
      projectProgress: "315 / 600 units",
      projectAssignmentKnown: true,
      status: "ON_TRACK",
      statusDetail: "On pace",
    },
  ],
};

const previewIntervalCounts = [
  6, 5, 7, 8, 9, 7, 8, 6,
  5, 6, 8, 9, 7, 8, 6, 5,
  7, 6, 8, 4, 5, 7, 8, 9,
  10, 8, 7, 7, 8, 8, 4, 5,
];

const previewProductionEvents = previewIntervalCounts.flatMap(
  (count, bucketIndex) =>
    Array.from({ length: count }, (_, eventIndex) => ({
      id: `preview-event-${bucketIndex}-${eventIndex}`,
      chunk_id: "preview-chunk-press-bay",
      occurred_at: new Date(
        Date.parse("2026-05-07T10:00:00Z")
          + bucketIndex * 15 * 60 * 1000
          + ((eventIndex + 1) * 15 * 60 * 1000) / (count + 1),
      ).toISOString(),
    })),
);

const previewWorkerIntervals = [
  {
    id: "preview-interval-1",
    worker_id: ownerPreviewWorkers[0].id,
    station_id: ownerPreviewDashboard.stations[0].id,
    project_id: ownerPreviewDashboard.projects[0].id,
    effective_start: "2026-05-07T10:00:00Z",
    effective_end: "2026-05-07T12:45:00Z",
    source: "badge" as const,
  },
  {
    id: "preview-interval-2",
    worker_id: ownerPreviewWorkers[1].id,
    station_id: ownerPreviewDashboard.stations[0].id,
    project_id: ownerPreviewDashboard.projects[0].id,
    effective_start: "2026-05-07T12:45:00Z",
    effective_end: "2026-05-07T16:30:00Z",
    source: "schedule" as const,
  },
  {
    id: "preview-interval-3",
    worker_id: ownerPreviewWorkers[2].id,
    station_id: ownerPreviewDashboard.stations[0].id,
    project_id: ownerPreviewDashboard.projects[0].id,
    effective_start: "2026-05-07T16:30:00Z",
    effective_end: "2026-05-07T18:00:00Z",
    source: "schedule" as const,
  },
];

export const ownerPreviewStation = buildOwnerStationData({
  factoryId: ownerPreviewDashboard.factoryId,
  timezone: ownerPreviewDashboard.timezone,
  selectedDate: "2026-05-07",
  station: {
    id: ownerPreviewDashboard.stations[0].id,
    name: ownerPreviewDashboard.stations[0].name,
    status: "active",
  },
  stationOptions: ownerPreviewDashboard.stations.map((station) => ({
    id: station.id,
    name: station.name,
  })),
  project: {
    id: ownerPreviewDashboard.projects[0].id,
    name: ownerPreviewDashboard.projects[0].name,
  },
  projectAssignmentKnown: true,
  windowStartIso: "2026-05-07T10:00:00Z",
  windowEndIso: "2026-05-07T18:00:00Z",
  requiredUnitsPerHour: 22.5,
  verificationRows: [
    {
      id: "preview-verification-1",
      chunk_id: "preview-chunk-press-bay",
      revision: 1,
      source_start_at: "2026-05-07T10:00:00Z",
      source_end_at: "2026-05-07T18:00:00Z",
      status: "verified",
    },
  ],
  eventRows: previewProductionEvents,
  workerRows: ownerPreviewWorkers.map((worker) => ({
    id: worker.id,
    display_name: worker.name,
    primary_role: worker.primaryRole,
    status: "active",
  })),
  workerIntervals: previewWorkerIntervals,
  downtimeRows: [
    {
      effective_start: "2026-05-07T14:15:00Z",
      effective_end: "2026-05-07T14:42:00Z",
    },
  ],
  adjustmentRows: [
    {
      kind: "scrap",
      delta_good_units: -6,
      occurred_at: "2026-05-07T15:20:00Z",
    },
    {
      kind: "rework",
      delta_good_units: -3,
      occurred_at: "2026-05-07T16:05:00Z",
    },
  ],
  nowIso: "2026-05-07T18:00:00Z",
  imageSrc: "/owner-preview/press-bay.jpg",
  evidenceLabel: "CAM-01 · Press Bay North",
  cycleTimeSeconds: 45,
  comparisonBps: {
    verifiedGoodUnits: 900,
    unitsPerHour: 800,
    laborHours: 500,
    outputPerLaborHour: 300,
  },
});

export const ownerPreviewWorkforce = buildOwnerWorkforceData({
  factoryId: ownerPreviewDashboard.factoryId,
  workers: ownerPreviewWorkers.map((worker) => ({
    id: worker.id,
    display_name: worker.name,
    employee_code: `FV-${worker.id.slice(-3)}`,
    primary_role: worker.primaryRole,
    status: "active",
  })),
  intervals: previewWorkerIntervals,
  stationNames: {
    [ownerPreviewDashboard.stations[0].id]:
      ownerPreviewDashboard.stations[0].name,
  },
  projectNames: {
    [ownerPreviewDashboard.projects[0].id]:
      ownerPreviewDashboard.projects[0].name,
  },
  windowStartIso: "2026-05-07T10:00:00Z",
  windowEndIso: "2026-05-07T18:00:00Z",
  timezone: ownerPreviewDashboard.timezone,
});

export function ownerPreviewStationFor(
  stationId?: string,
  state?: "gap" | string,
) {
  const selected =
    ownerPreviewDashboard.stations.find((station) => station.id === stationId)
    ?? ownerPreviewDashboard.stations[0];
  const project =
    ownerPreviewDashboard.projects.find(
      (candidate) => candidate.name === selected.projectName,
    )
    ?? ownerPreviewDashboard.projects[0];
  const stationData = {
    ...ownerPreviewStation,
    station: {
      ...ownerPreviewStation.station,
      id: selected.id,
      name: selected.name,
      imageSrc: selected.imageSrc,
      evidenceLabel: `${selected.cameraCount ?? "—"} cameras · ${selected.name}`,
      cycleTimeSeconds:
        selected.unitsPerHour && selected.unitsPerHour > 0
          ? Math.round(3600 / selected.unitsPerHour)
          : null,
    },
    project: { id: project.id, name: project.name },
  };
  if (state !== "gap") return stationData;
  const gapStart = 16;
  const gapEnd = 18;
  return {
    ...stationData,
    nowIso: "2026-05-07T16:00:00.000Z",
    verifiedThroughIso: "2026-05-07T14:00:00.000Z",
    verifiedThroughLabel: "10:00 AM",
    verificationState: "delayed" as const,
    production: stationData.production.map((bucket, index) =>
      index >= gapStart && index < gapEnd
        ? { ...bucket, verifiedGoodUnits: null }
        : bucket,
    ),
  };
}
