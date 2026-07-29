import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { DELETE, POST } from "@/app/api/ops/session/route";

function request(body: Record<string, unknown>, cookie = "") {
  return new NextRequest("https://factoryvision.example/api/ops/session", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      origin: "https://factoryvision.example",
      ...(cookie ? { cookie } : {}),
    },
    body: JSON.stringify(body),
  });
}

describe("/api/ops/session", () => {
  beforeEach(() => {
    process.env.NEXT_PUBLIC_SUPABASE_URL = "https://project.supabase.co";
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY = "publishable-key";
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("establishes strict ops cookies only after ops authorization", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(
          Response.json({ id: "ops-user", email: "ops@example.com" }),
        )
        .mockResolvedValueOnce(Response.json(true)),
    );
    const response = await POST(
      request({
        action: "completePasswordless",
        accessToken: "ops-access",
        refreshToken: "ops-refresh",
        expiresIn: 3600,
      }),
    );
    expect(response.status).toBe(200);
    const cookies = response.headers.get("set-cookie") ?? "";
    expect(cookies).toContain("fv_ops_access=ops-access");
    expect(cookies).toContain("fv_ops_refresh=ops-refresh");
    expect(cookies).toContain("HttpOnly");
    expect(cookies).toContain("SameSite=strict");
  });

  it("denies a valid Supabase user without an ops membership", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(Response.json({ id: "owner-user" }))
        .mockResolvedValueOnce(
          Response.json({ code: "42501", message: "ops access required" }, { status: 403 }),
        ),
    );
    const response = await POST(
      request({
        action: "completePasswordless",
        accessToken: "owner-access",
        refreshToken: "owner-refresh",
      }),
    );
    expect(response.status).toBe(403);
    expect(await response.json()).toEqual({ error: "OPS_ACCESS_DENIED" });
  });

  it("rotates ops access and refresh cookies through Supabase", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        Response.json({
          access_token: "rotated-ops-access",
          refresh_token: "rotated-ops-refresh",
          expires_in: 7200,
        }),
      )
      .mockResolvedValueOnce(
        Response.json({ id: "ops-user", email: "ops@example.com" }),
      )
      .mockResolvedValueOnce(Response.json(true));
    vi.stubGlobal("fetch", fetchMock);
    const response = await POST(
      request({ action: "refresh" }, "fv_ops_refresh=original-ops-refresh"),
    );
    expect(response.status).toBe(200);
    expect(fetchMock.mock.calls[0][0]).toContain(
      "/auth/v1/token?grant_type=refresh_token",
    );
    const cookies = response.headers.get("set-cookie") ?? "";
    expect(cookies).toContain("fv_ops_access=rotated-ops-access");
    expect(cookies).toContain("fv_ops_refresh=rotated-ops-refresh");
  });

  it("rejects cross-origin and malformed session requests before auth calls", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const crossOrigin = await POST(
      new NextRequest("https://factoryvision.example/api/ops/session", {
        method: "POST",
        headers: {
          "content-type": "application/json",
          origin: "https://attacker.example",
        },
        body: JSON.stringify({ action: "refresh" }),
      }),
    );
    expect(crossOrigin.status).toBe(403);
    const malformed = await POST(
      new NextRequest("https://factoryvision.example/api/ops/session", {
        method: "POST",
        headers: {
          "content-type": "application/json",
          origin: "https://factoryvision.example",
        },
        body: "{",
      }),
    );
    expect(malformed.status).toBe(400);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("clears both ops cookies on sign out", async () => {
    const response = await DELETE(
      new NextRequest("https://factoryvision.example/api/ops/session", {
        method: "DELETE",
        headers: { origin: "https://factoryvision.example" },
      }),
    );
    const cookies = response.headers.get("set-cookie") ?? "";
    expect(cookies).toContain("fv_ops_access=");
    expect(cookies).toContain("fv_ops_refresh=");
  });

  it("rejects cross-origin ops sign out", async () => {
    const response = await DELETE(
      new NextRequest("https://factoryvision.example/api/ops/session", {
        method: "DELETE",
        headers: { origin: "https://attacker.example" },
      }),
    );
    expect(response.status).toBe(403);
    expect(response.headers.get("set-cookie")).toBeNull();
  });
});
