import { afterEach, describe, expect, it } from "vitest";
import { NextRequest } from "next/server";
import { middleware } from "@/middleware";

const originalPortalOnly = process.env.FV_PUBLIC_PORTAL_ONLY;

afterEach(() => {
  if (originalPortalOnly === undefined) {
    delete process.env.FV_PUBLIC_PORTAL_ONLY;
  } else {
    process.env.FV_PUBLIC_PORTAL_ONLY = originalPortalOnly;
  }
});

describe("public portal middleware", () => {
  it("does not affect the private console by default", () => {
    delete process.env.FV_PUBLIC_PORTAL_ONLY;

    const response = middleware(
      new NextRequest("https://factoryvision.example/jobs"),
    );

    expect(response.headers.get("x-middleware-next")).toBe("1");
  });

  it.each([
    "/review",
    "/review/welcome",
    "/ops",
    "/api/review/session",
    "/api/ops/snapshot",
  ])("allows the workforce portal path %s", (pathname) => {
    process.env.FV_PUBLIC_PORTAL_ONLY = "1";

    const response = middleware(
      new NextRequest(`https://factoryvision.example${pathname}`),
    );

    expect(response.headers.get("x-middleware-next")).toBe("1");
  });

  it("redirects private console pages to the worker portal", () => {
    process.env.FV_PUBLIC_PORTAL_ONLY = "1";

    const response = middleware(
      new NextRequest("https://factoryvision.example/jobs"),
    );

    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe(
      "https://factoryvision.example/review",
    );
  });

  it("hides private console APIs", () => {
    process.env.FV_PUBLIC_PORTAL_ONLY = "1";

    const response = middleware(
      new NextRequest("https://factoryvision.example/api/jobs"),
    );

    expect(response.status).toBe(404);
  });
});
