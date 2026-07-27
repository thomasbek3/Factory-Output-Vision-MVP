"use client";

import { useEffect, useRef, useState } from "react";
import {
  Check,
  LifeBuoy,
  Loader2,
  Play,
  RotateCcw,
  ShieldCheck,
  Zap,
} from "lucide-react";
import {
  reviewerLifecycle,
  workerRpc,
  type ReviewerLifecycle,
  type ReviewSession,
} from "@/lib/reviewSupabase";
import { reviewerDeviceHash } from "@/lib/reviewerDevice";
import {
  isCountableSourceTime,
  timelineDurationMatches,
  videoTimeToSourceMs,
  type ReviewTimeline,
} from "@/lib/reviewTimeline";

type Qualification = {
  chunkId: string;
  stationName: string;
  sourceStartMs: number;
  sourceEndMs: number;
  renditionSourceStartMs?: number;
  renditionSourceEndMs?: number;
  mediaUrl: string;
};

type ClaimResult = {
  qualification: Qualification | null;
  attempts?: number;
  reason?: string;
};

export function ReviewerQualification({
  lifecycle,
  session,
  onChange,
}: {
  lifecycle: ReviewerLifecycle;
  session: ReviewSession;
  onChange: (next: ReviewerLifecycle) => void;
}) {
  const spanish = lifecycle.locale !== "en";
  const videoRef = useRef<HTMLVideoElement>(null);
  const [qualification, setQualification] = useState<Qualification | null>(null);
  const [attempts, setAttempts] = useState(0);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [eventTimes, setEventTimes] = useState<number[]>([]);
  const [speed, setSpeed] = useState(1);
  const [watchedToEnd, setWatchedToEnd] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [timelineIssue, setTimelineIssue] = useState(false);
  const [helpState, setHelpState] = useState<"idle" | "sending" | "sent" | "failed">("idle");

  useEffect(() => {
    void workerRpc<ClaimResult>(
      session,
      "worker_claim_reviewer_qualification",
      {},
    )
      .then((result) => {
        setQualification(result.qualification);
        setAttempts(result.attempts ?? 0);
      })
      .catch(() => {
        setError(
          spanish
            ? "No se pudo abrir la calificación."
            : "The qualification could not be opened.",
        );
      })
      .finally(() => setLoading(false));
  }, [session, spanish]);

  function markOutput() {
    if (!qualification || !videoRef.current) return;
    const timeline: ReviewTimeline = {
      canonicalStartMs: qualification.sourceStartMs,
      canonicalEndMs: qualification.sourceEndMs,
      renditionStartMs:
        qualification.renditionSourceStartMs ?? qualification.sourceStartMs,
      renditionEndMs:
        qualification.renditionSourceEndMs ?? qualification.sourceEndMs,
    };
    const sourceTimeMs = videoTimeToSourceMs(
      videoRef.current.currentTime,
      videoRef.current.duration,
      timeline,
    );
    if (!timelineDurationMatches(videoRef.current.duration, timeline)) return;
    if (!isCountableSourceTime(sourceTimeMs, timeline)) return;
    setEventTimes((current) => [
      ...current,
      sourceTimeMs,
    ]);
  }

  async function submit() {
    if (!qualification || !watchedToEnd || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const result = await workerRpc<{ passed: boolean; state: string }>(
        session,
        "worker_submit_reviewer_qualification",
        {
          p_chunk_id: qualification.chunkId,
          p_total_count: eventTimes.length,
          p_event_times_ms: eventTimes,
          p_device_id_hash: await reviewerDeviceHash(),
        },
      );
      if (result.passed) {
        onChange(await reviewerLifecycle("GET"));
        return;
      }
      setAttempts((current) => current + 1);
      setEventTimes([]);
      setWatchedToEnd(false);
      if (videoRef.current) videoRef.current.currentTime = 0;
      setError(
        spanish
          ? "El resultado no coincidió. Mira el video completo e inténtalo otra vez."
          : "The result did not match. Watch the full video and try again.",
      );
    } catch (submitError) {
      const attemptLimitReached =
        submitError instanceof Error &&
        /qualification attempt limit reached/i.test(submitError.message);
      if (attemptLimitReached) setAttempts(3);
      setError(attemptLimitReached
        ? (spanish
          ? "Alcanzaste el límite de tres intentos en 24 horas. Pide ayuda para continuar."
          : "You reached the three-attempt limit for 24 hours. Request help to continue.")
        : (spanish
          ? "No se pudo enviar la calificación. Inténtalo otra vez."
          : "The qualification could not be submitted. Try again."));
    } finally {
      setSubmitting(false);
    }
  }

  async function requestHelp() {
    setHelpState("sending");
    try {
      await workerRpc(session, "worker_request_support", {
        p_assignment_id: null,
        p_reason_code: "qualification",
        p_message: timelineIssue
          ? "Qualification video timing did not match its verified rendition timeline."
          : "Reviewer reached the qualification attempt limit and needs help.",
      });
      setHelpState("sent");
    } catch {
      setHelpState("failed");
    }
  }

  if (loading) {
    return (
      <div className="grid min-h-[320px] place-items-center">
        <Loader2 className="h-7 w-7 animate-spin text-[var(--accent)]" />
      </div>
    );
  }

  if (!qualification) {
    return (
      <div className="mx-auto max-w-lg text-center">
        <ShieldCheck className="mx-auto h-9 w-9 text-[var(--accent)]" />
        <h2 className="mt-5 text-[24px] font-semibold">
          {spanish ? "Calificación pendiente" : "Qualification pending"}
        </h2>
        <p className="mt-3 text-[14px] leading-6 text-[var(--text-mut)]">
          {spanish
            ? "FactoryVision todavía debe cargar el video de calificación aprobado."
            : "FactoryVision still needs to load the approved qualification video."}
        </p>
      </div>
    );
  }

  if (attempts >= 3) {
    return (
      <div className="mx-auto max-w-lg text-center">
        <LifeBuoy className="mx-auto h-9 w-9 text-[var(--accent)]" />
        <h2 className="mt-5 text-[24px] font-semibold">
          {spanish ? "Calificación pausada" : "Qualification paused"}
        </h2>
        <p className="mt-3 text-[14px] leading-6 text-[var(--text-mut)]">
          {spanish
            ? "Usaste los tres intentos. Pide ayuda y el equipo te dará otra práctica."
            : "You used all three attempts. Request help and the team will give you another practice."}
        </p>
        {helpState === "sent" ? (
          <div role="status" className="mt-5 border border-[var(--good)]/40 bg-[var(--good-tint)] px-4 py-3 text-[13px] text-[var(--good)]">
            {spanish ? "Solicitud enviada. El equipo se comunicará contigo." : "Request sent. The team will contact you."}
          </div>
        ) : (
          <button
            type="button"
            disabled={helpState === "sending"}
            onClick={() => void requestHelp()}
            className="mt-5 inline-flex h-12 items-center justify-center gap-2 bg-[var(--accent)] px-5 font-semibold text-black disabled:opacity-50"
          >
            <LifeBuoy className="h-4 w-4" />
            {spanish ? "Pedir ayuda" : "Request help"}
          </button>
        )}
        {helpState === "failed" ? (
          <div role="alert" className="mt-4 text-[13px] text-[var(--bad)]">
            {spanish ? "No se pudo enviar. Inténtalo otra vez." : "Could not send. Try again."}
          </div>
        ) : null}
      </div>
    );
  }

  const qualificationTimeline: ReviewTimeline = {
    canonicalStartMs: qualification.sourceStartMs,
    canonicalEndMs: qualification.sourceEndMs,
    renditionStartMs:
      qualification.renditionSourceStartMs ?? qualification.sourceStartMs,
    renditionEndMs:
      qualification.renditionSourceEndMs ?? qualification.sourceEndMs,
  };
  const currentSourceTimeMs =
    duration > 0
      ? videoTimeToSourceMs(currentTime, duration, qualificationTimeline)
      : null;
  const countEnabled =
    !timelineIssue &&
    currentSourceTimeMs !== null &&
    isCountableSourceTime(currentSourceTimeMs, qualificationTimeline);

  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-5">
        <div className="text-[11px] font-semibold uppercase text-[var(--text-dim)]">
          {spanish ? "Calificación final" : "Final qualification"}
        </div>
        <h2 className="mt-2 text-[24px] font-semibold">
          {spanish ? "Cuenta cada pieza terminada" : "Count every finished piece"}
        </h2>
        <p className="mt-2 text-[13px] text-[var(--text-mut)]">
          {spanish
            ? "Mira todo el video. Presiona +1 en el momento en que cada pieza queda en el área de salida."
            : "Watch the entire video. Press +1 when each piece remains in the output area."}
        </p>
      </div>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_240px]">
        <div>
          <div className="relative aspect-video overflow-hidden bg-black ring-1 ring-[var(--border)]">
            <video
              ref={videoRef}
              src={qualification.mediaUrl}
              className="h-full w-full object-contain"
              muted
              playsInline
              onLoadedMetadata={() => {
                if (!videoRef.current) return;
                setDuration(videoRef.current.duration);
                const validTimeline = timelineDurationMatches(
                  videoRef.current.duration,
                  qualificationTimeline,
                );
                setTimelineIssue(!validTimeline);
                if (!validTimeline) {
                  setError(
                    spanish
                      ? "No se pudo verificar el tiempo del video. Pide ayuda."
                      : "Video timing could not be verified. Request help.",
                  );
                }
              }}
              onTimeUpdate={() => {
                if (videoRef.current) setCurrentTime(videoRef.current.currentTime);
              }}
              onPlay={() => setPlaying(true)}
              onPause={() => setPlaying(false)}
              onEnded={() => {
                setPlaying(false);
                setWatchedToEnd(true);
              }}
            />
            {!playing ? (
              <button
                type="button"
                aria-label={spanish ? "Reproducir" : "Play"}
                onClick={() => void videoRef.current?.play()}
                className="absolute left-1/2 top-1/2 grid h-16 w-16 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full bg-[var(--accent)] text-black"
              >
                <Play className="ml-1 h-7 w-7 fill-current" />
              </button>
            ) : null}
            {duration > 0 && !countEnabled ? (
              <div className="absolute inset-x-0 bottom-0 bg-black/80 px-4 py-3 text-center text-[13px] font-semibold text-white">
                {timelineIssue
                  ? (spanish ? "No cuentes. El tiempo del video no coincide." : "Do not count. The video timing does not match.")
                  : (spanish ? "Contexto solamente. No cuentes aquí." : "Context only. Do not count here.")}
              </div>
            ) : null}
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {[1, 2, 5].map((value) => (
              <button
                key={value}
                type="button"
                onClick={() => {
                  setSpeed(value);
                  if (videoRef.current) videoRef.current.playbackRate = value;
                }}
                className={`h-10 min-w-12 border px-3 text-[13px] font-semibold ${
                  speed === value
                    ? "border-[var(--accent)] bg-[var(--accent)] text-black"
                    : "border-[var(--border)]"
                }`}
              >
                {value}x
              </button>
            ))}
          </div>
        </div>

        <aside className="flex min-h-[300px] flex-col justify-between border border-[var(--border)] bg-[var(--panel)] p-5">
          <div>
            <div className="text-[11px] font-semibold uppercase text-[var(--text-dim)]">
              {spanish ? "Conteo" : "Count"}
            </div>
            <div className="mt-3 text-[72px] font-bold leading-none">
              {eventTimes.length}
            </div>
            <div className="mt-3 text-[12px] text-[var(--text-dim)]">
              {spanish ? `Intentos usados: ${attempts} de 3` : `Attempts used: ${attempts} of 3`}
            </div>
          </div>
          <div className="grid gap-2">
            <button
              type="button"
              onClick={markOutput}
              disabled={!countEnabled}
              className="flex h-20 items-center justify-center gap-2 bg-[var(--accent)] text-[20px] font-bold text-black disabled:bg-[var(--idle)] disabled:text-[var(--text-dim)]"
            >
              <Zap className="h-6 w-6 fill-current" />
              +1
            </button>
            <button
              type="button"
              onClick={() => setEventTimes((current) => current.slice(0, -1))}
              disabled={!eventTimes.length}
              className="flex h-11 items-center justify-center gap-2 border border-[var(--border)] text-[13px] font-semibold disabled:opacity-40"
            >
              <RotateCcw className="h-4 w-4" />
              {spanish ? "Deshacer" : "Undo"}
            </button>
            <button
              type="button"
              onClick={() => void submit()}
              disabled={!watchedToEnd || submitting || attempts >= 3 || timelineIssue}
              className="mt-2 flex h-12 items-center justify-center gap-2 bg-[var(--good)] text-[13px] font-semibold text-black disabled:opacity-40"
            >
              {submitting ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Check className="h-4 w-4" />
              )}
              {spanish ? "Enviar calificación" : "Submit qualification"}
            </button>
          </div>
        </aside>
      </div>
      {error ? (
        <div role="alert" className="mt-4 border-l-4 border-[var(--bad)] bg-[var(--bad-tint)] px-4 py-3 text-[13px] text-[var(--bad)]">
          {error}
        </div>
      ) : null}
      {timelineIssue && helpState !== "sent" ? (
        <button
          type="button"
          disabled={helpState === "sending"}
          onClick={() => void requestHelp()}
          className="mt-4 inline-flex h-11 items-center justify-center gap-2 bg-[var(--accent)] px-4 text-[13px] font-semibold text-black disabled:opacity-50"
        >
          <LifeBuoy className="h-4 w-4" />
          {spanish ? "Pedir ayuda" : "Request help"}
        </button>
      ) : null}
    </div>
  );
}
