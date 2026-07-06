"use client";

import Link from "next/link";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { ArrowLeft, ArrowRight, BadgeCheck, Flag, SkipBack, SkipForward } from "lucide-react";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import {
  eventsForStation,
  findEventByClipId,
  jobForEvent,
  mediaUrlForStation,
  stationForEvent,
} from "@/lib/demoData";
import { loadDemoCountEvents, type CountEventShape } from "@/lib/demoEvents";
import { cn } from "@/lib/utils";

type ClipDrawerContextValue = {
  openClip: (clipId: string) => void;
  disputedClipIds: Set<string>;
};

const ClipDrawerContext = createContext<ClipDrawerContextValue | null>(null);

function formatTime(date: Date) {
  return new Intl.DateTimeFormat("en-US", {
    timeZone: "America/Los_Angeles",
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
  }).format(date);
}

function eventIndex(event: CountEventShape) {
  const stationEvents = eventsForStation(event.station_id);
  const index = stationEvents.findIndex((candidate) => candidate.clip_id === event.clip_id);
  return { stationEvents, index };
}

export function ClipDrawerProvider({ children }: { children: ReactNode }) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [activeClipId, setActiveClipId] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    return new URLSearchParams(window.location.search).get("clip");
  });
  const [disputedClipIds, setDisputedClipIds] = useState<Set<string>>(new Set());
  const [toast, setToast] = useState<string | null>(null);

  const activeEvent = useMemo(
    () => (activeClipId ? findEventByClipId(activeClipId) : undefined),
    [activeClipId],
  );

  const seekSecond = activeEvent ? Math.max(0, (activeEvent.demo_offset_sec % 60) - 5) : 0;

  const setClipParam = useCallback((clipId: string | null) => {
    if (typeof window === "undefined") return;
    const url = new URL(window.location.href);
    if (clipId) {
      url.searchParams.set("clip", clipId);
    } else {
      url.searchParams.delete("clip");
    }
    window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
  }, []);

  const openClip = useCallback(
    (clipId: string) => {
      setActiveClipId(clipId);
      setClipParam(clipId);
    },
    [setClipParam],
  );

  const closeClip = useCallback(() => {
    setActiveClipId(null);
    setClipParam(null);
  }, [setClipParam]);

  const move = useCallback(
    (direction: -1 | 1) => {
      if (!activeEvent) return;
      const { stationEvents, index } = eventIndex(activeEvent);
      const next = stationEvents[index + direction];
      if (next) openClip(next.clip_id);
    },
    [activeEvent, openClip],
  );

  useEffect(() => {
    const video = videoRef.current;
    if (!video || !activeEvent) return;

    const onLoaded = () => {
      video.currentTime = seekSecond;
      void video.play().catch(() => undefined);
    };
    const onTimeUpdate = () => {
      if (video.currentTime > seekSecond + 10) {
        video.currentTime = seekSecond;
      }
    };

    video.addEventListener("loadedmetadata", onLoaded);
    video.addEventListener("timeupdate", onTimeUpdate);
    return () => {
      video.removeEventListener("loadedmetadata", onLoaded);
      video.removeEventListener("timeupdate", onTimeUpdate);
    };
  }, [activeEvent, seekSecond]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (!activeEvent) return;
      if (event.key === "ArrowLeft") {
        event.preventDefault();
        move(-1);
      }
      if (event.key === "ArrowRight") {
        event.preventDefault();
        move(1);
      }
      if (event.key === " ") {
        event.preventDefault();
        const video = videoRef.current;
        if (!video) return;
        if (video.paused) void video.play();
        else video.pause();
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [activeEvent, move]);

  useEffect(() => {
    if (!toast) return;
    const timeout = window.setTimeout(() => setToast(null), 2200);
    return () => window.clearTimeout(timeout);
  }, [toast]);

  const contextValue = useMemo(
    () => ({ openClip, disputedClipIds }),
    [disputedClipIds, openClip],
  );

  const station = activeEvent ? stationForEvent(activeEvent) : undefined;
  const job = activeEvent ? jobForEvent(activeEvent) : undefined;
  const timestamp = activeEvent ? new Date(activeEvent.ts) : undefined;
  const { stationEvents, index } = activeEvent
    ? eventIndex(activeEvent)
    : { stationEvents: loadDemoCountEvents(), index: -1 };
  const hasPrev = index > 0;
  const hasNext = index >= 0 && index < stationEvents.length - 1;

  return (
    <ClipDrawerContext.Provider value={contextValue}>
      {children}
      <Sheet open={Boolean(activeEvent)} onOpenChange={(open) => (!open ? closeClip() : undefined)}>
        <SheetContent aria-describedby={undefined}>
          {activeEvent && timestamp ? (
            <div className="flex min-h-0 flex-1 flex-col">
              <SheetHeader>
                <div className="pr-12 text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--text-dim)]">
                  Evidence clip
                </div>
                <SheetTitle>{station?.name ?? activeEvent.station_id}</SheetTitle>
                <p className="text-[13px] leading-5 text-[var(--text-mut)]">
                  Count evidence loops around {formatTime(timestamp)}. This v0 uses the matching
                  demo MP4 bucket and seeks to the event offset ±5s.
                </p>
              </SheetHeader>

              <div className="px-6">
                <video
                  key={activeEvent.clip_id}
                  ref={videoRef}
                  src={mediaUrlForStation(activeEvent.station_id, timestamp)}
                  className="aspect-video w-full rounded-lg bg-black object-cover ring-1 ring-[var(--border)]"
                  controls
                  muted
                  loop
                  playsInline
                />
              </div>

              <div className="flex-1 space-y-4 overflow-y-auto px-6 py-5">
                <div className="grid grid-cols-[112px_1fr] gap-x-4 gap-y-3 text-[13px]">
                  <span className="text-[var(--text-dim)]">Station</span>
                  <span className="font-semibold text-[var(--text)]">{station?.name}</span>
                  <span className="text-[var(--text-dim)]">Wall clock</span>
                  <span className="text-[var(--text)]">{formatTime(timestamp)}</span>
                  <span className="text-[var(--text-dim)]">Job</span>
                  <span>
                    <span className="rounded-full border border-[var(--border)] bg-[var(--panel-2)] px-2 py-1 text-[12px] font-semibold text-[var(--text)]">
                      {job?.client ?? "Unassigned"}
                    </span>
                  </span>
                  <span className="text-[var(--text-dim)]">Verifier</span>
                  <span className="flex items-center gap-2 text-[var(--text)]">
                    <BadgeCheck className="h-4 w-4 text-[var(--good)]" strokeWidth={1.75} />
                    Verified by M. Reyes
                  </span>
                  <span className="text-[var(--text-dim)]">Model</span>
                  <span>
                    <span className="rounded-full bg-[var(--good-tint)] px-2 py-1 text-[12px] font-semibold text-[var(--good)]">
                      model agreed · {activeEvent.model_verdict.confidence.toFixed(2)}
                    </span>
                  </span>
                </div>

                <div className="flex gap-2">
                  <Button
                    type="button"
                    variant="secondary"
                    className="flex-1"
                    disabled={!hasPrev}
                    onClick={() => move(-1)}
                  >
                    <SkipBack className="h-4 w-4" strokeWidth={1.75} />
                    Prev
                  </Button>
                  <Button
                    type="button"
                    variant="secondary"
                    className="flex-1"
                    disabled={!hasNext}
                    onClick={() => move(1)}
                  >
                    Next
                    <SkipForward className="h-4 w-4" strokeWidth={1.75} />
                  </Button>
                </div>

                <Link
                  href={`/replay?station=${activeEvent.station_id}&t=${encodeURIComponent(activeEvent.ts)}`}
                  className="inline-flex h-9 w-full items-center justify-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--panel-2)] px-3 text-[13px] font-semibold text-[var(--text)] hover:bg-white/[.04]"
                >
                  <ArrowRight className="h-4 w-4" strokeWidth={1.75} />
                  Open in Replay
                </Link>

                <Button
                  type="button"
                  variant="secondary"
                  className={cn(
                    "w-full",
                    disputedClipIds.has(activeEvent.clip_id) &&
                      "border-[var(--warn)] bg-[var(--warn-tint)] text-[var(--warn)]",
                  )}
                  onClick={() => {
                    setDisputedClipIds((current) => {
                      const next = new Set(current);
                      next.add(activeEvent.clip_id);
                      return next;
                    });
                    setToast("Count disputed in this browser session.");
                  }}
                >
                  <Flag className="h-4 w-4" strokeWidth={1.75} />
                  Dispute this count
                </Button>

                <div className="flex items-center justify-between rounded-lg border border-[var(--border-soft)] bg-black/15 px-3 py-2 text-[12px] text-[var(--text-dim)]">
                  <span>Keyboard</span>
                  <span className="flex items-center gap-2">
                    Esc close
                    <ArrowLeft className="h-3.5 w-3.5" strokeWidth={1.75} />
                    <ArrowRight className="h-3.5 w-3.5" strokeWidth={1.75} />
                    Space play
                  </span>
                </div>
              </div>
            </div>
          ) : null}
        </SheetContent>
      </Sheet>
      {toast ? (
        <div className="fixed bottom-5 right-5 z-[60] rounded-lg border border-[var(--border)] bg-[var(--panel)] px-4 py-3 text-[13px] font-semibold text-[var(--text)] shadow-panel">
          {toast}
        </div>
      ) : null}
    </ClipDrawerContext.Provider>
  );
}

export function useClipDrawer() {
  const value = useContext(ClipDrawerContext);
  if (!value) {
    throw new Error("useClipDrawer must be used inside ClipDrawerProvider");
  }
  return value;
}
