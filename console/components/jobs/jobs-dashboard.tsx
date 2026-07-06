"use client";

import Link from "next/link";
import { AreaChart } from "@tremor/react";
import { CheckCircle2, CircleDollarSign, MoreHorizontal, Pause, Plus, RotateCcw } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useTime } from "@/components/providers/time-provider";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { countEventsThrough, stations, type JobSeed } from "@/lib/demoData";
import { validateNewJobInput, type NewJobInput } from "@/lib/jobForm";
import {
  cumulativeMarginSeries,
  jobPaceSentence,
  pacePercent,
  selectMoneyStripTotal,
  selectRunningJobSnapshots,
  type JobWithPace,
} from "@/lib/jobSelectors";
import { cn } from "@/lib/utils";
import { useConsoleJobs } from "@/components/jobs/use-console-jobs";

function formatMoney(value: number) {
  const rounded = Math.round(value);
  const sign = rounded >= 0 ? "+" : "-";
  return `${sign}$${Math.abs(rounded).toLocaleString("en-US")}`;
}

function stationNames(job: JobSeed) {
  return job.station_ids
    .map((stationId) => stations.find((station) => station.id === stationId)?.name ?? stationId)
    .join(", ");
}

function verdictTone(verdict: JobWithPace["snapshot"]["verdict"]) {
  if (verdict === "IN THE GREEN") return "from-[#54d978] to-[#1f8b47] text-[var(--good)] bg-[var(--good-tint)]";
  if (verdict === "GETTING TIGHT") return "from-[#f0b34f] to-[#a96a18] text-[var(--warn)] bg-[var(--warn-tint)]";
  return "from-[#f05b61] to-[#961f26] text-[var(--bad)] bg-[var(--bad-tint)]";
}

function labelLines(verdict: JobWithPace["snapshot"]["verdict"]) {
  if (verdict === "IN THE GREEN") return ["IN THE", "GREEN"];
  if (verdict === "GETTING TIGHT") return ["GETTING", "TIGHT"];
  return ["LOSING", "MONEY"];
}

function MoneyStrip({ jobSnapshots }: { jobSnapshots: JobWithPace[] }) {
  const { now } = useTime();
  const current = now();
  const allEvents = countEventsThrough(current);
  const totalMargin = selectMoneyStripTotal(jobSnapshots);
  const data = cumulativeMarginSeries(jobSnapshots, allEvents);

  return (
    <Panel className="relative min-h-[178px] overflow-hidden">
      <div className="relative z-[1]">
        <div className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--text-dim)]">
          PROJECTED PROFIT · {jobSnapshots.length} JOBS RUNNING
        </div>
        <div
          className={cn(
            "mt-4 text-[56px] font-bold leading-none tracking-[-0.01em] drop-shadow-[0_0_22px_rgba(70,194,107,.24)]",
            totalMargin >= 0 ? "text-[var(--good)]" : "text-[var(--bad)]",
          )}
        >
          {formatMoney(totalMargin)}
        </div>
        <p className="mt-3 max-w-2xl text-[14px] leading-6 text-[var(--text-mut)]">
          Active jobs only. Paused and finished work is outside this number.
        </p>
      </div>
      <div className="absolute inset-y-6 right-4 w-[42%] opacity-40">
        <AreaChart
          data={data.length ? data : [{ hour: "7a", margin: totalMargin }]}
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
  );
}

function JobCard({
  item,
  now,
  onPause,
  onResume,
  onFinish,
}: {
  item: JobWithPace;
  now: Date;
  onPause: (jobId: string) => void;
  onResume: (jobId: string) => void;
  onFinish: (jobId: string) => void;
}) {
  const { job, snapshot } = item;
  const percent = pacePercent(snapshot, job.units_required);
  const tone = verdictTone(snapshot.verdict);
  const lines = labelLines(snapshot.verdict);
  const keep = snapshot.projected_margin >= 0;
  const replayStation = job.station_ids[0] ?? stations[0]?.id;

  return (
    <Panel className={cn("grid gap-0 overflow-visible p-0 md:grid-cols-[148px_1fr_236px]", job.status === "paused" && "opacity-55")}>
      <div className={cn("flex min-h-[188px] flex-col justify-center rounded-l-[12px] bg-gradient-to-b px-5 text-white", tone)}>
        <span className="text-[17px] font-bold leading-5">{lines[0]}</span>
        <span className="text-[22px] font-bold leading-6">{lines[1]}</span>
      </div>

      <div className="min-w-0 px-6 py-5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="truncate text-[20px] font-semibold tracking-[-0.01em] text-[var(--text)]">
              {job.client}
            </h2>
            <div className="mt-1 text-[13px] text-[var(--text-dim)]">
              {job.title} · {stationNames(job)}
            </div>
          </div>
          {job.status === "paused" ? (
            <span className="rounded-full bg-[var(--warn-tint)] px-2 py-1 text-[12px] font-semibold text-[var(--warn)]">
              paused
            </span>
          ) : null}
        </div>

        <div className="mt-6">
          <div className="relative h-3 overflow-hidden rounded-full bg-white/[.06]">
            <div
              className={cn(
                "h-full rounded-full",
                snapshot.verdict === "IN THE GREEN" && "bg-[var(--good)]",
                snapshot.verdict === "GETTING TIGHT" && "bg-[var(--warn)]",
                snapshot.verdict === "LOSING MONEY" && "bg-[var(--bad)]",
              )}
              style={{ width: `${Math.min(percent, 100)}%` }}
            />
            <div
              className="absolute top-[-2px] h-7 w-[2px] bg-white shadow-[0_0_8px_rgba(255,255,255,.75)]"
              style={{ left: `${Math.min(Math.max(snapshot.elapsed_work_ratio * 100, 2), 98)}%` }}
            />
          </div>
          <div className="mt-2 flex justify-between text-[12px] text-[var(--text-dim)]">
            <span>NOW</span>
            <span className="font-semibold text-[var(--text-mut)]">{percent}%</span>
          </div>
        </div>

        <p className="mt-4 text-[14px] leading-6 text-[var(--text-mut)]">
          {jobPaceSentence(job, snapshot, now)}
        </p>
      </div>

      <div className="flex flex-col justify-between border-t border-[var(--border-soft)] px-5 py-5 md:border-l md:border-t-0">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--text-dim)]">
            {keep ? "YOU KEEP" : "YOU LOSE"}
          </div>
          <div
            className={cn(
              "mt-2 text-[36px] font-bold leading-none tracking-[-0.01em]",
              keep ? "text-[var(--good)]" : "text-[var(--bad)]",
            )}
          >
            {formatMoney(snapshot.projected_margin)}
          </div>
          <div className="mt-2 text-[12px] leading-5 text-[var(--text-dim)]">
            of the ${job.quote_usd.toLocaleString("en-US")} quote · planned $
            {job.labor_budget_usd.toLocaleString("en-US")}
          </div>
        </div>

        <details className="relative mt-4 self-end">
          <summary className="flex h-9 w-9 cursor-pointer list-none items-center justify-center rounded-lg text-[var(--text-dim)] hover:bg-white/[.04] hover:text-[var(--text)]">
            <MoreHorizontal className="h-4 w-4" strokeWidth={1.75} />
          </summary>
          <div className="absolute bottom-10 right-0 z-20 w-48 overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--panel)] p-1 shadow-[0_18px_42px_rgba(0,0,0,.55)]">
            <button type="button" className="block w-full rounded-md px-3 py-2 text-left text-[13px] text-[var(--text-mut)] hover:bg-white/[.04]">
              Edit
            </button>
            {job.status === "paused" ? (
              <button type="button" className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-[13px] text-[var(--text)] hover:bg-white/[.04]" onClick={() => onResume(job.id)}>
                <RotateCcw className="h-4 w-4" strokeWidth={1.75} />
                Resume
              </button>
            ) : (
              <button type="button" className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-[13px] text-[var(--text)] hover:bg-white/[.04]" onClick={() => onPause(job.id)}>
                <Pause className="h-4 w-4" strokeWidth={1.75} />
                Pause
              </button>
            )}
            <button type="button" className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-[13px] text-[var(--text)] hover:bg-white/[.04]" onClick={() => onFinish(job.id)}>
              <CheckCircle2 className="h-4 w-4" strokeWidth={1.75} />
              Mark finished
            </button>
            <Link href={`/replay?station=${replayStation}`} className="block rounded-md px-3 py-2 text-[13px] text-[var(--text)] hover:bg-white/[.04]">
              View on Replay
            </Link>
          </div>
        </details>
      </div>
    </Panel>
  );
}

function NewJobSheet({ onCreate }: { onCreate: (input: NewJobInput) => Promise<void> }) {
  const [open, setOpen] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [selectedStations, setSelectedStations] = useState<string[]>([stations[0]?.id ?? ""]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const input: NewJobInput = {
      client: String(form.get("client") ?? ""),
      title: String(form.get("title") ?? ""),
      units_required: Number(form.get("units_required")),
      quote_usd: Number(form.get("quote_usd")),
      cogs_usd: Number(form.get("cogs_usd")),
      labor_budget_usd: Number(form.get("labor_budget_usd")),
      deadline: String(form.get("deadline") ?? ""),
      station_ids: selectedStations.filter(Boolean),
    };
    const validation = validateNewJobInput(input);
    if (!validation.ok) {
      setErrors(validation.errors as Record<string, string>);
      return;
    }
    setSubmitting(true);
    try {
      await onCreate(input);
      setOpen(false);
      setErrors({});
    } catch (caught) {
      const next = caught as { errors?: Record<string, string> };
      setErrors(next.errors ?? { client: "Could not create job." });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button type="button" variant="primary" className="h-10">
          <Plus className="h-4 w-4" strokeWidth={1.75} />
          New Job
        </Button>
      </SheetTrigger>
      <SheetContent aria-describedby={undefined}>
        <SheetHeader>
          <div className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--text-dim)]">
            Add work
          </div>
          <SheetTitle>New Job</SheetTitle>
        </SheetHeader>
        <form onSubmit={submit} className="flex-1 space-y-4 overflow-y-auto px-6 pb-6">
          {[
            ["client", "Client", "Northline Metal"],
            ["title", "Title", "300 brackets"],
            ["units_required", "Units required", "300"],
            ["quote_usd", "Quote $", "2400"],
            ["cogs_usd", "COGS $", "900"],
            ["labor_budget_usd", "Labor budget $", "600"],
          ].map(([name, label, placeholder]) => (
            <label key={name} className="block">
              <span className="text-[12px] font-semibold text-[var(--text-mut)]">{label}</span>
              <input
                name={name}
                type={name.includes("usd") || name === "units_required" ? "number" : "text"}
                placeholder={placeholder}
                className="mt-2 h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--panel-2)] px-3 text-[14px] text-[var(--text)]"
              />
              {errors[name] ? <span className="mt-1 block text-[12px] text-[var(--bad)]">{errors[name]}</span> : null}
              {name === "labor_budget_usd" ? (
                <span className="mt-1 block text-[12px] text-[var(--text-dim)]">
                  Example: 3 days x $200 crew budget = $600.
                </span>
              ) : null}
            </label>
          ))}

          <label className="block">
            <span className="text-[12px] font-semibold text-[var(--text-mut)]">Deadline</span>
            <input
              name="deadline"
              type="date"
              className="mt-2 h-10 w-full rounded-lg border border-[var(--border)] bg-[var(--panel-2)] px-3 text-[14px] text-[var(--text)]"
            />
            {errors.deadline ? <span className="mt-1 block text-[12px] text-[var(--bad)]">{errors.deadline}</span> : null}
          </label>

          <div>
            <div className="text-[12px] font-semibold text-[var(--text-mut)]">Stations</div>
            <div className="mt-2 flex flex-wrap gap-2">
              {stations.map((station) => {
                const selected = selectedStations.includes(station.id);
                return (
                  <button
                    key={station.id}
                    type="button"
                    className={cn(
                      "rounded-full border px-3 py-2 text-[13px] font-semibold",
                      selected
                        ? "border-[var(--accent)] bg-[var(--accent-tint)] text-[var(--accent)]"
                        : "border-[var(--border)] text-[var(--text-mut)] hover:bg-white/[.04]",
                    )}
                    onClick={() =>
                      setSelectedStations((current) =>
                        selected ? current.filter((id) => id !== station.id) : [...current, station.id],
                      )
                    }
                  >
                    {station.name}
                  </button>
                );
              })}
            </div>
            {errors.station_ids ? <span className="mt-1 block text-[12px] text-[var(--bad)]">{errors.station_ids}</span> : null}
          </div>

          <Button type="submit" variant="primary" className="h-10 w-full" disabled={submitting}>
            <CircleDollarSign className="h-4 w-4" strokeWidth={1.75} />
            {submitting ? "Saving" : "Save job"}
          </Button>
        </form>
      </SheetContent>
    </Sheet>
  );
}

export function JobsDashboard() {
  const { now } = useTime();
  const current = now();
  const { jobs, error, createJob, pauseJob, resumeJob, finishJob } = useConsoleJobs();
  const visibleJobs = jobs.filter((job) => job.status !== "finished");
  const runningSnapshots = selectRunningJobSnapshots(current, jobs);
  const visibleSnapshots = visibleJobs.map((job) => {
    const active = runningSnapshots.find((candidate) => candidate.job.id === job.id);
    if (active) return active;
    return selectRunningJobSnapshots(current, [{ ...job, status: "active" }])[0];
  });
  const [toast, setToast] = useState<string | null>(null);

  async function finish(jobId: string) {
    if (!window.confirm("Mark this job finished? It will move to History in CP5.")) return;
    await finishJob(jobId);
    setToast("Finished. History link stub ready for CP5.");
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--text-dim)]">
            JOBS
          </div>
          <h1 className="mt-2 text-[28px] font-semibold tracking-[-0.01em] text-[var(--text)]">
            Active work
          </h1>
        </div>
        <NewJobSheet onCreate={async (input) => {
          await createJob(input);
        }} />
      </div>

      {error ? <div className="text-[13px] text-[var(--warn)]">{error}</div> : null}
      {toast ? (
        <div className="rounded-lg border border-[var(--border)] bg-[var(--panel-2)] px-3 py-2 text-[13px] text-[var(--text-mut)]">
          {toast} <Link href="/history" className="text-[var(--accent)]">Open History</Link>
        </div>
      ) : null}

      <MoneyStrip jobSnapshots={runningSnapshots} />

      <section className="space-y-4">
        {visibleSnapshots.map((item) => (
          <JobCard
            key={item.job.id}
            item={item}
            now={current}
            onPause={(jobId) => void pauseJob(jobId)}
            onResume={(jobId) => void resumeJob(jobId)}
            onFinish={(jobId) => void finish(jobId)}
          />
        ))}
      </section>
    </div>
  );
}
