"use client";

import { useEffect, useState } from "react";
import { Hand, History, MousePointerClick, MonitorPlay, ScanSearch } from "lucide-react";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";

export function HelpSheet() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const onOpen = () => setOpen(true);
    window.addEventListener("factoryvision:open-help", onOpen);
    return () => window.removeEventListener("factoryvision:open-help", onOpen);
  }, []);

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetContent aria-describedby={undefined}>
        <SheetHeader>
          <div className="pr-12 text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--text-dim)]">
            How FactoryVision works
          </div>
          <SheetTitle>Three doors to your footage</SheetTitle>
          <SheetDescription>
            Every piece that leaves the floor is counted, and every count keeps its clip. Here is
            how to get to any of them.
          </SheetDescription>
        </SheetHeader>

        <div className="flex-1 space-y-4 overflow-y-auto px-6 py-4 text-[13px] leading-6 text-[var(--text-mut)]">
          <HelpItem
            icon={MousePointerClick}
            title="1. Tap a number"
            body="On the Live wall or Stations, tap any count and you jump straight to the clip of that exact placement."
          />
          <HelpItem
            icon={ScanSearch}
            title="2. Scrub the day on Replay"
            body="Replay is your DVR. Drag the timeline, tap a diamond to watch that moment, or open the 15-minute chapter cards."
          />
          <HelpItem
            icon={Hand}
            title="3. Browse another day"
            body="Use the day picker on Replay to open any recorded day. Days with footage are dotted; empty days are dimmed."
          />

          <div className="rounded-lg border border-[var(--border-soft)] bg-black/15 p-4">
            <div className="mb-2 flex items-center gap-2 font-semibold text-[var(--text)]">
              <History className="h-4 w-4 text-[var(--accent)]" strokeWidth={1.75} />
              History vs Replay
            </div>
            <p>
              <span className="font-semibold text-[var(--text)]">History</span> is your money record —
              finished jobs with final counts and grades.{" "}
              <span className="font-semibold text-[var(--text)]">Replay</span> is the video. Every
              History row links across to its footage, so a number always has a clip behind it.
            </p>
          </div>

          <div className="flex items-center gap-2 text-[var(--text-dim)]">
            <MonitorPlay className="h-4 w-4" strokeWidth={1.75} />
            Tip: press <kbd className="rounded border border-[var(--border)] px-1.5 py-0.5 text-[11px]">⌘K</kbd> anywhere to search jobs, stations, or jump to a time.
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}

function HelpItem({
  icon: Icon,
  title,
  body,
}: {
  icon: typeof Hand;
  title: string;
  body: string;
}) {
  return (
    <div className="flex gap-3">
      <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-[var(--border)] bg-[var(--panel-2)] text-[var(--accent)]">
        <Icon className="h-4 w-4" strokeWidth={1.75} />
      </div>
      <div>
        <div className="font-semibold text-[var(--text)]">{title}</div>
        <p>{body}</p>
      </div>
    </div>
  );
}
