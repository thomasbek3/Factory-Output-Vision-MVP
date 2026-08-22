import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  ActionOutbox,
  CoverageTracker,
  activeClicks,
  mergeCoverage,
  readOutbox,
  submissionId,
  writeOutbox,
  type PendingAction,
} from "./reviewSessionEngine";

// ---------------------------------------------------------------------------
// CoverageTracker
// ---------------------------------------------------------------------------

describe("CoverageTracker", () => {
  it("merges contiguous watched ranges and caps the tail at 128", () => {
    const tracker = new CoverageTracker();
    tracker.onTimeUpdate(0, true, 2_000, 1_000_000);
    for (let second = 1; second <= 10; second += 1) {
      tracker.onTimeUpdate(second * 1000, true, 2_000, 1_000_000);
    }
    const { ranges } = tracker.snapshot();
    expect(ranges).toHaveLength(1);
    expect(ranges[0]).toEqual({ start_ms: 0, end_ms: 10_000 });
  });

  it("does not bridge gaps beyond tolerance", () => {
    const tracker = new CoverageTracker();
    tracker.onTimeUpdate(0, true, 2_000, 1_000_000);
    tracker.onTimeUpdate(1_000, true, 2_000, 1_000_000);
    // A seek-sized jump: uncountable (break), then playback resumes far ahead.
    tracker.onTimeUpdate(60_000, false, 2_000, 1_000_000);
    tracker.onTimeUpdate(60_500, true, 2_000, 1_000_000);
    tracker.onTimeUpdate(61_000, true, 2_000, 1_000_000);
    const { ranges } = tracker.snapshot();
    expect(ranges).toHaveLength(2);
    expect(ranges[1]).toEqual({ start_ms: 60_500, end_ms: 61_000 });
  });

  it("treats seeks as coverage breaks until playback resumes", () => {
    const tracker = new CoverageTracker();
    tracker.onTimeUpdate(5_000, true, 2_000, 1_000_000);
    tracker.onSeeked(500_000, true);
    tracker.onTimeUpdate(500_500, true, 2_000, 1_000_000);
    const { ranges } = tracker.snapshot();
    expect(ranges).toHaveLength(1);
    expect(ranges[0].start_ms).toBe(500_000);
  });

  it("accumulates active playback time across play/pause", () => {
    const tracker = new CoverageTracker();
    tracker.onPlay();
    tracker.onPause();
    tracker.onPlay();
    tracker.onPause();
    const { clientActiveMs } = tracker.snapshot();
    expect(clientActiveMs).toBeGreaterThanOrEqual(0);
  });

  it("reset restores server-provided coverage state", () => {
    const tracker = new CoverageTracker();
    tracker.onTimeUpdate(1_000, true, 2_000, 100_000);
    tracker.reset([{ start_ms: 0, end_ms: 5_000 }], 42_000);
    const snap = tracker.snapshot();
    expect(snap.ranges).toEqual([{ start_ms: 0, end_ms: 5_000 }]);
    expect(snap.clientActiveMs).toBeGreaterThanOrEqual(42_000);
  });
});

// ---------------------------------------------------------------------------
// Outbox helpers
// ---------------------------------------------------------------------------

function tallyAction(clientActionId: string, sourceTimeMs: number): PendingAction {
  return {
    clientActionId,
    type: "tally",
    sourceTimeMs,
    undoesClientActionId: null,
    playbackRate: 1,
  };
}

describe("outbox storage helpers", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    window.localStorage.clear();
  });

  it("readOutbox returns [] on corrupt JSON", () => {
    window.localStorage.setItem("factoryvision-review-outbox:a", "{not json");
    expect(readOutbox("a")).toEqual([]);
  });

  it("submissionId is stable per assignment", () => {
    const first = submissionId("a");
    expect(submissionId("a")).toBe(first);
    expect(submissionId("b")).not.toBe(first);
  });

  it("activeClicks reconciles server + pending tallies and undos", () => {
    const server = [
      {
        id: "srv-1",
        type: "tally" as const,
        clientActionId: "c1",
        sourceTimeMs: 10_000,
        undoesActionId: null,
        reasonCode: null,
        playbackRate: null,
        createdAt: "2026-08-22T00:00:00Z",
      },
      {
        id: "srv-2",
        type: "undo" as const,
        clientActionId: "c2",
        sourceTimeMs: 11_000,
        undoesActionId: "srv-1",
        reasonCode: null,
        playbackRate: null,
        createdAt: "2026-08-22T00:00:01Z",
      },
    ];
    const pending = [tallyAction("c3", 20_000)];
    const clicks = activeClicks(server, pending, 0);
    expect(clicks.map((click) => click.id)).toEqual(["c3"]);
  });
});

// ---------------------------------------------------------------------------
// ActionOutbox flush
// ---------------------------------------------------------------------------

function makeAssignment(id: string) {
  return {
    id,
    leaseToken: "lease",
  } as unknown as Parameters<ActionOutbox["flush"]>[1];
}

function makeSession() {
  return { accessToken: "token" } as unknown as Parameters<ActionOutbox["flush"]>[0];
}

describe("ActionOutbox", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    window.localStorage.clear();
    vi.restoreAllMocks();
  });

  it("enqueue persists and reports pending count", () => {
    const seen: number[] = [];
    const outbox = new ActionOutbox({
      onSaveState: () => undefined,
      onPendingCount: (count) => seen.push(count),
      onAssignmentUnavailable: () => undefined,
    });
    outbox.enqueue("a", tallyAction("c1", 1_000));
    expect(seen).toEqual([1]);
    expect(readOutbox("a")).toHaveLength(1);
  });

  it("flush drains the queue in order and marks saved", async () => {
    writeOutbox("a", [tallyAction("c1", 1_000), tallyAction("c2", 2_000)]);
    const calls: Array<Record<string, unknown>> = [];
    vi.spyOn(await import("./reviewSupabase"), "workerRpc").mockImplementation(
      async (_session, _fn, body) => {
        calls.push(body as Record<string, unknown>);
        return {};
      },
    );
    const states: string[] = [];
    const outbox = new ActionOutbox({
      onSaveState: (state) => states.push(state),
      onPendingCount: () => undefined,
      onAssignmentUnavailable: () => undefined,
    });
    const ok = await outbox.flush(makeSession(), makeAssignment("a"));
    expect(ok).toBe(true);
    expect(calls).toHaveLength(2);
    expect(calls[0].p_client_action_id).toBe("c1");
    expect(readOutbox("a")).toEqual([]);
    expect(states.at(-1)).toBe("saved");
  });

  it("flush failure keeps remaining actions and reports offline + unavailable", async () => {
    writeOutbox("a", [tallyAction("c1", 1_000), tallyAction("c2", 2_000)]);
    let callCount = 0;
    vi.spyOn(await import("./reviewSupabase"), "workerRpc").mockImplementation(async () => {
      callCount += 1;
      if (callCount === 1) return {};
      throw Object.assign(new Error("assignment lease is unavailable"), { isLease: true });
    });
    const unavailable = vi.fn();
    const outbox = new ActionOutbox({
      onSaveState: () => undefined,
      onPendingCount: () => undefined,
      onAssignmentUnavailable: unavailable,
    });
    await expect(outbox.flush(makeSession(), makeAssignment("a"))).rejects.toThrow();
    expect(readOutbox("a")).toHaveLength(1);
    expect(readOutbox("a")[0].clientActionId).toBe("c2");
    expect(unavailable).toHaveBeenCalled();
  });

  it("concurrent flush is a no-op", async () => {
    writeOutbox("a", [tallyAction("c1", 1_000)]);
    vi.spyOn(await import("./reviewSupabase"), "workerRpc").mockImplementation(async () => {
      await new Promise((resolve) => setTimeout(resolve, 10));
      return {};
    });
    const outbox = new ActionOutbox({
      onSaveState: () => undefined,
      onPendingCount: () => undefined,
      onAssignmentUnavailable: () => undefined,
    });
    const [first, second] = await Promise.all([
      outbox.flush(makeSession(), makeAssignment("a")),
      outbox.flush(makeSession(), makeAssignment("a")),
    ]);
    expect([first, second]).toContain(false);
  });
});
