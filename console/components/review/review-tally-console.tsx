"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { RotateCcw, SkipBack, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { ReviewChunk, TallyClick } from "@/lib/reviewChunks";
import { cn } from "@/lib/utils";

type NextChunkResponse = {
  chunk: ReviewChunk;
  nextChunk: ReviewChunk | null;
  stats: {
    chunksDone: number;
    clicks: number;
    chunksPerHour: number;
  };
  queueDepth: number;
};

type ConfirmResponse = {
  events: Array<{ id: string; ts: string }>;
  stats: NextChunkResponse["stats"];
};

function formatRange(chunk: ReviewChunk) {
  const start = chunk.startIso.slice(11, 16);
  const end = chunk.endIso.slice(11, 16);
  return `${start}-${end}`;
}

function formatClock(iso: string) {
  return new Intl.DateTimeFormat("en-US", {
    timeZone: "America/Los_Angeles",
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(iso));
}

function clickWallClock(chunk: ReviewChunk, click: TallyClick) {
  return new Date(new Date(chunk.startIso).getTime() + Math.min(900, Math.max(0, click.videoSec)) * 1000).toISOString();
}

export function ReviewTallyConsole() {
  const reviewerId = "live-session";
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [payload, setPayload] = useState<NextChunkResponse | null>(null);
  const [clicks, setClicks] = useState<TallyClick[]>([]);
  const [speed, setSpeed] = useState<5 | 10 | 15>(10);
  const [screen, setScreen] = useState<"loading" | "tally" | "summary">("loading");
  const [pressing, setPressing] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  const chunk = payload?.chunk ?? null;
  const lagMinutes = useMemo(() => {
    if (!chunk) return 0;
    return Math.round((new Date("2026-06-26T14:32:00-07:00").getTime() - new Date(chunk.endIso).getTime()) / 60_000);
  }, [chunk]);

  const loadNext = useCallback(async () => {
    setScreen("loading");
    const response = await fetch(`/api/review/chunks/next?reviewerId=${reviewerId}`, { cache: "no-store" });
    if (!response.ok) {
      setStatus(`No chunk available (${response.status})`);
      setPayload(null);
      return;
    }
    const next = (await response.json()) as NextChunkResponse;
    setPayload(next);
    setClicks([]);
    setStatus(null);
    setScreen("tally");
  }, []);

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      void loadNext();
    }, 0);
    return () => window.clearTimeout(timeout);
  }, [loadNext]);

  useEffect(() => {
    if (videoRef.current) videoRef.current.playbackRate = speed;
  }, [speed, chunk]);

  const addCount = useCallback(() => {
    if (!videoRef.current || screen !== "tally") return;
    const videoSec = Math.min(900, Math.max(0, videoRef.current.currentTime));
    setClicks((current) => [...current, { id: `click-${current.length + 1}`, videoSec }]);
    setPressing(true);
    window.setTimeout(() => setPressing(false), 140);
  }, [screen]);

  const undo = useCallback(() => {
    setClicks((current) => current.slice(0, -1));
  }, []);

  const backTen = useCallback(() => {
    if (!videoRef.current) return;
    videoRef.current.currentTime = Math.max(0, videoRef.current.currentTime - 10);
  }, []);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.code === "Space") {
        event.preventDefault();
        addCount();
      }
      if (event.key.toLowerCase() === "z") {
        event.preventDefault();
        undo();
      }
      if (event.key === "ArrowLeft") {
        event.preventDefault();
        backTen();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [addCount, backTen, undo]);

  async function confirm() {
    if (!chunk) return;
    const response = await fetch(`/api/review/chunks/${chunk.id}/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reviewerId, clicks }),
    });
    const result = (await response.json()) as Partial<ConfirmResponse> & { error?: string };
    if (!response.ok) {
      setStatus(result.error ?? `Confirm failed (${response.status})`);
      return;
    }
    setStatus(`Confirmed ${result.events?.length ?? 0} events.`);
    await loadNext();
  }

  if (screen === "loading") {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[var(--bg)] p-6 text-[var(--text)]" data-review-route="ready">
        <div className="text-[14px] text-[var(--text-mut)]">{status ?? "Loading next chunk..."}</div>
      </main>
    );
  }

  if (!chunk || !payload) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[var(--bg)] p-6 text-[var(--text)]" data-review-route="ready">
        <div className="text-[14px] text-[var(--text-mut)]">{status ?? "No eligible chunks."}</div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[var(--bg)] p-5 text-[var(--text)]" data-review-route="ready" data-review-chunk={chunk.id}>
      <header className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-[var(--border)] pb-4">
        <div>
          <div className="text-[13px] font-semibold text-[var(--text)]">
            {chunk.stationName} · {formatRange(chunk)}
          </div>
          <div className="mt-1 text-[12px] text-[var(--text-dim)]">
            counting {lagMinutes} min behind live · queue {payload.queueDepth}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-[12px]">
          <span className="rounded-lg border border-[var(--border)] bg-[var(--panel-2)] px-3 py-2">
            {payload.stats.chunksDone} chunks done
          </span>
          <span className="rounded-lg border border-[var(--border)] bg-[var(--panel-2)] px-3 py-2">
            {payload.stats.clicks} clicks
          </span>
          <span className="rounded-lg border border-[var(--border)] bg-[var(--panel-2)] px-3 py-2">
            {payload.stats.chunksPerHour} chunks/hr
          </span>
        </div>
      </header>

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div>
          <video
            ref={videoRef}
            src={chunk.mediaUrl}
            poster={chunk.posterUrl}
            className="aspect-video w-full rounded-lg bg-black object-cover ring-1 ring-[var(--border)]"
            autoPlay
            muted
            playsInline
            onLoadedMetadata={() => {
              if (videoRef.current) videoRef.current.playbackRate = speed;
            }}
            onEnded={() => setScreen("summary")}
          />
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {[5, 10, 15].map((value) => (
              <button
                key={value}
                type="button"
                className={cn(
                  "rounded-lg px-3 py-2 text-[13px] font-semibold",
                  speed === value ? "bg-[var(--accent)] text-[#11100d]" : "border border-[var(--border)] bg-[var(--panel-2)] text-[var(--text-mut)]",
                )}
                onClick={() => setSpeed(value as 5 | 10 | 15)}
              >
                {value}x
              </button>
            ))}
            <Button type="button" variant="secondary" onClick={() => videoRef.current?.pause()}>
              Pause
            </Button>
            <Button type="button" variant="secondary" onClick={backTen}>
              <SkipBack className="h-4 w-4" strokeWidth={1.75} />
              10s
            </Button>
            <Button type="button" variant="secondary" onClick={() => setScreen("summary")}>
              End chunk
            </Button>
          </div>
        </div>

        <aside className="flex min-h-[420px] flex-col justify-between rounded-xl border border-[var(--border)] bg-[linear-gradient(180deg,var(--panel),var(--panel-2))] p-5">
          {screen === "summary" ? (
            <div className="flex h-full flex-col">
              <div className="text-[13px] font-semibold text-[var(--text-mut)]">
                You counted {clicks.length} in {formatRange(chunk)}
              </div>
              <div className="mt-4 max-h-[300px] flex-1 space-y-2 overflow-y-auto">
                {clicks.map((click, index) => (
                  <button
                    key={click.id}
                    type="button"
                    className="flex w-full items-center justify-between rounded-lg border border-[var(--border-soft)] bg-white/[.02] px-3 py-2 text-left text-[13px] hover:bg-white/[.04]"
                    onClick={() => {
                      if (!videoRef.current) return;
                      videoRef.current.currentTime = Math.max(0, click.videoSec - 5);
                      setScreen("tally");
                      void videoRef.current.play();
                    }}
                  >
                    <span>#{index + 1}</span>
                    <span className="text-[var(--text-dim)]">{formatClock(clickWallClock(chunk, click))}</span>
                  </button>
                ))}
                {!clicks.length && <div className="text-[13px] text-[var(--text-dim)]">No clicks recorded.</div>}
              </div>
              <div className="mt-5 grid gap-2">
                <Button type="button" variant="primary" className="h-14 justify-center text-[16px]" onClick={confirm}>
                  CONFIRM
                </Button>
                <Button type="button" variant="secondary" className="h-12 justify-center" onClick={() => setScreen("tally")}>
                  REDO
                </Button>
              </div>
            </div>
          ) : (
            <>
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--text-dim)]">
                  Running tally
                </div>
                <div className="mt-3 text-[112px] font-bold leading-none tracking-[-0.01em] text-[var(--text)]">
                  {clicks.length}
                </div>
              </div>
              <div className="grid gap-3">
                <button
                  type="button"
                  className={cn(
                    "flex h-28 items-center justify-center gap-3 rounded-xl bg-[var(--accent)] text-[28px] font-black text-[#11100d] shadow-[0_18px_34px_rgba(232,116,47,.22)] transition-transform",
                    pressing && "scale-[.97] bg-[var(--accent-hi)]",
                  )}
                  onClick={addCount}
                >
                  <Zap className="h-8 w-8 fill-[#11100d]" strokeWidth={1.75} />
                  +1 COUNT
                </button>
                <Button type="button" variant="secondary" className="h-12 justify-center" onClick={undo}>
                  <RotateCcw className="h-4 w-4" strokeWidth={1.75} />
                  Undo
                </Button>
              </div>
            </>
          )}
        </aside>
      </section>

      {payload.nextChunk && (
        <video src={payload.nextChunk.mediaUrl} preload="auto" className="hidden" aria-hidden="true" />
      )}
    </main>
  );
}
