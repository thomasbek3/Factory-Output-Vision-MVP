import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

describe("reviewer passwordless session route", () => {
  beforeEach(() => {
    vi.resetModules();
    process.env.NEXT_PUBLIC_SUPABASE_URL = "https://project.supabase.co";
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY = "publishable-key";
    process.env.REVIEW_PUBLIC_BASE_URL =
      "https://factoryvision-review.vercel.app";
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    delete process.env.REVIEW_PUBLIC_BASE_URL;
  });

  it("requests an existing-user magic link without creating an account", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(Response.json(true))
      .mockResolvedValueOnce(
        new Response("{}", {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    const { POST } = await import("@/app/api/review/session/route");

    const response = await POST(
      new NextRequest("https://factoryvision-review.vercel.app/api/review/session", {
        method: "POST",
        body: JSON.stringify({
          action: "requestPasswordless",
          email: " Worker@Example.com ",
          language: "en",
        }),
      }),
    );

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ sent: true });
    const [rateUrl, rateRequest] = fetchMock.mock.calls[0] as [
      string,
      RequestInit,
    ];
    expect(rateUrl).toContain(
      "/rest/v1/rpc/check_passwordless_login_rate",
    );
    expect(JSON.parse(String(rateRequest.body))).toMatchObject({
      p_email_hash: expect.stringMatching(/^[0-9a-f]{64}$/),
      p_ip_hash: expect.stringMatching(/^[0-9a-f]{64}$/),
    });
    const [url, request] = fetchMock.mock.calls[1] as [string, RequestInit];
    expect(url).toContain("/auth/v1/otp?redirect_to=");
    expect(decodeURIComponent(url)).toContain(
      "https://factoryvision-review.vercel.app/review/welcome?mode=login&lang=en",
    );
    expect(JSON.parse(String(request.body))).toEqual({
      email: "worker@example.com",
      data: {},
      create_user: false,
    });
  });

  it("returns the same success response when Supabase does not know the email", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(Response.json(true))
      .mockResolvedValueOnce(
        Response.json(
          { msg: "Signups not allowed for otp" },
          { status: 422 },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);
    const { POST } = await import("@/app/api/review/session/route");

    const response = await POST(
      new NextRequest("https://factoryvision-review.vercel.app/api/review/session", {
        method: "POST",
        body: JSON.stringify({
          action: "requestPasswordless",
          email: "unknown@example.com",
          language: "en",
        }),
      }),
    );

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ sent: true });
  });

  it("rejects requests denied by the application rate limiter", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(Response.json(false));
    vi.stubGlobal("fetch", fetchMock);
    const { POST } = await import("@/app/api/review/session/route");

    const response = await POST(
      new NextRequest("https://factoryvision-review.vercel.app/api/review/session", {
        method: "POST",
        body: JSON.stringify({
          action: "requestPasswordless",
          email: "worker@example.com",
          language: "en",
        }),
      }),
    );

    expect(response.status).toBe(429);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("sets reviewer cookies only after lifecycle authorization succeeds", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        Response.json({ id: "reviewer-id", email: "worker@example.com" }),
      )
      .mockResolvedValueOnce(Response.json({ authorized: true }));
    vi.stubGlobal("fetch", fetchMock);
    const { POST } = await import("@/app/api/review/session/route");

    const response = await POST(
      new NextRequest("https://factoryvision-review.vercel.app/api/review/session", {
        method: "POST",
        body: JSON.stringify({
          action: "completePasswordless",
          accessToken: "access-token",
          refreshToken: "refresh-token",
          expiresIn: 1800,
        }),
      }),
    );

    expect(response.status).toBe(200);
    expect(response.headers.get("set-cookie")).toContain("fv_review_access");
    expect(response.headers.get("set-cookie")).toContain("HttpOnly");
    expect(response.headers.get("set-cookie")).toContain("Secure");
    expect(response.headers.get("set-cookie")).toContain("Max-Age=1800");
  });

  it("rejects a valid Supabase token that is not an authorized reviewer", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        Response.json({ id: "other-user", email: "other@example.com" }),
      )
      .mockResolvedValueOnce(new Response("{}", { status: 403 }));
    vi.stubGlobal("fetch", fetchMock);
    const { POST } = await import("@/app/api/review/session/route");

    const response = await POST(
      new NextRequest("https://factoryvision-review.vercel.app/api/review/session", {
        method: "POST",
        body: JSON.stringify({
          action: "completePasswordless",
          accessToken: "access-token",
          refreshToken: "refresh-token",
        }),
      }),
    );

    expect(response.status).toBe(401);
    expect(response.headers.get("set-cookie")).toBeNull();
  });
});
