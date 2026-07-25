"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, Play, RotateCcw, SkipBack, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { ReviewChunk, TallyClick } from "@/lib/reviewChunks";
import type { ReviewDayQueueRow } from "@/lib/reviewStore";
import { reviewStrings, type ReviewLanguage } from "@/lib/reviewStrings";
import { cn, isTypingTarget } from "@/lib/utils";

// 16x is the hard ceiling browsers allow for HTMLMediaElement.playbackRate
// (Chrome/Safari throw NotSupportedError above it — a 20x option crashes the app).
const reviewSpeeds = [1, 2, 5] as const;
type ReviewSpeed = (typeof reviewSpeeds)[number];

type NextChunkResponse = {
  chunk: ReviewChunk;
  nextChunk: ReviewChunk | null;
};

type ConfirmResponse = {
  events: Array<{ id: string; ts: string }>;
};

function formatRange(chunk: ReviewChunk) {
  const start = chunk.startIso.slice(11, 16);
  const end = chunk.endIso.slice(11, 16);
  return `${start}-${end}`;
}

/** "1 h 2 m" style lag, so the reviewer reads it like a person, not "62 min". */
function humanizeLag(minutes: number) {
  const total = Math.max(0, Math.round(minutes));
  const hours = Math.floor(total / 60);
  const mins = total % 60;
  if (hours && mins) return `${hours} h ${mins} m`;
  if (hours) return `${hours} h`;
  return `${mins} m`;
}

function formatClock(iso: string, language: ReviewLanguage) {
  return new Intl.DateTimeFormat(language === "es" ? "es-MX" : "en-US", {
    timeZone: "America/Los_Angeles",
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(iso));
}

function formatVideoTime(seconds: number) {
  const total = Math.max(0, Math.floor(seconds));
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

function formatTimeLeft(seconds: number) {
  const total = Math.max(0, Math.ceil(seconds));
  const minutes = Math.floor(total / 60);
  const secs = total % 60;
  return minutes ? `${minutes}m ${secs}s` : `${secs}s`;
}

function clickWallClock(chunk: ReviewChunk, click: TallyClick) {
  return new Date(new Date(chunk.startIso).getTime() + Math.min(900, Math.max(0, click.videoSec)) * 1000).toISOString();
}

export function ReviewTallyConsole() {
  const reviewerId = "live-session";
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const languageRef = useRef<ReviewLanguage>("es");
  const [payload, setPayload] = useState<NextChunkResponse | null>(null);
  const [clicks, setClicks] = useState<TallyClick[]>([]);
  const [speed, setSpeed] = useState<ReviewSpeed>(1);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [screen, setScreen] = useState<"loading" | "tally" | "summary">("loading");
  const [pressing, setPressing] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [language, setLanguage] = useState<ReviewLanguage>("es");
  const [dayQueue, setDayQueue] = useState<ReviewDayQueueRow[]>([]);
  const [isPlaying, setIsPlaying] = useState(false);
  const [showProblems, setShowProblems] = useState(false);
  const [showZeroGuard, setShowZeroGuard] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const chunk = payload?.chunk ?? null;
  const strings = reviewStrings[language];
  const progress = duration > 0 ? Math.min(1, currentTime / duration) : 0;
  const timeLeft = duration > 0 ? Math.max(0, duration - currentTime) / speed : 0;
  const lagMinutes = useMemo(() => {
    if (!chunk) return 0;
    return Math.round((new Date("2026-06-26T14:32:00-07:00").getTime() - new Date(chunk.endIso).getTime()) / 60_000);
  }, [chunk]);

  const loadNext = useCallback(async () => {
    setScreen("loading");
    const response = await fetch(`/api/review/chunks/next?reviewerId=${reviewerId}`, { cache: "no-store" });
    if (!response.ok) {
      setStatus(`${reviewStrings[languageRef.current].noChunkAvailable} (${response.status})`);
      setPayload(null);
      return;
    }
    const next = (await response.json()) as NextChunkResponse;
    setPayload(next);
    try {
      const saved = window.localStorage.getItem(`factoryvision-review-clicks:${next.chunk.id}`);
      setClicks(saved ? (JSON.parse(saved) as TallyClick[]) : []);
    } catch {
      setClicks([]);
    }
    setCurrentTime(0);
    setDuration(0);
    setIsPlaying(false);
    setShowProblems(false);
    setShowZeroGuard(false);
    setStatus(null);
    setScreen("tally");
    const queueResponse = await fetch(`/api/review/day-queue?reviewerId=${reviewerId}`, { cache: "no-store" });
    if (queueResponse.ok) {
      const queuePayload = (await queueResponse.json()) as { chunks: ReviewDayQueueRow[] };
      setDayQueue(queuePayload.chunks);
    }
  }, []);

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      const saved = window.localStorage.getItem("factoryvision-review-language");
      if (saved === "en" || saved === "es") {
        languageRef.current = saved;
        setLanguage(saved);
      }
    }, 0);
    return () => window.clearTimeout(timeout);
  }, []);

  useEffect(() => {
    if (!chunk) return;
    window.localStorage.setItem(`factoryvision-review-clicks:${chunk.id}`, JSON.stringify(clicks));
  }, [chunk, clicks]);

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      void loadNext();
    }, 0);
    return () => window.clearTimeout(timeout);
  }, [loadNext]);

  useEffect(() => {
    if (!videoRef.current) return;
    try {
      videoRef.current.playbackRate = speed;
    } catch {
      videoRef.current.playbackRate = 16;
    }
  }, [speed, chunk]);

  const addCount = useCallback(() => {
    if (!videoRef.current || screen !== "tally") return;
    const videoSec = Math.min(900, Math.max(0, videoRef.current.currentTime));
    setClicks((current) => [...current, { id: window.crypto.randomUUID(), videoSec }]);
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
      if (isTypingTarget(event.target)) return;
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

  function submissionId(chunkId: string) {
    const key = `factoryvision-review-submission:${chunkId}`;
    const existing = window.sessionStorage.getItem(key);
    if (existing) return existing;
    const created = window.crypto.randomUUID();
    window.sessionStorage.setItem(key, created);
    return created;
  }

  async function confirm(problem?: string) {
    if (!chunk) return;
    setSubmitting(true);
    const response = await fetch(`/api/review/chunks/${chunk.id}/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        reviewerId,
        clicks: problem ? [] : clicks,
        problem,
        idempotencyKey: `${chunk.id}:${submissionId(chunk.id)}`,
      }),
    });
    const result = (await response.json()) as Partial<ConfirmResponse> & { error?: string };
    if (!response.ok) {
      setStatus(`${strings.confirmFailed} (${response.status})`);
      setSubmitting(false);
      return;
    }
    window.localStorage.removeItem(`factoryvision-review-clicks:${chunk.id}`);
    setStatus(`${result.events?.length ?? 0} ${strings.confirmed}`);
    setSubmitting(false);
    await loadNext();
  }

  function requestConfirm() {
    if (!clicks.length) {
      setShowZeroGuard(true);
      return;
    }
    void confirm();
  }

  function setReviewLanguage(next: ReviewLanguage) {
    languageRef.current = next;
    setLanguage(next);
    window.localStorage.setItem("factoryvision-review-language", next);
  }

  if (screen === "loading") {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[var(--bg)] p-6 text-[var(--text)]" data-review-route="ready">
        <div className="text-[14px] text-[var(--text-mut)]">{status ?? strings.loadingNext}</div>
      </main>
    );
  }

  if (!chunk || !payload) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[var(--bg)] p-6 text-[var(--text)]" data-review-route="ready">
        <div className="text-[14px] text-[var(--text-mut)]">{status ?? strings.noEligible}</div>
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
          <div className="mt-1 text-[12px] text-[var(--text-dim)]" title={strings.leaseTitle}>
            {strings.countingBehind} {humanizeLag(lagMinutes)} {strings.behindLive}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-[12px]">
          <div className="flex rounded-lg border border-[var(--border)] bg-[var(--panel-2)] p-1" aria-label={strings.languageLabel}>
            {(["en", "es"] as const).map((value) => (
              <button
                key={value}
                type="button"
                className={cn("rounded px-2 py-1 font-semibold uppercase", language === value ? "bg-[var(--accent)] text-[#11100d]" : "text-[var(--text-mut)]")}
                onClick={() => setReviewLanguage(value)}
              >
                {value}
              </button>
            ))}
          </div>
        </div>
      </header>

      <div className="mb-4 flex flex-wrap items-center gap-2 rounded-lg border border-[rgba(232,116,47,.35)] bg-[rgba(232,116,47,.10)] px-4 py-3 text-[13px] text-[var(--text)]">
        <Zap className="h-4 w-4 shrink-0 fill-[var(--accent)] text-[var(--accent)]" strokeWidth={1.75} />
        <span className="font-semibold">
          {strings.instruction}
        </span>
        <span className="text-[var(--text-dim)]">
          {strings.awayWarning}
        </span>
      </div>

      <section className="grid min-w-0 gap-5 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0">
          <div className="relative aspect-video w-full overflow-hidden rounded-lg bg-black ring-1 ring-[var(--border)]">
            <video
              ref={videoRef}
              src={chunk.mediaUrl}
              poster={chunk.posterUrl}
              className="h-full w-full bg-black object-contain"
              muted
              playsInline
              onLoadedMetadata={() => {
                if (!videoRef.current) return;
                try {
                  videoRef.current.playbackRate = speed;
                } catch {
                  videoRef.current.playbackRate = 16;
                }
                setCurrentTime(videoRef.current.currentTime);
                setDuration(Number.isFinite(videoRef.current.duration) ? videoRef.current.duration : 0);
              }}
              onPlay={() => setIsPlaying(true)}
              onPause={() => setIsPlaying(false)}
              onTimeUpdate={() => setCurrentTime(videoRef.current?.currentTime ?? 0)}
              onEnded={() => {
                setIsPlaying(false);
                setScreen("summary");
              }}
            />
            {!isPlaying && (
              <button
                type="button"
                className="absolute left-1/2 top-1/2 flex h-20 w-20 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full bg-[var(--accent)] text-white shadow-[0_10px_28px_rgba(0,0,0,.42)] hover:bg-[var(--accent-hi)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
                aria-label={strings.play}
                onClick={() => {
                  void videoRef.current?.play().catch(() => setStatus(strings.playFailed));
                }}
              >
                <Play className="ml-1 h-9 w-9 fill-white" strokeWidth={1.75} />
              </button>
            )}
          </div>
          <div className="mt-3">
            <button
              type="button"
              className="flex w-full cursor-pointer items-center py-1.5 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)]"
              aria-label={strings.seekVideo}
              onPointerDown={(event) => {
                if (!videoRef.current || duration <= 0) return;
                const rect = event.currentTarget.getBoundingClientRect();
                const fraction = Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width));
                videoRef.current.currentTime = fraction * duration;
                setCurrentTime(videoRef.current.currentTime);
              }}
            >
              <span className="h-1 w-full overflow-hidden rounded-full bg-white/[.08]">
                <span className="block h-full rounded-full bg-[var(--accent)]" style={{ width: `${progress * 100}%` }} />
              </span>
            </button>
            <div className="mt-1 flex items-center justify-between gap-3 text-[12px] tabular-nums text-[var(--text-dim)]">
              <span>{formatVideoTime(currentTime)} / {formatVideoTime(duration)}</span>
              <span>~{formatTimeLeft(timeLeft)} {strings.leftAt} {speed}x</span>
            </div>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {reviewSpeeds.map((value) => (
              <button
                key={value}
                type="button"
                className={cn(
                  "rounded-lg px-3 py-2 text-[13px] font-semibold",
                  speed === value ? "bg-[var(--accent)] text-[#11100d]" : "border border-[var(--border)] bg-[var(--panel-2)] text-[var(--text-mut)]",
                )}
                onClick={() => setSpeed(value)}
              >
                {value}x
              </button>
            ))}
            <Button type="button" variant="secondary" onClick={() => videoRef.current?.pause()}>
              {strings.pause}
            </Button>
            <Button type="button" variant="secondary" onClick={backTen}>
              <SkipBack className="h-4 w-4" strokeWidth={1.75} />
              {strings.back10}
            </Button>
            <Button type="button" variant="secondary" onClick={() => setScreen("summary")}>
              {strings.endChunk}
            </Button>
            <div className="relative">
              <Button type="button" variant="secondary" onClick={() => setShowProblems((current) => !current)}>
                <AlertTriangle className="h-4 w-4" strokeWidth={1.75} />
                {strings.reportProblem}
              </Button>
              {showProblems && (
                <div className="absolute bottom-full left-0 z-10 mb-2 w-56 rounded-xl border border-[var(--border)] bg-[linear-gradient(180deg,var(--panel),var(--panel-2))] p-2 shadow-[0_10px_28px_rgba(0,0,0,.42)]">
                  <div className="px-2 pb-2 text-[11px] font-semibold text-[var(--text-dim)]">{strings.problemPrompt}</div>
                  {([
                    ["camera-blocked", strings.cameraBlocked],
                    ["cannot-tell", strings.cannotTell],
                    ["video-wont-play", strings.videoWontPlay],
                    ["wrong-scene", strings.wrongScene],
                  ] as const).map(([reason, label]) => (
                    <button
                      key={reason}
                      type="button"
                      className="block w-full rounded-lg px-2 py-2 text-left text-[13px] text-[var(--text-mut)] hover:bg-white/[.04] hover:text-[var(--text)]"
                      disabled={submitting}
                      onClick={() => void confirm(reason)}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        <aside className="flex min-w-0 min-h-[420px] flex-col rounded-xl border border-[var(--border)] bg-[linear-gradient(180deg,var(--panel),var(--panel-2))] p-5">
          <div className="flex min-h-[360px] flex-1 flex-col justify-between">
            {screen === "summary" ? (
            <div className="flex h-full flex-col">
              <div className="text-[13px] font-semibold text-[var(--text-mut)]">
                {strings.summaryPrefix} {clicks.length} {strings.summaryIn} {formatRange(chunk)}
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
                    <span className="text-[var(--text-dim)]">{formatClock(clickWallClock(chunk, click), language)}</span>
                  </button>
                ))}
                {!clicks.length && <div className="text-[13px] text-[var(--text-dim)]">{strings.noClicks}</div>}
              </div>
              <div className="mt-5 grid gap-2">
                {showZeroGuard ? (
                  <div className="rounded-lg border border-[rgba(232,116,47,.35)] bg-[rgba(232,116,47,.10)] p-3 text-[13px]">
                    <div>{strings.zeroGuard}</div>
                    <div className="mt-3 flex gap-2">
                      <Button type="button" variant="primary" className="flex-1 justify-center" disabled={submitting} onClick={() => void confirm()}>
                        {strings.yes}
                      </Button>
                      <Button type="button" variant="secondary" className="flex-1 justify-center" onClick={() => setShowZeroGuard(false)}>
                        {strings.no}
                      </Button>
                    </div>
                  </div>
                ) : (
                  <Button type="button" variant="primary" className="h-14 justify-center text-[16px]" disabled={submitting} onClick={requestConfirm}>
                    {strings.confirm}
                  </Button>
                )}
                <Button type="button" variant="secondary" className="h-12 justify-center" onClick={() => setScreen("tally")}>
                  {strings.redo}
                </Button>
              </div>
            </div>
          ) : (
            <>
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--text-dim)]">
                  {strings.runningTally}
                </div>
                <div data-testid="running-tally" className="mt-3 text-[112px] font-bold leading-none tracking-[-0.01em] text-[var(--text)]">
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
                  {strings.countButton}
                </button>
                <Button type="button" variant="secondary" className="h-12 justify-center" onClick={undo}>
                  <RotateCcw className="h-4 w-4" strokeWidth={1.75} />
                  {strings.undo}
                </Button>
                <div className="flex items-center justify-center gap-3 text-[12px] text-[var(--text-dim)]">
                  <span><kbd className="rounded border border-[var(--border)] px-1.5 py-0.5">Space</kbd> {strings.countHotkey}</span>
                  <span><kbd className="rounded border border-[var(--border)] px-1.5 py-0.5">Z</kbd> {strings.undoHotkey}</span>
                  <span><kbd className="rounded border border-[var(--border)] px-1.5 py-0.5">←</kbd> {strings.backHotkey}</span>
                </div>
              </div>
            </>
          )}
          </div>

          <div className="mt-5 border-t border-[var(--border)] pt-4">
            <div className="flex items-end justify-between gap-3">
              <div className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--text-dim)]">{strings.myWorkToday}</div>
              <div className="text-[11px] text-[var(--text-dim)]">
                {strings.todayPrefix} {dayQueue.filter((row) => row.state === "done").length} {strings.done} · {dayQueue.filter((row) => row.state !== "done").length} {strings.left}
              </div>
            </div>
            <div className="mt-3 grid grid-cols-[20px_minmax(52px,1fr)_58px_54px_40px] gap-0 border-b border-[var(--border)] px-2 pb-2 text-[10px] font-semibold text-[var(--text-dim)] sm:grid-cols-[24px_minmax(72px,1fr)_76px_66px_42px] sm:gap-1 sm:text-[11px]">
              <span>{strings.numberHeader}</span>
              <span>{strings.stationHeader}</span>
              <span>{strings.timeHeader}</span>
              <span>{strings.statusHeader}</span>
              <span className="text-right">{strings.countHeader}</span>
            </div>
            <div className="max-h-64 overflow-y-auto">
              {dayQueue.map((row) => {
                const current = row.id === chunk.id;
                const statusLabel = row.problem
                  ? strings.problemStatus
                  : row.state === "working"
                    ? strings.working
                    : row.state === "done"
                      ? strings.doneStatus
                      : row.state === "locked-by-other"
                        ? strings.lockedByOther
                        : strings.pending;
                return (
                  <div
                    key={row.id}
                    className={cn(
                      "grid grid-cols-[20px_minmax(52px,1fr)_58px_54px_40px] gap-0 border-b border-[var(--border-soft)] px-2 py-2 text-[10px] text-[var(--text-mut)] sm:grid-cols-[24px_minmax(72px,1fr)_76px_66px_42px] sm:gap-1 sm:text-[11px]",
                      current && "border-l-2 border-l-[var(--accent)] bg-[var(--accent-tint)] pl-1.5",
                    )}
                  >
                    <span className="tabular-nums text-[var(--text-dim)]">{row.order}</span>
                    <span className="truncate" title={row.stationName}>{row.stationName}</span>
                    <span className="tabular-nums text-[var(--text-dim)]">{row.timeRange}</span>
                    <span className={cn(row.state === "done" && !row.problem && "text-[var(--good)]", row.problem && "text-[var(--bad)]")}>{statusLabel}</span>
                    <span className="text-right tabular-nums text-[var(--text)]">{row.count ?? "—"}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </aside>
      </section>

      {payload.nextChunk && (
        <video src={payload.nextChunk.mediaUrl} preload="auto" className="hidden" aria-hidden="true" />
      )}
    </main>
  );
}
