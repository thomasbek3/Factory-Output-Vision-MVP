"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Download, Factory, RadioTower, ShieldCheck, TimerReset } from "lucide-react";
import { Panel } from "@/components/ui/panel";
import { demoSourceDay } from "@/lib/demoEvents";

type OpsSnapshot = {
  factories: number;
  camerasUp: number;
  camerasTotal: number;
  eventsToday: number;
  verificationLagMinutes: number;
  openQueueDepth: number;
  chunksTotal: number;
};

function StatCard({
  label,
  value,
  subtitle,
  icon: Icon,
}: {
  label: string;
  value: string;
  subtitle?: string;
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
      {subtitle ? (
        <div className="mt-2 text-[12px] leading-4 text-[var(--text-dim)]">{subtitle}</div>
      ) : null}
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

  // Auto-clear transient load feedback so stale errors do not linger.
  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 5000);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const cards = useMemo(() => {
    if (!snapshot) return [];
    const demoDayLabel = new Intl.DateTimeFormat("en-US", {
      timeZone: "America/Los_Angeles",
      month: "short",
      day: "numeric",
    }).format(new Date(`${demoSourceDay}T12:00:00-07:00`));
    return [
      { label: "Factories", value: String(snapshot.factories), subtitle: "sites streaming to this console", icon: Factory },
      { label: "Cameras up", value: `${snapshot.camerasUp}/${snapshot.camerasTotal}`, subtitle: "feeds online through the tunnel", icon: RadioTower },
      { label: "Events today", value: String(snapshot.eventsToday), subtitle: `seeded review events on ${demoDayLabel}`, icon: ShieldCheck },
      { label: "Review lag", value: `${snapshot.verificationLagMinutes}m`, subtitle: "demo review delay behind source time", icon: TimerReset },
      { label: "Open queue", value: String(snapshot.openQueueDepth), subtitle: "chunks still waiting for a reviewer", icon: Download },
    ];
  }, [snapshot]);

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

      <Panel className="mt-4">
        <div className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--text-dim)]">
          Review operations
        </div>
        <h2 className="mt-2 text-[20px] font-semibold">Queue health only</h2>
        <p className="mt-2 max-w-2xl text-[13px] leading-5 text-[var(--text-mut)]">
          Reviewer quality appears here only after durable identity, audited
          sample floors, and role isolation are active.
        </p>
        {toast && (
          <div className="mt-3 rounded-lg bg-[var(--bad-tint)] px-3 py-2 text-[12px] text-[var(--bad)]">
            {toast}
          </div>
        )}
      </Panel>
    </main>
  );
}
