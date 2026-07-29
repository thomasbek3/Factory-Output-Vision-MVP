import { describe, expect, it } from "vitest";
import { NextRequest } from "next/server";
import { middleware } from "@/middleware";

function request(pathname: string, cookie?: string) {
  return new NextRequest(`https://factoryvision.example${pathname}`, {
    headers: cookie ? { cookie } : undefined,
  });
}

function jwt(exp: number) {
  const encode = (value: object) =>
    Buffer.from(JSON.stringify(value)).toString("base64url");
  return `${encode({ alg: "none" })}.${encode({ exp })}.signature`;
}

describe("role surface middleware", () => {
  it.each([
    "/sign-in",
    "/ops/sign-in",
    "/review",
    "/review/welcome",
    "/api/review/preview",
    "/api/review/preview-access",
    "/owner-preview",
    "/owner-preview/tv",
    "/ops-preview",
  ])("allows the explicit public path %s", (pathname) => {
    const response = middleware(request(pathname));
    expect(response.headers.get("x-middleware-next")).toBe("1");
  });

  it("redirects an anonymous owner page to owner sign-in", () => {
    const response = middleware(request("/projects"));
    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe(
      "https://factoryvision.example/sign-in",
    );
  });

  it("allows an owner page only with an owner session cookie", () => {
    const response = middleware(
      request("/projects", "fv_owner_access=owner-token"),
    );
    expect(response.headers.get("x-middleware-next")).toBe("1");
    expect(
      response.headers.get(
        "x-middleware-request-x-fv-owner-return-to",
      ),
    ).toBe("/projects");
  });

  it.each([
    "fv_review_access=reviewer-token",
    "fv_ops_access=ops-token",
  ])("does not accept a foreign role cookie for owner pages", (cookie) => {
    const response = middleware(request("/projects", cookie));
    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe(
      "https://factoryvision.example/sign-in",
    );
  });

  it("rotates an expired owner page session before rendering", () => {
    const expired = jwt(Math.floor(Date.now() / 1000) - 60);
    const response = middleware(
      request(
        "/history?factory_id=10000000-0000-0000-0000-000000000001",
        `fv_owner_access=${expired}; fv_owner_refresh=refresh-token`,
      ),
    );
    expect(response.status).toBe(307);
    const location = new URL(response.headers.get("location") ?? "");
    expect(location.pathname).toBe("/api/owner/session");
    expect(location.searchParams.get("action")).toBe("refresh");
    expect(location.searchParams.get("return_to")).toBe(
      "/history?factory_id=10000000-0000-0000-0000-000000000001",
    );
  });

  it("redirects /ops unless an ops cookie is present", () => {
    const anonymous = middleware(request("/ops"));
    const owner = middleware(request("/ops", "fv_owner_access=owner-token"));
    const ops = middleware(request("/ops", "fv_ops_access=ops-token"));
    expect(anonymous.headers.get("location")).toBe(
      "https://factoryvision.example/ops/sign-in",
    );
    expect(owner.headers.get("location")).toBe(
      "https://factoryvision.example/ops/sign-in",
    );
    expect(ops.headers.get("x-middleware-next")).toBe("1");
  });

  it("does not accept reviewer or owner cookies for ops APIs", () => {
    expect(
      middleware(
        request("/api/ops/snapshot", "fv_review_access=reviewer-token"),
      ).status,
    ).toBe(401);
    expect(
      middleware(
        request("/api/ops/snapshot", "fv_owner_access=owner-token"),
      ).status,
    ).toBe(401);
  });

  it("rejects anonymous owner APIs", () => {
    const response = middleware(request("/api/owner/projects"));
    expect(response.status).toBe(401);
  });

  it("does not accept reviewer or ops cookies for owner APIs", () => {
    expect(
      middleware(
        request("/api/owner/projects", "fv_review_access=reviewer-token"),
      ).status,
    ).toBe(401);
    expect(
      middleware(
        request("/api/owner/projects", "fv_ops_access=ops-token"),
      ).status,
    ).toBe(401);
  });

  it("removes legacy owner and TV APIs from production", () => {
    expect(middleware(request("/api/jobs")).status).toBe(404);
    expect(middleware(request("/tv")).status).toBe(404);
    expect(middleware(request("/replay")).status).toBe(404);
    expect(middleware(request("/replay/fixture")).status).toBe(404);
  });
});
