"use client";

import Image from "next/image";
import Link from "next/link";
import {
  ArrowRight,
  BarChart3,
  Camera,
  ChevronRight,
  Clock3,
  Plus,
  Radio,
  TriangleAlert,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import type {
  OwnerAttentionItem,
  OwnerDashboardData,
  OwnerPaceStatus,
  OwnerProjectSummary,
} from "@/lib/ownerDashboardTypes";
import { ownerPaceChartIsValid } from "@/lib/ownerDashboardTypes";
import { NewProjectDrawer } from "@/components/owner-v2/new-project-drawer";
import { useOwnerSurfaceStatus } from "@/components/owner-v2/owner-shell";

type StationOption = {
  id: string;
  name: string;
  baselineUnitsPerDay: number | null;
};

type WorkerOption = {
  id: string;
  name: string;
};

const statusClass: Record<OwnerPaceStatus, string> = {
  BEHIND: "text-bad",
  ON_TRACK: "text-good",
  AHEAD: "text-good",
  DATA_DELAY: "text-warn",
};

const statusLabel: Record<OwnerPaceStatus, string> = {
  BEHIND: "BEHIND",
  ON_TRACK: "ON TRACK",
  AHEAD: "AHEAD",
  DATA_DELAY: "DATA DELAY",
};

const marginClass = {
  healthy: "text-good",
  at_risk: "text-bad",
  loss: "text-bad",
  unavailable: "text-text-dim",
} as const;

export function TodayDashboard({
  data,
  stationOptions,
  workers,
  preview = false,
  initialProjectOpen = false,
  stationSuggestion = null,
}: {
  data: OwnerDashboardData;
  stationOptions: StationOption[];
  workers: WorkerOption[];
  preview?: boolean;
  initialProjectOpen?: boolean;
  stationSuggestion?: {
    stationId: string;
    confidencePercent: number;
  } | null;
}) {
  const [selectedProjectId, setSelectedProjectId] = useState(
    data.projects[0]?.id ?? "",
  );
  const [projectDrawerOpen, setProjectDrawerOpen] =
    useState(initialProjectOpen);
  useOwnerSurfaceStatus(
    data.exceptionMonitoringAvailable ? "connected" : "delayed",
  );
  const rootRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    rootRef.current?.setAttribute("data-hydrated", "true");
  }, []);
  const selected =
    data.projects.find((project) => project.id === selectedProjectId)
    ?? data.projects[0]
    ?? null;

  return (
    <div ref={rootRef} data-owner-today data-hydrated="false">
      <div className="mb-3 flex items-center justify-between gap-4 lg:mb-0 lg:h-0">
        <div className="lg:sr-only">
          <p className="text-[11px] uppercase text-text-dim">Production control</p>
          <h1 className="mt-0.5 text-xl font-semibold">Today</h1>
        </div>
        <button
          type="button"
          onClick={() => setProjectDrawerOpen(true)}
          aria-expanded={projectDrawerOpen}
          aria-controls="new-project-drawer"
          className="inline-flex h-11 items-center gap-2 rounded-[7px] bg-accent px-5 text-sm font-semibold text-black shadow-[0_6px_18px_rgba(232,116,47,.18)] hover:bg-accent-hi lg:fixed lg:right-4 lg:top-3 lg:z-30 lg:h-10"
        >
          <Plus size={17} aria-hidden="true" />
          Project
        </button>
      </div>

      <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_324px]">
        <div className="min-w-0 space-y-3">
          <ActiveProjects
            projects={data.projects}
            selectedProjectId={selected?.id ?? ""}
            onSelect={setSelectedProjectId}
          />
          <PaceChart project={selected} />
        </div>
        <AttentionRail
          items={data.attention}
          monitoringAvailable={data.exceptionMonitoringAvailable}
          preview={preview}
        />
      </div>

      <StationTable data={data} preview={preview} />

      <NewProjectDrawer
        open={projectDrawerOpen}
        onOpenChange={setProjectDrawerOpen}
        factoryId={data.factoryId}
        timezone={data.timezone}
        nowIso={data.nowIso}
        stations={stationOptions}
        workers={workers}
        preview={preview}
        stationSuggestion={stationSuggestion}
      />
    </div>
  );
}

function ActiveProjects({
  projects,
  selectedProjectId,
  onSelect,
}: {
  projects: OwnerProjectSummary[];
  selectedProjectId: string;
  onSelect: (id: string) => void;
}) {
  return (
    <section
      className="overflow-hidden rounded-[8px] border border-border bg-panel-2"
      data-owner-active-projects
    >
      <div className="flex h-9 items-center px-4 text-[11px] font-medium uppercase text-text-mut">
        Active projects
      </div>
      {projects.length ? (
        <div className="space-y-1 px-1 pb-1">
          {projects.map((project) => {
            const selected = project.id === selectedProjectId;
            return (
              <button
                type="button"
                key={project.id}
                onClick={() => onSelect(project.id)}
                className={`grid min-h-[70px] w-full items-center gap-3 rounded-[6px] border px-3 text-left transition-colors md:grid-cols-[158px_1.25fr_1fr_1fr_138px_128px] ${
                  selected
                    ? "border-accent/70 bg-panel"
                    : "border-border-soft bg-[rgba(255,255,255,.012)] hover:bg-panel"
                }`}
              >
                <strong
                  className={`text-[21px] font-semibold ${statusClass[project.status]}`}
                >
                  {statusLabel[project.status]}
                </strong>
                <span>
                  <span className="block text-base font-semibold">
                    {project.name}
                  </span>
                  <span className="mt-0.5 block text-sm text-text-mut">
                    {project.verifiedGoodUnits === null
                      ? "Verified units unavailable"
                      : `${project.verifiedGoodUnits.toLocaleString()} / ${project.targetUnits.toLocaleString()} units`}
                  </span>
                </span>
                <span className="text-xs leading-5 text-text-mut">
                  {project.recoverySummary}
                </span>
                <span>
                  <span className="block text-xs text-text-mut">
                    Projected margin
                  </span>
                  <strong
                    className={`mt-0.5 block text-lg ${
                      marginClass[project.projectedMarginStatus]
                    }`}
                  >
                    {project.projectedMarginBps === null
                      ? "Unavailable"
                      : `${(project.projectedMarginBps / 100).toFixed(1)}%`}
                  </strong>
                  <span className="block text-[11px] text-text-mut">
                    after direct costs
                  </span>
                </span>
                <span>
                  <span className="block text-xs text-text-mut">Deadline</span>
                  <span className="mt-1 block text-xs">{project.deadlineLabel}</span>
                </span>
                <span>
                  <span className="block text-xs text-text-mut">
                    Verified through
                  </span>
                  <span className="mt-1 block text-xs">
                    {project.verifiedThroughLabel}
                  </span>
                </span>
              </button>
            );
          })}
        </div>
      ) : (
        <div className="grid min-h-[210px] place-items-center border-t border-border px-6 text-center">
          <div>
            <p className="font-medium">No active projects</p>
            <p className="mt-2 text-sm text-text-mut">
              Start a project to track verified output, labor, and margin.
            </p>
          </div>
        </div>
      )}
    </section>
  );
}

function PaceChart({ project }: { project: OwnerProjectSummary | null }) {
  const chartLabels = project?.chart?.labels ?? [];
  const plot = useMemo(() => {
    if (!ownerPaceChartIsValid(project?.chart ?? null) || !project?.chart) {
      return null;
    }
    const width = 920;
    const height = 190;
    const left = 42;
    const right = 24;
    const top = 18;
    const bottom = 30;
    const max = Math.max(
      project.targetUnits,
      ...project.chart.actual,
      ...project.chart.required,
      ...project.chart.requiredToRecover,
    );
    const x = (index: number, count: number) =>
      left + (index / Math.max(1, count - 1)) * (width - left - right);
    const y = (value: number) =>
      top + (1 - value / Math.max(1, max)) * (height - top - bottom);
    const path = (values: readonly number[], startIndex = 0, totalCount = values.length) =>
      values
        .map(
          (value, index) =>
            `${index ? "L" : "M"} ${x(index + startIndex, totalCount).toFixed(1)} ${y(value).toFixed(1)}`,
        )
        .join(" ");
    return {
      width,
      height,
      left,
      right,
      top,
      bottom,
      max,
      x,
      y,
      actualPath: path(project.chart.actual, 0, project.chart.labels.length),
      requiredPath: path(project.chart.required),
      recoveryPath: project.chart.requiredToRecover.length
          ? path(
            project.chart.requiredToRecover,
            project.chart.nowIndex,
            project.chart.labels.length,
          )
        : "",
    };
  }, [project]);

  return (
    <section
      className="min-h-[292px] rounded-[8px] border border-border bg-panel-2 px-4 pb-3 pt-3"
      data-owner-pace-chart
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[11px] font-medium uppercase text-text-mut">
          {project
            ? `${project.name} — actual vs required pace`
            : "Actual vs required pace"}
        </p>
        {project?.chart ? (
          <div className="flex flex-wrap gap-5 text-[11px] text-text-mut">
            <Legend color="#f2f4f5" label="Actual cumulative units" />
            <Legend color="#9aa1a9" label="Required cumulative units" dashed />
            {project.status === "BEHIND" ? (
              <Legend color="#e5484d" label="Required to recover" dashed />
            ) : null}
          </div>
        ) : null}
      </div>
      {plot && project?.chart ? (
        <>
        <p id={`pace-summary-${project.id}`} className="sr-only">
          {project.name}: actual output is {project.chart.actual.at(-1)} units,
          required output at the verified point is{" "}
          {project.chart.required[project.chart.nowIndex]} units, and the
          deadline target is {project.targetUnits} units.
        </p>
        <svg
          viewBox={`0 0 ${plot.width} ${plot.height}`}
          className="mt-3 h-[218px] w-full"
          role="img"
          aria-label={`${project.name} cumulative verified output versus required pace`}
          aria-describedby={`pace-summary-${project.id}`}
        >
          {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
            const value = Math.round(plot.max * ratio);
            const y = plot.y(value);
            return (
              <g key={ratio}>
                <line
                  x1={plot.left}
                  x2={plot.width - plot.right}
                  y1={y}
                  y2={y}
                  stroke="rgba(255,255,255,.07)"
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
          <path
            d={plot.requiredPath}
            fill="none"
            stroke="#9aa1a9"
            strokeDasharray="5 4"
            strokeWidth="1.5"
          />
          <path
            d={plot.actualPath}
            fill="none"
            stroke="#f2f4f5"
            strokeWidth="2"
          />
          {plot.recoveryPath ? (
            <path
              d={plot.recoveryPath}
              fill="none"
              stroke="#e5484d"
              strokeDasharray="5 4"
              strokeWidth="1.6"
            />
          ) : null}
          <line
            x1={plot.x(project.chart.nowIndex, project.chart.labels.length)}
            x2={plot.x(project.chart.nowIndex, project.chart.labels.length)}
            y1={plot.top}
            y2={plot.height - plot.bottom}
            stroke="#d6dadd"
            strokeWidth="1"
          />
          <rect
            x={plot.x(project.chart.nowIndex, project.chart.labels.length) - 18}
            y={0}
            width={36}
            height={16}
            rx={3}
            fill="#d6dadd"
          />
          <text
            x={plot.x(project.chart.nowIndex, project.chart.labels.length)}
            y={11}
            textAnchor="middle"
            fill="#111"
            fontSize="9"
            fontWeight="700"
          >
            NOW
          </text>
          {chartLabels.map((label, index) =>
            label ? (
              <text
                key={`${label}-${index}`}
                x={plot.x(index, chartLabels.length)}
                y={plot.height - 8}
                textAnchor={
                  index === 0
                    ? "start"
                    : index === chartLabels.length - 1
                      ? "end"
                      : "middle"
                }
                fill="#9aa1a9"
                fontSize="10"
              >
                {label}
              </text>
            ) : null,
          )}
          <line
            x1={plot.x(chartLabels.length - 1, chartLabels.length)}
            x2={plot.x(chartLabels.length - 1, chartLabels.length)}
            y1={plot.y(project.targetUnits)}
            y2={plot.height - plot.bottom}
            stroke="#e8742f"
            strokeDasharray="2 3"
            strokeWidth="1"
          />
          <circle
            cx={plot.x(chartLabels.length - 1, chartLabels.length)}
            cy={plot.y(project.targetUnits)}
            r="3"
            fill="#e8742f"
          />
        </svg>
        <p className="-mt-1 text-right text-[11px] text-text-mut">
          Actual {project.chart.actual.at(-1)?.toLocaleString()} · Required now{" "}
          {project.chart.required[project.chart.nowIndex]?.toLocaleString()} ·
          Deadline target {project.targetUnits.toLocaleString()}
        </p>
        </>
      ) : (
        <div className="grid min-h-[238px] place-items-center text-center">
          <div>
            <Clock3
              className="mx-auto text-warn"
              size={23}
              aria-hidden="true"
            />
            <p className="mt-3 font-medium">Pace data unavailable</p>
            <p className="mt-1 text-sm text-text-mut">
              The chart appears after contiguous production footage is verified.
            </p>
          </div>
        </div>
      )}
    </section>
  );
}

function AttentionRail({
  items,
  monitoringAvailable,
  preview,
}: {
  items: OwnerAttentionItem[];
  monitoringAvailable: boolean;
  preview: boolean;
}) {
  return (
    <aside
      className="overflow-hidden rounded-[8px] border border-border bg-panel-2 xl:min-h-[556px]"
      data-owner-attention
    >
      <div className="flex h-9 items-center px-4 text-[11px] font-medium uppercase text-text-mut">
        Attention
      </div>
      <div className="space-y-2 px-3 pb-3">
        {items.length ? (
          items.map((item) => {
            const Icon =
              item.kind === "verification" || item.kind === "verification_gap"
                ? Clock3
                : item.kind === "camera"
                  ? Camera
                  : item.kind === "pace"
                    ? BarChart3
                    : TriangleAlert;
            return (
              <Link
                href={preview ? `/owner-preview${item.href}` : item.href}
                key={item.id}
                className={`grid min-h-[82px] w-full grid-cols-[46px_1fr_18px] items-center gap-2 rounded-[6px] border px-2 text-left outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-bg ${
                  item.tone === "bad"
                    ? "border-bad/70"
                    : "border-warn/70"
                }`}
              >
                <Icon
                  size={27}
                  strokeWidth={1.6}
                  aria-hidden="true"
                  className={item.tone === "bad" ? "text-bad" : "text-warn"}
                />
                <span>
                  <strong className="block text-sm">{item.title}</strong>
                  <span className="mt-1 block text-xs text-text-mut">
                    {item.detail}
                  </span>
                  <span className="mt-1 block text-[11px] text-text-mut">
                    {item.meta}
                  </span>
                </span>
                <ChevronRight
                  size={16}
                  className="text-text-mut"
                  aria-hidden="true"
                />
              </Link>
            );
          })
        ) : monitoringAvailable ? (
          <div className="grid min-h-40 place-items-center border-t border-border text-center">
            <div>
              <Radio className="mx-auto text-good" size={22} />
              <p className="mt-2 text-sm">No active exceptions</p>
            </div>
          </div>
        ) : null}
        {!monitoringAvailable ? (
          <div className="grid min-h-40 place-items-center border-t border-border px-5 text-center">
            <div>
              <TriangleAlert className="mx-auto text-text-dim" size={22} />
              <p className="mt-2 text-sm">Exception monitoring unavailable</p>
              <p className="mt-1 text-xs leading-5 text-text-dim">
                No all-clear is inferred while camera and assignment checks are
                unavailable.
              </p>
            </div>
          </div>
        ) : null}
      </div>
      <Link
        href={preview ? "/owner-preview/alerts" : "/alerts"}
        className="flex h-12 w-full items-center gap-2 border-t border-border px-4 text-sm text-text-mut hover:text-text"
      >
        View all alerts
        <ArrowRight size={15} aria-hidden="true" />
      </Link>
    </aside>
  );
}

function StationTable({
  data,
  preview,
}: {
  data: OwnerDashboardData;
  preview: boolean;
}) {
  return (
    <section
      className="mt-3 overflow-hidden rounded-[8px] border border-border bg-panel-2"
      data-owner-station-table
    >
      <div className="overflow-x-auto">
        <div className="min-w-[900px]">
          <div className="grid h-10 grid-cols-[2fr_1fr_1.15fr_1.6fr_1.15fr_30px] items-center gap-3 px-3 text-[10px] uppercase text-text-mut">
            <span>Station</span>
            <span>Units / hour</span>
            <span>Output / labor hr</span>
            <span>Current project</span>
            <span>Status</span>
            <span />
          </div>
          <div className="space-y-1 px-1 pb-1">
            {data.stations.length ? (
              data.stations.map((station, stationIndex) => (
                <Link
                  href={`${
                    preview ? "/owner-preview/stations" : "/stations"
                  }?station_id=${encodeURIComponent(station.id)}`}
                  key={station.id}
                  className="grid min-h-[58px] w-full grid-cols-[2fr_1fr_1.15fr_1.6fr_1.15fr_30px] items-center gap-3 rounded-[6px] border border-border bg-[rgba(255,255,255,.012)] px-2 text-left hover:bg-panel"
                >
                  <span className="flex min-w-0 items-center gap-3">
                    <span className="relative h-12 w-28 shrink-0 overflow-hidden rounded-[4px] bg-idle">
                      {station.imageSrc ? (
                        <Image
                          src={station.imageSrc}
                          alt=""
                          fill
                          sizes="112px"
                          priority={stationIndex < 5}
                          className="object-cover"
                        />
                      ) : (
                        <span className="grid size-full place-items-center">
                          <Camera size={18} className="text-text-dim" />
                        </span>
                      )}
                    </span>
                    <span className="min-w-0">
                      <strong className="block break-words text-sm leading-4">
                        {station.name}
                      </strong>
                      <span className="mt-0.5 block text-[11px] text-text-mut">
                        {station.cameraCount !== null
                          ? `${station.cameraCount} cams`
                          : "Camera count unavailable"}
                      </span>
                    </span>
                  </span>
                  <strong className="text-base">
                    {station.unitsPerHour ?? "—"}
                  </strong>
                  <strong className="text-base">
                    {station.outputPerLaborHour ?? "—"}
                  </strong>
                  <span>
                    <strong className="block text-sm">
                      {station.projectAssignmentKnown
                        ? station.projectName ?? "No active project"
                        : "Assignment unavailable"}
                    </strong>
                    <span className="mt-0.5 block text-xs text-text-mut">
                      {station.projectAssignmentKnown
                        ? station.projectProgress ?? "—"
                        : "Not yet loaded"}
                    </span>
                  </span>
                  <span>
                    <strong
                      className={`block text-xs ${statusClass[station.status]}`}
                    >
                      {statusLabel[station.status]}
                    </strong>
                    <span className="mt-1 block text-[11px] text-text-mut">
                      {station.statusDetail}
                    </span>
                  </span>
                  <ArrowRight size={16} className="text-text-mut" aria-hidden="true" />
                </Link>
              ))
            ) : (
              <div className="grid min-h-36 place-items-center border-t border-border text-sm text-text-mut">
                No stations are configured for this factory.
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

function Legend({
  color,
  label,
  dashed = false,
}: {
  color: string;
  label: string;
  dashed?: boolean;
}) {
  return (
    <span className="flex items-center gap-2">
      <span
        className={`block h-px w-7 ${dashed ? "border-t border-dashed" : ""}`}
        style={{
          backgroundColor: dashed ? "transparent" : color,
          borderColor: dashed ? color : undefined,
        }}
      />
      {label}
    </span>
  );
}
