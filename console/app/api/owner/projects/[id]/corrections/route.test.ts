import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { POST } from "@/app/api/owner/projects/[id]/corrections/route";

const factoryId = "10000000-0000-0000-0000-000000000001";
const projectId = "40000000-0000-0000-0000-000000000001";

function request(
  body: unknown,
  origin = "https://factoryvision.example",
) {
  return new NextRequest(
    `https://factoryvision.example/api/owner/projects/${projectId}/corrections?factory_id=${factoryId}`,
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

const context = { params: Promise.resolve({ id: projectId }) };

describe("/api/owner/projects/[id]/corrections", () => {
  beforeEach(() => {
    process.env.NEXT_PUBLIC_SUPABASE_URL = "https://project.supabase.co";
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY = "publishable-key";
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("authorizes before validating correction details", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce(
        Response.json({ authorized: false, factories: [] }),
      ),
    );
    const response = await POST(request({ deltaGoodUnits: 0 }), context);
    expect(response.status).toBe(403);
    expect(await response.json()).toEqual({ error: "OWNER_ACCESS_DENIED" });
  });

  it("rejects a cross-origin correction before authorization", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const response = await POST(
      request({ deltaGoodUnits: 1 }, "https://attacker.example"),
      context,
    );
    expect(response.status).toBe(403);
    expect(await response.json()).toEqual({ error: "OWNER_ORIGIN_INVALID" });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects positive scrap adjustments", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce(
        Response.json({ authorized: true, factories: [{ id: factoryId }] }),
      ),
    );
    const response = await POST(
      request({
        kind: "scrap",
        deltaGoodUnits: 1,
        reasonCode: "scrap",
        occurredAt: "2026-07-28T20:00:00Z",
      }),
      context,
    );
    expect(response.status).toBe(422);
  });

  it("appends a correction closeout revision through the owner RPC", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        Response.json({ authorized: true, factories: [{ id: factoryId }] }),
      )
      .mockResolvedValueOnce(
        Response.json({ id: "closeout-2", revision: 2 }),
      );
    vi.stubGlobal("fetch", fetchMock);
    const response = await POST(
      request({
        kind: "correction",
        deltaGoodUnits: 2,
        reasonCode: "missed-output",
        note: "Verified against retained evidence.",
        occurredAt: "2026-07-28T20:00:00Z",
        actualMaterialCostCents: 26000,
      }),
      context,
    );
    expect(response.status).toBe(201);
    expect(fetchMock.mock.calls[1][0]).toContain(
      "/rest/v1/rpc/owner_correct_closeout",
    );
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({
      p_factory_id: factoryId,
      p_project_id: projectId,
      p_kind: "correction",
      p_delta_good_units: 2,
      p_reason_code: "missed-output",
      p_note: "Verified against retained evidence.",
      p_occurred_at: "2026-07-28T20:00:00Z",
      p_actual_material_cost_cents: 26000,
    });
  });
});
