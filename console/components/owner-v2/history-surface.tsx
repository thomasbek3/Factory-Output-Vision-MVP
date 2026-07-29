"use client";

import {
  CalendarDays,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  CircleDollarSign,
  Download,
  ExternalLink,
  Gauge,
  History,
  TriangleAlert,
  X,
} from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useMemo, useRef, useState } from "react";
import { ownerHistoryCsv } from "@/lib/ownerHistoryModel";
import {
  loadOwnerEvidence,
  type OwnerEvidenceClip,
} from "@/lib/ownerClient";
import type {
  OwnerHistoryData,
  OwnerHistoryRecord,
} from "@/lib/ownerHistoryTypes";
import { useOwnerSurfaceStatus } from "@/components/owner-v2/owner-shell";

function previewEvidenceClip(record: OwnerHistoryRecord): OwnerEvidenceClip {
  return {
    id: `preview-${record.id}`,
    objectSha256:
      "0f43ac7cb86ad17a7dc9d3a5f126a80d6d3e230cf3408c83c3ae3fd0b9c75519",
    retentionUntil: null,
    reasonCode: "closeout-sample",
    attachedAt: record.completedAt,
    contentType: "video/mp4",
    byteSize: 0,
    state: "available",
    signedUrl: "#preview-retained-evidence",
    expiresIn: null,
  };
}

function money(cents: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(cents / 100);
}

function dateLabel(iso: string, timezone: string) {
  return new Intl.DateTimeFormat("en-US", {
    timeZone: timezone,
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(new Date(iso));
}

function dateTimeLabel(iso: string, timezone: string) {
  return new Intl.DateTimeFormat("en-US", {
    timeZone: timezone,
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(iso));
}

function tone(
  actual: number,
  planned: number,
  direction: "higher" | "lower",
) {
  const good = direction === "higher" ? actual >= planned : actual <= planned;
  return good ? "text-good" : "text-bad";
}

function PlanActual({
  planned,
  actual,
  format = (value) => String(value),
  direction = "higher",
}: {
  planned: number;
  actual: number;
  format?: (value: number) => string;
  direction?: "higher" | "lower";
}) {
  return (
    <span className="inline-flex items-center gap-2 whitespace-nowrap">
      <span className="text-text-mut">{format(planned)}</span>
      <span className="text-text-dim">→</span>
      <span className={tone(actual, planned, direction)}>{format(actual)}</span>
    </span>
  );
}

function HistoryFilter({
  label,
  value,
  values,
  onChange,
}: {
  label: string;
  value: string;
  values: { value: string; label: string }[];
  onChange: (value: string) => void;
}) {
  return (
    <label className="relative block min-w-[148px] flex-1">
      <span className="sr-only">{label}</span>
      <select
        aria-label={label}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-11 w-full appearance-none border border-border bg-panel-2 pl-3 pr-9 text-sm text-text"
      >
        {values.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <ChevronDown
        size={15}
        className="pointer-events-none absolute right-3 top-3.5 text-text-dim"
        aria-hidden="true"
      />
    </label>
  );
}

function SummaryMetric({
  label,
  value,
  detail,
  icon: Icon,
  good = false,
}: {
  label: string;
  value: string;
  detail: string;
  icon: typeof CheckCircle2;
  good?: boolean;
}) {
  return (
    <section
      className="relative min-h-32 border border-border bg-panel px-5 py-4"
      data-owner-history-summary-card
    >
      <p className="text-[11px] font-semibold uppercase text-text-mut">{label}</p>
      <p className={`mt-1 text-[32px] font-semibold ${good ? "text-good" : ""}`}>
        {value}
      </p>
      <p className="mt-1 text-xs text-text-mut">{detail}</p>
      <Icon
        size={48}
        strokeWidth={1.25}
        className="absolute right-5 top-8 text-text-dim/70"
        aria-hidden="true"
      />
    </section>
  );
}

function variance(
  planned: number | null,
  actual: number | null,
  format: (value: number) => string,
  direction: "higher" | "lower",
) {
  if (planned === null || actual === null) return "Unavailable";
  const delta = actual - planned;
  const percent = planned === 0 ? null : (delta / Math.abs(planned)) * 100;
  const good = direction === "higher" ? delta >= 0 : delta <= 0;
  return (
    <span className={good ? "text-good" : "text-bad"}>
      {delta > 0 ? "+" : ""}
      {format(delta)}
      {percent === null ? "" : ` (${delta > 0 ? "+" : ""}${percent.toFixed(1)}%)`}
    </span>
  );
}

function OutputChart({ record }: { record: OwnerHistoryRecord }) {
  if (record.output.length === 0) {
    return (
      <div className="grid min-h-56 place-items-center border-l border-border px-5 text-center text-sm text-text-mut">
        Weekly output was not captured in this immutable closeout.
      </div>
    );
  }
  const values = record.output.flatMap((bucket) => [
    bucket.actualUnits ?? 0,
    bucket.plannedUnits ?? 0,
  ]);
  const maxPositive = Math.max(0, ...values);
  const maxNegative = Math.abs(Math.min(0, ...values));
  const span = Math.max(1, maxPositive + maxNegative);
  const zeroTopPercent = (maxPositive / span) * 100;
  function barStyle(value: number) {
    const height = value === 0 ? "2px" : `${(Math.abs(value) / span) * 100}%`;
    return value >= 0
      ? { bottom: `${100 - zeroTopPercent}%`, height }
      : { top: `${zeroTopPercent}%`, height };
  }
  return (
    <section className="border-l border-border px-5" aria-label="Weekly output">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase text-text-mut">
          Weekly output (units)
        </h3>
        <span className="text-[11px] text-text-mut">
          {record.output.some((bucket) => bucket.plannedUnits !== null)
            ? "Plan / actual"
            : "Verified net good units"}
        </span>
      </div>
      <div className="relative mt-5 flex h-44 gap-3 border-b border-l border-border px-3">
        <span
          className="pointer-events-none absolute inset-x-0 border-t border-text-dim/70"
          style={{ top: `${zeroTopPercent}%` }}
          data-owner-history-zero-line
          aria-hidden="true"
        />
        {record.output.map((bucket, index) => (
          <div
            key={bucket.weekStart ?? `${bucket.label}-${index}`}
            className="relative h-full min-w-0 flex-1"
          >
            {bucket.plannedUnits !== null ? (
              <div
                className="absolute left-[16%] w-[30%] bg-text-dim/70"
                style={barStyle(bucket.plannedUnits)}
                title={`${bucket.label} plan ${bucket.plannedUnits}`}
              />
            ) : null}
            {bucket.actualUnits !== null ? (
              <div
                className={`absolute left-[52%] w-[30%] ${
                  bucket.actualUnits >= 0 ? "bg-good" : "bg-bad"
                }`}
                style={barStyle(bucket.actualUnits)}
                title={`${bucket.label} actual ${bucket.actualUnits}`}
              />
            ) : null}
          </div>
        ))}
      </div>
      <div className="mt-2 flex gap-3 px-3">
        {record.output.map((bucket, index) => (
          <span
            key={bucket.weekStart ?? `${bucket.label}-${index}`}
            className="min-w-0 flex-1 text-center text-[10px] text-text-mut"
          >
            <span className="block truncate">{bucket.label}</span>
            <span
              className={`mt-0.5 block font-semibold ${
                (bucket.actualUnits ?? 0) < 0 ? "text-bad" : "text-good"
              }`}
            >
              {bucket.actualUnits === null
                ? "—"
                : `${bucket.actualUnits > 0 ? "+" : ""}${bucket.actualUnits}`}
            </span>
          </span>
        ))}
      </div>
    </section>
  );
}

function CloseoutExpansion({
  record,
  timezone,
  onEvidence,
}: {
  record: OwnerHistoryRecord;
  timezone: string;
  onEvidence: (trigger: HTMLButtonElement) => void;
}) {
  const recordTimezone = record.factoryTimezone ?? timezone;
  const rows = [
    {
      label: "Units",
      plan: record.plannedUnits,
      actual: record.actualUnits,
      format: (value: number) => Math.round(value).toLocaleString("en-US"),
      direction: "higher" as const,
    },
    {
      label: "Schedule duration",
      plan: record.plannedScheduleMinutes,
      actual: record.actualScheduleMinutes,
      format: (value: number) => `${(value / 60).toFixed(1)} h`,
      direction: "lower" as const,
    },
    {
      label: "Direct labor",
      plan: record.plannedLaborCents,
      actual: record.actualLaborCents,
      format: money,
      direction: "lower" as const,
    },
    {
      label: "Materials",
      plan: record.plannedMaterialsCents,
      actual: record.actualMaterialsCents,
      format: money,
      direction: "lower" as const,
    },
    {
      label: "Margin after direct costs",
      plan: record.plannedMarginCents,
      actual: record.actualMarginCents,
      format: money,
      direction: "higher" as const,
    },
  ];
  return (
    <div className="grid min-w-[1180px] grid-cols-[1.15fr_0.85fr_1fr] border-b border-border bg-panel-2 px-4 py-4">
      <section className="pr-5">
        <div className="flex items-center justify-between">
          <h3 className="text-xs font-semibold uppercase text-text-mut">
            {record.projectName} · closeout revision {record.revision}
          </h3>
          {record.evidence.state === "available" ? (
            <button
              type="button"
              onClick={(event) => onEvidence(event.currentTarget)}
              className="inline-flex min-h-11 items-center gap-1 text-xs font-semibold text-accent"
            >
              Evidence clips {record.evidence.count}
              <ExternalLink size={13} aria-hidden="true" />
            </button>
          ) : record.evidence.state === "expired" ? (
            <button
              type="button"
              disabled
              className="min-h-11 cursor-not-allowed text-xs text-text-mut"
              title={
                record.evidence.retentionDate
                  ? `Retained until ${dateLabel(record.evidence.retentionDate, recordTimezone)}`
                  : undefined
              }
            >
              Evidence expired
              {record.evidence.retentionDate
                ? ` · retained until ${dateLabel(record.evidence.retentionDate, recordTimezone)}`
                : ""}
            </button>
          ) : (
            <span className="text-xs text-text-mut">No evidence attached</span>
          )}
        </div>
        {record.verificationHasGap ? (
          <div
            className="mt-3 flex items-start gap-2 border border-bad/70 bg-bad/5 px-3 py-2 text-xs text-bad"
            data-owner-history-verification-gap
          >
            <TriangleAlert size={16} className="shrink-0" aria-hidden="true" />
            <span>
              Verification gap recorded. Later intervals were verified after
              missing scheduled footage; this closeout preserves that integrity warning.
            </span>
          </div>
        ) : null}
        <div className="mt-3 grid grid-cols-[1.25fr_0.85fr_0.85fr_1fr] border-t border-border text-xs">
          <span className="py-2 font-semibold uppercase text-text-mut">Metric</span>
          <span className="py-2 font-semibold uppercase text-text-mut">Plan</span>
          <span className="py-2 font-semibold uppercase text-text-mut">Actual</span>
          <span className="py-2 font-semibold uppercase text-text-mut">Variance</span>
          {rows.map((row) => (
            <div key={row.label} className="contents">
              <span className="border-t border-border py-2 text-text-mut">{row.label}</span>
              <span className="border-t border-border py-2">
                {row.plan === null ? "Unavailable" : row.format(row.plan)}
              </span>
              <span className="border-t border-border py-2">
                {row.actual === null ? "Unavailable" : row.format(row.actual)}
              </span>
              <span className="border-t border-border py-2">
                {variance(row.plan, row.actual, row.format, row.direction)}
              </span>
            </div>
          ))}
        </div>
        <p className="mt-3 text-[11px] text-text-mut">
          Overhead, indirect labor, rent, freight, taxes, and other expenses are excluded.
        </p>
      </section>
      <OutputChart record={record} />
      <section className="border-l border-border pl-5">
        <h3 className="text-xs font-semibold uppercase text-text-mut">Audit trail</h3>
        <div className="mt-3 max-h-64 overflow-y-auto">
          {record.audit.length ? record.audit.map((entry) => (
            <article key={entry.id} className="border-b border-border py-3 last:border-b-0">
              <div className="flex items-center justify-between gap-3 text-xs">
                <span className="text-text-mut">
                  {dateTimeLabel(entry.createdAt, timezone)}
                </span>
                <span className="capitalize text-text-mut">{entry.actorType}</span>
              </div>
              <p className="mt-1 text-sm font-medium">{entry.summary}</p>
              <p className="mt-1 text-xs text-text-mut">{entry.detail}</p>
            </article>
          )) : (
            <p className="py-8 text-sm text-text-mut">
              No audit entries were returned for this closeout.
            </p>
          )}
        </div>
      </section>
    </div>
  );
}

export function HistorySurface({
  data,
  preview = false,
}: {
  data: OwnerHistoryData;
  preview?: boolean;
}) {
  useOwnerSurfaceStatus(preview ? "preview" : "connected");
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [expandedId, setExpandedId] = useState<string | null>(
    data.records[0]?.id ?? null,
  );
  const [evidenceRecord, setEvidenceRecord] =
    useState<OwnerHistoryRecord | null>(null);
  const [evidenceClips, setEvidenceClips] =
    useState<OwnerEvidenceClip[] | null>(null);
  const [evidenceError, setEvidenceError] = useState(false);
  const evidenceTriggerRef = useRef<HTMLButtonElement | null>(null);
  const evidenceCloseRef = useRef<HTMLButtonElement | null>(null);
  const visibleExpandedId =
    expandedId === null
      ? null
      : data.records.some((record) => record.id === expandedId)
        ? expandedId
        : data.records[0]?.id ?? null;

  const filterOptions = useMemo(() => ({
    project: [{ value: "all", label: "Project · All" }, ...data.options.projects.map((value) => ({ value, label: value }))],
    customer: [{ value: "all", label: "Customer · All" }, ...data.options.customers.map((value) => ({ value, label: value }))],
    station: [{ value: "all", label: "Station · All" }, ...data.options.stations.map((value) => ({ value, label: value }))],
    shift: [{ value: "all", label: "Shift · All" }, ...data.options.shifts.map((value) => ({ value, label: value }))],
    team: [{ value: "all", label: "Team · All" }, ...data.options.teams.map((value) => ({ value, label: value }))],
  }), [data.options]);

  function setFilter(key: string, value: string) {
    const next = new URLSearchParams(searchParams.toString());
    const defaultValue = key === "range" ? "90" : "all";
    if (value === defaultValue) next.delete(key);
    else next.set(key, value);
    const serialized = next.toString();
    router.push(serialized ? `${pathname}?${serialized}` : pathname);
  }

  function exportCsv() {
    const blob = new Blob([ownerHistoryCsv(data.records, data.timezone)], {
      type: "text/csv;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "factoryvision-history.csv";
    anchor.click();
    URL.revokeObjectURL(url);
  }

  function closeEvidence() {
    setEvidenceRecord(null);
    setEvidenceClips(null);
    setEvidenceError(false);
    window.requestAnimationFrame(() => evidenceTriggerRef.current?.focus());
  }

  async function openEvidence(
    record: OwnerHistoryRecord,
    trigger: HTMLButtonElement,
  ) {
    evidenceTriggerRef.current = trigger;
    setEvidenceRecord(record);
    setEvidenceClips(preview ? [previewEvidenceClip(record)] : null);
    setEvidenceError(false);
    window.requestAnimationFrame(() => evidenceCloseRef.current?.focus());
    if (preview) return;
    try {
      setEvidenceClips(await loadOwnerEvidence(data.factoryId, record.id));
    } catch {
      setEvidenceError(true);
      setEvidenceClips([]);
    }
  }

  return (
    <div className="py-3" data-owner-history-surface>
      <h1 className="sr-only">{preview ? "History preview" : "History"}</h1>
      <div
        className="flex min-h-[60px] items-center gap-2 overflow-x-auto border border-border bg-panel-2 p-2"
        data-owner-history-filter-bar
      >
        <HistoryFilter
          label="Date range"
          value={data.filters.range}
          onChange={(value) => setFilter("range", value)}
          values={[
            { value: "30", label: "Last 30 days" },
            { value: "90", label: "Last 90 days" },
            { value: "365", label: "Last 12 months" },
            { value: "all", label: "All time" },
          ]}
        />
        {(["project", "customer", "station", "shift", "team"] as const).map((key) => (
          <HistoryFilter
            key={key}
            label={key[0].toUpperCase() + key.slice(1)}
            value={data.filters[key]}
            values={filterOptions[key]}
            onChange={(value) => setFilter(key, value)}
          />
        ))}
        <HistoryFilter
          label="Status"
          value={data.filters.status}
          onChange={(value) => setFilter("status", value)}
          values={[
            { value: "all", label: "Status · All" },
            { value: "on_time", label: "On time" },
            { value: "late", label: "Late or short" },
            { value: "positive_margin", label: "Positive margin" },
            { value: "negative_margin", label: "Negative margin" },
          ]}
        />
        <button
          type="button"
          onClick={exportCsv}
          disabled={data.records.length === 0}
          data-owner-history-export
          className="inline-flex h-11 shrink-0 items-center gap-2 bg-accent px-5 text-sm font-semibold text-black hover:bg-accent-hi disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Download size={17} aria-hidden="true" />
          Export
        </button>
      </div>

      <div className="mt-2 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        <SummaryMetric
          label="Projects completed"
          value={data.summary.completedProjects.toLocaleString("en-US")}
          detail="in selected range"
          icon={CalendarDays}
        />
        <SummaryMetric
          label="On time"
          value={
            data.summary.onTimePercent === null
              ? "—"
              : `${Math.round(data.summary.onTimePercent)}%`
          }
          detail={`${data.summary.onTimeCount} of ${data.summary.completedProjects} projects`}
          icon={CheckCircle2}
          good={data.summary.onTimePercent !== null && data.summary.onTimePercent >= 90}
        />
        <SummaryMetric
          label="Units / labor hour"
          value={
            data.summary.unitsPerLaborHour === null
              ? "—"
              : data.summary.unitsPerLaborHour.toFixed(1)
          }
          detail={
            data.summary.unitsPerLaborHour === null
              ? "labor time unavailable"
              : `weighted · ${data.summary.laborCoverageCount} of ${data.summary.completedProjects} projects`
          }
          icon={Gauge}
          good={data.summary.unitsPerLaborHour !== null}
        />
        <SummaryMetric
          label="Margin after direct costs"
          value={money(data.summary.marginAfterDirectCostsCents)}
          detail="direct costs only"
          icon={CircleDollarSign}
          good={data.summary.marginAfterDirectCostsCents >= 0}
        />
      </div>
      <p className="mt-2 px-1 text-[11px] text-text-mut">
        Margin after direct costs excludes overhead, indirect labor, rent, freight, taxes, and other expenses.
      </p>

      <section className="mt-2 overflow-hidden border border-border bg-panel" aria-label="Project closeout history">
        {data.records.length === 0 ? (
          <div className="grid min-h-[360px] place-items-center px-6 text-center">
            <div>
              <History size={32} className="mx-auto text-text-dim" aria-hidden="true" />
              <h2 className="mt-4 text-lg font-semibold">No closeouts match these filters</h2>
              <p className="mt-2 text-sm text-text-mut">
                Completed projects remain permanent; change a filter to widen this view.
              </p>
            </div>
          </div>
        ) : (
          <>
          <div className="divide-y divide-border sm:hidden" data-owner-history-mobile-list>
            {data.records.map((record) => (
              <article key={record.id} className="px-4 py-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <h2 className="truncate font-semibold">{record.projectName}</h2>
                    <p className="mt-1 truncate text-xs text-text-mut">
                      {record.customerName} · {dateLabel(
                        record.completedAt,
                        record.factoryTimezone ?? data.timezone,
                      )}
                    </p>
                  </div>
                  <span
                    className={`shrink-0 text-sm font-semibold ${
                      record.grade === "A"
                        ? "text-good"
                        : record.grade === "B"
                          ? "text-warn"
                          : "text-bad"
                    }`}
                  >
                    Grade {record.grade}
                  </span>
                </div>
                <div className="mt-3 grid grid-cols-2 gap-3 text-xs">
                  <div>
                    <p className="text-text-mut">Verified good units</p>
                    <p className="mt-1 font-semibold">{record.actualUnits.toLocaleString("en-US")}</p>
                  </div>
                  <div>
                    <p className="text-text-mut">Margin after direct costs</p>
                    <p className={`mt-1 font-semibold ${record.actualMarginCents >= 0 ? "text-good" : "text-bad"}`}>
                      {money(record.actualMarginCents)}
                    </p>
                  </div>
                </div>
              </article>
            ))}
          </div>
          <div className="hidden overflow-x-auto sm:block" data-owner-history-table-scroll>
            <div className="min-w-[1180px]">
              <div className="grid h-14 grid-cols-[220px_180px_150px_130px_140px_150px_180px_100px_80px] items-center border-b border-border px-4 text-xs font-medium text-text-mut">
                <span className="sticky left-0 z-10 bg-panel">Project</span>
                <span>Customer</span>
                <span>Completed</span>
                <span className="text-center">Units<br /><span className="text-[10px]">plan → actual</span></span>
                <span className="text-center">Labor<br /><span className="text-[10px]">plan → actual</span></span>
                <span className="text-center">Materials<br /><span className="text-[10px]">plan → actual</span></span>
                <span className="text-center">Margin after direct costs<br /><span className="text-[10px]">plan → actual</span></span>
                <span className="text-center">On time</span>
                <span className="text-center">Grade</span>
              </div>
              {data.records.map((record) => {
                const expanded = visibleExpandedId === record.id;
                return (
                  <div key={record.id}>
                    <div
                      data-owner-history-row
                      className={`grid min-h-[58px] grid-cols-[220px_180px_150px_130px_140px_150px_180px_100px_80px] items-center border-b border-border px-4 text-sm ${
                        expanded ? "bg-panel-2" : ""
                      }`}
                    >
                      <div className={`sticky left-0 z-10 ${expanded ? "bg-panel-2" : "bg-panel"}`}>
                        <button
                          type="button"
                          aria-expanded={expanded}
                          onClick={() => setExpandedId(expanded ? null : record.id)}
                          className={`flex min-h-11 w-full items-center gap-3 text-left font-semibold ${
                            expanded ? "text-accent" : ""
                          }`}
                        >
                          {expanded
                            ? <ChevronDown size={16} aria-hidden="true" />
                            : <ChevronRight size={16} aria-hidden="true" />}
                          <span className="truncate">{record.projectName}</span>
                        </button>
                      </div>
                      <span className="truncate pr-3 text-text-mut">{record.customerName}</span>
                      <span className="text-text-mut">
                        {dateLabel(
                          record.completedAt,
                          record.factoryTimezone ?? data.timezone,
                        )}
                      </span>
                      <span className="text-center"><PlanActual planned={record.plannedUnits} actual={record.actualUnits} /></span>
                      <span className="text-center"><PlanActual planned={record.plannedLaborCents} actual={record.actualLaborCents} format={money} direction="lower" /></span>
                      <span className="text-center"><PlanActual planned={record.plannedMaterialsCents} actual={record.actualMaterialsCents} format={money} direction="lower" /></span>
                      <span className="text-center"><PlanActual planned={record.plannedMarginCents} actual={record.actualMarginCents} format={money} /></span>
                      <span className="flex justify-center">
                        <span
                          role="img"
                          className={`grid size-7 place-items-center rounded-full border ${
                            record.onTime ? "border-good text-good" : "border-bad text-bad"
                          }`}
                          aria-label={record.onTime ? "On time" : "Late or short"}
                        >
                          {record.onTime
                            ? <Check size={15} aria-hidden="true" />
                            : <X size={15} aria-hidden="true" />}
                        </span>
                      </span>
                      <span className="flex justify-center">
                        <span
                          className={`grid size-8 place-items-center rounded-full border font-semibold ${
                            record.grade === "A"
                              ? "border-good text-good"
                              : record.grade === "B"
                                ? "border-warn text-warn"
                                : "border-bad text-bad"
                          }`}
                        >
                          {record.grade}
                        </span>
                      </span>
                    </div>
                    {expanded ? (
                      <CloseoutExpansion
                        record={record}
                        timezone={data.timezone}
                        onEvidence={(trigger) => {
                          void openEvidence(record, trigger);
                        }}
                      />
                    ) : null}
                  </div>
                );
              })}
            </div>
          </div>
          </>
        )}
      </section>

      {evidenceRecord ? (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/65" role="presentation">
          <button
            type="button"
            aria-label="Close evidence drawer"
            className="absolute inset-0 cursor-default"
            onClick={closeEvidence}
          />
          <aside
            role="dialog"
            aria-modal="true"
            aria-labelledby="evidence-title"
            className="relative h-full w-full max-w-md border-l border-border bg-bg p-5 shadow-2xl"
            onKeyDown={(event) => {
              if (event.key === "Escape") closeEvidence();
              if (event.key === "Tab") {
                const focusable = [
                  ...event.currentTarget.querySelectorAll<HTMLElement>(
                    "button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])",
                  ),
                ].filter((element) => !element.hasAttribute("hidden"));
                const first = focusable[0];
                const last = focusable.at(-1);
                if (!first || !last) {
                  event.preventDefault();
                  evidenceCloseRef.current?.focus();
                } else if (event.shiftKey && document.activeElement === first) {
                  event.preventDefault();
                  last.focus();
                } else if (
                  !event.shiftKey
                  && document.activeElement === last
                ) {
                  event.preventDefault();
                  first.focus();
                }
              }
            }}
          >
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs font-semibold uppercase text-accent">Retained evidence</p>
                <h2 id="evidence-title" className="mt-1 text-xl font-semibold">
                  {evidenceRecord.projectName}
                </h2>
              </div>
              <button
                ref={evidenceCloseRef}
                type="button"
                aria-label="Close"
                onClick={closeEvidence}
                className="grid size-11 place-items-center border border-border text-text-mut hover:text-text"
              >
                <X size={18} aria-hidden="true" />
              </button>
            </div>
            <div className="mt-6 border-y border-border py-4">
              <p className="text-3xl font-semibold">{evidenceRecord.evidence.count}</p>
              <p className="mt-1 text-sm text-text-mut">
                clips attached to closeout revision {evidenceRecord.revision}
              </p>
            </div>
            <p className="mt-5 text-sm leading-6 text-text-mut">
              This record exposes only clips attached to production exceptions or the immutable closeout. It is not a raw-footage browser.
            </p>
            <div className="mt-5 border border-border bg-panel-2 p-4">
              <p className="text-sm font-medium">Secure playback metadata retained</p>
              <p className="mt-2 text-xs leading-5 text-text-mut">
                Clip playback requires a signed evidence attachment. No unsigned storage URL is exposed.
              </p>
            </div>
            {
              <div className="mt-4 space-y-2" aria-live="polite">
                {evidenceClips === null ? (
                  <p className="text-sm text-text-mut">Loading secure evidence…</p>
                ) : evidenceError ? (
                  <p className="border border-warn/50 bg-panel-2 p-3 text-sm text-warn">
                    Evidence metadata is temporarily unavailable.
                  </p>
                ) : evidenceClips.length === 0 ? (
                  <p className="text-sm text-text-mut">
                    No retained evidence is currently playable.
                  </p>
                ) : evidenceClips.map((clip, index) => (
                  <article
                    key={clip.id}
                    className="border border-border bg-panel-2 p-3"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold">Clip {index + 1}</p>
                        <p className="mt-1 text-xs text-text-mut">
                          {clip.reasonCode.replaceAll("-", " ")}
                        </p>
                      </div>
                      {clip.state === "available" && clip.signedUrl ? (
                        <a
                          href={clip.signedUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex min-h-11 items-center gap-1 text-xs font-semibold text-accent"
                        >
                          Open
                          <ExternalLink size={13} aria-hidden="true" />
                        </a>
                      ) : (
                        <span className="py-2 text-xs text-text-mut">
                          {clip.state === "expired" ? "Expired" : "Unavailable"}
                        </span>
                      )}
                    </div>
                    <p className="mt-2 font-mono text-[10px] text-text-dim">
                      SHA-256 {clip.objectSha256.slice(0, 16)}…
                    </p>
                  </article>
                ))}
              </div>
            }
          </aside>
        </div>
      ) : null}
    </div>
  );
}
