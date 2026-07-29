import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { authorizeOps, opsRpc } from "@/lib/opsServer";

const factoryId = "10000000-0000-0000-0000-000000000001";

function request(cookie: string) {
  return new NextRequest("https://factoryvision.example/api/ops/snapshot", {
    headers: { cookie },
  });
}

describe("opsServer", () => {
  beforeEach(() => {
    process.env.NEXT_PUBLIC_SUPABASE_URL = "https://project.supabase.co";
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY = "publishable-key";
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("does not accept reviewer or owner cookies for ops", async () => {
    expect(await authorizeOps(request("fv_review_access=reviewer"), factoryId)).toEqual({
      authorized: false,
      status: 401,
    });
    expect(await authorizeOps(request("fv_owner_access=owner"), factoryId)).toEqual({
      authorized: false,
      status: 401,
    });
  });

  it("authorizes and calls ops RPCs with only the ops token", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(Response.json(true))
      .mockResolvedValueOnce(Response.json({ factories: 3 }));
    vi.stubGlobal("fetch", fetchMock);
    const opsRequest = request("fv_ops_access=ops-token");

    expect(await authorizeOps(opsRequest, factoryId)).toEqual({
      authorized: true,
      accessToken: "ops-token",
    });
    expect(await opsRpc(opsRequest, "ops_workforce_metrics", {})).toEqual({
      factories: 3,
    });
    for (const [, init] of fetchMock.mock.calls) {
      expect(init.headers.Authorization).toBe("Bearer ops-token");
      expect(init.headers.apikey).toBe("publishable-key");
    }
  });
});
