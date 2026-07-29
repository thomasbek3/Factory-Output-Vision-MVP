import { afterEach, describe, expect, it, vi } from "vitest";
import {
  loadOwnerEvidence,
  ownerApiFetch,
  signOutOwner,
} from "@/lib/ownerClient";

describe("ownerApiFetch", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("retries an idempotent GET after refreshing the owner session", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(Response.json({ error: "expired" }, { status: 401 }))
      .mockResolvedValueOnce(Response.json({ ok: true }))
      .mockResolvedValueOnce(Response.json({ projects: [] }));
    vi.stubGlobal("fetch", fetchMock);

    const response = await ownerApiFetch("/api/owner/projects");

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock.mock.calls[2][0]).toBe("/api/owner/projects");
  });

  it("never replays a POST after session refresh and asks for an explicit retry", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(Response.json({ error: "expired" }, { status: 401 }))
      .mockResolvedValueOnce(Response.json({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);

    const response = await ownerApiFetch("/api/owner/projects/start", {
      method: "POST",
      body: JSON.stringify({ name: "Harbor Fence Batch" }),
    });

    expect(response.status).toBe(409);
    expect(await response.json()).toEqual({ error: "OWNER_RETRY_REQUIRED" });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("preserves the original 401 when session refresh fails", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(Response.json({ error: "expired" }, { status: 401 }))
      .mockResolvedValueOnce(
        Response.json({ error: "refresh failed" }, { status: 401 }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const response = await ownerApiFetch("/api/owner/projects/start", {
      method: "POST",
    });

    expect(response.status).toBe(401);
    expect(await response.json()).toEqual({ error: "expired" });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("signs out through a same-origin, uncached session request", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(Response.json({ signedOut: true }));
    vi.stubGlobal("fetch", fetchMock);

    await signOutOwner();

    expect(fetchMock).toHaveBeenCalledWith("/api/owner/session", {
      method: "DELETE",
      credentials: "same-origin",
      cache: "no-store",
    });
  });

  it("loads owner-safe evidence without exposing storage object paths", async () => {
    const clip = {
      id: "clip-1",
      objectSha256: "a".repeat(64),
      retentionUntil: null,
      reasonCode: "closeout-verification",
      attachedAt: "2026-07-29T00:00:00Z",
      contentType: "video/mp4",
      byteSize: 1024,
      state: "available",
      signedUrl: "https://project.supabase.co/signed",
      expiresIn: 300,
    };
    const fetchMock = vi.fn().mockResolvedValue(Response.json({ clips: [clip] }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(loadOwnerEvidence("factory one", "closeout one"))
      .resolves.toEqual([clip]);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/owner/history/closeout%20one/evidence?factory_id=factory%20one",
      { cache: "no-store" },
    );
  });
});
