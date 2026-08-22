// Headless review-session engine extracted from ReviewTallyConsole (CP3).
//
// Three deep modules behind one small interface each, so the worker portal's
// session logic is unit-testable without a browser and the component renders
// screens only:
//
// - CoverageTracker: merges watched ranges from video timeupdate events with
//   gap-tolerance + seek protection; tracks client active-playback time for
//   the server coverage contract (sorted merge, 250ms join, tail-capped 128).
// - ActionOutbox: localStorage-backed offline queue of tally/undo actions
//   with idempotent flush over append_worker_action and click reconciliation.
// - AssignmentKeepAlive: owns the lease-liveness timers (heartbeat,
//   work session touch/close, periodic media reauthorization) plus the
//   coverage-save timer, with clean teardown.
//
// Nothing here touches React: plain classes + callbacks. The component wires
// its state setters to the events it cares about.

import { type DurableReviewAction, type ReviewSession, type WorkerAssignment, workerRpc } from "./reviewSupabase";

export const appVersion = "worker-portal-v2";

export type ActiveClick = {
  id: string;
  serverId?: string;
  videoSec: number;
};

export type PendingAction = {
  clientActionId: string;
  type: "tally" | "undo";
  sourceTimeMs: number | null;
  undoesClientActionId: string | null;
  playbackRate: number;
};

export type CoverageRange = { start_ms: number; end_ms: number };

const MAX_RANGES = 128;
const RANGE_JOIN_MS = 250;

// ---------------------------------------------------------------------------
// Coverage tracking
// ---------------------------------------------------------------------------

export function mergeCoverage(ranges: CoverageRange[], next: CoverageRange): CoverageRange[] {
  const sorted = [...ranges, next]
    .filter((range) => range.end_ms > range.start_ms)
    .sort((a, b) => a.start_ms - b.start_ms);
  const merged: CoverageRange[] = [];
  for (const range of sorted) {
    const prior = merged.at(-1);
    if (prior && range.start_ms <= prior.end_ms + RANGE_JOIN_MS) {
      prior.end_ms = Math.max(prior.end_ms, range.end_ms);
    } else {
      merged.push({ ...range });
    }
  }
  return merged.slice(-MAX_RANGES);
}

export class CoverageTracker {
  private ranges: CoverageRange[];
  private previousMs: number | null = null;
  private activeStartedAt: number | null = null;
  private activeMs: number;

  constructor(initial?: { ranges?: CoverageRange[]; clientActiveMs?: number }) {
    this.ranges = initial?.ranges ? initial.ranges.map((range) => ({ ...range })) : [];
    this.activeMs = initial?.clientActiveMs ?? 0;
  }

  /** Feed a timeupdate. `countable` false means seek/scrub/out-of-range. */
  onTimeUpdate(
    sourceMs: number,
    countable: boolean,
    gapToleranceMs: number,
    clampEndMs: number,
  ): void {
    const prior = this.previousMs;
    if (
      countable &&
      prior !== null &&
      sourceMs >= prior &&
      sourceMs - prior <= gapToleranceMs
    ) {
      this.ranges = mergeCoverage(this.ranges, {
        start_ms: prior,
        end_ms: Math.min(clampEndMs, sourceMs),
      });
    }
    this.previousMs = countable ? sourceMs : null;
  }

  /** Feed a seek: coverage resumes only if the target is countable. */
  onSeeked(sourceMs: number, countable: boolean): void {
    this.previousMs = countable ? sourceMs : null;
  }

  onPlay(): void {
    if (this.activeStartedAt === null) {
      this.activeStartedAt = Date.now();
    }
  }

  onPause(): void {
    if (this.activeStartedAt !== null) {
      this.activeMs += Date.now() - this.activeStartedAt;
      this.activeStartedAt = null;
    }
  }

  snapshot(): { ranges: CoverageRange[]; clientActiveMs: number } {
    const live =
      this.activeMs +
      (this.activeStartedAt !== null ? Math.round(Date.now() - this.activeStartedAt) : 0);
    return {
      ranges: this.ranges.map((range) => ({ ...range })),
      clientActiveMs: live,
    };
  }

  reset(ranges: CoverageRange[], clientActiveMs: number): void {
    this.ranges = ranges.map((range) => ({ ...range }));
    this.previousMs = null;
    this.activeStartedAt = null;
    this.activeMs = clientActiveMs;
  }
}

// ---------------------------------------------------------------------------
// Offline action outbox
// ---------------------------------------------------------------------------

function outboxKey(assignmentId: string) {
  return `factoryvision-review-outbox:${assignmentId}`;
}

function submissionKey(assignmentId: string) {
  return `factoryvision-review-submission:${assignmentId}`;
}

export function readOutbox(assignmentId: string): PendingAction[] {
  try {
    return JSON.parse(window.localStorage.getItem(outboxKey(assignmentId)) ?? "[]") as PendingAction[];
  } catch {
    return [];
  }
}

export function writeOutbox(assignmentId: string, actions: PendingAction[]): void {
  window.localStorage.setItem(outboxKey(assignmentId), JSON.stringify(actions));
}

export function submissionId(assignmentId: string): string {
  const existing = window.localStorage.getItem(submissionKey(assignmentId));
  if (existing) return existing;
  const created = window.crypto.randomUUID();
  window.localStorage.setItem(submissionKey(assignmentId), created);
  return created;
}

/** Reconcile server actions + pending queue into the visible click list. */
export function activeClicks(
  actions: DurableReviewAction[],
  pending: PendingAction[],
  sourceStartMs: number,
): ActiveClick[] {
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

export type OutboxEvents = {
  onSaveState: (state: "saving" | "saved" | "offline") => void;
  onPendingCount: (count: number) => void;
  onAssignmentUnavailable: () => void;
};

export class ActionOutbox {
  private flushing = false;

  constructor(private readonly events: OutboxEvents) {}

  enqueue(assignmentId: string, action: PendingAction): PendingAction[] {
    const pending = [...readOutbox(assignmentId), action];
    writeOutbox(assignmentId, pending);
    this.events.onPendingCount(pending.length);
    return pending;
  }

  async flush(session: ReviewSession, assignment: WorkerAssignment): Promise<boolean> {
    if (this.flushing) return false;
    this.flushing = true;
    this.events.onSaveState("saving");
    try {
      let pending = readOutbox(assignment.id);
      while (pending.length) {
        const action = pending[0];
        await workerRpc(session, "append_worker_action", {
          p_assignment_id: assignment.id,
          p_lease_token: assignment.leaseToken,
          p_client_action_id: action.clientActionId,
          p_action_type: action.type,
          p_source_time_ms: action.sourceTimeMs,
          p_undoes_client_action_id: action.undoesClientActionId,
          p_reason_code: null,
          p_playback_rate: action.playbackRate,
          p_app_version: appVersion,
        });
        pending = readOutbox(assignment.id).filter(
          (queued) => queued.clientActionId !== action.clientActionId,
        );
        writeOutbox(assignment.id, pending);
        this.events.onPendingCount(pending.length);
      }
      this.events.onSaveState("saved");
      return true;
    } catch (error) {
      this.events.onSaveState("offline");
      this.events.onPendingCount(readOutbox(assignment.id).length);
      // Lease-expiry classification stays with the caller via its classifier:
      // surface unavailability through the event channel instead of prose.
      this.events.onAssignmentUnavailable();
      throw error;
    } finally {
      this.flushing = false;
    }
  }
}

// ---------------------------------------------------------------------------
// Assignment keep-alive timers
// ---------------------------------------------------------------------------

export type KeepAliveTimers = {
  heartbeatMs: number;
  workSessionTouchMs: number;
  coverageSaveMs: number;
  mediaRefreshMs: number;
};

export const DEFAULT_KEEP_ALIVE: KeepAliveTimers = {
  heartbeatMs: 30_000,
  workSessionTouchMs: 30_000,
  coverageSaveMs: 5_000,
  mediaRefreshMs: 8 * 60 * 1000,
};

export type KeepAliveDeps = {
  session: ReviewSession | null;
  assignment: WorkerAssignment | null;
  enabled: boolean;
  heartbeatFailures: { current: number };
  workSessionId: { current: string | null };
  onHeartbeatHealthy: () => void;
  onHeartbeatDegraded: () => void;
  saveCoverage: () => Promise<void>;
  refreshMedia: () => Promise<void>;
  timers?: Partial<KeepAliveTimers>;
};

export class AssignmentKeepAlive {
  private intervals: number[] = [];
  private disposed = false;

  constructor(private readonly deps: KeepAliveDeps) {}

  start(): void {
    const timers = { ...DEFAULT_KEEP_ALIVE, ...(this.deps.timers ?? {}) };
    const { session, assignment } = this.deps;
    if (!assignment || !session) return;

    // Media reauthorization (signed URLs expire) runs in production AND
    // practice mode - practice URLs expire just like leased ones.
    this.every(timers.mediaRefreshMs, () => this.deps.refreshMedia().catch(() => undefined));

    // Lease-liveness timers only apply to real assignments.
    if (!this.deps.enabled) return;

    // Lease heartbeat.
    this.every(timers.heartbeatMs, async () => {
      try {
        await workerRpc(session, "heartbeat_worker_assignment", {
          p_assignment_id: assignment.id,
          p_lease_token: assignment.leaseToken,
        });
        this.deps.heartbeatFailures.current = 0;
        if (readOutbox(assignment.id).length === 0) this.deps.onHeartbeatHealthy();
      } catch {
        this.deps.heartbeatFailures.current += 1;
        if (this.deps.heartbeatFailures.current >= 2) this.deps.onHeartbeatDegraded();
      }
    });

    // Work session touch/close.
    void this.startWorkSession(assignment);

    // Coverage autosave.
    this.every(timers.coverageSaveMs, () =>
      this.deps.saveCoverage().catch(() => undefined),
    );
  }

  private async startWorkSession(assignment: WorkerAssignment): Promise<void> {
    const { session } = this.deps;
    if (!session) return;
    let timer: number | null = null;
    try {
      const deviceIdHash = await reviewerDeviceIdHash();
      const opened = await workerRpc<{ sessionId: string }>(session, "worker_touch_work_session", {
        p_session_id: this.deps.workSessionId.current,
        p_device_id_hash: deviceIdHash,
        p_active_seconds_delta: 0,
      });
      if (this.disposed) {
        await workerRpc(session, "worker_close_work_session", {
          p_session_id: opened.sessionId,
          p_close_reason: "screen_changed",
        }).catch(() => undefined);
        return;
      }
      this.deps.workSessionId.current = opened.sessionId;
      const timers = { ...DEFAULT_KEEP_ALIVE, ...(this.deps.timers ?? {}) };
      timer = window.setInterval(() => {
        if (document.visibilityState !== "visible") return;
        void workerRpc(session, "worker_touch_work_session", {
          p_session_id: opened.sessionId,
          p_device_id_hash: deviceIdHash,
          p_active_seconds_delta: 30,
        }).catch(() => undefined);
      }, timers.workSessionTouchMs);
      this.intervals.push(timer);
    } catch {
      return;
    }
  }

  /** Close the work session and stop every timer. Idempotent. */
  async stop(closeReason: "assignment_closed" | "screen_changed" = "assignment_closed"): Promise<void> {
    this.disposed = true;
    for (const interval of this.intervals) window.clearInterval(interval);
    this.intervals = [];
    const sessionId = this.deps.workSessionId.current;
    this.deps.workSessionId.current = null;
    if (sessionId && this.deps.session) {
      await workerRpc(this.deps.session, "worker_close_work_session", {
        p_session_id: sessionId,
        p_close_reason: closeReason,
      }).catch(() => undefined);
    }
  }

  private every(ms: number, fn: () => void | Promise<void>): void {
    const id = window.setInterval(() => void fn(), ms);
    this.intervals.push(id);
  }
}

async function reviewerDeviceIdHash(): Promise<string> {
  const { reviewerDeviceHash } = await import("./reviewerDevice");
  return reviewerDeviceHash();
}

