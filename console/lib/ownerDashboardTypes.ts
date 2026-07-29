export type OwnerPaceStatus =
  | "BEHIND"
  | "ON_TRACK"
  | "AHEAD"
  | "DATA_DELAY";

export type OwnerProjectSummary = {
  id: string;
  name: string;
  client: string;
  status: OwnerPaceStatus;
  verifiedGoodUnits: number | null;
  targetUnits: number;
  recoverySummary: string;
  projectedMarginBps: number | null;
  projectedMarginStatus: "healthy" | "at_risk" | "loss" | "unavailable";
  deadlineLabel: string;
  verifiedThroughLabel: string;
  verificationGap: {
    startLabel: string;
    verifiedAfterLabel: string;
  } | null;
  chart: {
    actual: readonly number[];
    required: readonly number[];
    requiredToRecover: readonly number[];
    labels: readonly string[];
    nowIndex: number;
  } | null;
};

export type OwnerAttentionItem = {
  id: string;
  tone: "bad" | "warn";
  kind:
    | "verification"
    | "verification_gap"
    | "pace"
    | "camera"
    | "assignment";
  title: string;
  detail: string;
  meta: string;
  href: string;
};

export type OwnerStationSummary = {
  id: string;
  name: string;
  cameraCount: number | null;
  imageSrc: string | null;
  unitsPerHour: number | null;
  outputPerLaborHour: number | null;
  projectName: string | null;
  projectProgress: string | null;
  projectAssignmentKnown: boolean;
  status: OwnerPaceStatus;
  statusDetail: string;
};

export type OwnerDashboardData = {
  factoryId: string;
  timezone: string;
  nowIso: string;
  projects: OwnerProjectSummary[];
  attention: OwnerAttentionItem[];
  exceptionMonitoringAvailable: boolean;
  stations: OwnerStationSummary[];
};

export function ownerPaceChartIsValid(
  chart: OwnerProjectSummary["chart"],
) {
  if (!chart) return false;
  const count = chart.labels.length;
  return (
    count >= 2
    && chart.nowIndex >= 0
    && chart.nowIndex < count
    && chart.required.length === count
    && chart.actual.length === chart.nowIndex + 1
    && (
      chart.requiredToRecover.length === 0
      || chart.requiredToRecover.length === count - chart.nowIndex
    )
  );
}
