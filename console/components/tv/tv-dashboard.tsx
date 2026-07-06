"use client";

import { useEffect, useMemo, useState } from "react";
import { ClipDrawerProvider } from "@/components/live/clip-drawer-provider";
import { CameraCard, MoneyStrip } from "@/components/live/live-dashboard";
import { TimeProvider, useTime } from "@/components/providers/time-provider";
import { useConsoleJobs } from "@/components/jobs/use-console-jobs";
import { jobForStation, jobs as seedJobs, laborConfig, stations } from "@/lib/demoData";
import { evaluateJobPace } from "@/lib/paceMath";
import { selectRunningJobSnapshots } from "@/lib/jobSelectors";
import { cn } from "@/lib/utils";

function TvSurface() {
  const { now } = useTime();
  const { jobs } = useConsoleJobs();
  const [view, setView] = useState<"wall" | "money">(() => {
    if (typeof window === "undefined") return "wall";
    const param = new URLSearchParams(window.location.search).get("view");
    return param === "money" ? "money" : "wall";
  });
  const [reconnectKey, setReconnectKey] = useState(0);
  const current = now();
  const snapshots = selectRunningJobSnapshots(current, jobs);

  const pinnedView = useMemo(() => {
    if (typeof window === "undefined") return null;
    const param = new URLSearchParams(window.location.search).get("view");
    return param === "wall" || param === "money" ? param : null;
  }, []);

  useEffect(() => {
    if (pinnedView) return;
    const interval = window.setInterval(() => {
      setView((currentView) => (currentView === "wall" ? "money" : "wall"));
    }, 20_000);
    return () => window.clearInterval(interval);
  }, [pinnedView]);

  useEffect(() => {
    const interval = window.setInterval(() => setReconnectKey((value) => value + 1), 30_000);
    return () => window.clearInterval(interval);
  }, []);

  return (
    <main className="min-h-screen bg-[var(--bg)] p-8 text-[var(--text)]" data-tv-route="ready" data-tv-view={view}>
      <div className="mb-6 flex items-center justify-between">
        <div className="text-[42px] font-bold tracking-[-0.01em]">
          <span className="text-[var(--text)]">Factory</span><span className="text-[var(--accent)]">Vision</span>
        </div>
        <div className="rounded-full border border-[var(--border)] bg-[var(--panel-2)] px-5 py-3 text-[24px] font-bold text-[var(--good)]">
          LIVE
        </div>
      </div>

      <section className={cn(view === "wall" ? "block" : "hidden")}>
        <div className="grid min-h-[calc(100vh-142px)] gap-5 xl:grid-cols-2">
          {stations.map((station) => {
            const job = jobForStation(station.id);
            const snapshot =
              snapshots.find((candidate) => candidate.job.id === job?.id)?.snapshot ??
              evaluateJobPace(seedJobs[0], 0, current, laborConfig);
            return (
              <CameraCard
                key={`${station.id}-${reconnectKey}`}
                station={station}
                now={current}
                snapshot={snapshot}
                scale="tv"
              />
            );
          })}
        </div>
      </section>

      <section className={cn(view === "money" ? "block" : "hidden")}>
        <div className="flex min-h-[calc(100vh-142px)] items-center">
          <MoneyStrip snapshots={snapshots} now={current} scale="tv" />
        </div>
      </section>
    </main>
  );
}

export function TvDashboard() {
  return (
    <TimeProvider>
      <ClipDrawerProvider>
        <TvSurface />
      </ClipDrawerProvider>
    </TimeProvider>
  );
}
