"use client";

import { useEffect, useRef, useState } from "react";
import {
  Check,
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

type Qualification = {
  chunkId: string;
  stationName: string;
  sourceStartMs: number;
  sourceEndMs: number;
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
    setEventTimes((current) => [
      ...current,
      qualification.sourceStartMs + Math.round(videoRef.current!.currentTime * 1000),
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
    } catch {
      setError(
        spanish
          ? "No se pudo enviar la calificación. Inténtalo otra vez."
          : "The qualification could not be submitted. Try again.",
      );
    } finally {
      setSubmitting(false);
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
              className="flex h-20 items-center justify-center gap-2 bg-[var(--accent)] text-[20px] font-bold text-black"
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
              disabled={!watchedToEnd || submitting || attempts >= 3}
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
    </div>
  );
}
