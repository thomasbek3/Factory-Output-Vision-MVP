"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { AreaChart } from "@tremor/react";
import { ArrowLeft, Download, Factory, RadioTower, ShieldCheck, TimerReset } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/ui/panel";

type OpsSnapshot = {
  factories: number;
  camerasUp: number;
  camerasTotal: number;
  eventsToday: number;
  verificationLagMinutes: number;
  openQueueDepth: number;
  chunksTotal: number;
  reviewers: Array<{
    reviewerId: string;
    name: string;
    chunksToday: number;
    clicksToday: number;
    chunksPerHour: number;
    goldenAccuracyPct: number | null;
  }>;
};

const agreementSeries = [
  { week: "Jun 1", agreement: 58 },
  { week: "Jun 8", agreement: 64 },
  { week: "Jun 15", agreement: 71 },
  { week: "Jun 22", agreement: 74 },
];

function StatCard({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: string;
  icon: typeof Factory;
}) {
  return (
    <Panel className="min-h-[120px]">
      <div className="flex items-center justify-between">
        <div className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--text-dim)]">
          {label}
        </div>
        <Icon className="h-4 w-4 text-[var(--accent)]" strokeWidth={1.75} />
      </div>
      <div className="mt-4 text-[32px] font-bold leading-none tracking-[-0.01em] text-[var(--text)]">
        {value}
      </div>
    </Panel>
  );
}

export function OpsConsole() {
  const [snapshot, setSnapshot] = useState<OpsSnapshot | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const response = await fetch("/api/ops/snapshot", { cache: "no-store" });
        if (!response.ok) throw new Error(`snapshot ${response.status}`);
        const data = (await response.json()) as OpsSnapshot;
        if (!cancelled) setSnapshot(data);
      } catch (error) {
        console.error("GET /api/ops/snapshot failed:", error);
        if (!cancelled) setToast("Could not load ops snapshot.");
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  // Auto-clear the export/error toast so stale feedback doesn't linger forever.
  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 5000);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const cards = useMemo(() => {
    if (!snapshot) return [];
    return [
      { label: "Factories", value: String(snapshot.factories), icon: Factory },
      { label: "Cameras up", value: `${snapshot.camerasUp}/${snapshot.camerasTotal}`, icon: RadioTower },
      { label: "Events today", value: String(snapshot.eventsToday), icon: ShieldCheck },
      { label: "Verification lag", value: `${snapshot.verificationLagMinutes}m`, icon: TimerReset },
      { label: "Open queue", value: String(snapshot.openQueueDepth), icon: Download },
    ];
  }, [snapshot]);

  async function exportLabels() {
    const response = await fetch("/api/ops/labels/export", { method: "POST" });
    const payload = (await response.json()) as { path?: string; eventCount?: number };
    setToast(payload.path ? `Wrote ${payload.eventCount ?? 0} labels to ${payload.path}` : "Export failed.");
  }

  return (
    <main className="min-h-screen bg-[var(--bg)] p-6 text-[var(--text)]" data-ops-route="ready">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <Link
            href="/"
            className="mb-2 inline-flex items-center gap-1 text-[12px] font-semibold text-[var(--text-dim)] hover:text-[var(--text)]"
          >
            <ArrowLeft className="h-3.5 w-3.5" strokeWidth={1.75} />
            Console
          </Link>
          <div className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--text-dim)]">
            OPS
          </div>
          <h1 className="mt-2 text-[28px] font-semibold tracking-[-0.01em]">FactoryVision internal</h1>
        </div>
        <div className="rounded-full border border-[var(--border)] bg-[var(--panel-2)] px-3 py-2 text-[12px] font-semibold text-[var(--text-mut)]">
          Read-only v1
        </div>
      </div>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        {cards.map((card) => (
          <StatCard key={card.label} {...card} />
        ))}
      </section>

      <section className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1.25fr)_minmax(360px,.75fr)]">
        <Panel>
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--text-dim)]">
                The Investor Chart
              </div>
              <h2 className="mt-2 text-[20px] font-semibold">Weekly model agreement</h2>
            </div>
            <span className="rounded-full bg-[var(--accent-tint)] px-3 py-1.5 text-[12px] font-semibold text-[var(--accent)]">
              demo seed
            </span>
          </div>
          <AreaChart
            data={agreementSeries}
            index="week"
            categories={["agreement"]}
            colors={["orange"]}
            valueFormatter={(value) => `${value}%`}
            showAnimation={false}
            className="mt-6 h-[280px]"
          />
        </Panel>

        <Panel>
          <div className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--text-dim)]">
            Model ops
          </div>
          <div className="mt-4 rounded-xl border border-[var(--border)] bg-white/[.02] p-4">
            <div className="text-[14px] font-semibold">Last held-out exam</div>
            <div className="mt-2 text-[32px] font-bold text-[var(--bad)]">3/7</div>
            <div className="mt-1 text-[13px] text-[var(--text-mut)]">
              0 false positives · dated 2026-06-18
            </div>
          </div>
          <Button type="button" variant="primary" className="mt-4 h-11 w-full justify-center" onClick={exportLabels}>
            <Download className="h-4 w-4" strokeWidth={1.75} />
            Export labels
          </Button>
          {toast && <div className="mt-3 rounded-lg bg-[var(--good-tint)] px-3 py-2 text-[12px] text-[var(--good)]">{toast}</div>}
        </Panel>
      </section>

      <Panel className="mt-4">
        <div className="mb-4 text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--text-dim)]">
          Reviewers
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] border-collapse text-left text-[13px]">
            <thead className="text-[11px] uppercase tracking-[0.06em] text-[var(--text-dim)]">
              <tr className="border-b border-[var(--border)]">
                <th className="py-3 font-semibold">Reviewer</th>
                <th className="py-3 font-semibold">Chunks today</th>
                <th className="py-3 font-semibold">Clicks</th>
                <th className="py-3 font-semibold">Chunks/hr</th>
                <th className="py-3 font-semibold">Golden accuracy</th>
              </tr>
            </thead>
            <tbody>
              {(snapshot?.reviewers ?? []).map((reviewer) => (
                <tr key={reviewer.reviewerId} className="border-b border-[var(--border-soft)]">
                  <td className="py-3 font-semibold text-[var(--text)]">{reviewer.name}</td>
                  <td className="py-3 text-[var(--text-mut)]">{reviewer.chunksToday}</td>
                  <td className="py-3 text-[var(--text-mut)]">{reviewer.clicksToday}</td>
                  <td className="py-3 text-[var(--text-mut)]">{reviewer.chunksPerHour}</td>
                  <td className="py-3 text-[var(--text-mut)]">
                    {reviewer.goldenAccuracyPct === null ? "n/a" : `${reviewer.goldenAccuracyPct}%`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </main>
  );
}
