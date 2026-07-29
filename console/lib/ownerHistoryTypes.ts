export type OwnerHistoryGrade = "A" | "B" | "C" | "C−";

export type OwnerHistoryEvidence = {
  count: number;
  state: "available" | "expired" | "unavailable";
  retentionDate: string | null;
};

export type OwnerHistoryAuditEntry = {
  id: string;
  createdAt: string;
  actorType: "user" | "service" | "system";
  action: string;
  summary: string;
  detail: string;
};

export type OwnerHistoryOutputBucket = {
  weekStart: string | null;
  label: string;
  plannedUnits: number | null;
  actualUnits: number | null;
};

export type OwnerHistoryRecord = {
  id: string;
  projectId: string;
  revision: number;
  projectName: string;
  customerName: string;
  factoryTimezone: string | null;
  completedAt: string;
  deadlineAt: string;
  plannedUnits: number;
  actualUnits: number;
  plannedScheduleMinutes: number | null;
  actualScheduleMinutes: number | null;
  plannedLaborCents: number;
  actualLaborCents: number;
  actualLaborMinutes: number | null;
  plannedMaterialsCents: number;
  actualMaterialsCents: number;
  plannedMarginCents: number;
  actualMarginCents: number;
  onTime: boolean;
  verificationHasGap: boolean;
  grade: OwnerHistoryGrade;
  stationNames: string[];
  shiftNames: string[];
  teamNames: string[];
  output: OwnerHistoryOutputBucket[];
  audit: OwnerHistoryAuditEntry[];
  evidence: OwnerHistoryEvidence;
};

export type OwnerHistoryFilters = {
  range: "30" | "90" | "365" | "all";
  project: string;
  customer: string;
  station: string;
  shift: string;
  team: string;
  status: "all" | "on_time" | "late" | "positive_margin" | "negative_margin";
};

export type OwnerHistorySummary = {
  completedProjects: number;
  onTimeCount: number;
  onTimePercent: number | null;
  unitsPerLaborHour: number | null;
  laborCoverageCount: number;
  marginAfterDirectCostsCents: number;
};

export type OwnerHistoryData = {
  factoryId: string;
  timezone: string;
  filters: OwnerHistoryFilters;
  records: OwnerHistoryRecord[];
  summary: OwnerHistorySummary;
  options: {
    projects: string[];
    customers: string[];
    stations: string[];
    shifts: string[];
    teams: string[];
  };
};
