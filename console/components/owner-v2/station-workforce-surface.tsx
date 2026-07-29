"use client";

import Image from "next/image";
import { Temporal } from "@js-temporal/polyfill";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import {
  Activity,
  CalendarDays,
  Camera,
  Check,
  ChevronDown,
  CircleAlert,
  Clock3,
  Factory,
  Info,
  RefreshCw,
  ShieldCheck,
  TriangleAlert,
  UserCheck,
  Users,
  X,
} from "lucide-react";
import { useMemo, useState } from "react";
import { useOwnerSurfaceStatus } from "@/components/owner-v2/owner-shell";
import { ownerApiFetch } from "@/lib/ownerClient";
import type {
  OwnerStationBucket,
  OwnerStationData,
  OwnerStationKpi,
} from "@/lib/ownerStationTypes";

const panel =
  "overflow-hidden rounded-[8px] border border-border bg-panel-2";

export function StationWorkforceSurface({
  data,
  preview = false,
}: {
  data: OwnerStationData;
  preview?: boolean;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  useOwnerSurfaceStatus(
    data.verificationState === "verified"
      ? "connected"
      : data.verificationState === "delayed"
        ? "delayed"
        : "unavailable",
  );

  function updateQuery(
    key: "station_id" | "assignment_id" | "date",
    value: string,
  ) {
    const next = new URLSearchParams(searchParams.toString());
    next.set(key, value);
    router.push(`${pathname}?${next.toString()}`);
  }

  return (
    <div
      data-owner-station-workforce
      data-owner-verification-state={data.verificationState}
      className="space-y-3"
    >
      <h1 className="sr-only">{data.station.name} station performance</h1>
      <section
        className={`${panel} flex min-h-[60px] flex-col justify-between gap-3 px-4 py-3 md:flex-row md:items-center md:py-0`}
        aria-label="Station context"
      >
        <div className="flex min-w-0 items-center gap-3">
          <span className="grid size-10 shrink-0 place-items-center rounded-[6px] border border-border bg-panel text-accent">
            <Factory size={21} strokeWidth={1.7} aria-hidden="true" />
          </span>
          <label className="relative min-w-0">
            <span className="sr-only">Station</span>
            <select
              value={data.station.id}
              onChange={(event) => updateQuery("station_id", event.target.value)}
              className="h-11 max-w-full appearance-none bg-transparent pr-8 text-lg font-semibold outline-none md:h-10"
            >
              {data.stationOptions.map((station) => (
                <option key={station.id} value={station.id}>
                  {station.name}
                </option>
              ))}
            </select>
            <ChevronDown
              size={16}
              className="pointer-events-none absolute right-1 top-3.5 text-text-mut md:top-3"
              aria-hidden="true"
            />
          </label>
          <span className="hidden h-7 w-px bg-border sm:block" />
          <span
            className={`hidden items-center gap-2 text-xs sm:inline-flex ${
              data.verificationState === "verified"
                ? "text-good"
                : data.verificationState === "delayed"
                  ? "text-warn"
                  : "text-text-dim"
            }`}
          >
            <span className="size-2 rounded-full bg-current" />
            {preview
              ? "Preview fixture"
              : data.verificationState === "verified"
                ? "Verified coverage"
                : data.verificationState === "delayed"
                  ? "Coverage delayed"
                  : "Coverage unavailable"}
          </span>
          <span className="hidden text-xs text-text-mut lg:inline">
            Verified through {data.verifiedThroughLabel}
          </span>
        </div>
        <div className="flex items-center gap-2 text-xs text-text-mut md:justify-end">
          <span>Current project:</span>
          <span className={data.project ? "font-medium text-accent" : "text-text-dim"}>
            {data.projectAssignmentKnown
              ? data.project?.name ?? "No active project"
            : "Assignment unavailable"}
          </span>
          <span className="text-text-dim sm:hidden">·</span>
          <span className="sm:hidden">
            Verified through {data.verifiedThroughLabel}
          </span>
        </div>
      </section>

      <section
        className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"
        aria-label="Station metrics"
      >
        <KpiCard
          label="Verified good units"
          metric={data.kpis.verifiedGoodUnits}
          buckets={data.production}
          tone="good"
        />
        <KpiCard
          label="Units / hour"
          metric={data.kpis.unitsPerHour}
          buckets={data.production}
        />
        <KpiCard
          label="Labor hours"
          metric={data.kpis.laborHours}
          buckets={data.production}
          showSparkline={false}
        />
        <KpiCard
          label="Output per labor hour"
          metric={data.kpis.outputPerLaborHour}
          buckets={data.production}
          showSparkline={false}
        />
      </section>

      <div className="grid min-w-0 gap-3 xl:grid-cols-[minmax(0,2fr)_minmax(360px,1fr)]">
        <ProductionChart
          buckets={data.production}
          selectedAssignmentId={data.selectedAssignmentId}
          shiftOptions={data.shiftOptions}
          onShiftChange={(assignmentId) =>
            updateQuery("assignment_id", assignmentId)
          }
          selectedDate={data.selectedDate}
          onDateChange={(date) => updateQuery("date", date)}
          windowStartIso={data.windowStartIso}
          windowEndIso={data.windowEndIso}
          nowIso={data.nowIso}
          verifiedThroughIso={data.verifiedThroughIso}
        />
        <EvidencePanel data={data} preview={preview} />
      </div>

      <div className="grid min-w-0 gap-3 xl:grid-cols-[minmax(0,2fr)_minmax(360px,1fr)]">
        <TeamTable data={data} />
        <ShiftSummary data={data} preview={preview} />
      </div>
    </div>
  );
}

function KpiCard({
  label,
  metric,
  buckets,
  tone = "text",
  showSparkline = true,
}: {
  label: string;
  metric: OwnerStationKpi;
  buckets: OwnerStationBucket[];
  tone?: "text" | "good";
  showSparkline?: boolean;
}) {
  const spark = useMemo(() => {
    const values = buckets.flatMap((bucket) =>
      bucket.verifiedGoodUnits === null ? [] : [bucket.verifiedGoodUnits * 4],
    );
    if (values.length < 2) return "";
    const maximum = Math.max(...values, 1);
    return values
      .map((value, index) => {
        const x = (index / (values.length - 1)) * 128;
        const y = 34 - (value / maximum) * 29;
        return `${index ? "L" : "M"} ${x.toFixed(1)} ${y.toFixed(1)}`;
      })
      .join(" ");
  }, [buckets]);
  const comparison = metric.comparisonBps;
  return (
    <article className={`${panel} min-h-[128px] px-4 py-4 md:min-h-[146px]`}>
      <p className="text-[11px] font-medium uppercase text-text-mut">{label}</p>
      <div className="mt-3 flex items-end justify-between gap-3">
        <div>
          <p
            className={`text-[38px] font-semibold leading-none ${
              metric.value === null
                ? "text-text-dim"
                : tone === "good"
                  ? "text-good"
                  : "text-text"
            }`}
          >
            {metric.value === null
              ? "—"
              : metric.value.toFixed(metric.decimals)}
            {metric.suffix ?? ""}
          </p>
          <p className="mt-2 text-xs text-text-mut">selected shift</p>
        </div>
        {spark && showSparkline ? (
          <svg
            viewBox="0 0 128 38"
            className="h-10 w-28"
            role="img"
            aria-label={`${label} intrashift trend`}
          >
            <path d={spark} fill="none" stroke="#46c26b" strokeWidth="1.7" />
          </svg>
        ) : null}
      </div>
      <p
        className={`mt-2 text-[11px] ${
          comparison === null
            ? "text-text-dim"
            : comparison >= 0
              ? "text-good"
              : "text-bad"
        }`}
      >
        {comparison === null
          ? "Prior-shift comparison unavailable"
          : `${comparison >= 0 ? "▲" : "▼"} ${Math.abs(comparison / 100).toFixed(0)}% vs prior shift`}
      </p>
    </article>
  );
}

function chartSegments(
  buckets: OwnerStationBucket[],
  plot: { left: number; top: number; width: number; height: number },
  maximum: number,
) {
  const segments: string[] = [];
  let current = "";
  buckets.forEach((bucket, index) => {
    if (bucket.verifiedGoodUnits === null) {
      if (current) segments.push(current);
      current = "";
      return;
    }
    const x =
      plot.left + ((index + 0.5) / Math.max(1, buckets.length)) * plot.width;
    const hourlyRate = bucket.verifiedGoodUnits * 4;
    const y = plot.top + plot.height - (hourlyRate / maximum) * plot.height;
    current += `${current ? " L" : "M"} ${x.toFixed(1)} ${y.toFixed(1)}`;
  });
  if (current) segments.push(current);
  return segments;
}

function ProductionChart({
  buckets,
  selectedAssignmentId,
  shiftOptions,
  onShiftChange,
  selectedDate,
  onDateChange,
  windowStartIso,
  windowEndIso,
  nowIso,
  verifiedThroughIso,
}: {
  buckets: OwnerStationBucket[];
  selectedAssignmentId: string;
  shiftOptions: { id: string; label: string }[];
  onShiftChange: (assignmentId: string) => void;
  selectedDate: string;
  onDateChange: (date: string) => void;
  windowStartIso: string;
  windowEndIso: string;
  nowIso: string;
  verifiedThroughIso: string | null;
}) {
  const plot = { left: 52, top: 24, width: 820, height: 214 };
  const maximum = Math.max(
    20,
    ...buckets.flatMap((bucket) =>
      bucket.verifiedGoodUnits === null
        ? []
        : [bucket.verifiedGoodUnits * 4],
    ),
    ...buckets.flatMap((bucket) =>
      bucket.requiredUnits === null ? [] : [bucket.requiredUnits * 4],
    ),
  );
  const roundedMaximum = Math.ceil(maximum / 10) * 10;
  const paths = chartSegments(buckets, plot, roundedMaximum);
  const required =
    buckets.find((bucket) => bucket.requiredUnits !== null)?.requiredUnits
    ?? null;
  const requiredY =
    required === null
      ? null
      : plot.top
        + plot.height
        - ((required * 4) / roundedMaximum) * plot.height;
  const windowStart = Date.parse(windowStartIso);
  const windowEnd = Date.parse(windowEndIso);
  const xForTime = (iso: string | null) => {
    if (!iso || !Number.isFinite(windowStart) || !Number.isFinite(windowEnd)) {
      return null;
    }
    const timestamp = Date.parse(iso);
    if (
      !Number.isFinite(timestamp)
      || timestamp < windowStart
      || timestamp > windowEnd
      || windowEnd <= windowStart
    ) {
      return null;
    }
    return (
      plot.left
      + ((timestamp - windowStart) / (windowEnd - windowStart)) * plot.width
    );
  };
  const nowTimestamp = Date.parse(nowIso);
  const nowX =
    nowTimestamp >= windowStart && nowTimestamp < windowEnd
      ? xForTime(nowIso)
      : null;
  const verifiedX = xForTime(verifiedThroughIso);

  return (
    <section className={`${panel} min-h-[348px]`} data-owner-station-chart>
      <div className="flex min-h-[58px] flex-col justify-between gap-2 border-b border-border px-4 py-3 sm:flex-row sm:items-center">
        <div>
          <h2 className="text-[11px] font-medium uppercase text-text-mut">
            Production by 15-minute interval
          </h2>
          <p className="mt-1 text-[11px] text-text-mut">
            Hourly rate normalized from each verified 15-minute window
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label className="relative">
            <span className="sr-only">Shift</span>
            <select
              value={selectedAssignmentId}
              onChange={(event) => onShiftChange(event.target.value)}
              className="h-11 max-w-[210px] appearance-none border border-border bg-transparent pl-9 pr-8 text-xs text-text-mut outline-none md:h-9"
            >
              {shiftOptions.map((shift) => (
                <option key={shift.id} value={shift.id}>
                  {shift.label}
                </option>
              ))}
            </select>
            <Clock3
              size={14}
              className="pointer-events-none absolute left-3 top-3.5 text-text-mut md:top-2.5"
              aria-hidden="true"
            />
            <ChevronDown
              size={14}
              className="pointer-events-none absolute right-3 top-3.5 text-text-dim md:top-2.5"
              aria-hidden="true"
            />
          </label>
          <label className="relative">
            <span className="sr-only">Production date</span>
            <CalendarDays
              size={14}
              className="pointer-events-none absolute left-3 top-3.5 text-text-mut md:top-2.5"
              aria-hidden="true"
            />
            <input
              type="date"
              value={selectedDate}
              onChange={(event) => onDateChange(event.target.value)}
              className="h-11 border border-border bg-transparent pl-9 pr-3 text-xs text-text-mut outline-none md:h-9"
            />
          </label>
        </div>
      </div>
      <div className="hidden px-4 pb-3 pt-3 md:block">
        <div className="flex flex-wrap gap-5 text-[11px] text-text-mut">
          <span className="inline-flex items-center gap-2">
            <span className="h-0.5 w-7 bg-good" /> Verified rate
          </span>
          <span className="inline-flex items-center gap-2">
            <span className="w-7 border-t border-dashed border-text-mut" />
            Required pace
          </span>
          <span className="inline-flex items-center gap-2">
            <span className="size-3 bg-warn/25" /> Downtime
          </span>
        </div>
        <svg
          viewBox="0 0 900 270"
          className="mt-2 h-[248px] w-full"
          role="img"
          aria-label="Verified station production rate by 15-minute interval"
        >
          {[0, 0.25, 0.5, 0.75, 1].map((fraction) => {
            const y = plot.top + plot.height * fraction;
            const value = Math.round(roundedMaximum * (1 - fraction));
            return (
              <g key={fraction}>
                <line
                  x1={plot.left}
                  x2={plot.left + plot.width}
                  y1={y}
                  y2={y}
                  stroke="rgba(255,255,255,.08)"
                />
                <text
                  x={plot.left - 10}
                  y={y + 4}
                  textAnchor="end"
                  fill="#6f7476"
                  fontSize="10"
                >
                  {value}
                </text>
              </g>
            );
          })}
          {buckets.map((bucket, index) =>
            bucket.downtimeMinutes > 0 ? (
              <rect
                key={bucket.startIso}
                x={plot.left + (index / buckets.length) * plot.width}
                y={plot.top}
                width={plot.width / buckets.length}
                height={plot.height}
                fill="rgba(231,161,59,.12)"
              />
            ) : null,
          )}
          {requiredY !== null ? (
            <line
              x1={plot.left}
              x2={plot.left + plot.width}
              y1={requiredY}
              y2={requiredY}
              stroke="#9aa1a9"
              strokeDasharray="6 6"
              strokeWidth="1.3"
            />
          ) : null}
          {paths.map((path) => (
            <path
              key={path}
              d={path}
              fill="none"
              stroke="#46c26b"
              strokeWidth="2"
            />
          ))}
          {verifiedX !== null ? (
            <>
              <line
                data-owner-verified-marker
                x1={verifiedX}
                x2={verifiedX}
                y1={plot.top}
                y2={plot.top + plot.height}
                stroke="#e8742f"
                strokeDasharray="2 4"
                strokeWidth="1"
              />
              <text
                x={verifiedX}
                y={15}
                textAnchor="middle"
                fill="#e8742f"
                fontSize="9"
                fontWeight="700"
              >
                VERIFIED
              </text>
            </>
          ) : null}
          {nowX !== null ? (
            <>
              <line
                data-owner-now-marker
                x1={nowX}
                x2={nowX}
                y1={plot.top}
                y2={plot.top + plot.height}
                stroke="#f2f4f5"
                strokeDasharray="4 4"
                strokeWidth="1"
              />
              <text
                x={nowX}
                y={verifiedX !== null && Math.abs(verifiedX - nowX) < 42 ? 28 : 15}
                textAnchor="middle"
                fill="#46c26b"
                fontSize="10"
                fontWeight="700"
              >
                NOW
              </text>
            </>
          ) : null}
          {buckets.map((bucket, index) =>
            index % 4 === 0 || index === buckets.length - 1 ? (
              <text
                key={bucket.startIso}
                x={plot.left + (index / Math.max(1, buckets.length)) * plot.width}
                y={260}
                textAnchor={index === 0 ? "start" : index === buckets.length - 1 ? "end" : "middle"}
                fill="#6f7476"
                fontSize="10"
              >
                {bucket.label}
              </text>
            ) : null,
          )}
        </svg>
      </div>
      <div className="grid min-h-[176px] place-items-center px-6 text-center md:hidden">
        <div>
          <Activity className="mx-auto text-good" aria-hidden="true" />
          <p className="mt-3 font-medium">Interval chart available in the wider view</p>
          <p className="mt-1 text-sm text-text-mut">
            The mobile view keeps station KPIs and exceptions readable first.
          </p>
        </div>
      </div>
    </section>
  );
}

function EvidencePanel({
  data,
  preview,
}: {
  data: OwnerStationData;
  preview: boolean;
}) {
  return (
    <section className={`${panel} min-h-[348px]`}>
      <div className="flex h-[58px] items-center justify-between border-b border-border px-4">
        <div>
          <h2 className="text-[11px] font-medium uppercase text-text-mut">
            Station evidence
          </h2>
          <p className="mt-1 text-xs text-text">{data.station.evidenceLabel}</p>
        </div>
        <span
          className={`border px-2 py-1 text-[10px] font-semibold ${
            preview
              ? "border-accent/40 bg-accent-tint text-accent"
              : data.station.imageSrc
                ? "border-good/40 bg-good-tint text-good"
                : "border-border text-text-dim"
          }`}
        >
          {preview ? "PREVIEW" : data.station.imageSrc ? "EVIDENCE" : "UNAVAILABLE"}
        </span>
      </div>
      <div className="p-3">
        <div className="relative aspect-[16/9] overflow-hidden rounded-[6px] bg-idle">
          {data.station.imageSrc ? (
            <Image
              src={data.station.imageSrc}
              alt={`${data.station.name} station evidence`}
              fill
              sizes="(min-width: 1280px) 32vw, 100vw"
              className="object-cover"
              priority={preview}
            />
          ) : (
            <div className="grid size-full place-items-center text-center">
              <div>
                <Camera className="mx-auto text-text-dim" aria-hidden="true" />
                <p className="mt-3 text-sm text-text-mut">
                  Evidence preview unavailable
                </p>
                <p className="mt-1 text-xs text-text-dim">
                  No owner-safe clip or image is attached.
                </p>
              </div>
            </div>
          )}
        </div>
        <div className="mt-3 flex items-center gap-3 text-xs">
          <span
            className={
              data.station.status === "active" ? "text-good" : "text-text-dim"
            }
          >
            {data.station.status === "active" ? "Running" : "Inactive"}
          </span>
          <span className="text-text-dim">·</span>
          <span className="text-text-mut">
            Cycle time:{" "}
            {data.station.cycleTimeSeconds === null
              ? "Unavailable"
              : `${data.station.cycleTimeSeconds}s`}
          </span>
        </div>
      </div>
    </section>
  );
}

function TeamTable({ data }: { data: OwnerStationData }) {
  return (
    <section className={panel} data-owner-station-team>
      <div className="flex min-h-[50px] items-center gap-2 border-b border-border px-4">
        <h2 className="text-[11px] font-medium uppercase text-text-mut">
          Team on station
        </h2>
        <span className="text-text-dim">·</span>
        <span className="text-xs text-text-mut">{data.shiftLabel}</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] border-collapse text-left text-xs">
          <thead className="text-text-mut">
            <tr className="h-10 border-b border-border">
              <th className="px-4 font-normal">Worker</th>
              <th className="px-3 font-normal">Scheduled interval</th>
              <th className="px-3 font-normal">Labor hours</th>
              <th className="px-3 font-normal">Primary role</th>
              <th className="px-3 font-normal">Attribution state</th>
            </tr>
          </thead>
          <tbody>
            {data.team.length ? (
              data.team.map((member) => (
                <tr key={member.id} className="min-h-[58px] border-b border-border last:border-b-0">
                  <td className="px-4 py-3 font-medium">{member.name}</td>
                  <td className="px-3 py-3 text-text-mut">
                    {member.scheduledInterval}
                  </td>
                  <td className="px-3 py-3">
                    {member.laborHours === null
                      ? "Unavailable"
                      : member.laborHours.toFixed(2)}
                  </td>
                  <td className="px-3 py-3 text-text-mut">
                    {member.primaryRole ?? "Not recorded"}
                  </td>
                  <td className="px-3 py-3">
                    <span className="flex items-start gap-2">
                      {member.attribution === "solo_high_confidence" ? (
                        <UserCheck
                          size={16}
                          className="mt-0.5 shrink-0 text-good"
                          aria-hidden="true"
                        />
                      ) : member.attribution === "team_only" ? (
                        <Users
                          size={16}
                          className="mt-0.5 shrink-0 text-warn"
                          aria-hidden="true"
                        />
                      ) : (
                        <CircleAlert
                          size={16}
                          className="mt-0.5 shrink-0 text-text-dim"
                          aria-hidden="true"
                        />
                      )}
                      <span>
                        <span className="block text-text">
                          {member.attribution === "solo_high_confidence"
                            ? "Solo interval · high confidence"
                            : member.attribution === "team_only"
                              ? "Team contribution only"
                              : "Attribution unavailable"}
                        </span>
                        <span className="mt-0.5 block text-[11px] text-text-mut">
                          {member.attributionDetail}
                        </span>
                      </span>
                    </span>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={5} className="h-28 px-4 text-center text-text-mut">
                  No worker intervals are recorded for this station and shift.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <p className="flex min-h-[48px] items-center gap-2 border-t border-border px-4 text-xs italic text-text-mut">
        <Info size={15} className="shrink-0" aria-hidden="true" />
        Output is attributed to the station team unless a worker was alone and
        checked in.
      </p>
    </section>
  );
}

function factoryLocalInputValue(iso: string, timezone: string) {
  return Temporal.Instant.from(iso)
    .toZonedDateTimeISO(timezone)
    .toPlainDateTime()
    .toString({ smallestUnit: "minute" });
}

function ShiftSummary({
  data,
  preview,
}: {
  data: OwnerStationData;
  preview: boolean;
}) {
  const router = useRouter();
  const project = data.project;
  const windowStartMs = Date.parse(data.windowStartIso);
  const windowEndMs = Date.parse(data.windowEndIso);
  const nowMs = Date.parse(data.nowIso);
  const defaultEndMs = Math.max(
    windowStartMs + 60_000,
    Math.min(windowEndMs, nowMs),
  );
  const defaultStartMs = Math.max(windowStartMs, defaultEndMs - 15 * 60_000);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [startLocal, setStartLocal] = useState(
    factoryLocalInputValue(new Date(defaultStartMs).toISOString(), data.timezone),
  );
  const [endLocal, setEndLocal] = useState(
    factoryLocalInputValue(new Date(defaultEndMs).toISOString(), data.timezone),
  );
  const [reasonCode, setReasonCode] = useState("equipment_breakdown");
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const rows = [
    {
      label: "Scrap",
      value: data.summary.scrapUnits,
      suffix: "units",
      icon: Check,
      tone: "text-good",
    },
    {
      label: "Rework",
      value: data.summary.reworkUnits,
      suffix: "units",
      icon: RefreshCw,
      tone: "text-warn",
    },
    {
      label: "Downtime",
      value: data.summary.downtimeMinutes,
      suffix: "min",
      icon: Clock3,
      tone: "text-bad",
    },
  ] as const;
  return (
    <section className={panel}>
      <div className="flex h-[50px] items-center border-b border-border px-4">
        <h2 className="text-[11px] font-medium uppercase text-text-mut">
          Shift summary
        </h2>
      </div>
      <div>
        {rows.map((row) => {
          const Icon = row.icon;
          return (
            <div
              key={row.label}
              className="grid min-h-[64px] grid-cols-[32px_1fr_auto] items-center gap-3 border-b border-border px-4"
            >
              <Icon size={20} className={row.tone} aria-hidden="true" />
              <span className="text-sm">{row.label}</span>
              <span className="text-right">
                <span className="text-xl font-semibold">
                  {row.value ?? "—"}
                </span>
                <span className="ml-2 text-[11px] text-text-mut">
                  {row.value === null ? "unavailable" : row.suffix}
                </span>
              </span>
            </div>
          );
        })}
      </div>
      <div className="p-4">
        <p className="flex items-start gap-2 text-xs leading-5 text-text-mut">
          {data.verificationState === "verified" ? (
            <ShieldCheck className="mt-0.5 shrink-0 text-good" size={16} aria-hidden="true" />
          ) : (
            <TriangleAlert className="mt-0.5 shrink-0 text-warn" size={16} aria-hidden="true" />
          )}
          {data.verificationState === "verified"
            ? "Metrics use published verified coverage for this shift."
            : "Gaps remain unavailable and are not replaced with estimates."}
        </p>
        <button
          type="button"
          onClick={() => setDialogOpen(true)}
          disabled={!project}
          className="mt-4 inline-flex h-11 w-full items-center justify-center gap-2 rounded-[6px] border border-accent/70 text-sm font-semibold text-accent hover:bg-accent/10 disabled:cursor-not-allowed disabled:border-border disabled:text-text-dim"
        >
          <Clock3 size={16} aria-hidden="true" />
          Record downtime
        </button>
      </div>
      {dialogOpen && project ? (
        <div
          className="fixed inset-0 z-50 grid place-items-center bg-black/70 p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="record-downtime-title"
        >
          <form
            className="w-full max-w-lg rounded-[8px] border border-border bg-panel p-5 shadow-2xl"
            onSubmit={async (event) => {
              event.preventDefault();
              setError(null);
              if (preview) {
                setError("Preview data only. No downtime was recorded.");
                return;
              }
              setSubmitting(true);
              try {
                const effectiveStart = Temporal.PlainDateTime.from(startLocal)
                  .toZonedDateTime(data.timezone, { disambiguation: "reject" })
                  .toInstant()
                  .toString();
                const effectiveEnd = Temporal.PlainDateTime.from(endLocal)
                  .toZonedDateTime(data.timezone, { disambiguation: "reject" })
                  .toInstant()
                  .toString();
                const response = await ownerApiFetch(
                  `/api/owner/downtime?factory_id=${encodeURIComponent(data.factoryId)}`,
                  {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                      projectId: project.id,
                      stationId: data.station.id,
                      effectiveStart,
                      effectiveEnd,
                      reasonCode,
                      note,
                    }),
                  },
                );
                if (!response.ok) throw new Error("record_failed");
                setDialogOpen(false);
                setNote("");
                router.refresh();
              } catch {
                setError(
                  "Downtime could not be recorded. Check the interval and try again.",
                );
              } finally {
                setSubmitting(false);
              }
            }}
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 id="record-downtime-title" className="text-lg font-semibold">
                  Record downtime
                </h2>
                <p className="mt-1 text-xs text-text-mut">
                  {data.station.name} · {project.name}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setDialogOpen(false)}
                className="grid size-10 place-items-center rounded-[6px] border border-border text-text-mut hover:text-text"
                aria-label="Close downtime form"
              >
                <X size={18} aria-hidden="true" />
              </button>
            </div>
            {preview ? (
              <p className="mt-4 rounded-[6px] border border-accent/30 bg-accent/10 px-3 py-2 text-xs text-accent">
                Preview data only. Downtime recording is disabled.
              </p>
            ) : null}
            <div className="mt-5 grid gap-4 sm:grid-cols-2">
              <label className="text-xs font-medium text-text-mut">
                Start
                <input
                  type="datetime-local"
                  value={startLocal}
                  onChange={(event) => setStartLocal(event.target.value)}
                  required
                  className="mt-2 h-11 w-full rounded-[6px] border border-border bg-bg px-3 text-sm text-text"
                />
              </label>
              <label className="text-xs font-medium text-text-mut">
                End
                <input
                  type="datetime-local"
                  value={endLocal}
                  onChange={(event) => setEndLocal(event.target.value)}
                  required
                  className="mt-2 h-11 w-full rounded-[6px] border border-border bg-bg px-3 text-sm text-text"
                />
              </label>
            </div>
            <label className="mt-4 block text-xs font-medium text-text-mut">
              Reason
              <select
                value={reasonCode}
                onChange={(event) => setReasonCode(event.target.value)}
                className="mt-2 h-11 w-full rounded-[6px] border border-border bg-bg px-3 text-sm text-text"
              >
                <option value="equipment_breakdown">Equipment breakdown</option>
                <option value="maintenance">Maintenance</option>
                <option value="material_shortage">Material shortage</option>
                <option value="changeover">Changeover</option>
                <option value="other">Other</option>
              </select>
            </label>
            <label className="mt-4 block text-xs font-medium text-text-mut">
              Note (optional)
              <textarea
                value={note}
                onChange={(event) => setNote(event.target.value)}
                maxLength={1_000}
                rows={3}
                className="mt-2 w-full resize-none rounded-[6px] border border-border bg-bg px-3 py-2 text-sm text-text"
              />
            </label>
            {error ? (
              <p className="mt-3 text-xs text-bad" role="alert">
                {error}
              </p>
            ) : null}
            <button
              type="submit"
              disabled={submitting || preview}
              className="mt-5 inline-flex h-11 w-full items-center justify-center rounded-[6px] bg-accent text-sm font-semibold text-black hover:bg-accent-hi disabled:opacity-60"
            >
              {submitting
                ? "Recording…"
                : preview
                  ? "Preview only"
                  : "Record downtime"}
            </button>
          </form>
        </div>
      ) : null}
    </section>
  );
}
