export type FinishedJob = {
  id: string;
  client: string;
  product: string;
  spec: string;
  finishedAt: string;
  stations: string[];
  quotedDays: number;
  actualDays: number;
  plannedMarginUsd: number;
  realMarginUsd: number;
  plannedLaborUsd: number;
  actualLaborUsd: number;
  dailyOutput: { day: string; units: number }[];
  stationContribution: { station: string; units: number }[];
  bottleneckStation: string;
};

export type FinishedJobGrade = "A" | "B" | "C" | "C−";

export function roundHalf(value: number) {
  return Math.round(value * 2) / 2;
}

export function gradeFinishedJob(job: Pick<FinishedJob, "quotedDays" | "actualDays" | "plannedMarginUsd" | "realMarginUsd">): FinishedJobGrade {
  if (job.realMarginUsd < 0) return "C−";
  if (job.realMarginUsd >= job.plannedMarginUsd && job.actualDays <= job.quotedDays) return "A";
  if (job.realMarginUsd >= 0.8 * job.plannedMarginUsd || job.actualDays <= job.quotedDays + 1) return "B";
  return "C";
}

export function nextTimeSuggestion(job: Pick<FinishedJob, "client" | "product" | "quotedDays" | "actualDays" | "plannedMarginUsd" | "realMarginUsd" | "bottleneckStation">) {
  const suggestDays = roundHalf(job.actualDays * 1.05);
  const delta = Math.round(job.realMarginUsd - job.plannedMarginUsd);

  if (job.actualDays > job.quotedDays) {
    const pct = Math.round(((job.actualDays - job.quotedDays) / job.quotedDays) * 100);
    return {
      suggestDays,
      delta,
      sentence: `You quoted ${job.quotedDays.toFixed(1)} days. Your crew did it in ${job.actualDays.toFixed(1)}. This ran ${pct}% over — price the next one up or fix the bottleneck at ${job.bottleneckStation}.`,
    };
  }

  return {
    suggestDays,
    delta,
    sentence: `You quoted ${job.quotedDays.toFixed(1)} days. Your crew did it in ${job.actualDays.toFixed(1)}. Quote the next ${job.client} ${job.product} order at ${suggestDays.toFixed(1)} days — same price keeps $${Math.abs(delta).toLocaleString("en-US")} more margin.`,
  };
}

export const finishedJobs: FinishedJob[] = [
  {
    id: "hist-ramirez",
    client: "Ramirez",
    product: "wire panels",
    spec: "400 wire panels · Pallet A",
    finishedAt: "2026-06-24T15:20:00-07:00",
    stations: ["Pallet A"],
    quotedDays: 4.0,
    actualDays: 3.4,
    plannedMarginUsd: 200,
    realMarginUsd: 264,
    plannedLaborUsd: 300,
    actualLaborUsd: 236,
    dailyOutput: [
      { day: "Mon", units: 88 },
      { day: "Tue", units: 124 },
      { day: "Wed", units: 116 },
      { day: "Thu", units: 72 },
    ],
    stationContribution: [{ station: "Pallet A", units: 400 }],
    bottleneckStation: "Pallet A",
  },
  {
    id: "hist-kowalski",
    client: "Kowalski",
    product: "brackets",
    spec: "520 brackets · Press bay",
    finishedAt: "2026-06-20T16:10:00-07:00",
    stations: ["Press Bay", "Pallet A"],
    quotedDays: 3.0,
    actualDays: 3.2,
    plannedMarginUsd: 360,
    realMarginUsd: 318,
    plannedLaborUsd: 420,
    actualLaborUsd: 462,
    dailyOutput: [
      { day: "Tue", units: 132 },
      { day: "Wed", units: 171 },
      { day: "Thu", units: 154 },
      { day: "Fri", units: 63 },
    ],
    stationContribution: [
      { station: "Press Bay", units: 336 },
      { station: "Pallet A", units: 184 },
    ],
    bottleneckStation: "Press Bay",
  },
  {
    id: "hist-delgado",
    client: "Delgado",
    product: "HVAC brackets",
    spec: "600 HVAC brackets · Gate line",
    finishedAt: "2026-06-17T14:45:00-07:00",
    stations: ["Gate line"],
    quotedDays: 2.5,
    actualDays: 3.9,
    plannedMarginUsd: 420,
    realMarginUsd: 112,
    plannedLaborUsd: 520,
    actualLaborUsd: 828,
    dailyOutput: [
      { day: "Thu", units: 104 },
      { day: "Fri", units: 128 },
      { day: "Mon", units: 162 },
      { day: "Tue", units: 206 },
    ],
    stationContribution: [{ station: "Gate line", units: 600 }],
    bottleneckStation: "Gate line",
  },
  {
    id: "hist-alvarez",
    client: "Alvarez",
    product: "frame gates",
    spec: "120 frame gates · Gate line + Pallet A",
    finishedAt: "2026-06-13T17:05:00-07:00",
    stations: ["Gate line", "Pallet A"],
    quotedDays: 2.0,
    actualDays: 3.1,
    plannedMarginUsd: 450,
    realMarginUsd: -86,
    plannedLaborUsd: 800,
    actualLaborUsd: 1336,
    dailyOutput: [
      { day: "Tue", units: 22 },
      { day: "Wed", units: 31 },
      { day: "Thu", units: 29 },
      { day: "Fri", units: 38 },
    ],
    stationContribution: [
      { station: "Gate line", units: 73 },
      { station: "Pallet A", units: 47 },
    ],
    bottleneckStation: "Gate line",
  },
].sort((a, b) => new Date(b.finishedAt).getTime() - new Date(a.finishedAt).getTime());

export function historyAggregates(records: FinishedJob[] = finishedJobs) {
  const avgQuoteErrorPct =
    records.reduce((total, job) => total + Math.abs(job.actualDays - job.quotedDays) / job.quotedDays, 0) /
    Math.max(records.length, 1);
  const marginRecovered = records.reduce(
    (total, job) => total + Math.max(0, job.realMarginUsd - job.plannedMarginUsd),
    0,
  );

  return {
    lifetimeJobs: records.length,
    avgQuoteErrorPct: Math.round(avgQuoteErrorPct * 100),
    marginRecovered,
  };
}
