"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Image from "next/image";
import {
  BadgeCheck,
  ChevronLeft,
  ChevronRight,
  Clock3,
  MoreHorizontal,
  Play,
} from "lucide-react";
import { useClipDrawer } from "@/components/live/clip-drawer-provider";
import { useTime } from "@/components/providers/time-provider";
import { Panel } from "@/components/ui/panel";
import {
  demoDay,
  mediaPosterUrlForStation,
  mediaUrlForStation,
  stations,
} from "@/lib/demoData";
import { loadDemoCountEvents, type CountEventShape } from "@/lib/demoEvents";
import { cn } from "@/lib/utils";

type ReplayStation = "all" | string;
type Speed = 1 | 4 | 15 | 60;
type TimelineMarker =
  | {
      id: string;
      kind: "single";
      event: CountEventShape;
      count: 1;
      minutes: number;
    }
  | {
      id: string;
      kind: "cluster";
      event: CountEventShape;
      count: number;
      minutes: number;
    };

type ReplayDashboardProps = {
  initialStation: string;
  initialTime: string | null;
};

const workStart = 7 * 60;
const workEnd = 17 * 60 + 30;
const workMinutes = workEnd - workStart;
const chapterMinutes = 15;
const demoGap = { start: 13 * 60 + 5, end: 13 * 60 + 12 };

function parseClockToMinutes(value: string) {
  const match = value.match(/^(\d{1,2}):(\d{2})(?::\d{2})?$/);
  if (!match) return null;
  const hours = Number(match[1]);
  const minutes = Number(match[2]);
  if (hours > 23 || minutes > 59) return null;
  return hours * 60 + minutes;
}

function dateForMinutes(minutes: number) {
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  return new Date(`${demoDay}T${String(hours).padStart(2, "0")}:${String(mins).padStart(2, "0")}:00-07:00`);
}

function minutesForDate(date: Date) {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/Los_Angeles",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(date);
  const value = (type: string) => parts.find((part) => part.type === type)?.value ?? "0";
  return Number(value("hour")) * 60 + Number(value("minute"));
}

function clampMinutes(minutes: number) {
  return Math.min(workEnd, Math.max(workStart, minutes));
}

function formatClock(date: Date, withSeconds = false) {
  return new Intl.DateTimeFormat("en-US", {
    timeZone: "America/Los_Angeles",
    hour: "2-digit",
    minute: "2-digit",
    second: withSeconds ? "2-digit" : undefined,
    hourCycle: "h23",
  }).format(date);
}

function formatDateLabel() {
  return "Thu Jun 26";
}

function positionPct(minutes: number) {
  return ((clampMinutes(minutes) - workStart) / workMinutes) * 100;
}

function widthPct(start: number, end: number) {
  return ((Math.min(end, workEnd) - Math.max(start, workStart)) / workMinutes) * 100;
}

function uniquePlacementMoments(events: CountEventShape[]) {
  const seen = new Set<string>();
  return events.filter((event) => {
    if (seen.has(event.clip_id)) return false;
    seen.add(event.clip_id);
    return true;
  });
}

function stationLabel(stationId: string) {
  return stations.find((station) => station.id === stationId)?.name ?? stationId;
}

function normalizeInitialStation(value: string): ReplayStation {
  if (value === "all") return "all";
  return stations.some((station) => station.id === value) ? value : stations[0]?.id ?? "all";
}

function timeParamToClock(value: string | null) {
  if (!value) return null;
  if (/^\d{1,2}:\d{2}/.test(value)) return value.slice(0, 5);
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return formatClock(date);
}

export function ReplayDashboard({ initialStation, initialTime }: ReplayDashboardProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const skipTimerRef = useRef<number | null>(null);
  const { now } = useTime();
  const { openClip } = useClipDrawer();
  const [selectedStation, setSelectedStation] = useState<ReplayStation>(() =>
    normalizeInitialStation(initialStation),
  );
  const [selectedTime, setSelectedTime] = useState(() => {
    const fromParam = timeParamToClock(initialTime);
    return fromParam ?? "14:32";
  });
  const [jumpValue, setJumpValue] = useState(selectedTime);
  const [speed, setSpeed] = useState<Speed>(15);
  const [paused, setPaused] = useState(true);

  const selectedDate = useMemo(
    () => dateForMinutes(parseClockToMinutes(selectedTime) ?? 14 * 60 + 32),
    [selectedTime],
  );

  const allEvents = useMemo(() => loadDemoCountEvents(), []);
  const filteredEvents = useMemo(
    () =>
      selectedStation === "all"
        ? allEvents
        : allEvents.filter((event) => event.station_id === selectedStation),
    [allEvents, selectedStation],
  );
  const placements = useMemo(() => uniquePlacementMoments(filteredEvents), [filteredEvents]);
  const selectedMinutes = parseClockToMinutes(selectedTime) ?? workStart;
  const nearestPlacement = useMemo(() => {
    if (!placements.length) return null;
    return placements.reduce<CountEventShape | null>((best, event) => {
      if (!best) return event;
      const eventDistance = Math.abs(minutesForDate(new Date(event.ts)) - selectedMinutes);
      const bestDistance = Math.abs(minutesForDate(new Date(best.ts)) - selectedMinutes);
      return eventDistance < bestDistance ? event : best;
    }, null);
  }, [placements, selectedMinutes]);
  const viewerStation =
    selectedStation === "all"
      ? nearestPlacement?.station_id ?? stations[0]?.id ?? "pallet-a"
      : selectedStation;
  const nearEvent =
    nearestPlacement &&
    Math.abs(minutesForDate(new Date(nearestPlacement.ts)) - selectedMinutes) <= 1
      ? nearestPlacement
      : null;
  const placementNumber = nearEvent
    ? placements.findIndex((event) => event.clip_id === nearEvent.clip_id) + 1
    : 0;

  const chapters = useMemo(
    () =>
      Array.from({ length: workMinutes / chapterMinutes }, (_, index) => {
        const start = workStart + index * chapterMinutes;
        const end = start + chapterMinutes;
        const events = filteredEvents.filter((event) => {
          const eventMinutes = minutesForDate(new Date(event.ts));
          return eventMinutes >= start && eventMinutes < end;
        });
        return { start, end, events };
      }),
    [filteredEvents],
  );

  const activeChapterIndex = Math.floor((clampMinutes(selectedMinutes) - workStart) / chapterMinutes);
  const nowMinutes = minutesForDate(now());

  const updateUrl = useCallback((station: ReplayStation, clock: string) => {
    const url = new URL(window.location.href);
    url.searchParams.set("station", station);
    url.searchParams.set("t", clock);
    window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
  }, []);

  const seekToClock = useCallback(
    (clock: string) => {
      const minutes = parseClockToMinutes(clock);
      if (minutes === null) return;
      const clamped = clampMinutes(minutes);
      const nextClock = formatClock(dateForMinutes(clamped));
      setSelectedTime(nextClock);
      setJumpValue(nextClock);
      updateUrl(selectedStation, nextClock);
      const video = videoRef.current;
      if (video) video.currentTime = Math.max(0, (clamped - workStart) % 60);
    },
    [selectedStation, updateUrl],
  );

  function setStation(next: ReplayStation) {
    setSelectedStation(next);
    updateUrl(next, selectedTime);
  }

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    video.playbackRate = speed === 60 ? 16 : speed;
  }, [speed, viewerStation, selectedTime]);

  useEffect(() => {
    if (skipTimerRef.current) {
      window.clearInterval(skipTimerRef.current);
      skipTimerRef.current = null;
    }
    if (speed !== 60 || paused) return;
    skipTimerRef.current = window.setInterval(() => {
      const video = videoRef.current;
      if (!video) return;
      video.currentTime = Math.min((video.duration || 60) - 0.25, video.currentTime + 1.75);
    }, 500);
    return () => {
      if (skipTimerRef.current) window.clearInterval(skipTimerRef.current);
      skipTimerRef.current = null;
    };
  }, [paused, speed]);

  return (
    <div className="space-y-5" data-selected-station={selectedStation}>
      <section className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-[28px] font-semibold tracking-[-0.01em] text-[var(--text)]">
            Replay
          </h1>
          <p className="mt-1 text-[14px] text-[var(--text-mut)]">
            Demo DVR for verified placement evidence.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {(["all", ...stations.map((station) => station.id)] as ReplayStation[]).map((stationId) => (
            <button
              key={stationId}
              type="button"
              className={cn(
                "h-9 rounded-lg border px-3 text-[13px] font-semibold transition-colors",
                selectedStation === stationId
                  ? "border-[var(--accent)] bg-[var(--accent)] text-[#11100d]"
                  : "border-[var(--border)] bg-[var(--panel-2)] text-[var(--text-mut)] hover:text-[var(--text)]",
              )}
              onClick={() => setStation(stationId)}
            >
              {stationId === "all" ? "All" : stationLabel(stationId)}
            </button>
          ))}
          <div className="flex h-9 items-center overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--panel-2)]">
            <button
              type="button"
              className="flex h-full w-9 items-center justify-center text-[var(--text-dim)] disabled:opacity-40"
              disabled
              title="Demo data only exists for Thu Jun 26."
            >
              <ChevronLeft className="h-4 w-4" strokeWidth={1.75} />
            </button>
            <div className="border-x border-[var(--border)] px-3 text-[13px] font-semibold text-[var(--text)]">
              {formatDateLabel()}
            </div>
            <button
              type="button"
              className="flex h-full w-9 items-center justify-center text-[var(--text-dim)] disabled:opacity-40"
              disabled
              title="Demo data only exists for Thu Jun 26."
            >
              <ChevronRight className="h-4 w-4" strokeWidth={1.75} />
            </button>
          </div>
          <form
            className="flex h-9 items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--panel-2)] px-2"
            onSubmit={(event) => {
              event.preventDefault();
              seekToClock(jumpValue);
            }}
          >
            <Clock3 className="h-4 w-4 text-[var(--text-dim)]" strokeWidth={1.75} />
            <input
              value={jumpValue}
              onChange={(event) => setJumpValue(event.target.value)}
              placeholder="HH:MM"
              className="w-16 bg-transparent text-[13px] font-semibold text-[var(--text)] outline-none"
              aria-label="Jump to time"
            />
          </form>
        </div>
      </section>

      <section className="space-y-5">
        <Panel className="space-y-4 p-4">
          <div className="relative overflow-hidden rounded-lg bg-black ring-1 ring-[var(--border)]">
            <video
              key={`${viewerStation}-${mediaUrlForStation(viewerStation, selectedDate)}`}
              ref={videoRef}
              src={mediaUrlForStation(viewerStation, selectedDate)}
              poster={mediaPosterUrlForStation(viewerStation, selectedDate)}
              className="aspect-video w-full bg-black object-cover"
              controls
              muted
              playsInline
              onPause={() => setPaused(true)}
              onPlay={() => setPaused(false)}
              onLoadedMetadata={(event) => {
                event.currentTarget.currentTime = Math.max(0, (selectedMinutes - workStart) % 60);
                event.currentTarget.playbackRate = speed === 60 ? 16 : speed;
              }}
            />
            {paused ? (
              <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
                <div className="flex h-14 w-14 items-center justify-center rounded-full bg-[var(--accent)] text-[#11100d] shadow-[0_12px_36px_rgba(0,0,0,.42)]">
                  <Play className="ml-1 h-7 w-7 fill-current" strokeWidth={1.75} />
                </div>
              </div>
            ) : null}
            {nearEvent ? (
              <button
                type="button"
                className="absolute bottom-4 left-4 rounded-lg bg-black/70 px-3 py-2 text-left text-[13px] font-semibold text-white backdrop-blur hover:bg-black/85"
                onClick={() => openClip(nearEvent.clip_id)}
              >
                PLACEMENT #{placementNumber} · {formatClock(new Date(nearEvent.ts), true)} · Verified by M. Reyes
              </button>
            ) : null}
            <div className="absolute bottom-4 right-4 flex rounded-lg border border-white/10 bg-black/65 p-1 backdrop-blur">
              {([1, 4, 15, 60] as Speed[]).map((nextSpeed) => (
                <button
                  key={nextSpeed}
                  type="button"
                  className={cn(
                    "h-8 rounded-md px-3 text-[12px] font-bold transition-colors",
                    speed === nextSpeed
                      ? "bg-[var(--accent)] text-[#11100d]"
                      : "text-white/70 hover:bg-white/10 hover:text-white",
                  )}
                  onClick={() => setSpeed(nextSpeed)}
                >
                  {nextSpeed}×
                </button>
              ))}
            </div>
          </div>

          <DayTimeline
            chapters={chapters}
            placements={placements}
            nowMinutes={nowMinutes}
            selectedMinutes={selectedMinutes}
            onSeek={(minutes) => seekToClock(formatClock(dateForMinutes(minutes)))}
            onOpenClip={openClip}
          />
        </Panel>

        <ChaptersGrid
          chapters={chapters}
          activeIndex={activeChapterIndex}
          selectedStation={viewerStation}
          onOpenClip={openClip}
          onSelect={(minutes) => {
            setSpeed(15);
            seekToClock(formatClock(dateForMinutes(minutes)));
          }}
        />
      </section>
    </div>
  );
}

function DayTimeline({
  chapters,
  placements,
  nowMinutes,
  selectedMinutes,
  onSeek,
  onOpenClip,
}: {
  chapters: { start: number; end: number; events: CountEventShape[] }[];
  placements: CountEventShape[];
  nowMinutes: number;
  selectedMinutes: number;
  onSeek: (minutes: number) => void;
  onOpenClip: (clipId: string) => void;
}) {
  const hourLabels = Array.from({ length: 11 }, (_, index) => 7 + index);
  const dense = placements.length > 40;
  const markerGroups: TimelineMarker[] = chapters.flatMap((chapter): TimelineMarker[] => {
    const events = placements.filter((event) => {
      const eventMinutes = minutesForDate(new Date(event.ts));
      return eventMinutes >= chapter.start && eventMinutes < chapter.end;
    });
    if (!dense || events.length <= 3) {
      return events.map((event) => ({
        id: event.clip_id,
        kind: "single" as const,
        event,
        count: 1,
        minutes: minutesForDate(new Date(event.ts)),
      }));
    }

    return [
      {
        id: `${chapter.start}-cluster`,
        kind: "cluster" as const,
        event: events[0],
        count: events.length,
        minutes: Math.round(chapter.start + chapterMinutes / 2),
      },
    ];
  });

  return (
    <div className="space-y-3">
      <div className="relative h-[140px] rounded-lg border border-[var(--border)] bg-[#0b0d0f] px-3 pt-8">
        <div className="absolute left-3 right-3 top-3 flex justify-between text-[11px] text-[var(--text-dim)]">
          {hourLabels.map((hour) => (
            <span key={hour}>{hour > 12 ? hour - 12 : hour}{hour >= 12 ? "p" : "a"}</span>
          ))}
        </div>
        <div className="relative mt-8 h-12 rounded-md bg-black/30">
          {chapters.map((chapter) => {
            const count = chapter.events.length;
            const tone =
              count >= 3
                ? "bg-[var(--good)]"
                : count > 0
                  ? "bg-[var(--warn)]"
                  : "bg-[var(--idle)]";
            return (
              <button
                key={chapter.start}
                type="button"
                title={`${formatClock(dateForMinutes(chapter.start))}-${formatClock(dateForMinutes(chapter.end))}`}
                className={cn("absolute top-0 h-12 opacity-85 hover:opacity-100", tone)}
                style={{
                  left: `${positionPct(chapter.start)}%`,
                  width: `${widthPct(chapter.start, chapter.end)}%`,
                }}
                onClick={() => onSeek(chapter.start)}
              />
            );
          })}
          <div
            className="absolute top-0 h-12 border-x border-white/20 bg-[repeating-linear-gradient(135deg,rgba(255,255,255,.18)_0,rgba(255,255,255,.18)_3px,rgba(120,124,128,.18)_3px,rgba(120,124,128,.18)_8px)]"
            title="Synthetic demo gap: no footage 13:05-13:12. Rendering path only."
            style={{
              left: `${positionPct(demoGap.start)}%`,
              width: `${widthPct(demoGap.start, demoGap.end)}%`,
            }}
          />
          {markerGroups.map((marker, index) => {
            return (
              <button
                key={marker.id}
                type="button"
                title={
                  marker.kind === "cluster"
                    ? `${marker.count} placements · ${formatClock(dateForMinutes(marker.minutes))}`
                    : `${formatClock(new Date(marker.event.ts), true)} · ${marker.event.clip_id}`
                }
                className="absolute top-[-22px] z-[2] h-4 w-4 -translate-x-1/2 rotate-45 rounded-[2px] bg-[var(--accent)] shadow-[0_0_12px_rgba(232,116,47,.55)] ring-1 ring-black/40 hover:bg-[var(--accent-hi)]"
                style={{ left: `${positionPct(marker.minutes)}%` }}
                aria-label={marker.kind === "cluster" ? `Open ${marker.count} placements` : `Open placement ${index + 1}`}
                onClick={() => {
                  onSeek(marker.minutes);
                  onOpenClip(marker.event.clip_id);
                }}
              >
                {marker.kind === "cluster" ? (
                  <span className="absolute left-3 top-[-10px] rotate-[-45deg] rounded-full bg-[#21160f] px-1.5 py-0.5 text-[10px] font-bold leading-none text-[var(--accent)] ring-1 ring-[var(--accent-tint)]">
                    ×{marker.count}
                  </span>
                ) : null}
              </button>
            );
          })}
          <div
            className="absolute -top-2 bottom-[-18px] w-[2px] bg-white shadow-[0_0_12px_rgba(255,255,255,.85)]"
            style={{ left: `${positionPct(nowMinutes)}%` }}
          >
            <span className="absolute -top-6 left-1/2 -translate-x-1/2 rounded bg-white px-1.5 py-0.5 text-[10px] font-bold text-[#11100d]">
              NOW
            </span>
          </div>
          <div
            className="absolute -bottom-5 h-4 w-[2px] bg-[var(--accent)]"
            style={{ left: `${positionPct(selectedMinutes)}%` }}
          />
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-4 text-[12px] text-[var(--text-dim)]">
        <span className="inline-flex items-center gap-2"><i className="h-2.5 w-6 rounded bg-[var(--good)]" /> events</span>
        <span className="inline-flex items-center gap-2"><i className="h-2.5 w-6 rounded bg-[var(--warn)]" /> sparse</span>
        <span className="inline-flex items-center gap-2"><i className="h-2.5 w-6 rounded bg-[var(--idle)]" /> idle</span>
        <span className="inline-flex items-center gap-2"><i className="h-3 w-3 rotate-45 rounded-[2px] bg-[var(--accent)]" /> verified placement</span>
        <span className="inline-flex items-center gap-2 text-[var(--text-dim)]">×N = clustered 15-minute bucket</span>
        <span className="inline-flex items-center gap-2"><i className="h-3 w-6 bg-[repeating-linear-gradient(135deg,rgba(255,255,255,.25)_0,rgba(255,255,255,.25)_3px,rgba(120,124,128,.25)_3px,rgba(120,124,128,.25)_8px)]" /> demo gap</span>
      </div>
    </div>
  );
}

function ChaptersGrid({
  chapters,
  activeIndex,
  selectedStation,
  onOpenClip,
  onSelect,
}: {
  chapters: { start: number; end: number; events: CountEventShape[] }[];
  activeIndex: number;
  selectedStation: string;
  onOpenClip: (clipId: string) => void;
  onSelect: (minutes: number) => void;
}) {
  return (
    <Panel className="p-4">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--text-dim)]">
            Chapters
          </div>
          <div className="mt-1 text-[14px] text-[var(--text-mut)]">15-minute scan cards</div>
        </div>
        <BadgeCheck className="h-5 w-5 text-[var(--good)]" strokeWidth={1.75} />
      </div>
      <div className="flex gap-3 overflow-x-auto pb-1">
        {chapters.map((chapter, index) => {
          const count = chapter.events.length;
          const firstEvent = uniquePlacementMoments(chapter.events)[0];
          const thumbnailDate = dateForMinutes(chapter.start);
          return (
            <div
              key={chapter.start}
              role="button"
              tabIndex={0}
              className={cn(
                "group relative min-w-[250px] cursor-pointer overflow-hidden rounded-lg border bg-[var(--panel-2)] text-left transition-colors",
                activeIndex === index
                  ? "border-[1.5px] border-[var(--accent)]"
                  : "border-[var(--border)] hover:border-[var(--border-soft)]",
              )}
              onClick={() => onSelect(chapter.start)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onSelect(chapter.start);
                }
              }}
            >
              <Image
                src={mediaPosterUrlForStation(selectedStation, thumbnailDate)}
                alt=""
                width={320}
                height={180}
                unoptimized
                loading="lazy"
                className="h-24 w-full bg-black object-cover opacity-78 transition-opacity group-hover:opacity-100"
              />
              <div className="flex items-center justify-between gap-2 p-3">
                <div>
                  <div className="text-[12px] font-semibold text-[var(--text)]">
                    {formatClock(dateForMinutes(chapter.start))} - {formatClock(dateForMinutes(chapter.end))}
                  </div>
                  <div
                    className={cn(
                      "mt-1 text-[12px] font-bold",
                      count > 0 ? "text-[var(--good)]" : "text-[var(--text-dim)]",
                    )}
                  >
                    {count > 0 ? `${count} PLACED` : "0 QUIET"}
                  </div>
                </div>
                <span
                  role="button"
                  tabIndex={0}
                  title="View events"
                  className="flex h-8 w-8 items-center justify-center rounded-md text-[var(--text-dim)] hover:bg-white/[.06] hover:text-[var(--text)]"
                  onClick={(event) => {
                    event.stopPropagation();
                    if (firstEvent) onOpenClip(firstEvent.clip_id);
                  }}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      event.stopPropagation();
                      if (firstEvent) onOpenClip(firstEvent.clip_id);
                    }
                  }}
                >
                  <MoreHorizontal className="h-4 w-4" strokeWidth={1.75} />
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </Panel>
  );
}
