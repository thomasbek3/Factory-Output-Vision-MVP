"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AlertTriangle, Clock3, MoreHorizontal, Play, WifiOff } from "lucide-react";
import { AreaSpark } from "@/components/charts/AreaSpark";
import { Panel } from "@/components/ui/panel";
import { Button } from "@/components/ui/button";
import { useTime } from "@/components/providers/time-provider";
import { useClipDrawer } from "@/components/live/clip-drawer-provider";
import { CameraTileMenu } from "@/components/live/camera-tile-menu";
import { useConsoleJobs } from "@/components/jobs/use-console-jobs";
import {
  countEventsThrough,
  lastFridayBaselineUnits,
  mediaPosterUrlForStation,
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

function hourlyValues(data: Array<{ units: number }>) {
  return data.map((point) => point.units);
}

function marginValues(data: Array<{ margin: number }>) {
  return data.map((point) => point.margin);
}

function cameraSparkValues(events: StationCountSnapshot["events"], isBehind: boolean) {
  const values = hourlyValues(eventsByHour(events));
  if (!isBehind) return values;
  const max = Math.max(...values, 1);
  return values.map((value, index) => Math.max(0, max - index * 1.6 - value * 0.12));
}

/**
 * Live camera feed. Autoplays muted+playsInline and shows the poster before it
 * plays. If the media errors (dead feed through the tunnel), it swaps to a
 * "reconnecting…" card instead of a black void and retries the source on a
 * backoff, so a transient blip self-heals.
 */
function LiveVideo({
  src,
  poster,
  className,
}: {
  src: string;
  poster: string;
  className?: string;
}) {
  const [errored, setErrored] = useState(false);
  const [cacheBust, setCacheBust] = useState(0);

  // On error, retry the source after a short delay (up to a few attempts).
  useEffect(() => {
    if (!errored || cacheBust >= 3) return;
    const timer = window.setTimeout(() => {
      setErrored(false);
      setCacheBust((n) => n + 1);
    }, 3000);
    return () => window.clearTimeout(timer);
  }, [errored, cacheBust]);

  const resolvedSrc = cacheBust > 0 ? `${src}?r=${cacheBust}` : src;

  if (errored) {
    return (
      <div
        data-camera-state="reconnecting"
        className={cn(
          "flex aspect-video w-full flex-col items-center justify-center gap-2 rounded-lg bg-black text-[var(--text-mut)] ring-1 ring-[var(--border-soft)]",
          className,
        )}
        style={{ backgroundImage: `url(${poster})`, backgroundSize: "cover", backgroundPosition: "center" }}
      >
        <div className="flex flex-col items-center gap-2 rounded-lg bg-black/60 px-4 py-3">
          <WifiOff className="h-5 w-5 animate-pulse text-[var(--warn)]" strokeWidth={1.75} />
          <span className="text-[12px] font-semibold">Reconnecting…</span>
        </div>
      </div>
    );
  }

  return (
    <video
      key={resolvedSrc}
      src={resolvedSrc}
      poster={poster}
      data-camera-state="live"
      className={cn(
        "aspect-video w-full rounded-lg bg-black object-cover ring-1 ring-[var(--border-soft)]",
        className,
      )}
      autoPlay
      muted
      loop
      playsInline
      onError={() => setErrored(true)}
    />
  );
}

function PacePill({
  delta,
  scale = "normal",
}: {
  delta: number;
  scale?: "normal" | "tv";
}) {
  const behind = Math.round(delta) < 0;

  return (
    <span
      className={cn(
        "rounded-full border px-3 py-2 text-[12px] font-extrabold tabular-nums",
        scale === "tv" && "px-5 py-3 text-[24px]",
        behind
          ? "border-[rgba(255,84,73,.4)] bg-[var(--bad-tint)] text-[var(--bad)]"
          : "border-[rgba(70,194,107,.4)] bg-[var(--good-tint)] text-[var(--good)]",
      )}
    >
      {pacePillLabel(delta)}
    </span>
  );
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
      <Panel className={cn("relative min-h-[208px] overflow-hidden pr-[44%]", scale === "tv" && "min-h-[420px] p-10 pr-[44%]")}>
        <div className="relative z-[1] max-w-[620px]">
          <div className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--text-dim)]">
            PROJECTED PROFIT (TODAY)
          </div>
          <div
            className={cn(
              "mt-4 text-[72px] font-extrabold leading-none tracking-[-0.01em] tabular-nums drop-shadow-[0_0_24px_rgba(70,194,107,.30)]",
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
        <div className="pointer-events-none absolute bottom-0 right-0 top-7 w-[52%] opacity-95 [mask-image:linear-gradient(90deg,transparent_0%,black_18%,black_100%)]">
          <AreaSpark
            values={marginValues(marginChartData)}
            color={totalMargin >= 0 ? "good" : "bad"}
            size="hero"
            endpoint
            className="h-full"
            aria-label="projected margin trend"
          />
        </div>
      </Panel>

      <Panel className={cn("flex min-h-[208px] flex-col overflow-hidden pb-4", scale === "tv" && "hidden")}>
        <div className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--text-dim)]">
          UNITS VERIFIED TODAY
        </div>
        <button
          type="button"
          className="mt-4 text-left text-[30px] font-extrabold leading-none tracking-[-0.01em] tabular-nums text-[var(--text)] hover:text-[var(--accent)]"
          style={{ fontSize: 30, fontWeight: 800, lineHeight: 1 }}
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
        <AreaSpark values={hourlyValues(chartData)} color="good" size="kpi" endpoint className="-mx-2 mt-auto" aria-label="units verified trend" />
      </Panel>

      <Panel className={cn("flex min-h-[208px] flex-col overflow-hidden pb-4", scale === "tv" && "hidden")}>
        <div className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--text-dim)]">
          COUNTS VERIFIED
        </div>
        <div className="mt-4 text-[30px] font-extrabold leading-none tracking-[-0.01em] tabular-nums text-[var(--text)]">
          100%
        </div>
        <div className="mt-3 inline-flex rounded-full bg-[var(--good-tint)] px-2 py-1 text-[12px] font-semibold text-[var(--good)]">
          HUMAN+AI
        </div>
        <p className="mt-5 text-[14px] leading-6 text-[var(--text-mut)]">
          Every count has a reviewed clip behind it. Tap a number and the proof opens.
        </p>
        <AreaSpark values={[94, 95, 96, 97, 98, 99, 100, 100, 100, 100, 100]} color="good" size="kpi" endpoint className="-mx-2 mt-auto" aria-label="verification trend" />
      </Panel>
    </section>
  );
}

export function CameraCard({
  station,
  now,
  snapshot,
  events: selectedEvents,
  unitsToday,
  scale = "normal",
  onHide,
}: {
  station: (typeof stations)[number];
  now: Date;
  snapshot: PaceSnapshot;
  events?: StationCountSnapshot["events"];
  unitsToday?: number;
  scale?: "normal" | "tv";
  onHide?: () => void;
}) {
  const { openClip } = useClipDrawer();
  const events = selectedEvents ?? stationEventsThrough(station.id, now);
  const latest = events.at(-1);
  const isBehind = snapshot.pace_delta < 0;
  const sparkValues = cameraSparkValues(events, isBehind);

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
          {scale !== "tv" && onHide ? (
            <CameraTileMenu
              stationId={station.id}
              stationName={station.name}
              latestClipId={latest?.clip_id}
              onHide={onHide}
            />
          ) : null}
        </div>
      </div>

      <LiveVideo
        key={mediaUrlForStation(station.id, now)}
        src={mediaUrlForStation(station.id, now)}
        poster={mediaPosterUrlForStation(station.id, now)}
      />

      <div className={cn("mt-4 grid grid-cols-[minmax(116px,.7fr)_minmax(140px,1fr)_auto] items-center gap-4", scale === "tv" && "grid-cols-[minmax(220px,.7fr)_minmax(220px,1fr)_auto]")}>
        <div>
          <button
            type="button"
            data-testid="station-count"
            data-station={station.id}
            className={cn("text-left text-[46px] font-extrabold leading-none tracking-[-0.01em] tabular-nums text-[var(--text)] hover:text-[var(--accent)]", scale === "tv" && "text-[96px]")}
            style={{ fontSize: scale === "tv" ? 96 : 46, fontWeight: 800, lineHeight: scale === "tv" ? 0.9 : 1 }}
            onClick={() => latest && openClip(latest.clip_id)}
          >
            {unitsToday ?? events.length}
          </button>
          <button
            type="button"
            className={cn("mt-2 block text-left text-[12px] text-[var(--text-dim)] hover:text-[var(--accent)]", scale === "tv" && "text-[20px]")}
            onClick={() => latest && openClip(latest.clip_id)}
          >
            today · last count {latest ? formatCompactTime(new Date(latest.ts)) : "none"}
          </button>
        </div>
        <AreaSpark
          values={sparkValues}
          color={isBehind ? "bad" : "good"}
          size="cam"
          endpoint
          className={cn("h-[64px] self-end", scale === "tv" && "h-[112px]")}
          aria-label={`${station.name} pace trend`}
        />
        <PacePill delta={snapshot.pace_delta} scale={scale} />
      </div>
    </Panel>
  );
}

function AlertsRail({ alerts }: { alerts: DemoAlert[] }) {
  const { openClip } = useClipDrawer();

  return (
    <Panel className="mt-4 p-0">
      <div className="mb-4 flex items-center justify-between">
        <div className="px-6 pt-6 text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--text-dim)]">
          ALERTS
        </div>
        <Link href="/alerts" className="px-6 pt-6 text-[13px] font-semibold text-[var(--accent)]">
          View all alerts →
        </Link>
      </div>
      <div className="divide-y divide-[var(--border-soft)]">
        {alerts.length ? (
          alerts.map((alert) => (
            <div key={alert.id} className="grid grid-cols-[24px_72px_minmax(104px,.5fr)_1fr_auto_28px] items-center gap-3 px-6 py-3.5 text-[13px] hover:bg-white/[.02]">
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
          <div className="px-6 py-5 text-[14px] text-[var(--text-mut)]">
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
  const [hiddenStations, setHiddenStations] = useState<Set<string>>(new Set());
  const current = now();
  const snapshots = selectRunningJobSnapshots(current, consoleJobs);
  const stationSnapshots = selectStationCountSnapshots(current, consoleJobs);
  const alerts = evaluateDemoAlerts(current, snapshots).slice(0, 3);
  const visibleSnapshots = stationSnapshots.filter(({ station }) => !hiddenStations.has(station.id));

  return (
    <div className="space-y-4">
      <div className="sr-only">
        <TimeControls />
      </div>

      <MoneyStrip snapshots={snapshots} now={current} />

      {hiddenStations.size > 0 ? (
        <button
          type="button"
          onClick={() => setHiddenStations(new Set())}
          className="flex items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--panel-2)] px-3 py-2 text-[12px] font-semibold text-[var(--text-mut)] hover:text-[var(--text)]"
        >
          Show {hiddenStations.size} hidden tile{hiddenStations.size > 1 ? "s" : ""}
        </button>
      ) : null}

      <section className="grid gap-4 lg:grid-cols-2">
        {visibleSnapshots.map(({ station, events, pace, unitsToday }) => {
          return (
            <CameraCard
              key={station.id}
              station={station}
              now={current}
              snapshot={pace}
              events={events}
              unitsToday={unitsToday}
              onHide={() =>
                setHiddenStations((current) => new Set(current).add(station.id))
              }
            />
          );
        })}
      </section>

      <AlertsRail alerts={alerts} />
    </div>
  );
}
