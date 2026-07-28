"use client";

import { type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  CalendarDays,
  Check,
  CheckCircle2,
  CirclePlay,
  Clock3,
  CloudOff,
  LifeBuoy,
  LoaderCircle,
  LogOut,
  Pause,
  Play,
  RotateCcw,
  SkipBack,
  Trash2,
  X,
  Zap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ReviewerOnboarding } from "@/components/review/reviewer-onboarding";
import { reviewStrings, type ReviewLanguage } from "@/lib/reviewStrings";
import { applyValidatedPlaybackRate } from "@/lib/reviewPlayback";
import {
  requestReviewerSignInLink,
  restoreReviewerSession,
  reviewerLifecycle,
  signOutReviewer,
  workerRpc,
  type DurableReviewAction,
  type ReviewSession,
  type ReviewerLifecycle,
  type WorkerAssignment,
} from "@/lib/reviewSupabase";
import { cn, isTypingTarget } from "@/lib/utils";
import { reviewerDeviceHash } from "@/lib/reviewerDevice";
import {
  isCountableSourceTime,
  sourceTimeToVideoSec,
  timelineDurationMatches,
  videoTimeToSourceMs,
  type ReviewTimeline,
} from "@/lib/reviewTimeline";

const appVersion = "worker-portal-v2";
const reviewSpeeds = [1, 2, 5] as const;
type ReviewSpeed = (typeof reviewSpeeds)[number];
type Screen = "auth" | "loading" | "onboarding" | "today" | "tally" | "summary";
type SaveState = "saved" | "saving" | "offline";
type WorkSummary = {
  ready: number;
  inProgress: number;
  completedToday: number;
  observedAt: string;
};

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

function assignmentTimeline(assignment: WorkerAssignment): ReviewTimeline {
  return {
    canonicalStartMs: assignment.chunk.sourceStartMs,
    canonicalEndMs: assignment.chunk.sourceEndMs,
    renditionStartMs:
      assignment.chunk.renditionSourceStartMs ?? assignment.chunk.sourceStartMs,
    renditionEndMs:
      assignment.chunk.renditionSourceEndMs ?? assignment.chunk.sourceEndMs,
  };
}

function isAssignmentUnavailable(error: unknown) {
  const message = error instanceof Error ? error.message : String(error);
  return /lease|assignment.*(?:unavailable|expired|not submittable)|access disabled/i.test(message);
}

function isCoverageIncomplete(error: unknown) {
  const message = error instanceof Error ? error.message : String(error);
  return /coverage|98 percent|faster than the enabled playback speed/i.test(message);
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

export function ReviewTallyConsole() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const flushActive = useRef(false);
  const heartbeatFailures = useRef(0);
  const coverageRanges = useRef<CoverageRange[]>([]);
  const coveragePreviousMs = useRef<number | null>(null);
  const coverageActiveStartedAt = useRef<number | null>(null);
  const coverageActiveMs = useRef(0);
  const resumeSourceMs = useRef(0);
  const appliedInitialResume = useRef(false);
  const pageEpoch = useRef("");
  const workSessionId = useRef<string | null>(null);
  const clicksRef = useRef<ActiveClick[]>([]);
  const [session, setSession] = useState<ReviewSession | null>(null);
  const [lifecycle, setLifecycle] = useState<ReviewerLifecycle | null>(null);
  const [assignment, setAssignment] = useState<WorkerAssignment | null>(null);
  const [workSummary, setWorkSummary] = useState<WorkSummary | null>(null);
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
  const [authBusy, setAuthBusy] = useState(false);
  const [authLinkSent, setAuthLinkSent] = useState(false);
  const [supportOpen, setSupportOpen] = useState(false);
  const [supportReason, setSupportReason] = useState("assignment");
  const [supportMessage, setSupportMessage] = useState("");
  const [supportBusy, setSupportBusy] = useState(false);
  const [pendingProblem, setPendingProblem] = useState<{ code: string; label: string } | null>(null);
  const [assignmentUnavailable, setAssignmentUnavailable] = useState(false);
  const [videoIssue, setVideoIssue] = useState(false);
  const [timelineIssue, setTimelineIssue] = useState(false);

  const strings = reviewStrings[language];
  const progress = duration > 0 ? Math.min(1, currentTime / duration) : 0;
  const timeLeft = duration > 0 ? Math.ceil((duration - currentTime) / speed) : 0;
  const currentSourceTimeMs =
    assignment && duration > 0
      ? videoTimeToSourceMs(
        currentTime,
        duration,
        assignmentTimeline(assignment),
      )
      : null;
  const countInputEnabled =
    assignment !== null &&
    !timelineIssue &&
    currentSourceTimeMs !== null &&
    isCountableSourceTime(currentSourceTimeMs, assignmentTimeline(assignment));

  const refreshWorkSummary = useCallback(async (
    activeSession: ReviewSession,
    options: { showToday?: boolean } = {},
  ) => {
    const summary = await workerRpc<WorkSummary>(
      activeSession,
      "worker_daily_progress",
      {},
    );
    setWorkSummary(summary);
    if (options.showToday) setScreen("today");
    return summary;
  }, []);

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
    } catch (error) {
      setSaveState("offline");
      setPendingCount(readOutbox(activeAssignment.id).length);
      if (isAssignmentUnavailable(error)) {
        setAssignmentUnavailable(true);
        setStatus(
          language === "es"
            ? "Esta tarea venció. Vuelve a Trabajo de hoy para continuar."
            : "This task expired. Return to Today's work to continue.",
        );
      }
      return false;
    } finally {
      flushActive.current = false;
    }
  }, [language]);

  const retryConnection = useCallback(async () => {
    if (!session || !assignment) return;
    if (readOutbox(assignment.id).length) {
      await flushOutbox(session, assignment);
      return;
    }
    setSaveState("saving");
    try {
      await workerRpc(session, "heartbeat_worker_assignment", {
        p_assignment_id: assignment.id,
        p_lease_token: assignment.leaseToken,
      });
      heartbeatFailures.current = 0;
      setSaveState("saved");
      setStatus(null);
    } catch {
      setSaveState("offline");
    }
  }, [assignment, flushOutbox, session]);

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
        clicksRef.current = [];
        setClicks([]);
        await refreshWorkSummary(activeSession, { showToday: true });
        return;
      }
      const next = payload.assignment;
      pageEpoch.current = window.crypto.randomUUID();
      coverageRanges.current = next.coverage?.ranges ?? [];
      coveragePreviousMs.current = null;
      coverageActiveStartedAt.current = null;
      coverageActiveMs.current = next.coverage?.clientActiveMs ?? 0;
      const furthestCoveredMs = Math.max(
        next.chunk.sourceStartMs,
        ...(next.coverage?.ranges ?? []).map((range) => range.end_ms),
      );
      resumeSourceMs.current = furthestCoveredMs;
      appliedInitialResume.current = false;
      const pending = readOutbox(next.id);
      const restoredClicks = activeClicks(
        next.actions,
        pending,
        next.chunk.sourceStartMs,
      );
      setAssignment(next);
      setPendingCount(pending.length);
      clicksRef.current = restoredClicks;
      setClicks(restoredClicks);
      setCurrentTime(0);
      setDuration(0);
      setIsPlaying(false);
      setShowProblems(false);
      setShowZeroGuard(false);
      setPendingProblem(null);
      setAssignmentUnavailable(false);
      setVideoIssue(false);
      setTimelineIssue(false);
      setScreen("tally");
      if (pending.length) void flushOutbox(activeSession, next);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Unable to load work.");
      setScreen("today");
    }
  }, [flushOutbox, refreshWorkSummary]);

  const beginReviewer = useCallback(async (activeSession: ReviewSession) => {
    const state = await reviewerLifecycle("GET");
    setLifecycle(state);
    const savedLanguage = window.localStorage.getItem("factoryvision-review-language");
    if (savedLanguage !== "en" && savedLanguage !== "es") {
      setLanguage(state.locale === "es-419" ? "es" : "en");
    }
    if (state.state === "active" && (state.isTestAccount || state.currentAal === "aal2")) {
      await workerRpc(activeSession, "worker_register_active_device", {
        p_device_id_hash: await reviewerDeviceHash(),
      });
      await refreshWorkSummary(activeSession, { showToday: true });
    } else {
      setScreen("onboarding");
    }
  }, [refreshWorkSummary]);

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
        if (readOutbox(assignment.id).length === 0) setSaveState("saved");
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

  const refreshMedia = useCallback(async () => {
    if (!assignment || !session) return;
    const video = videoRef.current;
    const position = video?.currentTime ?? 0;
    try {
      const result = await workerRpc<{ mediaUrl: string }>(session, "authorize_worker_media", {
        p_assignment_id: assignment.id,
        p_lease_token: assignment.leaseToken,
      });
      if (!video || !result.mediaUrl) return;
      const wasPlaying = !video.paused;
      video.src = result.mediaUrl;
      video.currentTime = position;
      setVideoIssue(false);
      setStatus(null);
      if (wasPlaying) void video.play();
    } catch {
      video?.pause();
      setVideoIssue(true);
      setStatus(
        language === "es"
          ? "El video necesita una conexión nueva."
          : "The video needs a new connection.",
      );
    }
  }, [assignment, language, session]);

  useEffect(() => {
    if (!assignment || !session) return;
    const timer = window.setInterval(() => {
      void refreshMedia();
    }, 8 * 60 * 1000);
    return () => window.clearInterval(timer);
  }, [assignment, refreshMedia, session]);

  useEffect(() => {
    if (screen !== "today" || !session) return;
    const timer = window.setInterval(() => {
      void refreshWorkSummary(session).catch(() => undefined);
    }, 5_000);
    return () => window.clearInterval(timer);
  }, [refreshWorkSummary, screen, session]);

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
    const video = videoRef.current;
    const timeline = assignmentTimeline(assignment);
    if (!timelineDurationMatches(video.duration, timeline)) return;
    const sourceTimeMs = videoTimeToSourceMs(
      video.currentTime,
      video.duration,
      timeline,
    );
    if (!isCountableSourceTime(sourceTimeMs, timeline)) return;
    const videoSec = Math.max(0, video.currentTime);
    const clientActionId = window.crypto.randomUUID();
    const nextClicks = [...clicksRef.current, { id: clientActionId, videoSec }];
    clicksRef.current = nextClicks;
    setClicks(nextClicks);
    queueAction({
      clientActionId,
      type: "tally",
      sourceTimeMs,
      undoesClientActionId: null,
      playbackRate: speed,
    });
  }, [assignment, queueAction, screen, speed]);

  const undo = useCallback(() => {
    const last = clicksRef.current.at(-1);
    if (!last) return;
    const nextClicks = clicksRef.current.slice(0, -1);
    clicksRef.current = nextClicks;
    setClicks(nextClicks);
    queueAction({
      clientActionId: window.crypto.randomUUID(),
      type: "undo",
      sourceTimeMs: null,
      undoesClientActionId: last.id,
      playbackRate: speed,
    });
  }, [queueAction, speed]);

  const removeClick = useCallback((click: ActiveClick) => {
    const nextClicks = clicksRef.current.filter(
      (candidate) => candidate.id !== click.id,
    );
    clicksRef.current = nextClicks;
    setClicks(nextClicks);
    queueAction({
      clientActionId: window.crypto.randomUUID(),
      type: "undo",
      sourceTimeMs: null,
      undoesClientActionId: click.id,
      playbackRate: speed,
    });
  }, [queueAction, speed]);

  const backTen = useCallback(() => {
    if (videoRef.current) videoRef.current.currentTime = Math.max(0, videoRef.current.currentTime - 10);
  }, []);

  const togglePlayback = useCallback(() => {
    const video = videoRef.current;
    if (!video || screen !== "tally") return;
    if (video.paused) {
      void video.play();
    } else {
      video.pause();
    }
  }, [screen]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (isTypingTarget(event.target)) return;
      if (event.repeat) return;
      if (event.key.toLowerCase() === "j") {
        event.preventDefault();
        addCount();
      } else if (event.key.toLowerCase() === "z") {
        event.preventDefault();
        undo();
      } else if (event.code === "Space") {
        event.preventDefault();
        togglePlayback();
      } else if (event.key === "ArrowLeft") {
        event.preventDefault();
        backTen();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [addCount, backTen, togglePlayback, undo]);

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
      await saveCoverage();
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
      setAssignment(null);
      clicksRef.current = [];
      setClicks([]);
      await refreshWorkSummary(session);
      setStatus(
        result.alreadySubmitted
          ? (language === "es" ? "Ya estaba enviado. Todo está guardado." : "Already submitted. Everything is saved.")
          : language === "es"
            ? `Video enviado. ${result.totalCount ?? 0} piezas guardadas.`
            : `Video submitted. ${result.totalCount ?? 0} outputs saved.`,
      );
      setScreen("today");
    } catch (error) {
      if (isAssignmentUnavailable(error)) {
        setAssignmentUnavailable(true);
        setStatus(
          language === "es"
            ? "Esta tarea venció. Vuelve a Trabajo de hoy para continuar."
            : "This task expired. Return to Today's work to continue.",
        );
      } else if (isCoverageIncomplete(error)) {
        setScreen("tally");
        setStatus(
          language === "es"
            ? "Mira todo el video antes de enviar."
            : "Watch the entire video before submitting.",
        );
      } else {
        setStatus(strings.confirmFailed);
      }
    } finally {
      setSubmitting(false);
    }
  }

  async function handleSignIn(event: React.FormEvent) {
    event.preventDefault();
    setAuthBusy(true);
    setAuthLinkSent(false);
    setStatus(null);
    try {
      await requestReviewerSignInLink(email.trim(), language);
      setAuthLinkSent(true);
      setStatus(
        language === "es"
          ? "Revisa tu correo y abre el enlace de FactoryVision."
          : "Check your email and open the FactoryVision sign-in link.",
      );
    } catch (error) {
      setStatus(
        error instanceof Error
          ? error.message
          : language === "es"
            ? "No se pudo enviar el enlace."
            : "Could not send the sign-in link.",
      );
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
    if (!session || !supportMessage.trim()) return;
    setSupportBusy(true);
    try {
      await workerRpc(session, "worker_request_support", {
        p_assignment_id: assignment?.id ?? null,
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

  const supportDialog = supportOpen ? (
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
  ) : null;

  if (screen === "auth") {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[var(--bg)] p-5 text-[var(--text)]" data-review-route="auth">
        <form className="w-full max-w-sm rounded-xl border border-[var(--border)] bg-[var(--panel)] p-6" onSubmit={handleSignIn}>
          <div className="mb-6 flex items-center justify-between">
            <div>
              <h1 className="text-[20px] font-semibold">
                {language === "es" ? "Trabajo de hoy" : "Today's work"}
              </h1>
              <p className="mt-1 text-[13px] text-[var(--text-dim)]">
                {language === "es"
                  ? "Escribe tu correo. No necesitas contraseña."
                  : "Enter your email. No password needed."}
              </p>
            </div>
            <LanguageControl language={language} onChange={toggleLanguage} />
          </div>
          <label className="block text-[12px] font-semibold text-[var(--text-mut)]">
            {language === "es" ? "Correo" : "Email"}
            <input className="mt-2 h-11 w-full rounded-lg border border-[var(--border)] bg-[var(--panel-2)] px-3 text-[14px] outline-none focus:border-[var(--accent)]" type="email" autoComplete="username" required value={email} onChange={(event) => setEmail(event.target.value)} />
          </label>
          {status && (
            <div
              role={authLinkSent ? "status" : "alert"}
              className={`mt-4 text-[13px] ${authLinkSent ? "text-[var(--good)]" : "text-[var(--bad)]"}`}
            >
              {status}
            </div>
          )}
          <Button type="submit" variant="primary" className="mt-5 h-12 w-full justify-center" disabled={authBusy}>
            {authBusy && <LoaderCircle className="h-4 w-4 animate-spin" />}
            {language === "es" ? "Enviarme un enlace" : "Email me a sign-in link"}
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

  if (screen === "onboarding" && lifecycle && session) {
    return (
      <ReviewerOnboarding
        lifecycle={lifecycle}
        session={session}
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

  if (screen === "today") {
    const ready = workSummary?.ready ?? 0;
    const inProgress = workSummary?.inProgress ?? 0;
    const completedToday = workSummary?.completedToday ?? 0;
    const hasWork = ready > 0 || inProgress > 0;
    return (
      <main className="min-h-screen bg-[var(--bg)] text-[var(--text)]" data-review-route="today">
        <WorkerHeader
          language={language}
          onLanguageChange={toggleLanguage}
          onHelp={() => {
            setSupportReason("account");
            setSupportOpen(true);
          }}
          onSignOut={() => {
            void signOutReviewer();
            setSession(null);
            setWorkSummary(null);
            setScreen("auth");
          }}
        />
        <section className="mx-auto flex min-h-[calc(100vh-73px)] w-full max-w-4xl flex-col items-center px-5 pb-10 pt-[clamp(56px,10vh,104px)] text-center">
          <h1 className="text-[34px] font-semibold">{language === "es" ? "Trabajo de hoy" : "Today's work"}</h1>
          <div className="mt-2 flex items-center gap-2 text-[14px] text-[var(--text-dim)]">
            <CalendarDays className="h-4 w-4" />
            {formatCurrentDate(language)}
          </div>

          <div className={cn(
            "mt-7 flex items-center gap-2 text-[18px] font-medium",
            hasWork ? "text-[var(--good)]" : "text-[var(--text-mut)]",
          )}>
            {hasWork ? <CirclePlay className="h-5 w-5" /> : <CheckCircle2 className="h-5 w-5" />}
            {inProgress > 0
              ? (language === "es" ? "Tienes un video en curso" : "You have a video in progress")
              : ready > 0
                ? language === "es"
                  ? `${ready} ${ready === 1 ? "video está listo" : "videos están listos"}`
                  : `${ready} ${ready === 1 ? "video is ready" : "videos are ready"}`
                : (language === "es" ? "No hay videos listos" : "No videos are ready")}
          </div>

          {hasWork ? (
            <button
              type="button"
              className="mt-8 flex h-20 w-full max-w-lg items-center justify-center gap-3 rounded-lg bg-[var(--accent)] px-6 text-[21px] font-bold text-[#11100d] transition-colors hover:bg-[var(--accent-hi)]"
              onClick={() => session && void loadNext(session)}
            >
              <Play className="h-6 w-6 fill-current" />
              {inProgress > 0
                ? (language === "es" ? "Continuar video" : "Resume video")
                : (language === "es" ? "Comenzar siguiente video" : "Start next video")}
            </button>
          ) : null}

          <div className="mt-9 grid w-full grid-cols-3 divide-x divide-[var(--border)] rounded-lg border border-[var(--border)] bg-[var(--panel)]">
            <WorkMetric
              label={language === "es" ? "Listos" : "Ready"}
              value={ready}
              icon={<CirclePlay className="h-5 w-5" />}
            />
            <WorkMetric
              label={language === "es" ? "En curso" : "In progress"}
              value={inProgress}
              icon={<Clock3 className="h-5 w-5" />}
            />
            <WorkMetric
              label={language === "es" ? "Completados hoy" : "Completed today"}
              value={completedToday}
              testId="completed-today"
              icon={<CheckCircle2 className="h-5 w-5" />}
            />
          </div>

          <p className="mt-8 text-[14px] text-[var(--text-dim)]">
            {language === "es"
              ? "Los videos nuevos aparecen aquí automáticamente."
              : "New videos appear here automatically."}
          </p>
          {status ? (
            <div role="status" className="mt-5 rounded-lg border border-[var(--border)] bg-[var(--panel)] px-4 py-3 text-[13px] text-[var(--text-mut)]">
              {status}
            </div>
          ) : null}
        </section>
        {supportDialog}
      </main>
    );
  }

  if (!assignment) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[var(--bg)] text-[var(--text)]" data-review-route="loading">
        <LoaderCircle className="h-6 w-6 animate-spin text-[var(--accent)]" />
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[var(--bg)] text-[var(--text)]" data-review-route="ready" data-review-chunk={assignment.chunk.id} data-assignment-id={assignment.id}>
      <WorkerHeader
        language={language}
        onLanguageChange={toggleLanguage}
        onHelp={() => {
          setSupportReason("assignment");
          setSupportOpen(true);
        }}
        onSignOut={() => {
          void signOutReviewer();
          setSession(null);
          setAssignment(null);
          setScreen("auth");
        }}
      />
      <div className="mx-auto w-full max-w-[1240px] px-4 pb-5 pt-4 sm:px-5">
        <div className="mb-3 grid gap-2 rounded-lg border border-[var(--border)] bg-[var(--panel)] px-4 py-3 text-[13px] sm:grid-cols-[1fr_auto_auto_auto] sm:items-center sm:gap-5">
          <div className="font-semibold">{assignment.chunk.stationName}</div>
          <div className="flex items-center gap-2 text-[var(--text-mut)]">
            <CalendarDays className="h-4 w-4" />
            {formatRange(assignment, language)}
          </div>
          <div className="flex items-center gap-2 text-[var(--text-mut)]">
            <Clock3 className="h-4 w-4" />
            {language === "es" ? "Hora de la fábrica" : "Factory time"}
          </div>
          <div className="text-[12px] font-semibold text-[var(--text-dim)]">
            {language === "es" ? "Tarea" : "Task"} #{assignment.id.slice(0, 8)}
          </div>
        </div>

        <div className="mb-3 flex items-start gap-2 px-1 text-[13px] leading-5 text-[var(--text-mut)]">
          <Zap className="mt-0.5 h-4 w-4 shrink-0 fill-[var(--accent)] text-[var(--accent)]" />
          <span>{strings.instruction}</span>
        </div>

        <section className="grid min-w-0 gap-4 lg:grid-cols-[minmax(0,1fr)_286px]">
        <div className="min-w-0">
          <div className="relative aspect-video overflow-hidden rounded-lg bg-black ring-1 ring-[var(--border)]">
            <video ref={videoRef} src={assignment.chunk.mediaUrl} poster={assignment.chunk.posterUrl ?? undefined} className="h-full w-full bg-black object-contain" muted playsInline
              onLoadedMetadata={() => {
                const video = videoRef.current;
                if (!video) return;
                setDuration(video.duration);
                const validTimeline = timelineDurationMatches(
                  video.duration,
                  assignmentTimeline(assignment),
                );
                setTimelineIssue(!validTimeline);
                if (!validTimeline) {
                  setStatus(
                    language === "es"
                      ? "No se pudo verificar el tiempo del video. Repórtalo en lugar de contar."
                      : "Video timing could not be verified. Report this video instead of counting.",
                  );
                }
                if (!appliedInitialResume.current) {
                  appliedInitialResume.current = true;
                  const resumeSeconds = sourceTimeToVideoSec(
                    resumeSourceMs.current,
                    video.duration,
                    assignmentTimeline(assignment),
                  );
                  video.currentTime = Math.min(
                    resumeSeconds,
                    Math.max(0, video.duration - 0.1),
                  );
                }
                applyValidatedPlaybackRate(video, speed);
              }}
              onTimeUpdate={() => {
                const video = videoRef.current;
                if (!video) return;
                setCurrentTime(video.currentTime);
                const sourceMs = videoTimeToSourceMs(
                  video.currentTime,
                  video.duration,
                  assignmentTimeline(assignment),
                );
                const prior = coveragePreviousMs.current;
                const countable = isCountableSourceTime(
                  sourceMs,
                  assignmentTimeline(assignment),
                );
                if (
                  countable &&
                  prior !== null &&
                  sourceMs >= prior &&
                  sourceMs - prior <= 3_000
                ) {
                  coverageRanges.current = mergeCoverage(coverageRanges.current, {
                    start_ms: prior,
                    end_ms: Math.min(assignment.chunk.sourceEndMs, sourceMs),
                  });
                }
                coveragePreviousMs.current = countable ? sourceMs : null;
              }}
              onSeeked={() => {
                const video = videoRef.current;
                if (!video) return;
                setCurrentTime(video.currentTime);
                const sourceMs = videoTimeToSourceMs(
                  video.currentTime,
                  video.duration,
                  assignmentTimeline(assignment),
                );
                coveragePreviousMs.current = isCountableSourceTime(
                  sourceMs,
                  assignmentTimeline(assignment),
                ) ? sourceMs : null;
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
              onError={() => {
                setIsPlaying(false);
                setVideoIssue(true);
                setStatus(
                  language === "es"
                    ? "No se pudo cargar el video."
                    : "The video could not be loaded.",
                );
              }}
              onEnded={() => { setIsPlaying(false); setScreen("summary"); }} />
            {!isPlaying && (
              <button type="button" className="absolute left-1/2 top-1/2 flex h-20 w-20 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full bg-[var(--accent)] text-white" aria-label={strings.play} onClick={() => void videoRef.current?.play()}>
                <Play className="ml-1 h-9 w-9 fill-white" />
              </button>
            )}
            {duration > 0 && (!countInputEnabled || timelineIssue) ? (
              <div className="absolute inset-x-0 bottom-0 bg-black/80 px-4 py-3 text-center text-[13px] font-semibold text-white">
                {timelineIssue
                  ? (language === "es"
                    ? "No cuentes. El tiempo de este video no coincide."
                    : "Do not count. This video's timing does not match.")
                  : currentSourceTimeMs !== null && currentSourceTimeMs < assignment.chunk.sourceStartMs
                  ? strings.previousContext
                  : strings.nextContext}
              </div>
            ) : null}
            <div className="worker-review-watermark" aria-hidden="true">
              FV REVIEW · {assignment.id.slice(0, 8)}
            </div>
          </div>
          <div className="mt-3 h-1 overflow-hidden rounded-full bg-white/[.08]"><div className="h-full bg-[var(--accent)]" style={{ width: `${progress * 100}%` }} /></div>
          <div className="mt-2 flex justify-between text-[12px] tabular-nums text-[var(--text-dim)]">
            <span>{formatVideoTime(currentTime)} / {formatVideoTime(duration)}</span>
            <span>~{formatVideoTime(timeLeft)} {strings.leftAt} {speed}x</span>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Button type="button" variant="secondary" onClick={togglePlayback}>
              {isPlaying ? <Pause className="h-4 w-4 fill-current" /> : <Play className="h-4 w-4 fill-current" />}
              {isPlaying
                ? (language === "es" ? "Pausar" : "Pause")
                : (language === "es" ? "Reproducir" : "Play")}
            </Button>
            <Button type="button" variant="secondary" onClick={backTen}><SkipBack className="h-4 w-4" />{strings.back10}</Button>
            <div className="flex rounded-lg border border-[var(--border)] bg-[var(--panel-2)] p-1" aria-label={language === "es" ? "Velocidad" : "Speed"}>
              {reviewSpeeds.map((value) => <button key={value} type="button" className={cn("rounded px-3 py-1.5 text-[13px] font-semibold", speed === value ? "bg-[var(--accent)] text-[#11100d]" : "text-[var(--text-mut)]")} onClick={() => setSpeed(value)}>{value}x</button>)}
            </div>
            <Button type="button" variant="secondary" onClick={() => setScreen("summary")}>{strings.endChunk}</Button>
            <div className="relative">
              <button type="button" className="flex h-9 items-center gap-2 px-2 text-[13px] font-semibold text-[var(--text-mut)] underline decoration-[var(--border)] underline-offset-4" onClick={() => setShowProblems((value) => !value)}><AlertTriangle className="h-4 w-4" />{language === "es" ? "Algo está mal" : "Something is wrong"}</button>
              {showProblems && (
                <div className="absolute bottom-full right-0 z-10 mb-2 w-64 rounded-lg border border-[var(--border)] bg-[var(--panel)] p-3 shadow-xl">
                  {pendingProblem ? (
                    <>
                      <div className="text-[13px] font-semibold">{pendingProblem.label}</div>
                      <p className="mt-2 text-[12px] leading-5 text-[var(--text-dim)]">
                        {language === "es"
                          ? "Esto cerrará la tarea y volverás a Trabajo de hoy."
                          : "This will close the task and return you to Today's work."}
                      </p>
                      <div className="mt-3 flex gap-2">
                        <Button className="flex-1" type="button" variant="primary" disabled={submitting} onClick={() => void submit(pendingProblem.code)}>
                          {language === "es" ? "Reportar" : "Report"}
                        </Button>
                        <Button className="flex-1" type="button" variant="secondary" onClick={() => setPendingProblem(null)}>
                          {language === "es" ? "Cancelar" : "Cancel"}
                        </Button>
                      </div>
                    </>
                  ) : (
                    <>
                      <div className="px-2 pb-2 text-[12px] font-semibold text-[var(--text-mut)]">{strings.problemPrompt}</div>
                      {([["video-wont-play", strings.videoWontPlay], ["camera-blocked", strings.cameraBlocked], ["timestamp-jump", strings.timestampJump], ["wrong-station", strings.wrongStation], ["no-usable-footage", strings.noUsableFootage], ["other", strings.otherProblem]] as const).map(([code, label]) =>
                        <button key={code} type="button" className="block w-full rounded-lg px-2 py-2 text-left text-[13px] hover:bg-white/[.04]" disabled={submitting} onClick={() => setPendingProblem({ code, label })}>{label}</button>)}
                    </>
                  )}
                </div>
              )}
            </div>
          </div>
          {videoIssue ? (
            <div role="alert" className="mt-3 flex items-center justify-between gap-3 rounded-lg border border-[var(--warn)]/40 bg-[var(--warn-tint)] px-3 py-2 text-[13px]">
              <span>{language === "es" ? "El video está pausado." : "The video is paused."}</span>
              <Button type="button" variant="secondary" onClick={() => void refreshMedia()}>
                {language === "es" ? "Reintentar video" : "Retry video"}
              </Button>
            </div>
          ) : null}
        </div>

        <aside className="flex min-h-[410px] min-w-0 flex-col justify-between rounded-lg border border-[var(--border)] bg-[var(--panel)] p-5">
          {screen === "summary" ? (
            <>
              <div>
                <h2 className="text-[18px] font-semibold">{language === "es" ? "Revisa tu conteo" : "Review your count"}</h2>
                <div className="mt-2 text-[13px] text-[var(--text-mut)]">
                  {clicks.length} {language === "es" ? (clicks.length === 1 ? "evento" : "eventos") : (clicks.length === 1 ? "event" : "events")}
                </div>
                <div className="mt-4 max-h-[290px] space-y-2 overflow-y-auto">
                  {clicks.map((click, index) => (
                    <div key={click.id} className="flex items-center rounded-lg border border-[var(--border-soft)]">
                      <button type="button" className="flex min-w-0 flex-1 justify-between px-3 py-2 text-[13px]" onClick={() => { if (videoRef.current) videoRef.current.currentTime = Math.max(0, click.videoSec - 5); setScreen("tally"); }}>
                        <span>#{index + 1}</span>
                        <span>{formatVideoTime(click.videoSec)}</span>
                      </button>
                      <button type="button" className="border-l border-[var(--border-soft)] p-2 text-[var(--text-dim)] hover:text-[var(--bad)]" aria-label={`${language === "es" ? "Eliminar evento" : "Delete event"} ${index + 1}`} title={language === "es" ? "Eliminar" : "Delete"} onClick={() => removeClick(click)}>
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  ))}
                  {!clicks.length && <div className="text-[13px] text-[var(--text-dim)]">{strings.noClicks}</div>}
                </div>
              </div>
              <div className="grid gap-2">
                {showZeroGuard ? (
                  <div className="rounded-lg border border-[rgba(232,116,47,.35)] bg-[rgba(232,116,47,.10)] p-3 text-[13px]">
                    <div>{strings.zeroGuard}</div>
                    <div className="mt-3 flex gap-2"><Button className="flex-1 justify-center" variant="primary" disabled={submitting} onClick={() => void submit()}>{strings.yes}</Button><Button className="flex-1 justify-center" variant="secondary" onClick={() => setShowZeroGuard(false)}>{strings.no}</Button></div>
                  </div>
                ) : <Button className="h-14 justify-center text-[16px]" variant="primary" disabled={submitting || saveState !== "saved"} onClick={() => clicks.length ? void submit() : setShowZeroGuard(true)}>{language === "es" ? "Enviar conteo" : "Submit count"}</Button>}
                {saveState === "offline" ? (
                  <Button className="h-11 justify-center" variant="secondary" onClick={() => void retryConnection()}>
                    {language === "es" ? "Reintentar conexión" : "Retry connection"}
                  </Button>
                ) : null}
                <Button className="h-12 justify-center" variant="secondary" onClick={() => setScreen("tally")}>{language === "es" ? "Volver al video" : "Back to video"}</Button>
              </div>
            </>
          ) : (
            <>
              <div>
                <div className="text-[11px] font-semibold uppercase text-[var(--text-dim)]">{language === "es" ? "Conteo de salida" : "Output count"}</div>
                <div data-testid="running-tally" className="mt-3 text-[96px] font-bold leading-none">{clicks.length}</div>
              </div>
              <div className="grid gap-3">
                <button type="button" disabled={!countInputEnabled} className="flex h-24 items-center justify-center gap-3 rounded-lg bg-[var(--accent)] px-4 text-[22px] font-bold text-[#11100d] disabled:cursor-not-allowed disabled:bg-[var(--idle)] disabled:text-[var(--text-dim)]" onClick={addCount}>
                  <Zap className="h-7 w-7 fill-[#11100d]" />
                  {language === "es" ? "+1 Pieza" : "+1 Output"}
                  <kbd className="ml-1 rounded border border-black/30 px-2 py-1 text-[12px]">J</kbd>
                </button>
                <Button className="h-12 justify-center" type="button" variant="secondary" onClick={undo} disabled={!clicks.length}>
                  <RotateCcw className="h-4 w-4" />{strings.undo}
                  <kbd className="ml-1 rounded border border-[var(--border)] px-1.5 py-0.5 text-[11px]">Z</kbd>
                </Button>
                <div className="flex items-center justify-center gap-1.5 text-[12px] text-[var(--text-dim)]" data-testid="save-state">
                  {saveState === "offline" ? <CloudOff className="h-3.5 w-3.5 text-[var(--bad)]" /> : saveState === "saving" ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5 text-[var(--good)]" />}
                  {saveLabel}
                  {saveState === "offline" && (
                    <button className="ml-2 font-semibold text-[var(--accent)]" type="button" onClick={() => void retryConnection()}>
                      {language === "es" ? "Reintentar" : "Retry"}
                    </button>
                  )}
                </div>
                <div className="text-center text-[11px] text-[var(--text-dim)]">J {language === "es" ? "contar" : "count"} · Z {language === "es" ? "deshacer" : "undo"} · Space {language === "es" ? "reproducir/pausar" : "play/pause"}</div>
              </div>
            </>
          )}
          {status && <div role="status" className="mt-4 border-t border-[var(--border)] pt-3 text-[13px] text-[var(--text-mut)]">{status}</div>}
          {assignmentUnavailable ? (
            <Button
              className="mt-3 h-11 justify-center"
              type="button"
              variant="secondary"
              onClick={() => {
                setAssignment(null);
                clicksRef.current = [];
                setClicks([]);
                setAssignmentUnavailable(false);
                if (session) void refreshWorkSummary(session, { showToday: true });
              }}
            >
              {language === "es" ? "Volver a Trabajo de hoy" : "Return to Today's work"}
            </Button>
          ) : null}
        </aside>
        </section>
      </div>
      {supportDialog}
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

function formatCurrentDate(language: ReviewLanguage) {
  return new Intl.DateTimeFormat(language === "es" ? "es-419" : "en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  }).format(new Date());
}

function WorkerHeader({
  language,
  onLanguageChange,
  onHelp,
  onSignOut,
}: {
  language: ReviewLanguage;
  onLanguageChange: (language: ReviewLanguage) => void;
  onHelp: () => void;
  onSignOut: () => void;
}) {
  return (
    <header className="border-b border-[var(--border)] bg-[var(--bg-rail)]">
      <div className="mx-auto flex h-[73px] w-full max-w-[1240px] items-center justify-between px-4 sm:px-5">
        <div className="flex items-center gap-3 text-[17px] font-semibold">
          <span className="grid h-6 w-6 place-items-center border-2 border-[var(--accent)]">
            <span className="h-2.5 w-2.5 border border-[var(--accent)]" />
          </span>
          <span>FactoryVision</span>
        </div>
        <div className="flex items-center gap-2">
          <LanguageControl language={language} onChange={onLanguageChange} />
          <button
            type="button"
            aria-label={language === "es" ? "Obtener ayuda" : "Get help"}
            className="flex h-10 items-center gap-2 rounded-lg px-3 text-[13px] font-semibold text-[var(--text-mut)] hover:bg-white/[.04] hover:text-[var(--text)]"
            onClick={onHelp}
          >
            <LifeBuoy className="h-4 w-4" />
            <span className="hidden sm:inline">{language === "es" ? "Ayuda" : "Help"}</span>
          </button>
          <button
            type="button"
            title={language === "es" ? "Cerrar sesión" : "Sign out"}
            aria-label={language === "es" ? "Cerrar sesión" : "Sign out"}
            className="grid h-10 w-10 place-items-center rounded-lg text-[var(--text-mut)] hover:bg-white/[.04] hover:text-[var(--text)]"
            onClick={onSignOut}
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </header>
  );
}

function WorkMetric({
  label,
  value,
  icon,
  testId,
}: {
  label: string;
  value: number;
  icon: ReactNode;
  testId?: string;
}) {
  return (
    <div className="flex min-w-0 flex-col items-center px-3 py-5 sm:px-6">
      <div className="text-[var(--text-dim)]">{icon}</div>
      <div className="mt-2 text-[13px] text-[var(--text-mut)]">{label}</div>
      <div className="mt-2 text-[28px] font-semibold" data-testid={testId}>{value}</div>
    </div>
  );
}
