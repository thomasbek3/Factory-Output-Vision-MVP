"use client";

import { useEffect, useMemo, useState } from "react";
import { ChevronDown, Search } from "lucide-react";
import { Panel } from "@/components/ui/panel";
import {
  finishedJobs,
  finishedJobFromSeed,
  gradeFinishedJob,
  historyAggregates,
  nextTimeSuggestion,
  type FinishedJob,
  type FinishedJobGrade,
} from "@/lib/historyRecords";
import type { JobSeed } from "@/lib/demoData";
import { cn } from "@/lib/utils";

function money(value: number) {
  const sign = value >= 0 ? "+" : "-";
  return `${sign}$${Math.abs(Math.round(value)).toLocaleString("en-US")}`;
}

function dateLabel(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    timeZone: "America/Los_Angeles",
    month: "short",
    day: "numeric",
  }).format(new Date(value));
}

function GradeChip({ grade }: { grade: FinishedJobGrade }) {
  const tone =
    grade === "A"
      ? "bg-[var(--good-tint)] text-[var(--good)] shadow-[0_0_18px_rgba(70,194,107,.16)]"
      : grade === "B"
        ? "bg-[var(--warn-tint)] text-[var(--warn)] shadow-[0_0_18px_rgba(231,161,59,.14)]"
        : "bg-[var(--bad-tint)] text-[var(--bad)] shadow-[0_0_18px_rgba(229,72,77,.14)]";

  return (
    <span className={cn("inline-flex h-11 w-11 items-center justify-center rounded-full text-[20px] font-bold", tone)}>
      {grade}
    </span>
  );
}

function ExpandedHistoryRow({ job }: { job: FinishedJob }) {
  const nextTime = nextTimeSuggestion(job);
  const totalUnits = job.stationContribution.reduce((total, station) => total + station.units, 0);
  const maxUnits = Math.max(...job.dailyOutput.map((day) => day.units), 1);

  return (
    <div className="grid gap-4 p-5 lg:grid-cols-[minmax(0,1.2fr)_minmax(260px,.8fr)_minmax(280px,.9fr)]">
      <div>
        <div className="mb-3 text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--text-dim)]">
          Daily output
        </div>
        <div className="relative h-[230px] border-b border-[rgba(255,255,255,.28)]">
          <div className="absolute inset-x-0 top-[18%] border-t border-[rgba(255,255,255,.16)]" />
          <div className="absolute inset-x-0 top-[42%] border-t border-[rgba(255,255,255,.14)]" />
          <div className="absolute inset-x-0 top-[66%] border-t border-[rgba(255,255,255,.12)]" />
          <div className="absolute inset-x-0 bottom-0 flex h-full items-end justify-around gap-5 px-6 pb-7">
            {job.dailyOutput.map((day) => {
              const height = Math.max(18, (day.units / maxUnits) * 150);
              return (
                <div key={day.day} className="flex h-full flex-1 flex-col items-center justify-end">
                  <div className="mb-2 text-[12px] font-semibold text-[var(--text)]">{day.units}</div>
                  <div
                    className="w-full max-w-[92px] rounded-t-lg bg-[linear-gradient(180deg,rgba(70,194,107,.9),rgba(70,194,107,.18))]"
                    style={{ height }}
                  />
                  <div className="absolute bottom-0 translate-y-6 text-[12px] text-[var(--text-mut)]">{day.day}</div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <div className="space-y-5">
        <div>
          <div className="mb-3 text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--text-dim)]">
            Station contribution
          </div>
          <div className="space-y-3">
            {job.stationContribution.map((station) => {
              const pct = Math.round((station.units / Math.max(totalUnits, 1)) * 100);
              return (
                <div key={station.station}>
                  <div className="mb-1 flex justify-between text-[13px]">
                    <span className="font-semibold text-[var(--text)]">{station.station}</span>
                    <span className="text-[var(--text-mut)]">{station.units} · {pct}%</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-black/35">
                    <div className="h-full rounded-full bg-[var(--good)]" style={{ width: `${pct}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div>
          <div className="mb-3 text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--text-dim)]">
            Labor planned vs actual
          </div>
          <div className="rounded-lg border border-[var(--border-soft)] bg-black/15 p-3">
            <div className="flex justify-between text-[13px]">
              <span className="text-[var(--text-mut)]">Planned</span>
              <span className="font-semibold text-[var(--text)]">${job.plannedLaborUsd.toLocaleString("en-US")}</span>
            </div>
            <div className="mt-2 flex justify-between text-[13px]">
              <span className="text-[var(--text-mut)]">Actual</span>
              <span className={cn("font-semibold", job.actualLaborUsd <= job.plannedLaborUsd ? "text-[var(--good)]" : "text-[var(--bad)]")}>
                ${job.actualLaborUsd.toLocaleString("en-US")}
              </span>
            </div>
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-[rgba(232,116,47,.35)] bg-[rgba(232,116,47,.10)] p-5">
        <div className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--accent)]">
          Next time
        </div>
        <p className="mt-3 text-[18px] font-semibold leading-7 text-[var(--text)]">
          {nextTime.sentence}
        </p>
        <div className="mt-4 flex gap-2 text-[12px] font-semibold">
          <span className="rounded-full bg-black/25 px-2 py-1 text-[var(--accent)]">
            Suggest {nextTime.suggestDays.toFixed(1)} days
          </span>
          <span className={cn("rounded-full px-2 py-1", nextTime.delta >= 0 ? "bg-[var(--good-tint)] text-[var(--good)]" : "bg-[var(--bad-tint)] text-[var(--bad)]")}>
            {money(nextTime.delta)} margin
          </span>
        </div>
      </div>
    </div>
  );
}

export function HistoryDashboard() {
  const [query, setQuery] = useState("");
  const [dbFinished, setDbFinished] = useState<FinishedJob[]>([]);

  // Wire jobs marked finished in /jobs (persisted in the DB) through to History.
  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const response = await fetch("/api/jobs", { cache: "no-store" });
        if (!response.ok) return;
        const data = (await response.json()) as { jobs: JobSeed[] };
        const finished = data.jobs
          .filter((job) => job.status === "finished")
          .map(finishedJobFromSeed);
        if (!cancelled) setDbFinished(finished);
      } catch (error) {
        console.error("History: could not load finished jobs:", error);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const allJobs = useMemo(() => {
    const seen = new Set<string>();
    return [...dbFinished, ...finishedJobs]
      .filter((job) => (seen.has(job.id) ? false : (seen.add(job.id), true)))
      .sort((a, b) => new Date(b.finishedAt).getTime() - new Date(a.finishedAt).getTime());
  }, [dbFinished]);

  const [expandedId, setExpandedId] = useState(finishedJobs[0]?.id ?? "");
  const aggregates = historyAggregates(allJobs);
  const normalizedQuery = query.trim().toLowerCase();
  const filteredJobs = normalizedQuery
    ? allJobs.filter((job) =>
        `${job.client} ${job.product} ${job.spec}`.toLowerCase().includes(normalizedQuery),
      )
    : allJobs;

  return (
    <div className="space-y-5" data-history-route="ready">
      <section className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--text-dim)]">
            HISTORY
          </div>
          <h1 className="mt-2 text-[28px] font-semibold tracking-[-0.01em] text-[var(--text)]">
            Finished projects
          </h1>
        </div>
        <div className="flex h-9 min-w-[280px] items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--panel-2)] px-3 text-[13px] text-[var(--text-dim)]">
          <Search className="h-4 w-4" strokeWidth={1.75} />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search clients"
            className="min-w-0 flex-1 bg-transparent text-[13px] font-semibold text-[var(--text)] outline-none placeholder:text-[var(--text-dim)]"
          />
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        <Panel className="p-5">
          <div className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--text-dim)]">Lifetime jobs</div>
          <div className="mt-3 text-[32px] font-bold text-[var(--text)]">{aggregates.lifetimeJobs}</div>
        </Panel>
        <Panel className="p-5">
          <div className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--text-dim)]">Avg quote error</div>
          <div className="mt-3 text-[32px] font-bold text-[var(--warn)]">{aggregates.avgQuoteErrorPct}%</div>
        </Panel>
        <Panel className="p-5">
          <div className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--text-dim)]">Margin recovered</div>
          <div className="mt-3 text-[32px] font-bold text-[var(--good)]">{money(aggregates.marginRecovered)}</div>
        </Panel>
      </section>

      <Panel className="overflow-hidden p-0">
        <div className="grid grid-cols-[minmax(240px,1.4fr)_120px_120px_minmax(180px,.8fr)_96px_44px] border-b border-[var(--border-soft)] px-5 py-3 text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--text-dim)]">
          <span>Project</span>
          <span>Quoted</span>
          <span>Actual</span>
          <span>Margin plan → real</span>
          <span>Grade</span>
          <span />
        </div>
        <div className="divide-y divide-[var(--border-soft)]">
          {filteredJobs.map((job) => {
            const grade = gradeFinishedJob(job);
            const expanded = expandedId === job.id;
            return (
              <div key={job.id}>
                <button
                  type="button"
                  className="grid w-full grid-cols-[minmax(240px,1.4fr)_120px_120px_minmax(180px,.8fr)_96px_44px] items-center px-5 py-4 text-left hover:bg-white/[.02]"
                  onClick={() => setExpandedId(expanded ? "" : job.id)}
                >
                  <span>
                    <span className="block text-[15px] font-semibold text-[var(--text)]">{job.client} — {job.product}</span>
                    <span className="mt-1 block text-[12px] text-[var(--text-dim)]">
                      {job.spec} · finished {dateLabel(job.finishedAt)} · {job.stations.join(", ")}
                    </span>
                  </span>
                  <span className="text-[14px] font-semibold text-[var(--text)]">{job.quotedDays.toFixed(1)} days</span>
                  <span className={cn("text-[14px] font-semibold", job.actualDays <= job.quotedDays ? "text-[var(--good)]" : "text-[var(--warn)]")}>
                    {job.actualDays.toFixed(1)} days
                  </span>
                  <span className="text-[14px] font-semibold text-[var(--text)]">
                    ${job.plannedMarginUsd.toLocaleString("en-US")} →{" "}
                    <span className={job.realMarginUsd >= 0 ? "text-[var(--good)]" : "text-[var(--bad)]"}>
                      {money(job.realMarginUsd)}
                    </span>
                  </span>
                  <GradeChip grade={grade} />
                  <ChevronDown className={cn("h-4 w-4 text-[var(--text-dim)] transition-transform", expanded && "rotate-180")} strokeWidth={1.75} />
                </button>
                {expanded ? <ExpandedHistoryRow job={job} /> : null}
              </div>
            );
          })}
        </div>
      </Panel>
    </div>
  );
}
