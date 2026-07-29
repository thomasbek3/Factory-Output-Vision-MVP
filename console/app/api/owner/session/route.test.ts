import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { DELETE, GET, POST } from "@/app/api/owner/session/route";

describe("/api/owner/session", () => {
  beforeEach(() => {
    process.env.NEXT_PUBLIC_SUPABASE_URL = "https://project.supabase.co";
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY = "publishable-key";
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("completes a passwordless owner session with strict HttpOnly cookies", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(
          Response.json({ id: "owner-1", email: "owner@example.com" }),
        )
        .mockResolvedValueOnce(
          Response.json({ authorized: true, factories: [{ id: "factory-1" }] }),
        ),
    );
    const response = await POST(
      new NextRequest("https://factoryvision.example/api/owner/session", {
        method: "POST",
        headers: { origin: "https://factoryvision.example" },
        body: JSON.stringify({
          action: "completePasswordless",
          accessToken: "access-token",
          refreshToken: "refresh-token",
          expiresIn: 3600,
        }),
      }),
    );

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({
      user: { id: "owner-1", email: "owner@example.com" },
      factories: [{ id: "factory-1" }],
    });
    const cookies = response.headers.getSetCookie().join("\n");
    expect(cookies).toContain("fv_owner_access=access-token");
    expect(cookies).toContain("fv_owner_refresh=refresh-token");
    expect(cookies).toContain("HttpOnly");
    expect(cookies).toContain("SameSite=strict");
    expect(cookies).toContain("Secure");
  });

  it("rejects a valid Supabase identity without an owner membership", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(
          Response.json({ id: "reviewer-1", email: "reviewer@example.com" }),
        )
        .mockResolvedValueOnce(
          Response.json({ authorized: false, factories: [] }),
        ),
    );
    const response = await POST(
      new NextRequest("https://factoryvision.example/api/owner/session", {
        method: "POST",
        headers: { origin: "https://factoryvision.example" },
        body: JSON.stringify({
          action: "completePasswordless",
          accessToken: "reviewer-token",
          refreshToken: "refresh-token",
        }),
      }),
    );
    expect(response.status).toBe(403);
    expect(response.headers.getSetCookie()).toHaveLength(0);
  });

  it("rotates owner access and refresh cookies through Supabase", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        Response.json({
          access_token: "rotated-access",
          refresh_token: "rotated-refresh",
          expires_in: 7200,
        }),
      )
      .mockResolvedValueOnce(
        Response.json({ id: "owner-1", email: "owner@example.com" }),
      )
      .mockResolvedValueOnce(
        Response.json({ authorized: true, factories: [{ id: "factory-1" }] }),
      );
    vi.stubGlobal("fetch", fetchMock);
    const response = await POST(
      new NextRequest("https://factoryvision.example/api/owner/session", {
        method: "POST",
        headers: {
          cookie: "fv_owner_refresh=original-refresh",
          "content-type": "application/json",
          origin: "https://factoryvision.example",
        },
        body: JSON.stringify({ action: "refresh" }),
      }),
    );
    expect(response.status).toBe(200);
    expect(fetchMock.mock.calls[0][0]).toContain(
      "/auth/v1/token?grant_type=refresh_token",
    );
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      refresh_token: "original-refresh",
    });
    const cookies = response.headers.getSetCookie().join("\n");
    expect(cookies).toContain("fv_owner_access=rotated-access");
    expect(cookies).toContain("fv_owner_refresh=rotated-refresh");
  });

  it("rejects a cross-origin session refresh before token rotation", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const response = await POST(
      new NextRequest("https://factoryvision.example/api/owner/session", {
        method: "POST",
        headers: {
          cookie: "fv_owner_refresh=original-refresh",
          "content-type": "application/json",
          origin: "https://attacker.example",
        },
        body: JSON.stringify({ action: "refresh" }),
      }),
    );

    expect(response.status).toBe(403);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects cross-origin passwordless completion before token inspection", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const response = await POST(
      new NextRequest("https://factoryvision.example/api/owner/session", {
        method: "POST",
        headers: { origin: "https://attacker.example" },
        body: JSON.stringify({
          action: "completePasswordless",
          accessToken: "attacker-access",
          refreshToken: "attacker-refresh",
        }),
      }),
    );
    expect(response.status).toBe(403);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("requests a magic link that preserves a safe owner return path", async () => {
    const fetchMock = vi.fn().mockResolvedValue(Response.json({}));
    vi.stubGlobal("fetch", fetchMock);
    const response = await POST(
      new NextRequest("https://factoryvision.example/api/owner/session", {
        method: "POST",
        headers: {
          origin: "https://factoryvision.example",
          "content-type": "application/json",
        },
        body: JSON.stringify({
          action: "requestPasswordless",
          email: "owner@example.com",
          returnTo: "/?new=1&factory_id=factory-1",
        }),
      }),
    );

    expect(response.status).toBe(200);
    const requestUrl = new URL(fetchMock.mock.calls[0][0] as string);
    const redirectTo = new URL(requestUrl.searchParams.get("redirect_to") ?? "");
    expect(redirectTo.origin).toBe("https://factoryvision.example");
    expect(redirectTo.pathname).toBe("/sign-in");
    expect(redirectTo.searchParams.get("return_to")).toBe(
      "/?new=1&factory_id=factory-1",
    );
  });

  it("replaces an unsafe magic-link return path with the owner root", async () => {
    const fetchMock = vi.fn().mockResolvedValue(Response.json({}));
    vi.stubGlobal("fetch", fetchMock);
    await POST(
      new NextRequest("https://factoryvision.example/api/owner/session", {
        method: "POST",
        headers: {
          origin: "https://factoryvision.example",
          "content-type": "application/json",
        },
        body: JSON.stringify({
          action: "requestPasswordless",
          email: "owner@example.com",
          returnTo: "//attacker.example",
        }),
      }),
    );

    const requestUrl = new URL(fetchMock.mock.calls[0][0] as string);
    const redirectTo = new URL(requestUrl.searchParams.get("redirect_to") ?? "");
    expect(redirectTo.searchParams.get("return_to")).toBe("/");
  });

  it("refreshes an expired page session and returns to the same owner route", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(
          Response.json({
            access_token: "rotated-access",
            refresh_token: "rotated-refresh",
            expires_in: 7200,
          }),
        )
        .mockResolvedValueOnce(
          Response.json({ id: "owner-1", email: "owner@example.com" }),
        )
        .mockResolvedValueOnce(
          Response.json({ authorized: true, factories: [{ id: "factory-1" }] }),
        ),
    );
    const response = await GET(
      new NextRequest(
        "https://factoryvision.example/api/owner/session?action=refresh&return_to=%2Fhistory%3Ffactory_id%3Dfactory-1",
        { headers: { cookie: "fv_owner_refresh=original-refresh" } },
      ),
    );
    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe(
      "https://factoryvision.example/history?factory_id=factory-1",
    );
    expect(response.headers.getSetCookie().join("\n")).toContain(
      "fv_owner_access=rotated-access",
    );
  });

  it("refuses a backslash-based refresh redirect escape", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(
          Response.json({
            access_token: "rotated-access",
            refresh_token: "rotated-refresh",
          }),
        )
        .mockResolvedValueOnce(
          Response.json({ id: "owner-1", email: "owner@example.com" }),
        )
        .mockResolvedValueOnce(
          Response.json({ authorized: true, factories: [{ id: "factory-1" }] }),
        ),
    );
    const response = await GET(
      new NextRequest(
        "https://factoryvision.example/api/owner/session?action=refresh&return_to=%2F%5Cevil.example",
        { headers: { cookie: "fv_owner_refresh=original-refresh" } },
      ),
    );
    expect(response.headers.get("location")).toBe(
      "https://factoryvision.example/",
    );
  });

  it("clears both owner cookies on sign out", async () => {
    const response = await DELETE(
      new NextRequest("https://factoryvision.example/api/owner/session", {
        method: "DELETE",
        headers: { origin: "https://factoryvision.example" },
      }),
    );
    const cookies = response.headers.getSetCookie().join("\n");
    expect(cookies).toContain("fv_owner_access=;");
    expect(cookies).toContain("fv_owner_refresh=;");
    expect(cookies).toContain("Max-Age=0");
  });

  it("rejects cross-origin owner sign out", async () => {
    const response = await DELETE(
      new NextRequest("https://factoryvision.example/api/owner/session", {
        method: "DELETE",
        headers: { origin: "https://attacker.example" },
      }),
    );
    expect(response.status).toBe(403);
    expect(response.headers.get("set-cookie")).toBeNull();
  });
});
