export type OwnerStationOption = {
  id: string;
  name: string;
};

export type OwnerStationKpi = {
  value: number | null;
  decimals: number;
  suffix?: string;
  comparisonBps: number | null;
};

export type OwnerStationBucket = {
  startIso: string;
  label: string;
  verifiedGoodUnits: number | null;
  requiredUnits: number | null;
  downtimeMinutes: number;
};

export type OwnerStationTeamMember = {
  id: string;
  name: string;
  scheduledInterval: string;
  laborHours: number | null;
  primaryRole: string | null;
  attribution: "solo_high_confidence" | "team_only" | "unavailable";
  attributionDetail: string;
};

export type OwnerStationData = {
  factoryId: string;
  timezone: string;
  selectedDate: string;
  station: OwnerStationOption & {
    status: "active" | "inactive";
    imageSrc: string | null;
    evidenceLabel: string;
    cycleTimeSeconds: number | null;
  };
  stationOptions: OwnerStationOption[];
  project: { id: string; name: string } | null;
  projectAssignmentKnown: boolean;
  verifiedThroughLabel: string;
  verifiedThroughIso: string | null;
  nowIso: string;
  windowStartIso: string;
  windowEndIso: string;
  verificationState: "verified" | "delayed" | "unavailable";
  shiftLabel: string;
  selectedAssignmentId: string;
  shiftOptions: { id: string; label: string }[];
  kpis: {
    verifiedGoodUnits: OwnerStationKpi;
    unitsPerHour: OwnerStationKpi;
    laborHours: OwnerStationKpi;
    outputPerLaborHour: OwnerStationKpi;
  };
  production: OwnerStationBucket[];
  team: OwnerStationTeamMember[];
  summary: {
    scrapUnits: number | null;
    reworkUnits: number | null;
    downtimeMinutes: number | null;
  };
};

export type OwnerWorkforceMember = {
  id: string;
  name: string;
  employeeCode: string | null;
  primaryRole: string | null;
  status: "active" | "inactive";
  stationName: string | null;
  projectName: string | null;
  scheduledInterval: string | null;
  attribution: "team_only" | "solo_high_confidence" | "unassigned";
};

export type OwnerWorkforceData = {
  factoryId: string;
  members: OwnerWorkforceMember[];
  activeCount: number;
  assignedCount: number;
  stationCount: number;
};
