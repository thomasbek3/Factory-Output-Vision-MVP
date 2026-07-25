"use client";

import { ChevronLeft, ChevronRight, Copy, Download, Film, ListVideo } from "lucide-react";
import { stations } from "@/lib/demoData";
import { demoSourceDay, type CountEventShape } from "@/lib/demoEvents";
import type { SavedClip } from "@/components/replay/use-saved-clips";
import { cn } from "@/lib/utils";

function dayLabel(day: string) {
  return new Intl.DateTimeFormat("en-US", {
    timeZone: "America/Los_Angeles",
    weekday: "short",
    month: "short",
    day: "numeric",
  }).format(new Date(`${day}T12:00:00-07:00`));
}

function timeLabel(ts: string, withSeconds = false) {
  return new Intl.DateTimeFormat("en-US", {
    timeZone: "America/Los_Angeles",
    hour: "numeric",
    minute: "2-digit",
    second: withSeconds ? "2-digit" : undefined,
  }).format(new Date(ts));
}

function stationName(stationId: string) {
  return stations.find((station) => station.id === stationId)?.name ?? stationId;
}

/** Date pager + day-strip. Days with footage are dotted and selectable; others disabled. */
export function DayPicker({
  days,
  selectedDay,
  onSelect,
}: {
  days: string[];
  selectedDay: string;
  onSelect: (day: string) => void;
}) {
  const ordered = [...days].sort((a, b) => a.localeCompare(b));
  const index = ordered.indexOf(selectedDay);
  const prevDay = index > 0 ? ordered[index - 1] : null;
  const nextDay = index >= 0 && index < ordered.length - 1 ? ordered[index + 1] : null;

  return (
    <div className="flex flex-wrap items-center gap-3">
      <div className="flex items-center gap-1">
        <button
          type="button"
          aria-label="Previous day"
          disabled={!prevDay}
          onClick={() => prevDay && onSelect(prevDay)}
          className="flex h-9 w-9 items-center justify-center rounded-lg border border-[var(--border)] text-[var(--text-mut)] hover:bg-white/[.04] disabled:opacity-40"
        >
          <ChevronLeft className="h-4 w-4" strokeWidth={1.75} />
        </button>
        <div className="min-w-[150px] px-2 text-center text-[14px] font-semibold text-[var(--text)]">
          {dayLabel(selectedDay)}
          {selectedDay === demoSourceDay ? (
            <span className="ml-2 text-[11px] font-medium text-[var(--text-dim)]">today</span>
          ) : null}
        </div>
        <button
          type="button"
          aria-label="Next day"
          disabled={!nextDay}
          onClick={() => nextDay && onSelect(nextDay)}
          className="flex h-9 w-9 items-center justify-center rounded-lg border border-[var(--border)] text-[var(--text-mut)] hover:bg-white/[.04] disabled:opacity-40"
        >
          <ChevronRight className="h-4 w-4" strokeWidth={1.75} />
        </button>
      </div>
      <div className="flex items-center gap-1.5">
        {ordered.map((day) => (
          <button
            key={day}
            type="button"
            aria-label={`Open ${dayLabel(day)}`}
            aria-pressed={day === selectedDay}
            title={dayLabel(day)}
            onClick={() => onSelect(day)}
            className={cn(
              "h-2.5 w-2.5 rounded-full transition-colors",
              day === selectedDay ? "bg-[var(--accent)]" : "bg-[var(--border)] hover:bg-[var(--text-dim)]",
            )}
          />
        ))}
      </div>
    </div>
  );
}

/** Chronological "Counted moments" for the selected day/station. */
export function CountedMoments({
  placements,
  onOpen,
}: {
  placements: CountEventShape[];
  onOpen: (clipId: string) => void;
}) {
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--panel-2)]">
      <div className="flex items-center gap-2 border-b border-[var(--border-soft)] px-4 py-3">
        <ListVideo className="h-4 w-4 text-[var(--accent)]" strokeWidth={1.75} />
        <span className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--text-dim)]">
          Counted moments
        </span>
        <span className="ml-auto text-[12px] text-[var(--text-dim)]">{placements.length}</span>
      </div>
      {placements.length ? (
        <div className="max-h-[320px] divide-y divide-[var(--border-soft)] overflow-y-auto">
          {placements.map((event) => (
            <button
              key={event.clip_id}
              type="button"
              data-testid="counted-moment"
              onClick={() => onOpen(event.clip_id)}
              className="flex w-full items-center gap-3 px-4 py-2.5 text-left text-[13px] hover:bg-white/[.03]"
            >
              <span className="font-semibold tabular-nums text-[var(--text)]">{timeLabel(event.ts, true)}</span>
              <span className="text-[var(--text-dim)]">{stationName(event.station_id)}</span>
              <span className="ml-auto text-[12px] text-[var(--text-dim)]">Historical review</span>
            </button>
          ))}
        </div>
      ) : (
        <div className="px-4 py-6 text-center text-[13px] text-[var(--text-dim)]">
          No counted moments for this day and station.
        </div>
      )}
    </div>
  );
}

/** Saved clips shelf — persisted extractions the owner kept. */
export function SavedClipsShelf({ clips, onOpen }: { clips: SavedClip[]; onOpen: (clipId: string) => void }) {
  if (!clips.length) return null;
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--panel-2)]">
      <div className="flex items-center gap-2 border-b border-[var(--border-soft)] px-4 py-3">
        <Film className="h-4 w-4 text-[var(--accent)]" strokeWidth={1.75} />
        <span className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--text-dim)]">
          Saved clips
        </span>
        <span className="ml-auto text-[12px] text-[var(--text-dim)]">{clips.length}</span>
      </div>
      <div className="flex gap-3 overflow-x-auto p-3">
        {clips.map((clip) => (
          <div
            key={clip.id}
            className="min-w-[210px] rounded-lg border border-[var(--border)] bg-[var(--panel)] p-3"
          >
            <div className="text-[13px] font-semibold text-[var(--text)]">
              {stationName(clip.stationId)} · {timeLabel(clip.ts, true)}
            </div>
            <div className="mt-1 text-[12px] text-[var(--text-dim)]">
              {dayLabel(clip.ts.slice(0, 10))}
              {clip.note ? ` · ${clip.note}` : ""}
            </div>
            <div className="mt-3 flex gap-2">
              <button
                type="button"
                onClick={() => onOpen(clip.eventId)}
                className="flex-1 rounded-md border border-[var(--border)] px-2 py-1.5 text-[12px] font-semibold text-[var(--text-mut)] hover:bg-white/[.04]"
              >
                Watch
              </button>
              <a
                href={`/api/clip/${encodeURIComponent(clip.eventId)}/download`}
                className="flex items-center gap-1 rounded-md border border-[var(--border)] px-2 py-1.5 text-[12px] font-semibold text-[var(--text-mut)] hover:bg-white/[.04]"
              >
                <Download className="h-3.5 w-3.5" strokeWidth={1.75} />
              </a>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/** Save-clip + copy-link actions for the currently-focused event. */
export function ClipActions({
  event,
  onSave,
  onCopyLink,
  saving,
}: {
  event: CountEventShape | null;
  onSave: () => void;
  onCopyLink: () => void;
  saving: boolean;
}) {
  return (
    <div className="flex gap-2">
      <button
        type="button"
        disabled={!event || saving}
        onClick={onSave}
        className="flex h-9 items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--panel-2)] px-3 text-[13px] font-semibold text-[var(--text)] hover:bg-white/[.04] disabled:opacity-50"
      >
        <Download className="h-4 w-4" strokeWidth={1.75} />
        {saving ? "Saving…" : "Save clip"}
      </button>
      <button
        type="button"
        disabled={!event}
        onClick={onCopyLink}
        className="flex h-9 items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--panel-2)] px-3 text-[13px] font-semibold text-[var(--text)] hover:bg-white/[.04] disabled:opacity-50"
      >
        <Copy className="h-4 w-4" strokeWidth={1.75} />
        Copy link
      </button>
    </div>
  );
}
