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
    factoryTimezone: string;
    startIso: string;
    endIso: string;
    sourceStartMs: number;
    sourceEndMs: number;
    renditionSourceStartMs?: number;
    renditionSourceEndMs?: number;
    sourceSha256: string;
    renditionId: string;
    mediaUrl: string;
    posterUrl: string | null;
  };
  actions: DurableReviewAction[];
  coverage?: {
    pageEpoch: string;
    ranges: Array<{ start_ms: number; end_ms: number }>;
    clientActiveMs: number;
  } | null;
};

async function sessionRequest<T = ReviewSession>(
  method: "GET" | "POST" | "DELETE",
  body?: object,
): Promise<T> {
  const response = await fetch("/api/review/session", {
    method,
    credentials: "same-origin",
    cache: "no-store",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const result = (await response.json()) as T & { error?: string };
  if (!response.ok) {
    throw new Error(result.error ?? `AUTH_${response.status}`);
  }
  return result;
}

export async function requestReviewerSignInLink(
  email: string,
  language: "en" | "es",
) {
  return sessionRequest<{ sent: true }>("POST", {
    action: "requestPasswordless",
    email,
    language,
  });
}

export async function signInReviewer(email: string, password: string) {
  return sessionRequest("POST", { email, password });
}

export async function acceptReviewerPasswordlessSession(
  accessToken: string,
  refreshToken: string,
  expiresIn: number,
) {
  return sessionRequest("POST", {
    action: "completePasswordless",
    accessToken,
    refreshToken,
    expiresIn,
  });
}

export async function acceptReviewerInviteSession(
  accessToken: string,
  refreshToken: string,
  invitationToken: string,
) {
  return sessionRequest("POST", {
    accessToken,
    refreshToken,
    invitationToken,
  });
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

export type ReviewerLifecycle = {
  userId?: string;
  displayName?: string;
  email?: string;
  locale?: "en" | "es-419";
  state:
    | "unregistered"
    | "invited"
    | "mfa_required"
    | "terms_required"
    | "training"
    | "qualification"
    | "active"
    | "suspended"
    | "offboarded";
  termsVersion?: string | null;
  termsAcceptedAt?: string | null;
  mfaVerifiedAt?: string | null;
  currentAal?: "aal1" | "aal2";
  walkthroughCompletedAt?: string | null;
  practiceCompletedAt?: string | null;
  qualifiedAt?: string | null;
  activatedAt?: string | null;
  isTestAccount?: boolean;
};

export async function reviewerLifecycle(method: "GET" | "POST", body?: object) {
  const response = await fetch("/api/review/onboarding", {
    method,
    credentials: "same-origin",
    cache: "no-store",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const result = (await response.json()) as ReviewerLifecycle & { error?: string };
  if (!response.ok) throw new Error(result.error ?? `ONBOARDING_${response.status}`);
  return result;
}
