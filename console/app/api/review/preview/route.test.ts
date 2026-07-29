import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const opsRpc = vi.fn();
const hasReviewPreviewPass = vi.fn();
const authorizeOps = vi.fn();

vi.mock("@/lib/reviewerAdminServer", () => ({ opsRpc }));
vi.mock("@/lib/reviewPreviewPass", () => ({ hasReviewPreviewPass }));
vi.mock("@/lib/opsServer", () => ({ authorizeOps }));

describe("ops practice preview route", () => {
  beforeEach(() => {
    vi.resetModules();
    opsRpc.mockReset();
    authorizeOps.mockReset();
    authorizeOps.mockResolvedValue({
      authorized: true,
      accessToken: "ops-token",
    });
    hasReviewPreviewPass.mockReset();
    hasReviewPreviewPass.mockReturnValue(false);
    process.env.NEXT_PUBLIC_SUPABASE_URL = "https://project.supabase.co";
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY = "publishable-key";
    process.env.SUPABASE_SECRET_KEY = "secret-key";
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    delete process.env.SUPABASE_SECRET_KEY;
  });

  it("returns a signed, non-durable practice assignment to an ops user", async () => {
    opsRpc
      .mockResolvedValueOnce({
        chunkId: "chunk-id",
        stationId: "station-id",
        stationName: "Pallet A",
        factoryTimezone: "America/New_York",
        startIso: "2026-07-14T20:00:35Z",
        endIso: "2026-07-14T20:15:35Z",
        sourceStartMs: 0,
        sourceEndMs: 900000,
        renditionSourceStartMs: 0,
        renditionSourceEndMs: 900000,
        sourceSha256: "c".repeat(64),
        renditionId: "rendition-id",
        mediaBucket: "review-renditions",
        mediaPath: "review/pallet-a.mp4",
      });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        Response.json({ signedURL: "/object/sign/review-renditions/token" }),
      ),
    );
    const { GET } = await import("@/app/api/review/preview/route");

    const response = await GET(
      new NextRequest("https://factoryvision-review.vercel.app/api/review/preview"),
    );
    const body = await response.json();

    expect(response.status).toBe(200);
    expect(body).toMatchObject({
      allowed: true,
      practice: {
        id: "practice-preview-chunk-id",
        leaseToken: "practice-preview",
        chunk: {
          id: "chunk-id",
          stationName: "Pallet A",
          mediaUrl:
            "https://project.supabase.co/storage/v1/object/sign/review-renditions/token",
        },
        actions: [],
        coverage: null,
      },
    });
    expect(opsRpc).toHaveBeenNthCalledWith(
      1,
      expect.any(NextRequest),
      "ops_latest_practice_preview",
      {},
    );
  });

  it("returns no practice assignment when none is configured", async () => {
    opsRpc.mockResolvedValueOnce(null);
    const { GET } = await import("@/app/api/review/preview/route");

    const response = await GET(
      new NextRequest("https://factoryvision-review.vercel.app/api/review/preview"),
    );

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ allowed: true, practice: null });
  });

  it("returns a clean negative capability response without an ops session", async () => {
    authorizeOps.mockResolvedValue({ authorized: false, status: 401 });
    const { GET } = await import("@/app/api/review/preview/route");

    const response = await GET(
      new NextRequest("https://factoryvision-review.vercel.app/api/review/preview"),
    );

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({
      allowed: false,
      practice: null,
    });
    expect(opsRpc).not.toHaveBeenCalled();
  });

  it("reports an unavailable capability service separately from denial", async () => {
    authorizeOps.mockRejectedValue(new Error("provider unavailable"));
    const { GET } = await import("@/app/api/review/preview/route");

    const response = await GET(
      new NextRequest("https://factoryvision-review.vercel.app/api/review/preview"),
    );

    expect(response.status).toBe(503);
    expect(await response.json()).toEqual({
      error: "PRACTICE_PREVIEW_UNAVAILABLE",
    });
  });

  it("uses the service-only practice lookup for a valid preview pass", async () => {
    hasReviewPreviewPass.mockReturnValue(true);
    const chunk = {
      chunkId: "chunk-id",
      stationId: "station-id",
      stationName: "Pallet A",
      factoryTimezone: "America/New_York",
      startIso: "2026-07-14T20:00:35Z",
      endIso: "2026-07-14T20:15:35Z",
      sourceStartMs: 0,
      sourceEndMs: 900000,
      renditionSourceStartMs: 0,
      renditionSourceEndMs: 900000,
      sourceSha256: "c".repeat(64),
      renditionId: "rendition-id",
      mediaBucket: "review-renditions",
      mediaPath: "review/pallet-a.mp4",
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(Response.json(chunk))
      .mockResolvedValueOnce(
        Response.json({ signedURL: "/object/sign/review-renditions/token" }),
      );
    vi.stubGlobal("fetch", fetchMock);
    const { GET } = await import("@/app/api/review/preview/route");

    const response = await GET(
      new NextRequest("https://factoryvision-review.vercel.app/api/review/preview"),
    );

    expect(response.status).toBe(200);
    expect((await response.json()).practice.chunk.stationName).toBe("Pallet A");
    expect(opsRpc).not.toHaveBeenCalled();
    expect(authorizeOps).not.toHaveBeenCalled();
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "https://project.supabase.co/rest/v1/rpc/service_latest_practice_preview",
      expect.objectContaining({ method: "POST", body: "{}" }),
    );
  });
});
