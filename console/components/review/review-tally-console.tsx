"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  Check,
  CloudOff,
  LifeBuoy,
  LoaderCircle,
  LogOut,
  Play,
  RotateCcw,
  SkipBack,
  X,
  Zap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ReviewerOnboarding } from "@/components/review/reviewer-onboarding";
import { reviewStrings, type ReviewLanguage } from "@/lib/reviewStrings";
import { applyValidatedPlaybackRate } from "@/lib/reviewPlayback";
import {
  restoreReviewerSession,
  reviewerLifecycle,
  signInReviewer,
  signOutReviewer,
  workerRpc,
  type DurableReviewAction,
  type ReviewSession,
  type ReviewerLifecycle,
  type WorkerAssignment,
} from "@/lib/reviewSupabase";
import { cn, isTypingTarget } from "@/lib/utils";
import { reviewerDeviceHash } from "@/lib/reviewerDevice";

const appVersion = "worker-portal-v1";
const reviewSpeeds = [1, 2, 5] as const;
type ReviewSpeed = (typeof reviewSpeeds)[number];
type Screen = "auth" | "loading" | "onboarding" | "empty" | "tally" | "summary";
type SaveState = "saved" | "saving" | "offline";

type ActiveClick = {
  id: string;
  serverId?: string;
  videoSec: number;
};

type PendingAction = {
  clientActionId: string;
  type: "tally" | "undo";
  sourceTimeMs: number | null;
  undoesClientActionId: string | null;
  playbackRate: number;
};

type CoverageRange = { start_ms: number; end_ms: number };

function mergeCoverage(ranges: CoverageRange[], next: CoverageRange) {
  const sorted = [...ranges, next]
    .filter((range) => range.end_ms > range.start_ms)
    .sort((a, b) => a.start_ms - b.start_ms);
  const merged: CoverageRange[] = [];
  for (const range of sorted) {
    const prior = merged.at(-1);
    if (prior && range.start_ms <= prior.end_ms + 250) {
      prior.end_ms = Math.max(prior.end_ms, range.end_ms);
    } else {
      merged.push({ ...range });
    }
  }
  return merged.slice(-128);
}

function formatRange(assignment: WorkerAssignment, language: ReviewLanguage) {
  const locale = language === "es" ? "es-419" : "en-US";
  const timeZone = assignment.chunk.factoryTimezone || "UTC";
  const date = new Intl.DateTimeFormat(locale, {
    timeZone,
    weekday: "short",
    month: "short",
    day: "numeric",
  }).format(new Date(assignment.chunk.startIso));
  const time = new Intl.DateTimeFormat(locale, {
    timeZone,
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  return `${date} · ${time.format(new Date(assignment.chunk.startIso))}-${time.format(new Date(assignment.chunk.endIso))}`;
}

function formatVideoTime(seconds: number) {
  const total = Math.max(0, Math.floor(seconds));
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

function outboxKey(assignmentId: string) {
  return `factoryvision-review-outbox:${assignmentId}`;
}

function readOutbox(assignmentId: string): PendingAction[] {
  try {
    return JSON.parse(window.localStorage.getItem(outboxKey(assignmentId)) ?? "[]") as PendingAction[];
  } catch {
    return [];
  }
}

function writeOutbox(assignmentId: string, actions: PendingAction[]) {
  window.localStorage.setItem(outboxKey(assignmentId), JSON.stringify(actions));
}

function activeClicks(
  actions: DurableReviewAction[],
  pending: PendingAction[],
  sourceStartMs: number,
) {
  const undoneServerIds = new Set(
    actions.filter((action) => action.type === "undo").map((action) => action.undoesActionId),
  );
  const clicks: ActiveClick[] = actions
    .filter((action) => action.type === "tally" && !undoneServerIds.has(action.id))
    .map((action) => ({
      id: action.clientActionId,
      serverId: action.id,
      videoSec: Math.max(0, ((action.sourceTimeMs ?? sourceStartMs) - sourceStartMs) / 1000),
    }));

  for (const action of pending) {
    if (action.type === "tally") {
      clicks.push({
        id: action.clientActionId,
        videoSec: Math.max(0, ((action.sourceTimeMs ?? sourceStartMs) - sourceStartMs) / 1000),
      });
    } else {
      const index = clicks.findIndex((click) => click.id === action.undoesClientActionId);
      if (index >= 0) clicks.splice(index, 1);
    }
  }
  return clicks;
}

function submissionId(assignmentId: string) {
  const key = `factoryvision-review-submission:${assignmentId}`;
  const existing = window.localStorage.getItem(key);
  if (existing) return existing;
  const created = window.crypto.randomUUID();
  window.localStorage.setItem(key, created);
  return created;
}

function submissionCoverageKey(assignmentId: string) {
  return `factoryvision-review-submit-coverage:${assignmentId}`;
}

export function ReviewTallyConsole() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const flushActive = useRef(false);
  const heartbeatFailures = useRef(0);
  const coverageRanges = useRef<CoverageRange[]>([]);
  const coveragePreviousMs = useRef<number | null>(null);
  const coverageActiveStartedAt = useRef<number | null>(null);
  const coverageActiveMs = useRef(0);
  const pageEpoch = useRef("");
  const workSessionId = useRef<string | null>(null);
  const [session, setSession] = useState<ReviewSession | null>(null);
  const [lifecycle, setLifecycle] = useState<ReviewerLifecycle | null>(null);
  const [assignment, setAssignment] = useState<WorkerAssignment | null>(null);
  const [clicks, setClicks] = useState<ActiveClick[]>([]);
  const [screen, setScreen] = useState<Screen>("loading");
  const [language, setLanguage] = useState<ReviewLanguage>("en");
  const [speed, setSpeed] = useState<ReviewSpeed>(1);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [showProblems, setShowProblems] = useState(false);
  const [showZeroGuard, setShowZeroGuard] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [saveState, setSaveState] = useState<SaveState>("saved");
  const [pendingCount, setPendingCount] = useState(0);
  const [status, setStatus] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [authBusy, setAuthBusy] = useState(false);
  const [supportOpen, setSupportOpen] = useState(false);
  const [supportReason, setSupportReason] = useState("assignment");
  const [supportMessage, setSupportMessage] = useState("");
  const [supportBusy, setSupportBusy] = useState(false);

  const strings = reviewStrings[language];
  const progress = duration > 0 ? Math.min(1, currentTime / duration) : 0;
  const timeLeft = duration > 0 ? Math.ceil((duration - currentTime) / speed) : 0;

  const flushOutbox = useCallback(async (
    activeSession: ReviewSession,
    activeAssignment: WorkerAssignment,
  ) => {
    if (flushActive.current) return false;
    flushActive.current = true;
    setSaveState("saving");
    try {
      let pending = readOutbox(activeAssignment.id);
      while (pending.length) {
        const action = pending[0];
        await workerRpc(activeSession, "append_worker_action", {
          p_assignment_id: activeAssignment.id,
          p_lease_token: activeAssignment.leaseToken,
          p_client_action_id: action.clientActionId,
          p_action_type: action.type,
          p_source_time_ms: action.sourceTimeMs,
          p_undoes_client_action_id: action.undoesClientActionId,
          p_reason_code: null,
          p_playback_rate: action.playbackRate,
          p_app_version: appVersion,
        });
        pending = readOutbox(activeAssignment.id).filter(
          (queued) => queued.clientActionId !== action.clientActionId,
        );
        writeOutbox(activeAssignment.id, pending);
        setPendingCount(pending.length);
      }
      setSaveState("saved");
      setStatus(null);
      return true;
    } catch {
      setSaveState("offline");
      setPendingCount(readOutbox(activeAssignment.id).length);
      return false;
    } finally {
      flushActive.current = false;
    }
  }, []);

  const loadNext = useCallback(async (activeSession: ReviewSession) => {
    setScreen("loading");
    setStatus(null);
    try {
      const payload = await workerRpc<{ assignment: WorkerAssignment | null }>(
        activeSession,
        "claim_worker_assignment",
        { p_app_version: appVersion },
      );
      if (!payload.assignment) {
        setAssignment(null);
        setClicks([]);
        setScreen("empty");
        return;
      }
      const next = payload.assignment;
      pageEpoch.current = window.crypto.randomUUID();
      coverageRanges.current = next.coverage?.ranges ?? [];
      coveragePreviousMs.current = null;
      coverageActiveStartedAt.current = null;
      coverageActiveMs.current = next.coverage?.clientActiveMs ?? 0;
      const pending = readOutbox(next.id);
      setAssignment(next);
      setPendingCount(pending.length);
      setClicks(activeClicks(next.actions, pending, next.chunk.sourceStartMs));
      setCurrentTime(0);
      setDuration(0);
      setIsPlaying(false);
      setShowProblems(false);
      setShowZeroGuard(false);
      setScreen("tally");
      if (pending.length) void flushOutbox(activeSession, next);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Unable to load work.");
      setScreen("empty");
    }
  }, [flushOutbox]);

  const beginReviewer = useCallback(async (activeSession: ReviewSession) => {
    const state = await reviewerLifecycle("GET");
    setLifecycle(state);
    if (state.state === "active" && (state.isTestAccount || state.currentAal === "aal2")) {
      await workerRpc(activeSession, "worker_register_active_device", {
        p_device_id_hash: await reviewerDeviceHash(),
      });
      await loadNext(activeSession);
    } else {
      setScreen("onboarding");
    }
  }, [loadNext]);

  useEffect(() => {
    const savedLanguage = window.localStorage.getItem("factoryvision-review-language");
    if (savedLanguage === "es" || savedLanguage === "en") setLanguage(savedLanguage);
    void restoreReviewerSession().then((restored) => {
      if (!restored) {
        setScreen("auth");
        return;
      }
      setSession(restored);
      void beginReviewer(restored).catch((error) => {
        setStatus(error instanceof Error ? error.message : "Unable to load reviewer profile.");
        setScreen("auth");
      });
    });
  }, [beginReviewer]);

  useEffect(() => {
    if (!assignment || !session) return;
    const timer = window.setInterval(() => {
      void workerRpc(session, "heartbeat_worker_assignment", {
        p_assignment_id: assignment.id,
        p_lease_token: assignment.leaseToken,
      }).then(() => {
        heartbeatFailures.current = 0;
      }).catch(() => {
        heartbeatFailures.current += 1;
        if (heartbeatFailures.current >= 2) setSaveState("offline");
      });
    }, 30_000);
    return () => window.clearInterval(timer);
  }, [assignment, session]);

  useEffect(() => {
    if (!assignment || !session) return;
    let disposed = false;
    let timer: number | null = null;
    void reviewerDeviceHash()
      .then(async (deviceIdHash) => {
        const opened = await workerRpc<{ sessionId: string }>(
          session,
          "worker_touch_work_session",
          {
            p_session_id: workSessionId.current,
            p_device_id_hash: deviceIdHash,
            p_active_seconds_delta: 0,
          },
        );
        if (disposed) {
          await workerRpc(session, "worker_close_work_session", {
            p_session_id: opened.sessionId,
            p_close_reason: "screen_changed",
          }).catch(() => undefined);
          return;
        }
        workSessionId.current = opened.sessionId;
        timer = window.setInterval(() => {
          if (document.visibilityState !== "visible") return;
          void workerRpc(session, "worker_touch_work_session", {
            p_session_id: opened.sessionId,
            p_device_id_hash: deviceIdHash,
            p_active_seconds_delta: 30,
          }).catch(() => undefined);
        }, 30_000);
      })
      .catch(() => undefined);
    return () => {
      disposed = true;
      if (timer !== null) window.clearInterval(timer);
      const sessionId = workSessionId.current;
      workSessionId.current = null;
      if (sessionId) {
        void workerRpc(session, "worker_close_work_session", {
          p_session_id: sessionId,
          p_close_reason: "assignment_closed",
        }).catch(() => undefined);
      }
    };
  }, [assignment, session]);

  const saveCoverage = useCallback(async () => {
    if (!assignment || !session || !pageEpoch.current) return;
    const activeMs =
      coverageActiveMs.current +
      (coverageActiveStartedAt.current ? performance.now() - coverageActiveStartedAt.current : 0);
    await workerRpc(session, "save_worker_coverage", {
      p_assignment_id: assignment.id,
      p_lease_token: assignment.leaseToken,
      p_page_epoch: pageEpoch.current,
      p_ranges: coverageRanges.current,
      p_client_active_ms: Math.round(activeMs),
    });
  }, [assignment, session]);

  useEffect(() => {
    if (!assignment || !session) return;
    const timer = window.setInterval(() => void saveCoverage().catch(() => undefined), 5_000);
    return () => window.clearInterval(timer);
  }, [assignment, saveCoverage, session]);

  useEffect(() => {
    if (!assignment || !session) return;
    const timer = window.setInterval(() => {
      const video = videoRef.current;
      const position = video?.currentTime ?? 0;
      void workerRpc<{ mediaUrl: string }>(session, "authorize_worker_media", {
        p_assignment_id: assignment.id,
        p_lease_token: assignment.leaseToken,
      }).then((result) => {
        if (!video || !result.mediaUrl) return;
        const wasPlaying = !video.paused;
        video.src = result.mediaUrl;
        video.currentTime = position;
        if (wasPlaying) void video.play();
      }).catch(() => {
        setStatus(language === "es" ? "No se pudo renovar el video." : "Video access could not be refreshed.");
      });
    }, 8 * 60 * 1000);
    return () => window.clearInterval(timer);
  }, [assignment, language, session]);

  useEffect(() => {
    if (screen !== "empty" || !session) return;
    const timer = window.setInterval(() => {
      void loadNext(session);
    }, 5_000);
    return () => window.clearInterval(timer);
  }, [loadNext, screen, session]);

  useEffect(() => {
    if (!videoRef.current) return;
    const result = applyValidatedPlaybackRate(videoRef.current, speed);
    if (result.steppedDown) {
      setSpeed(1);
      setStatus(strings.speedSteppedDown);
    }
  }, [speed, assignment, strings.speedSteppedDown]);

  const queueAction = useCallback((action: PendingAction) => {
    if (!assignment || !session) return;
    const pending = [...readOutbox(assignment.id), action];
    writeOutbox(assignment.id, pending);
    setPendingCount(pending.length);
    setSaveState("saving");
    void flushOutbox(session, assignment);
  }, [assignment, flushOutbox, session]);

  const addCount = useCallback(() => {
    if (!assignment || !videoRef.current || screen !== "tally") return;
    const videoSec = Math.min(
      Math.max(0, (assignment.chunk.sourceEndMs - assignment.chunk.sourceStartMs - 1) / 1000),
      Math.max(0, videoRef.current.currentTime),
    );
    const clientActionId = window.crypto.randomUUID();
    setClicks((current) => [...current, { id: clientActionId, videoSec }]);
    queueAction({
      clientActionId,
      type: "tally",
      sourceTimeMs: assignment.chunk.sourceStartMs + Math.round(videoSec * 1000),
      undoesClientActionId: null,
      playbackRate: speed,
    });
  }, [assignment, queueAction, screen, speed]);

  const undo = useCallback(() => {
    const last = clicks.at(-1);
    if (!last) return;
    setClicks((current) => current.slice(0, -1));
    queueAction({
      clientActionId: window.crypto.randomUUID(),
      type: "undo",
      sourceTimeMs: null,
      undoesClientActionId: last.id,
      playbackRate: speed,
    });
  }, [clicks, queueAction, speed]);

  const backTen = useCallback(() => {
    if (videoRef.current) videoRef.current.currentTime = Math.max(0, videoRef.current.currentTime - 10);
  }, []);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (isTypingTarget(event.target)) return;
      if (event.code === "Space") {
        event.preventDefault();
        addCount();
      } else if (event.key.toLowerCase() === "z") {
        event.preventDefault();
        undo();
      } else if (event.key === "ArrowLeft") {
        event.preventDefault();
        backTen();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [addCount, backTen, undo]);

  async function submit(problemCode?: string) {
    if (!assignment || !session) return;
    setSubmitting(true);
    const saved = await flushOutbox(session, assignment);
    if (!saved && readOutbox(assignment.id).length) {
      setStatus(language === "es" ? "Sin conexión. Guarda los cambios antes de enviar." : "Offline. Save changes before submitting.");
      setSubmitting(false);
      return;
    }
    try {
      const coverageKey = submissionCoverageKey(assignment.id);
      if (!window.localStorage.getItem(coverageKey)) {
        await saveCoverage();
        window.localStorage.setItem(coverageKey, "saved");
      }
      const result = await workerRpc<{ totalCount: number | null; alreadySubmitted: boolean }>(
        session,
        "submit_worker_assignment_v2",
        {
          p_assignment_id: assignment.id,
          p_lease_token: assignment.leaseToken,
          p_idempotency_key: submissionId(assignment.id),
          p_result_type: problemCode ? "problem" : "counted",
          p_problem_code: problemCode ?? null,
          p_app_version: appVersion,
        },
      );
      window.localStorage.removeItem(outboxKey(assignment.id));
      setStatus(
        result.alreadySubmitted
          ? (language === "es" ? "Ya estaba enviado. Todo está guardado." : "Already submitted. Everything is saved.")
          : `${result.totalCount ?? 0} ${strings.confirmed}`,
      );
      await loadNext(session);
    } catch {
      setStatus(strings.confirmFailed);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleSignIn(event: React.FormEvent) {
    event.preventDefault();
    setAuthBusy(true);
    setStatus(null);
    try {
      const authenticated = await signInReviewer(email.trim(), password);
      setSession(authenticated);
      setPassword("");
      await beginReviewer(authenticated);
    } catch {
      setStatus(language === "es" ? "No se pudo iniciar sesión." : "Could not sign in.");
    } finally {
      setAuthBusy(false);
    }
  }

  function toggleLanguage(next: ReviewLanguage) {
    setLanguage(next);
    window.localStorage.setItem("factoryvision-review-language", next);
  }

  async function sendSupportRequest(event: React.FormEvent) {
    event.preventDefault();
    if (!assignment || !session || !supportMessage.trim()) return;
    setSupportBusy(true);
    try {
      await workerRpc(session, "worker_request_support", {
        p_assignment_id: assignment.id,
        p_reason_code: supportReason,
        p_message: supportMessage.trim(),
      });
      setSupportMessage("");
      setSupportOpen(false);
      setStatus(
        language === "es"
          ? "La solicitud de ayuda fue enviada."
          : "Your help request was sent.",
      );
    } catch {
      setStatus(
        language === "es"
          ? "No se pudo enviar la solicitud de ayuda."
          : "The help request could not be sent.",
      );
    } finally {
      setSupportBusy(false);
    }
  }

  const saveLabel = useMemo(() => {
    if (saveState === "saving") return language === "es" ? "Guardando..." : "Saving...";
    if (saveState === "offline") return language === "es" ? `${pendingCount} sin guardar` : `${pendingCount} unsaved`;
    return language === "es" ? "Guardado" : "Saved";
  }, [language, pendingCount, saveState]);

  if (screen === "auth") {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[var(--bg)] p-5 text-[var(--text)]" data-review-route="auth">
        <form className="w-full max-w-sm rounded-xl border border-[var(--border)] bg-[var(--panel)] p-6" onSubmit={handleSignIn}>
          <div className="mb-6 flex items-center justify-between">
            <div>
              <h1 className="text-[20px] font-semibold">{language === "es" ? "Trabajo de hoy" : "Today&apos;s work"}</h1>
              <p className="mt-1 text-[13px] text-[var(--text-dim)]">{language === "es" ? "Inicia sesión para continuar." : "Sign in to continue."}</p>
            </div>
            <LanguageControl language={language} onChange={toggleLanguage} />
          </div>
          <label className="block text-[12px] font-semibold text-[var(--text-mut)]">
            {language === "es" ? "Correo" : "Email"}
            <input className="mt-2 h-11 w-full rounded-lg border border-[var(--border)] bg-[var(--panel-2)] px-3 text-[14px] outline-none focus:border-[var(--accent)]" type="email" autoComplete="username" required value={email} onChange={(event) => setEmail(event.target.value)} />
          </label>
          <label className="mt-4 block text-[12px] font-semibold text-[var(--text-mut)]">
            {language === "es" ? "Contraseña" : "Password"}
            <input className="mt-2 h-11 w-full rounded-lg border border-[var(--border)] bg-[var(--panel-2)] px-3 text-[14px] outline-none focus:border-[var(--accent)]" type="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} />
          </label>
          {status && <div role="alert" className="mt-4 text-[13px] text-[var(--bad)]">{status}</div>}
          <Button type="submit" variant="primary" className="mt-5 h-12 w-full justify-center" disabled={authBusy}>
            {authBusy && <LoaderCircle className="h-4 w-4 animate-spin" />}
            {language === "es" ? "Iniciar sesión" : "Sign in"}
          </Button>
        </form>
      </main>
    );
  }

  if (screen === "loading") {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[var(--bg)] text-[var(--text)]" data-review-route="loading">
        <LoaderCircle className="h-6 w-6 animate-spin text-[var(--accent)]" />
      </main>
    );
  }

  if (screen === "onboarding" && lifecycle) {
    return (
      <ReviewerOnboarding
        lifecycle={lifecycle}
        onChange={(next) => {
          setLifecycle(next);
          if (next.state === "active" && session) void loadNext(session);
        }}
        onSignOut={() => {
          void signOutReviewer();
          setSession(null);
          setLifecycle(null);
          setScreen("auth");
        }}
      />
    );
  }

  if (screen === "empty" || !assignment) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[var(--bg)] p-5 text-[var(--text)]" data-review-route="empty">
        <div className="text-center">
          <Check className="mx-auto h-10 w-10 text-[var(--good)]" />
          <h1 className="mt-4 text-[22px] font-semibold">{language === "es" ? "No hay videos listos" : "No videos are ready"}</h1>
          <p className="mt-2 text-[14px] text-[var(--text-dim)]">{status ?? (language === "es" ? "Esta pantalla se actualizará automáticamente." : "This screen will update automatically.")}</p>
          <Button className="mt-5" variant="secondary" onClick={() => session && void loadNext(session)}>
            {language === "es" ? "Revisar ahora" : "Check now"}
          </Button>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[var(--bg)] p-4 text-[var(--text)] sm:p-5" data-review-route="ready" data-review-chunk={assignment.chunk.id} data-assignment-id={assignment.id}>
      <header className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-[var(--border)] pb-4">
        <div>
          <div className="text-[13px] font-semibold">{assignment.chunk.stationName} · {formatRange(assignment, language)} · {language === "es" ? "hora de la fábrica" : "factory time"}</div>
          <div className="mt-1 flex items-center gap-1.5 text-[12px] text-[var(--text-dim)]" data-testid="save-state">
            {saveState === "offline" ? <CloudOff className="h-3.5 w-3.5 text-[var(--bad)]" /> : saveState === "saving" ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5 text-[var(--good)]" />}
            {saveLabel}
            {saveState === "offline" && (
              <button className="ml-2 font-semibold text-[var(--accent)]" type="button" onClick={() => session && void flushOutbox(session, assignment)}>
                {language === "es" ? "Reintentar" : "Retry"}
              </button>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <LanguageControl language={language} onChange={toggleLanguage} />
          <button
            type="button"
            title={language === "es" ? "Obtener ayuda" : "Get help"}
            className="rounded-lg border border-[var(--border)] p-2 text-[var(--text-mut)]"
            onClick={() => setSupportOpen(true)}
          >
            <LifeBuoy className="h-4 w-4" />
          </button>
          <button type="button" title={language === "es" ? "Cerrar sesión" : "Sign out"} className="rounded-lg border border-[var(--border)] p-2 text-[var(--text-mut)]" onClick={() => { signOutReviewer(); setSession(null); setAssignment(null); setScreen("auth"); }}>
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </header>

      <div className="mb-4 flex items-center gap-2 rounded-lg border border-[rgba(232,116,47,.35)] bg-[rgba(232,116,47,.10)] px-4 py-3 text-[13px]">
        <Zap className="h-4 w-4 shrink-0 fill-[var(--accent)] text-[var(--accent)]" />
        <span className="font-semibold">{strings.instruction}</span>
      </div>

      <section className="grid min-w-0 gap-5 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0">
          <div className="relative aspect-video overflow-hidden rounded-lg bg-black ring-1 ring-[var(--border)]">
            <video ref={videoRef} src={assignment.chunk.mediaUrl} poster={assignment.chunk.posterUrl ?? undefined} className="h-full w-full bg-black object-contain" muted playsInline
              onLoadedMetadata={() => { if (!videoRef.current) return; setDuration(videoRef.current.duration); applyValidatedPlaybackRate(videoRef.current, speed); }}
              onTimeUpdate={() => {
                const video = videoRef.current;
                if (!video) return;
                setCurrentTime(video.currentTime);
                const sourceMs = assignment.chunk.sourceStartMs + Math.round(video.currentTime * 1000);
                const prior = coveragePreviousMs.current;
                if (prior !== null && sourceMs >= prior && sourceMs - prior <= 3_000) {
                  coverageRanges.current = mergeCoverage(coverageRanges.current, {
                    start_ms: prior,
                    end_ms: Math.min(assignment.chunk.sourceEndMs, sourceMs),
                  });
                }
                coveragePreviousMs.current = sourceMs;
              }}
              onPlay={() => {
                setIsPlaying(true);
                coverageActiveStartedAt.current = performance.now();
              }}
              onPause={() => {
                setIsPlaying(false);
                if (coverageActiveStartedAt.current) {
                  coverageActiveMs.current += performance.now() - coverageActiveStartedAt.current;
                  coverageActiveStartedAt.current = null;
                }
              }}
              onEnded={() => { setIsPlaying(false); setScreen("summary"); }} />
            {!isPlaying && (
              <button type="button" className="absolute left-1/2 top-1/2 flex h-20 w-20 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full bg-[var(--accent)] text-white" aria-label={strings.play} onClick={() => void videoRef.current?.play()}>
                <Play className="ml-1 h-9 w-9 fill-white" />
              </button>
            )}
          </div>
          <div className="mt-3 h-1 overflow-hidden rounded-full bg-white/[.08]"><div className="h-full bg-[var(--accent)]" style={{ width: `${progress * 100}%` }} /></div>
          <div className="mt-2 flex justify-between text-[12px] tabular-nums text-[var(--text-dim)]">
            <span>{formatVideoTime(currentTime)} / {formatVideoTime(duration)}</span>
            <span>~{formatVideoTime(timeLeft)} {strings.leftAt} {speed}x</span>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {reviewSpeeds.map((value) => <button key={value} type="button" className={cn("rounded-lg px-3 py-2 text-[13px] font-semibold", speed === value ? "bg-[var(--accent)] text-[#11100d]" : "border border-[var(--border)] bg-[var(--panel-2)] text-[var(--text-mut)]")} onClick={() => setSpeed(value)}>{value}x</button>)}
            <Button type="button" variant="secondary" onClick={backTen}><SkipBack className="h-4 w-4" />{strings.back10}</Button>
            <Button type="button" variant="secondary" onClick={() => setScreen("summary")}>{strings.endChunk}</Button>
            <div className="relative">
              <Button type="button" variant="secondary" onClick={() => setShowProblems((value) => !value)}><AlertTriangle className="h-4 w-4" />{strings.reportProblem}</Button>
              {showProblems && (
                <div className="absolute bottom-full left-0 z-10 mb-2 w-56 rounded-lg border border-[var(--border)] bg-[var(--panel)] p-2 shadow-xl">
                  {([["video-wont-play", strings.videoWontPlay], ["camera-blocked", strings.cameraBlocked], ["timestamp-jump", strings.timestampJump], ["wrong-station", strings.wrongStation], ["no-usable-footage", strings.noUsableFootage], ["other", strings.otherProblem]] as const).map(([code, label]) =>
                    <button key={code} type="button" className="block w-full rounded-lg px-2 py-2 text-left text-[13px] hover:bg-white/[.04]" disabled={submitting} onClick={() => void submit(code)}>{label}</button>)}
                </div>
              )}
            </div>
          </div>
        </div>

        <aside className="flex min-h-[410px] min-w-0 flex-col justify-between rounded-xl border border-[var(--border)] bg-[var(--panel)] p-5">
          {screen === "summary" ? (
            <>
              <div>
                <div className="text-[13px] font-semibold text-[var(--text-mut)]">{strings.summaryPrefix} {clicks.length} {strings.summaryIn} {formatRange(assignment, language)}</div>
                <div className="mt-4 max-h-[290px] space-y-2 overflow-y-auto">
                  {clicks.map((click, index) => <button key={click.id} type="button" className="flex w-full justify-between rounded-lg border border-[var(--border-soft)] px-3 py-2 text-[13px]" onClick={() => { if (videoRef.current) videoRef.current.currentTime = Math.max(0, click.videoSec - 5); setScreen("tally"); }}><span>#{index + 1}</span><span>{formatVideoTime(click.videoSec)}</span></button>)}
                  {!clicks.length && <div className="text-[13px] text-[var(--text-dim)]">{strings.noClicks}</div>}
                </div>
              </div>
              <div className="grid gap-2">
                {showZeroGuard ? (
                  <div className="rounded-lg border border-[rgba(232,116,47,.35)] bg-[rgba(232,116,47,.10)] p-3 text-[13px]">
                    <div>{strings.zeroGuard}</div>
                    <div className="mt-3 flex gap-2"><Button className="flex-1 justify-center" variant="primary" disabled={submitting} onClick={() => void submit()}>{strings.yes}</Button><Button className="flex-1 justify-center" variant="secondary" onClick={() => setShowZeroGuard(false)}>{strings.no}</Button></div>
                  </div>
                ) : <Button className="h-14 justify-center text-[16px]" variant="primary" disabled={submitting || saveState !== "saved"} onClick={() => clicks.length ? void submit() : setShowZeroGuard(true)}>{strings.confirm}</Button>}
                <Button className="h-12 justify-center" variant="secondary" onClick={() => setScreen("tally")}>{strings.redo}</Button>
              </div>
            </>
          ) : (
            <>
              <div><div className="text-[11px] font-semibold uppercase text-[var(--text-dim)]">{strings.runningTally}</div><div data-testid="running-tally" className="mt-3 text-[96px] font-bold leading-none">{clicks.length}</div></div>
              <div className="grid gap-3">
                <button type="button" className="flex h-28 items-center justify-center gap-3 rounded-xl bg-[var(--accent)] text-[28px] font-black text-[#11100d]" onClick={addCount}><Zap className="h-8 w-8 fill-[#11100d]" />{strings.countButton}</button>
                <Button className="h-12 justify-center" type="button" variant="secondary" onClick={undo}><RotateCcw className="h-4 w-4" />{strings.undo}</Button>
                <div className="text-center text-[12px] text-[var(--text-dim)]">Space · Z · ←</div>
              </div>
            </>
          )}
          {status && <div role="status" className="mt-4 border-t border-[var(--border)] pt-3 text-[13px] text-[var(--text-mut)]">{status}</div>}
        </aside>
      </section>
      {supportOpen ? (
        <div
          className="fixed inset-0 z-50 grid place-items-center bg-black/75 p-4"
          role="dialog"
          aria-modal="true"
          aria-label={language === "es" ? "Obtener ayuda" : "Get help"}
        >
          <form
            className="w-full max-w-md border border-[var(--border)] bg-[var(--panel)]"
            onSubmit={sendSupportRequest}
          >
            <div className="flex items-center justify-between border-b border-[var(--border)] px-5 py-4">
              <div className="flex items-center gap-2 text-[14px] font-semibold">
                <LifeBuoy className="h-4 w-4 text-[var(--accent)]" />
                {language === "es" ? "Obtener ayuda" : "Get help"}
              </div>
              <button
                type="button"
                title={language === "es" ? "Cerrar" : "Close"}
                onClick={() => setSupportOpen(false)}
                className="p-2"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="grid gap-4 p-5">
              <label className="grid gap-2 text-[12px] text-[var(--text-mut)]">
                {language === "es" ? "Tema" : "Topic"}
                <select
                  value={supportReason}
                  onChange={(event) => setSupportReason(event.target.value)}
                  className="h-11 border border-[var(--border)] bg-[var(--bg)] px-3 text-[14px]"
                >
                  <option value="assignment">{language === "es" ? "Esta tarea" : "This assignment"}</option>
                  <option value="account">{language === "es" ? "Mi cuenta" : "My account"}</option>
                  <option value="mfa">{language === "es" ? "Código de seguridad" : "Security code"}</option>
                  <option value="payment">{language === "es" ? "Pago" : "Payment"}</option>
                  <option value="privacy">{language === "es" ? "Privacidad" : "Privacy"}</option>
                  <option value="other">{language === "es" ? "Otro" : "Other"}</option>
                </select>
              </label>
              <label className="grid gap-2 text-[12px] text-[var(--text-mut)]">
                {language === "es" ? "¿Qué necesitas?" : "What do you need?"}
                <textarea
                  required
                  maxLength={2000}
                  rows={5}
                  value={supportMessage}
                  onChange={(event) => setSupportMessage(event.target.value)}
                  className="resize-none border border-[var(--border)] bg-[var(--bg)] p-3 text-[14px]"
                />
              </label>
            </div>
            <div className="flex justify-end gap-2 border-t border-[var(--border)] px-5 py-4">
              <Button type="button" variant="secondary" onClick={() => setSupportOpen(false)}>
                {language === "es" ? "Cancelar" : "Cancel"}
              </Button>
              <Button type="submit" variant="primary" disabled={supportBusy}>
                {language === "es" ? "Enviar" : "Send"}
              </Button>
            </div>
          </form>
        </div>
      ) : null}
    </main>
  );
}

function LanguageControl({ language, onChange }: { language: ReviewLanguage; onChange: (language: ReviewLanguage) => void }) {
  return (
    <div className="flex rounded-lg border border-[var(--border)] bg-[var(--panel-2)] p-1" aria-label="Language">
      {(["en", "es"] as const).map((value) => <button key={value} type="button" className={cn("rounded px-2 py-1 text-[12px] font-semibold uppercase", language === value ? "bg-[var(--accent)] text-[#11100d]" : "text-[var(--text-mut)]")} onClick={() => onChange(value)}>{value}</button>)}
    </div>
  );
}
