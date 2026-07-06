import { demoSourceDay, loadDemoCountEvents, type CountEventShape } from "@/lib/demoEvents";

export type StationSeed = {
  id: string;
  name: string;
  cameraId: string;
  location: string;
  baselineRate: number;
  assignedJobId: string;
  mediaSlug: string;
};

export type JobSeed = {
  id: string;
  client: string;
  title: string;
  units_required: number;
  quote_usd: number;
  cogs_usd: number;
  labor_budget_usd: number;
  created_at: string;
  deadline: string;
  station_ids: string[];
  status: "active" | "paused" | "finished";
};

export type WorkDayKey =
  | "monday"
  | "tuesday"
  | "wednesday"
  | "thursday"
  | "friday"
  | "saturday"
  | "sunday";

export type LaborConfigSeed = {
  work_hours: Partial<Record<WorkDayKey, { start: string; end: string }>>;
  hourly_rate_usd: number;
  workers_per_station: number;
};

export const demoDay = demoSourceDay;
export const demoNowIso = `${demoSourceDay}T14:32:00-07:00`;
export const lastFridayBaselineUnits = 440;

export const laborConfig: LaborConfigSeed = {
  work_hours: {
    monday: { start: "07:00", end: "17:30" },
    tuesday: { start: "07:00", end: "17:30" },
    wednesday: { start: "07:00", end: "17:30" },
    thursday: { start: "07:00", end: "17:30" },
    friday: { start: "07:00", end: "17:30" },
  },
  hourly_rate_usd: 22,
  workers_per_station: 1,
};

export const stations: StationSeed[] = [
  {
    id: "pallet-a",
    name: "Pallet A",
    cameraId: "CAM-01",
    location: "Pallet station",
    baselineRate: 19,
    assignedJobId: "job-ramirez-fencing",
    mediaSlug: "pallet-a",
  },
  {
    id: "gate-line",
    name: "Gate line",
    cameraId: "CAM-02",
    location: "Gate line",
    baselineRate: 8,
    assignedJobId: "job-alvarez-gates",
    mediaSlug: "gate-line",
  },
];

function demoIso(time: string) {
  return `${demoSourceDay}T${time}-07:00`;
}

function demoIsoOffset(days: number, time: string) {
  const date = new Date(`${demoSourceDay}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return `${date.toISOString().slice(0, 10)}T${time}-07:00`;
}

export const jobs: JobSeed[] = [
  {
    id: "job-ramirez-fencing",
    client: "Ramirez Fencing",
    title: "400 wire panels",
    units_required: 400,
    quote_usd: 1000,
    cogs_usd: 500,
    labor_budget_usd: 300,
    created_at: demoIso("07:47:49"),
    deadline: demoIsoOffset(3, "10:15:05"),
    station_ids: ["pallet-a"],
    status: "active",
  },
  {
    id: "job-delgado-hvac",
    client: "Delgado HVAC",
    title: "600 brackets",
    units_required: 600,
    quote_usd: 1800,
    cogs_usd: 700,
    labor_budget_usd: 520,
    created_at: demoIso("07:00:00"),
    deadline: demoIsoOffset(4, "12:16:44"),
    station_ids: ["gate-line"],
    status: "active",
  },
  {
    id: "job-alvarez-gates",
    client: "Alvarez Gates",
    title: "120 frame gates",
    units_required: 120,
    quote_usd: 2400,
    cogs_usd: 1150,
    labor_budget_usd: 800,
    created_at: demoIsoOffset(-1, "07:00:00"),
    deadline: demoIsoOffset(4, "08:33:33"),
    station_ids: ["gate-line", "pallet-a"],
    status: "active",
  },
];

export function countEventsThrough(now: Date): CountEventShape[] {
  return loadDemoCountEvents().filter((event) => new Date(event.ts) <= now);
}

export function stationEventsThrough(stationId: string, now: Date): CountEventShape[] {
  return countEventsThrough(now).filter((event) => event.station_id === stationId);
}

export function eventsForStation(stationId: string): CountEventShape[] {
  return loadDemoCountEvents()
    .filter((event) => event.station_id === stationId)
    .sort((a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime());
}

export function findEventByClipId(clipId: string) {
  return loadDemoCountEvents().find((event) => event.clip_id === clipId || event.id === clipId);
}

export function jobForStation(stationId: string) {
  const station = stations.find((candidate) => candidate.id === stationId);
  return station ? jobs.find((job) => job.id === station.assignedJobId) : undefined;
}

export function jobForEvent(event: CountEventShape) {
  return jobs.find((job) => job.id === event.job_id) ?? jobForStation(event.station_id);
}

export function stationForEvent(event: CountEventShape) {
  return stations.find((station) => station.id === event.station_id);
}

export function mediaBucketForTime(date: Date) {
  const hour = Number(
    new Intl.DateTimeFormat("en-US", {
      timeZone: "America/Los_Angeles",
      hour: "2-digit",
      hour12: false,
    }).format(date),
  );

  if (hour < 12) return "morning";
  if (hour < 15) return "midday";
  return "afternoon";
}

export function mediaUrlForStation(stationId: string, now: Date) {
  const station = stations.find((candidate) => candidate.id === stationId);
  const slug = station?.mediaSlug ?? stationId;
  return `/api/media/${slug}/${mediaBucketForTime(now)}.mp4`;
}

export function mediaPosterUrlForStation(stationId: string, now: Date) {
  const station = stations.find((candidate) => candidate.id === stationId);
  const slug = station?.mediaSlug ?? stationId;
  return `/api/media/${slug}/${mediaBucketForTime(now)}.jpg`;
}
