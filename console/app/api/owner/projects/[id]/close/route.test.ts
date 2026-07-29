import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { POST } from "@/app/api/owner/projects/[id]/close/route";

const factoryId = "10000000-0000-0000-0000-000000000001";
const projectId = "40000000-0000-0000-0000-000000000001";

function request(
  body: unknown,
  targetFactoryId = factoryId,
  origin = "https://factoryvision.example",
) {
  return new NextRequest(
    `https://factoryvision.example/api/owner/projects/${projectId}/close?factory_id=${targetFactoryId}`,
    {
      method: "POST",
      headers: {
        cookie: "fv_owner_access=owner-token",
        "content-type": "application/json",
        origin,
      },
      body: JSON.stringify(body),
    },
  );
}

function context(id = projectId) {
  return { params: Promise.resolve({ id }) };
}

describe("/api/owner/projects/[id]/close", () => {
  beforeEach(() => {
    process.env.NEXT_PUBLIC_SUPABASE_URL = "https://project.supabase.co";
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY = "publishable-key";
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("rejects malformed ids before authorization", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const response = await POST(
      request({ actualMaterialCostCents: 100 }, "bad-id"),
      context(),
    );
    expect(response.status).toBe(422);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects a cross-origin closeout before authorization", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const response = await POST(
      request(
        { actualMaterialCostCents: 100 },
        factoryId,
        "https://attacker.example",
      ),
      context(),
    );
    expect(response.status).toBe(403);
    expect(await response.json()).toEqual({ error: "OWNER_ORIGIN_INVALID" });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("authorizes before validating closeout details", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce(
        Response.json({ authorized: false, factories: [] }),
      ),
    );
    const response = await POST(
      request({ actualMaterialCostCents: -1 }),
      context(),
    );
    expect(response.status).toBe(403);
    expect(await response.json()).toEqual({ error: "OWNER_ACCESS_DENIED" });
  });

  it("requires explicit actual material cents", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce(
        Response.json({ authorized: true, factories: [{ id: factoryId }] }),
      ),
    );
    const response = await POST(request({}), context());
    expect(response.status).toBe(422);
    expect(await response.json()).toEqual({ error: "OWNER_CLOSEOUT_INVALID" });
  });

  it("rejects a future completion after authorization", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce(
        Response.json({ authorized: true, factories: [{ id: factoryId }] }),
      ),
    );
    const response = await POST(
      request({
        actualMaterialCostCents: 100,
        completedAt: "2999-01-01T00:00:00Z",
      }),
      context(),
    );
    expect(response.status).toBe(422);
    expect(await response.json()).toEqual({ error: "OWNER_CLOSEOUT_INVALID" });
  });

  it("creates an immutable closeout through the owner RPC", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        Response.json({ authorized: true, factories: [{ id: factoryId }] }),
      )
      .mockResolvedValueOnce(
        Response.json({
          id: "closeout-1",
          project_id: projectId,
          revision: 1,
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    const response = await POST(
      request({
        actualMaterialCostCents: 27500,
        completedAt: "2026-07-28T23:00:00Z",
      }),
      context(),
    );
    expect(response.status).toBe(201);
    expect(fetchMock.mock.calls[1][0]).toContain(
      "/rest/v1/rpc/owner_close_project",
    );
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({
      p_factory_id: factoryId,
      p_project_id: projectId,
      p_actual_material_cost_cents: 27500,
      p_completed_at: "2026-07-28T23:00:00Z",
    });
  });
});
