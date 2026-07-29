"use client";

export async function ownerApiFetch(
  input: RequestInfo | URL,
  init?: RequestInit,
) {
  let response = await fetch(input, init);
  if (response.status !== 401) return response;

  const refreshed = await fetch("/api/owner/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action: "refresh" }),
  });
  if (!refreshed.ok) return response;
  const method = (init?.method ?? "GET").toUpperCase();
  if (!["GET", "HEAD", "PUT", "DELETE"].includes(method)) {
    return new Response(
      JSON.stringify({ error: "OWNER_RETRY_REQUIRED" }),
      {
        status: 409,
        headers: { "Content-Type": "application/json" },
      },
    );
  }
  response = await fetch(input, init);
  return response;
}

export async function signOutOwner() {
  return fetch("/api/owner/session", {
    method: "DELETE",
    credentials: "same-origin",
    cache: "no-store",
  });
}

export type OwnerEvidenceClip = {
  id: string;
  objectSha256: string;
  retentionUntil: string | null;
  reasonCode: string;
  attachedAt: string;
  contentType: string;
  byteSize: number;
  state: "available" | "expired" | "unavailable";
  signedUrl: string | null;
  expiresIn: number | null;
};

export async function loadOwnerEvidence(
  factoryId: string,
  closeoutId: string,
) {
  const response = await ownerApiFetch(
    `/api/owner/history/${encodeURIComponent(
      closeoutId,
    )}/evidence?factory_id=${encodeURIComponent(factoryId)}`,
    { cache: "no-store" },
  );
  if (!response.ok) throw new Error("OWNER_EVIDENCE_UNAVAILABLE");
  const payload = (await response.json()) as { clips?: OwnerEvidenceClip[] };
  return Array.isArray(payload.clips) ? payload.clips : [];
}
