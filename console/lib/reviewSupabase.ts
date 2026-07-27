"use client";

export type ReviewSession = {
  user: { id: string; email: string };
};

export type DurableReviewAction = {
  id: string;
  clientActionId: string;
  type: "tally" | "undo" | "problem";
  sourceTimeMs: number | null;
  undoesActionId: string | null;
  reasonCode: string | null;
  playbackRate: number | null;
  createdAt: string;
};

export type WorkerAssignment = {
  id: string;
  leaseToken: string;
  leaseExpiresAt: string;
  chunk: {
    id: string;
    stationId: string;
    stationName: string;
    startIso: string;
    endIso: string;
    sourceStartMs: number;
    sourceEndMs: number;
    sourceSha256: string;
    renditionId: string;
    mediaUrl: string;
    posterUrl: string | null;
  };
  actions: DurableReviewAction[];
};

async function sessionRequest(method: "GET" | "POST" | "DELETE", body?: object) {
  const response = await fetch("/api/review/session", {
    method,
    credentials: "same-origin",
    cache: "no-store",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const result = (await response.json()) as ReviewSession & { error?: string };
  if (!response.ok) {
    throw new Error(result.error ?? `AUTH_${response.status}`);
  }
  return result;
}

export async function signInReviewer(email: string, password: string) {
  return sessionRequest("POST", { email, password });
}

export async function signOutReviewer() {
  await sessionRequest("DELETE");
}

export async function restoreReviewerSession(): Promise<ReviewSession | null> {
  try {
    const session = await sessionRequest("GET");
    return session.user ? session : null;
  } catch {
    return null;
  }
}

export async function workerRpc<T>(
  _session: ReviewSession,
  functionName: string,
  body: object,
): Promise<T> {
  const response = await fetch(`/api/review/rpc/${functionName}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    credentials: "same-origin",
    cache: "no-store",
    body: JSON.stringify(body),
  });
  const text = await response.text();
  const result: unknown = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const message =
      result && typeof result === "object" && "message" in result
        ? String(result.message)
        : `RPC_${response.status}`;
    throw new Error(message);
  }
  return result as T;
}
