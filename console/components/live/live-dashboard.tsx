"use client";

import Link from "next/link";
import { AreaChart } from "@tremor/react";
import { AlertTriangle, ChevronDown, Clock3, MoreHorizontal, Play, Search } from "lucide-react";
import { Panel } from "@/components/ui/panel";
import { Button } from "@/components/ui/button";
import { useTime } from "@/components/providers/time-provider";
import { useClipDrawer } from "@/components/live/clip-drawer-provider";
import { useConsoleJobs } from "@/components/jobs/use-console-jobs";
import {
  countEventsThrough,
  lastFridayBaselineUnits,
  mediaUrlForStation,
  stationEventsThrough,
  stations,
} from "@/lib/demoData";
import { evaluateDemoAlerts, type DemoAlert } from "@/lib/alerts";
import { type PaceSnapshot } from "@/lib/paceMath";
import {
  cumulativeMarginSeries,
  eventsByHour,
  moneySentence,
  pacePillLabel,
  proratedBaselineUnits,
  selectMoneyStripTotal,
  selectRunningJobSnapshots,
  type JobWithPace,
} from "@/lib/jobSelectors";
import { selectStationCountSnapshots, type StationCountSnapshot } from "@/lib/stationSelectors";
import { cn } from "@/lib/utils";

export function formatMoney(value: number) {
  const rounded = Math.round(value);
  const sign = rounded >= 0 ? "+" : "-";
  return `${sign}$${Math.abs(rounded).toLocaleString("en-US")}`;
}

export function formatCompactTime(date: Date) {
  return new Intl.DateTimeFormat("en-US", {
    timeZone: "America/Los_Angeles",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

export function MoneyStrip({
  snapshots,
  now,
  scale = "normal",
}: {
  snapshots: JobWithPace[];
  now: Date;
  scale?: "normal" | "tv";
}) {
  const allEvents = countEventsThrough(now);
  const totalMargin = selectMoneyStripTotal(snapshots);
  const expectedByNow = proratedBaselineUnits(now, lastFridayBaselineUnits);
  const delta = allEvents.length - expectedByNow;
  const percentDelta = Math.round((delta / Math.max(expectedByNow, 1)) * 100);
  const chartData = eventsByHour(allEvents);
  const marginChartData = cumulativeMarginSeries(snapshots, allEvents);
  const latest = allEvents.at(-1);
  const { openClip } = useClipDrawer();

  return (
    <section className={cn("grid gap-4 xl:grid-cols-[minmax(0,1.6fr)_minmax(260px,.7fr)_minmax(260px,.7fr)]", scale === "tv" && "xl:grid-cols-1")}>
      <Panel className={cn("relative min-h-[214px] overflow-hidden", scale === "tv" && "min-h-[420px] p-10")}>
        <div className="relative z-[1]">
          <div className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--text-dim)]">
          TODAY · {snapshots.length} JOBS RUNNING
          </div>
          <div
            className={cn(
              "mt-4 text-[60px] font-bold leading-none tracking-[-0.01em] drop-shadow-[0_0_22px_rgba(70,194,107,.24)]",
              scale === "tv" && "text-[128px]",
              totalMargin >= 0 ? "text-[var(--good)]" : "text-[var(--bad)]",
            )}
          >
            {formatMoney(totalMargin)}
          </div>
          <p className={cn("mt-4 max-w-xl text-[14px] leading-6 text-[var(--text-mut)]", scale === "tv" && "max-w-5xl text-[34px] leading-[1.25]")}>
            {moneySentence(snapshots)}
          </p>
        </div>
        <div className="absolute inset-y-6 right-4 w-[46%] opacity-35">
          <AreaChart
            data={marginChartData}
            index="hour"
            categories={["margin"]}
            colors={["emerald"]}
            showAnimation={false}
            showLegend={false}
            showXAxis={false}
            showYAxis={false}
            showGridLines={false}
            className="h-full"
          />
        </div>
      </Panel>

      <Panel className={cn("min-h-[214px]", scale === "tv" && "hidden")}>
        <div className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--text-dim)]">
          UNITS VERIFIED TODAY
        </div>
        <button
          type="button"
          className="mt-4 text-left text-[32px] font-bold leading-none tracking-[-0.01em] text-[var(--text)] hover:text-[var(--accent)]"
          onClick={() => latest && openClip(latest.clip_id)}
        >
          {allEvents.length}
        </button>
        <div
          className={cn(
            "mt-3 inline-flex rounded-full px-2 py-1 text-[12px] font-semibold",
            delta >= 0 ? "bg-[var(--good-tint)] text-[var(--good)]" : "bg-[var(--bad-tint)] text-[var(--bad)]",
          )}
        >
          {delta >= 0 ? "▲" : "▼"} {Math.abs(percentDelta)}% vs expected by now
        </div>
        <AreaChart
          data={chartData}
          index="hour"
          categories={["units"]}
          colors={["emerald"]}
          showAnimation={false}
          showLegend={false}
          showXAxis={false}
          showYAxis={false}
          showGridLines={false}
          className="mt-5 h-[72px]"
        />
      </Panel>

      <Panel className={cn("min-h-[214px]", scale === "tv" && "hidden")}>
        <div className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--text-dim)]">
          COUNTS VERIFIED
        </div>
        <div className="mt-4 text-[32px] font-bold leading-none tracking-[-0.01em] text-[var(--text)]">
          100%
        </div>
        <div className="mt-3 inline-flex rounded-full bg-[var(--good-tint)] px-2 py-1 text-[12px] font-semibold text-[var(--good)]">
          HUMAN+AI
        </div>
        <p className="mt-5 text-[14px] leading-6 text-[var(--text-mut)]">
          Every count has a reviewed clip behind it. Tap a number and the proof opens.
        </p>
      </Panel>
    </section>
  );
}

export function CameraCard({
  station,
  now,
  snapshot,
  events: selectedEvents,
  scale = "normal",
}: {
  station: (typeof stations)[number];
  now: Date;
  snapshot: PaceSnapshot;
  events?: StationCountSnapshot["events"];
  scale?: "normal" | "tv";
}) {
  const { openClip } = useClipDrawer();
  const events = selectedEvents ?? stationEventsThrough(station.id, now);
  const latest = events.at(-1);
  const chartData = eventsByHour(events);
  const isBehind = snapshot.pace_delta < 0;

  return (
    <Panel className={cn("p-5", scale === "tv" && "p-8")}>
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h2 className={cn("text-[16px] font-semibold text-[var(--text)]", scale === "tv" && "text-[34px]")}>{station.name}</h2>
          <div className={cn("mt-1 text-[12px] text-[var(--text-dim)]", scale === "tv" && "text-[18px]")}>
            {station.cameraId} · {station.location}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-[var(--bad-tint)] px-2 py-1 text-[11px] font-bold text-[var(--bad)]">
            <span className="h-1.5 w-1.5 rounded-full bg-[var(--bad)] shadow-[0_0_10px_rgba(229,72,77,.7)]" />
            LIVE
          </span>
          <button
            type="button"
            className="flex h-8 w-8 items-center justify-center rounded-lg text-[var(--text-dim)] hover:bg-white/[.04] hover:text-[var(--text)]"
            aria-label={`${station.name} menu`}
          >
            <MoreHorizontal className="h-4 w-4" strokeWidth={1.75} />
          </button>
        </div>
      </div>

      <video
        src={mediaUrlForStation(station.id, now)}
        className="aspect-video w-full rounded-lg bg-black object-cover ring-1 ring-[var(--border-soft)]"
        autoPlay
        muted
        loop
        playsInline
      />

      <div className={cn("mt-4 grid grid-cols-[minmax(116px,.7fr)_minmax(140px,1fr)_auto] items-center gap-4", scale === "tv" && "grid-cols-[minmax(220px,.7fr)_minmax(220px,1fr)_auto]")}>
        <div>
          <button
            type="button"
            className={cn("text-left text-[40px] font-bold leading-none tracking-[-0.01em] text-[var(--text)] hover:text-[var(--accent)]", scale === "tv" && "text-[96px]")}
            style={scale === "tv" ? { fontSize: 96, lineHeight: 0.9 } : undefined}
            onClick={() => latest && openClip(latest.clip_id)}
          >
            {events.length}
          </button>
          <button
            type="button"
            className={cn("mt-2 block text-left text-[12px] text-[var(--text-dim)] hover:text-[var(--accent)]", scale === "tv" && "text-[20px]")}
            onClick={() => latest && openClip(latest.clip_id)}
          >
            today · last count {latest ? formatCompactTime(new Date(latest.ts)) : "none"}
          </button>
        </div>
        <AreaChart
          data={chartData}
          index="hour"
          categories={["units"]}
          colors={[isBehind ? "red" : "emerald"]}
          showAnimation={false}
          showLegend={false}
          showXAxis={false}
          showYAxis={false}
          showGridLines={false}
          className={cn("h-[78px]", scale === "tv" && "h-[136px]")}
        />
        <span
          className={cn(
            "rounded-full px-3 py-2 text-[12px] font-bold",
            scale === "tv" && "px-5 py-3 text-[24px]",
            isBehind ? "bg-[var(--bad-tint)] text-[var(--bad)]" : "bg-[var(--good-tint)] text-[var(--good)]",
          )}
        >
          {pacePillLabel(snapshot.pace_delta)}
        </span>
      </div>
    </Panel>
  );
}

function AlertsRail({ alerts }: { alerts: DemoAlert[] }) {
  const { openClip } = useClipDrawer();

  return (
    <Panel className="mt-4">
      <div className="mb-4 flex items-center justify-between">
        <div className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--text-dim)]">
          ALERTS
        </div>
        <Link href="/alerts" className="text-[13px] font-semibold text-[var(--accent)]">
          View all alerts →
        </Link>
      </div>
      <div className="divide-y divide-[var(--border-soft)]">
        {alerts.length ? (
          alerts.map((alert) => (
            <div key={alert.id} className="grid grid-cols-[24px_64px_minmax(96px,.5fr)_1fr_auto_28px] items-center gap-3 py-3 text-[13px]">
              <AlertTriangle
                className={cn("h-4 w-4", alert.severity === "crit" ? "text-[var(--bad)]" : "text-[var(--warn)]")}
                strokeWidth={1.75}
              />
              <span className="text-[12px] text-[var(--text-dim)]">{formatCompactTime(alert.ts)}</span>
              <span className="font-semibold text-[var(--text)]">{alert.stationName}</span>
              <span className="text-[var(--text-mut)]">{alert.message}</span>
              <Button
                type="button"
                variant="primary"
                className="h-8"
                onClick={() => alert.clipId && openClip(alert.clipId)}
              >
                <Play className="h-3.5 w-3.5 fill-[#11100d]" strokeWidth={1.75} />
                Watch replay
              </Button>
              <button
                type="button"
                className="flex h-8 w-8 items-center justify-center rounded-lg text-[var(--text-dim)] hover:bg-white/[.04]"
                aria-label={`${alert.stationName} alert menu`}
              >
                <MoreHorizontal className="h-4 w-4" strokeWidth={1.75} />
              </button>
            </div>
          ))
        ) : (
          <div className="py-5 text-[14px] text-[var(--text-mut)]">
            No open alerts. The wall is quiet and on pace.
          </div>
        )}
      </div>
    </Panel>
  );
}

function TimeControls() {
  const { now, speed, setSpeed, jumpTo } = useTime();

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--panel-2)] px-2 py-2 text-[12px] text-[var(--text-mut)]">
      <Clock3 className="h-4 w-4 text-[var(--accent)]" strokeWidth={1.75} />
      <span className="px-1 font-semibold text-[var(--text)]">{formatCompactTime(now())}</span>
      <button
        type="button"
        className={cn("rounded-md px-2 py-1 font-semibold", speed === 1 ? "bg-[var(--accent)] text-[#11100d]" : "hover:bg-white/[.04]")}
        onClick={() => setSpeed(1)}
      >
        1x
      </button>
      <button
        type="button"
        className={cn("rounded-md px-2 py-1 font-semibold", speed === 60 ? "bg-[var(--accent)] text-[#11100d]" : "hover:bg-white/[.04]")}
        onClick={() => setSpeed(60)}
      >
        60x
      </button>
      <button
        type="button"
        className="rounded-md px-2 py-1 font-semibold hover:bg-white/[.04]"
        onClick={() => jumpTo("2026-06-26T14:32:00-07:00")}
      >
        Jump 2:32p
      </button>
    </div>
  );
}

export function LiveDashboard() {
  const { now } = useTime();
  const { jobs: consoleJobs } = useConsoleJobs();
  const current = now();
  const snapshots = selectRunningJobSnapshots(current, consoleJobs);
  const stationSnapshots = selectStationCountSnapshots(current, consoleJobs);
  const alerts = evaluateDemoAlerts(current, snapshots).slice(0, 3);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--text-dim)]">
            LIVE
          </div>
          <h1 className="mt-2 text-[28px] font-semibold tracking-[-0.01em] text-[var(--text)]">
            Factory floor
          </h1>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="hidden h-9 items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--panel-2)] px-3 text-[13px] text-[var(--text-dim)] md:flex">
            <Search className="h-4 w-4" strokeWidth={1.75} />
            Jump to station or time
            <ChevronDown className="h-4 w-4" strokeWidth={1.75} />
          </div>
          <TimeControls />
        </div>
      </div>

      <MoneyStrip snapshots={snapshots} now={current} />

      <section className="grid gap-4 lg:grid-cols-2">
        {stationSnapshots.map(({ station, events, pace }) => {
          return (
            <CameraCard
              key={station.id}
              station={station}
              now={current}
              snapshot={pace}
              events={events}
            />
          );
        })}
      </section>

      <AlertsRail alerts={alerts} />
    </div>
  );
}
