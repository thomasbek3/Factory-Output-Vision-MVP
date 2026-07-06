import {
  jobForStation,
  laborConfig,
  stationEventsThrough,
  stations,
} from "@/lib/demoData";
import { loadDemoCountEvents, type CountEventShape } from "@/lib/demoEvents";
import { pacePillLabel, workMinutesBetween } from "@/lib/paceMath";
import type { JobWithPace } from "@/lib/jobSelectors";

export type AlertType = "behind_pace" | "station_quiet" | "camera_offline";
export type AlertSeverity = "crit" | "warn";

export type DemoAlert = {
  id: string;
  source: "rules" | "demo";
  type: AlertType;
  severity: AlertSeverity;
  stationId: string;
  stationName: string;
  ts: Date;
  message: string;
  clipId: string | null;
};

function nearestClipId(stationId: string, target: Date) {
  const events = loadDemoCountEvents().filter((event) => event.station_id === stationId);
  const nearest = events.reduce<CountEventShape | null>((best, event) => {
    if (!best) return event;
    const eventDistance = Math.abs(new Date(event.ts).getTime() - target.getTime());
    const bestDistance = Math.abs(new Date(best.ts).getTime() - target.getTime());
    return eventDistance < bestDistance ? event : best;
  }, null);
  return nearest?.clip_id ?? null;
}

function stationQuietMinutes(stationId: string, now: Date) {
  const events = stationEventsThrough(stationId, now);
  const latest = events.at(-1);
  if (!latest) return Infinity;
  return workMinutesBetween(new Date(latest.ts), now, laborConfig);
}

export function evaluateDemoAlerts(now: Date, snapshots: JobWithPace[]): DemoAlert[] {
  const alerts: DemoAlert[] = [];

  for (const station of stations) {
    const job = jobForStation(station.id);
    const jobSnapshot = snapshots.find((candidate) => candidate.job.id === job?.id)?.snapshot;
    if (!job || !jobSnapshot) continue;

    if (
      jobSnapshot.expected_units_by_now > 0 &&
      jobSnapshot.pace_delta <= -0.15 * jobSnapshot.expected_units_by_now
    ) {
      alerts.push({
        id: `${station.id}-behind`,
        source: "rules",
        type: "behind_pace",
        severity: jobSnapshot.verdict === "LOSING MONEY" ? "crit" : "warn",
        stationId: station.id,
        stationName: station.name,
        ts: now,
        message: `${station.name} is ${pacePillLabel(jobSnapshot.pace_delta).toLowerCase()} on ${job.client}.`,
        clipId: nearestClipId(station.id, now),
      });
    }

    const quietMinutes = stationQuietMinutes(station.id, now);
    if (quietMinutes >= 25) {
      alerts.push({
        id: `${station.id}-quiet`,
        source: "rules",
        type: "station_quiet",
        severity: "warn",
        stationId: station.id,
        stationName: station.name,
        ts: now,
        message: `${station.name} has no verified count in ${quietMinutes} work minutes.`,
        clipId: nearestClipId(station.id, now),
      });
    }
  }

  alerts.push({
    id: "gate-line-camera-offline",
    source: "demo",
    type: "camera_offline",
    severity: "warn",
    stationId: "gate-line",
    stationName: "Gate line",
    ts: new Date(now.getTime() - 8 * 60_000),
    message: "Gate line camera missed frames for 8 minutes.",
    clipId: nearestClipId("gate-line", now),
  });

  const day = new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Los_Angeles",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(now);

  // TODO: live mode should derive alerts purely from persisted rule evaluations, not synthesized demo rows.
  alerts.push(
    {
      id: "alvarez-behind-demo",
      source: "demo",
      type: "behind_pace",
      severity: "crit",
      stationId: "gate-line",
      stationName: "Gate line",
      ts: new Date(`${day}T12:45:00-07:00`),
      message: "Gate line fell 18% behind expected output on Alvarez.",
      clipId: nearestClipId("gate-line", new Date(`${day}T12:45:00-07:00`)),
    },
    {
      id: "pallet-quiet-demo",
      source: "demo",
      type: "station_quiet",
      severity: "warn",
      stationId: "pallet-a",
      stationName: "Pallet A",
      ts: new Date(`${day}T13:12:00-07:00`),
      message: "Pallet A had no verified count for 25 work minutes.",
      clipId: nearestClipId("pallet-a", new Date(`${day}T13:12:00-07:00`)),
    },
  );

  return alerts.sort((a, b) => b.ts.getTime() - a.ts.getTime());
}

export function openAlertCount(alerts: DemoAlert[], resolvedIds: Set<string>) {
  return alerts.filter((alert) => !resolvedIds.has(alert.id)).length;
}
