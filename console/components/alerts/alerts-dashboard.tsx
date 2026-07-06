"use client";

import { useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, CircleDot, Filter, Play } from "lucide-react";
import { useConsoleJobs } from "@/components/jobs/use-console-jobs";
import { useClipDrawer } from "@/components/live/clip-drawer-provider";
import { formatCompactTime } from "@/components/live/live-dashboard";
import { useTime } from "@/components/providers/time-provider";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";
import { evaluateDemoAlerts, type AlertType, type DemoAlert } from "@/lib/alerts";
import { stations } from "@/lib/demoData";
import { selectRunningJobSnapshots } from "@/lib/jobSelectors";
import { cn } from "@/lib/utils";

const storageKey = "factoryvision.resolvedAlertIds";
const alertTypes: AlertType[] = ["behind_pace", "station_quiet", "camera_offline"];

function readResolvedIds() {
  if (typeof window === "undefined") return new Set<string>();
  try {
    const value = window.localStorage.getItem(storageKey);
    const parsed = value ? (JSON.parse(value) as string[]) : [];
    return new Set(parsed);
  } catch {
    return new Set<string>();
  }
}

function writeResolvedIds(ids: Set<string>) {
  window.localStorage.setItem(storageKey, JSON.stringify([...ids]));
  window.dispatchEvent(new CustomEvent("factoryvision:alerts-resolved"));
}

function dayLabel(date: Date) {
  return new Intl.DateTimeFormat("en-US", {
    timeZone: "America/Los_Angeles",
    weekday: "long",
    month: "short",
    day: "numeric",
  }).format(date);
}

function typeLabel(type: AlertType) {
  return type.replace("_", " ");
}

function SeverityIcon({ alert }: { alert: DemoAlert }) {
  return (
    <span
      className={cn(
        "inline-flex h-8 w-8 items-center justify-center rounded-full",
        alert.severity === "crit" ? "bg-[var(--bad-tint)] text-[var(--bad)]" : "bg-[var(--warn-tint)] text-[var(--warn)]",
      )}
    >
      <AlertTriangle className="h-4 w-4" strokeWidth={1.75} />
    </span>
  );
}

export function AlertsDashboard() {
  const { now } = useTime();
  const { jobs } = useConsoleJobs();
  const { openClip } = useClipDrawer();
  const [resolvedIds, setResolvedIds] = useState<Set<string>>(() => readResolvedIds());
  const [status, setStatus] = useState<"open" | "resolved">("open");
  const [stationId, setStationId] = useState("all");
  const [type, setType] = useState<AlertType | "all">("all");
  const current = now();
  const snapshots = selectRunningJobSnapshots(current, jobs);
  const alerts = evaluateDemoAlerts(current, snapshots);

  const filteredAlerts = useMemo(
    () =>
      alerts.filter((alert) => {
        const resolved = resolvedIds.has(alert.id);
        return (
          (status === "resolved" ? resolved : !resolved) &&
          (stationId === "all" || alert.stationId === stationId) &&
          (type === "all" || alert.type === type)
        );
      }),
    [alerts, resolvedIds, stationId, status, type],
  );

  const grouped = useMemo(() => {
    const groups = new Map<string, DemoAlert[]>();
    for (const alert of filteredAlerts) {
      const key = dayLabel(alert.ts);
      groups.set(key, [...(groups.get(key) ?? []), alert]);
    }
    return [...groups.entries()];
  }, [filteredAlerts]);

  function resolveAlert(alertId: string) {
    setResolvedIds((currentIds) => {
      const next = new Set(currentIds);
      next.add(alertId);
      writeResolvedIds(next);
      return next;
    });
  }

  return (
    <div className="space-y-5" data-alerts-route="ready" data-open-alert-count={alerts.filter((alert) => !resolvedIds.has(alert.id)).length}>
      <section className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--text-dim)]">
            ALERTS
          </div>
          <h1 className="mt-2 text-[28px] font-semibold tracking-[-0.01em] text-[var(--text)]">
            Floor exceptions
          </h1>
        </div>
        <div className="flex items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--panel-2)] px-3 py-2 text-[13px] text-[var(--text-mut)]">
          <Filter className="h-4 w-4 text-[var(--accent)]" strokeWidth={1.75} />
          {alerts.filter((alert) => !resolvedIds.has(alert.id)).length} open
        </div>
      </section>

      <Panel className="p-4">
        <div className="flex flex-wrap gap-2">
          {(["open", "resolved"] as const).map((nextStatus) => (
            <button
              key={nextStatus}
              type="button"
              className={cn(
                "h-9 rounded-lg border px-3 text-[13px] font-semibold capitalize",
                status === nextStatus
                  ? "border-[var(--accent)] bg-[var(--accent)] text-[#11100d]"
                  : "border-[var(--border)] bg-[var(--panel-2)] text-[var(--text-mut)]",
              )}
              onClick={() => setStatus(nextStatus)}
            >
              {nextStatus}
            </button>
          ))}
          <select
            value={stationId}
            onChange={(event) => setStationId(event.target.value)}
            className="h-9 rounded-lg border border-[var(--border)] bg-[var(--panel-2)] px-3 text-[13px] font-semibold text-[var(--text)]"
          >
            <option value="all">All stations</option>
            {stations.map((station) => (
              <option key={station.id} value={station.id}>{station.name}</option>
            ))}
          </select>
          <select
            value={type}
            onChange={(event) => setType(event.target.value as AlertType | "all")}
            className="h-9 rounded-lg border border-[var(--border)] bg-[var(--panel-2)] px-3 text-[13px] font-semibold text-[var(--text)]"
          >
            <option value="all">All types</option>
            {alertTypes.map((alertType) => (
              <option key={alertType} value={alertType}>{typeLabel(alertType)}</option>
            ))}
          </select>
        </div>
      </Panel>

      <Panel className="overflow-hidden p-0">
        {grouped.length ? (
          grouped.map(([day, dayAlerts]) => (
            <section key={day}>
              <div className="border-b border-[var(--border-soft)] bg-black/10 px-5 py-3 text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--text-dim)]">
                {day}
              </div>
              <div className="divide-y divide-[var(--border-soft)]">
                {dayAlerts.map((alert) => {
                  const resolved = resolvedIds.has(alert.id);
                  return (
                    <div key={alert.id} className="grid grid-cols-[40px_72px_minmax(110px,.45fr)_120px_minmax(220px,1fr)_auto_auto] items-center gap-3 px-5 py-4 text-[13px]">
                      <SeverityIcon alert={alert} />
                      <span className="text-[12px] text-[var(--text-dim)]">{formatCompactTime(alert.ts)}</span>
                      <span className="font-semibold text-[var(--text)]">{alert.stationName}</span>
                      <span className="inline-flex w-fit items-center gap-1 rounded-full border border-[var(--border)] bg-[var(--panel-2)] px-2 py-1 text-[11px] font-semibold text-[var(--text-mut)]">
                        <CircleDot className="h-3 w-3" strokeWidth={1.75} />
                        {typeLabel(alert.type)}
                      </span>
                      <span className="leading-5 text-[var(--text-mut)]">{alert.message}</span>
                      <Button
                        type="button"
                        variant="primary"
                        onClick={() => alert.clipId && openClip(alert.clipId)}
                      >
                        <Play className="h-3.5 w-3.5 fill-[#11100d]" strokeWidth={1.75} />
                        Watch replay
                      </Button>
                      {resolved ? (
                        <span className="inline-flex h-9 items-center gap-2 rounded-lg bg-[var(--good-tint)] px-3 text-[13px] font-semibold text-[var(--good)]">
                          <CheckCircle2 className="h-4 w-4" strokeWidth={1.75} />
                          Resolved
                        </span>
                      ) : (
                        <Button type="button" variant="secondary" onClick={() => resolveAlert(alert.id)}>
                          Resolve
                        </Button>
                      )}
                    </div>
                  );
                })}
              </div>
            </section>
          ))
        ) : (
          <div className="px-5 py-8 text-[14px] text-[var(--text-mut)]">
            No alerts match these filters.
          </div>
        )}
      </Panel>
    </div>
  );
}
