import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { GET } from "./route";

const factoryId = "10000000-0000-0000-0000-000000000001";
const closeoutId = "20000000-0000-0000-0000-000000000002";

function request() {
  return new NextRequest(
    `https://factoryvision.example/api/owner/history/${closeoutId}/evidence?factory_id=${factoryId}`,
    { headers: { cookie: "fv_owner_access=owner-token" } },
  );
}

const context = { params: Promise.resolve({ id: closeoutId }) };

describe("owner closeout evidence route", () => {
  beforeEach(() => {
    process.env.NEXT_PUBLIC_SUPABASE_URL = "https://project.supabase.co";
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY = "publishable-key";
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns the contract 400 for malformed owner evidence ids", async () => {
    const response = await GET(
      new NextRequest(
        "https://factoryvision.example/api/owner/history/not-a-uuid/evidence?factory_id=bad",
      ),
      { params: Promise.resolve({ id: "not-a-uuid" }) },
    );
    expect(response.status).toBe(400);
    expect(await response.json()).toEqual({ error: "OWNER_EVIDENCE_INVALID" });
  });

  it("authorizes the owner and returns a short-lived signed URL", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        Response.json({ authorized: true, factories: [{ id: factoryId }] }),
      )
      .mockResolvedValueOnce(
        Response.json([
          {
            id: "30000000-0000-0000-0000-000000000003",
            object_sha256: "a".repeat(64),
            retention_until: "2099-08-30T00:00:00Z",
            reason_code: "closeout-verification",
            attached_at: "2026-07-29T00:00:00Z",
            bucket_id: "evidence-clips",
            object_path: "fixture/evidence clip.mp4",
            content_type: "video/mp4",
            byte_size: 1024,
            status: "verified",
          },
        ]),
      )
      .mockResolvedValueOnce(
        Response.json({
          signedURL:
            "/object/sign/evidence-clips/fixture/tokenized.mp4?token=fixture",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const response = await GET(request(), context);

    expect(response.status).toBe(200);
    const payload = await response.json();
    expect(payload.clips[0]).toMatchObject({
      state: "available",
      expiresIn: 300,
      objectSha256: "a".repeat(64),
    });
    expect(payload.clips[0].signedUrl).toContain("/storage/v1/object/sign/");
    expect(response.headers.get("cache-control")).toBe("private, no-store");
    expect(fetchMock.mock.calls[1][0]).toContain(
      "/rest/v1/rpc/owner_history_evidence",
    );
    expect(fetchMock.mock.calls[2][0]).toContain(
      "/storage/v1/object/sign/evidence-clips/fixture/evidence%20clip.mp4",
    );
    expect(fetchMock.mock.calls[2][1].headers).toMatchObject({
      apikey: "publishable-key",
      Authorization: "Bearer owner-token",
    });
  });

  it("keeps other evidence available when one clip cannot be signed", async () => {
    const row = {
      object_sha256: "a".repeat(64),
      retention_until: "2099-08-30T00:00:00Z",
      reason_code: "closeout-verification",
      attached_at: "2026-07-29T00:00:00Z",
      bucket_id: "evidence-clips",
      content_type: "video/mp4",
      byte_size: 1024,
      status: "verified",
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        Response.json({ authorized: true, factories: [{ id: factoryId }] }),
      )
      .mockResolvedValueOnce(
        Response.json([
          {
            ...row,
            id: "30000000-0000-0000-0000-000000000003",
            object_path: "fixture/missing.mp4",
          },
          {
            ...row,
            id: "40000000-0000-0000-0000-000000000004",
            object_path: "fixture/available.mp4",
          },
        ]),
      )
      .mockResolvedValueOnce(
        Response.json({ message: "missing" }, { status: 404 }),
      )
      .mockResolvedValueOnce(
        Response.json({
          signedURL: "/object/sign/evidence-clips/fixture/available.mp4?token=ok",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const response = await GET(request(), context);
    const payload = await response.json();

    expect(response.status).toBe(200);
    expect(payload.clips.map((clip: { state: string }) => clip.state))
      .toEqual(["unavailable", "available"]);
  });

  it("does not sign expired evidence", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        Response.json({ authorized: true, factories: [{ id: factoryId }] }),
      )
      .mockResolvedValueOnce(
        Response.json([
          {
            id: "30000000-0000-0000-0000-000000000003",
            object_sha256: "a".repeat(64),
            retention_until: "2020-01-01T00:00:00Z",
            reason_code: "closeout-verification",
            attached_at: "2026-07-29T00:00:00Z",
            bucket_id: "evidence-clips",
            object_path: "fixture/expired.mp4",
            content_type: "video/mp4",
            byte_size: 1024,
            status: "verified",
          },
        ]),
      );
    vi.stubGlobal("fetch", fetchMock);

    const response = await GET(request(), context);

    expect(response.status).toBe(200);
    expect((await response.json()).clips[0]).toMatchObject({
      state: "expired",
      signedUrl: null,
      expiresIn: null,
    });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("rejects traversal-shaped storage paths without signing them", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        Response.json({ authorized: true, factories: [{ id: factoryId }] }),
      )
      .mockResolvedValueOnce(
        Response.json([
          {
            id: "30000000-0000-0000-0000-000000000003",
            object_sha256: "a".repeat(64),
            retention_until: "2099-08-30T00:00:00Z",
            reason_code: "closeout-verification",
            attached_at: "2026-07-29T00:00:00Z",
            bucket_id: "evidence-clips",
            object_path: "fixture/../secret.mp4",
            content_type: "video/mp4",
            byte_size: 1024,
            status: "verified",
          },
        ]),
      );
    vi.stubGlobal("fetch", fetchMock);

    const response = await GET(request(), context);

    expect(response.status).toBe(200);
    expect((await response.json()).clips[0]).toMatchObject({
      state: "unavailable",
      signedUrl: null,
      expiresIn: null,
    });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("fails closed when owner authorization is denied", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce(
        Response.json({ authorized: false, factories: [] }),
      ),
    );

    const response = await GET(request(), context);

    expect(response.status).toBe(403);
    expect(await response.json()).toEqual({ error: "OWNER_ACCESS_DENIED" });
  });
});
