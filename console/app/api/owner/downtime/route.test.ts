import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { POST } from "@/app/api/owner/downtime/route";

const factoryId = "10000000-0000-0000-0000-000000000001";
const projectId = "40000000-0000-0000-0000-000000000001";
const stationId = "20000000-0000-0000-0000-000000000001";

function request(body: unknown, origin = "https://factoryvision.example") {
  return new NextRequest(
    `https://factoryvision.example/api/owner/downtime?factory_id=${factoryId}`,
    {
      method: "POST",
      headers: {
        cookie: "fv_owner_access=owner-token",
        origin,
        "content-type": "application/json",
      },
      body: JSON.stringify(body),
    },
  );
}

describe("/api/owner/downtime", () => {
  beforeEach(() => {
    process.env.NEXT_PUBLIC_SUPABASE_URL = "https://project.supabase.co";
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY = "publishable-key";
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("records owner-entered downtime through the audited RPC", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        Response.json({ authorized: true, factories: [{ id: factoryId }] }),
      )
      .mockResolvedValueOnce(Response.json({ id: "downtime-1" }));
    vi.stubGlobal("fetch", fetchMock);
    const response = await POST(request({
      projectId,
      stationId,
      effectiveStart: "2026-07-29T09:00:00Z",
      effectiveEnd: "2026-07-29T09:15:00Z",
      reasonCode: "equipment_breakdown",
      note: "Press jam",
    }));
    expect(response.status).toBe(201);
    expect(fetchMock.mock.calls[1]?.[0]).toContain(
      "/rest/v1/rpc/owner_record_downtime",
    );
    expect(JSON.parse(String(fetchMock.mock.calls[1]?.[1]?.body))).toEqual({
      p_factory_id: factoryId,
      p_project_id: projectId,
      p_station_id: stationId,
      p_effective_start: "2026-07-29T09:00:00Z",
      p_effective_end: "2026-07-29T09:15:00Z",
      p_reason_code: "equipment_breakdown",
      p_note: "Press jam",
    });
  });

  it("authorizes before revealing downtime validation details", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce(
        Response.json({ authorized: false, factories: [] }),
      ),
    );
    const response = await POST(request({}));
    expect(response.status).toBe(403);
    expect(await response.json()).toEqual({ error: "OWNER_ACCESS_DENIED" });
  });

  it("rejects cross-origin and invalid downtime before mutation", async () => {
    const crossOriginFetch = vi.fn();
    vi.stubGlobal("fetch", crossOriginFetch);
    const crossOrigin = await POST(request(
      {
        projectId,
        stationId,
        effectiveStart: "2026-07-29T09:00:00Z",
        effectiveEnd: "2026-07-29T09:15:00Z",
        reasonCode: "changeover",
      },
      "https://attacker.example",
    ));
    expect(crossOrigin.status).toBe(403);
    expect(crossOriginFetch).not.toHaveBeenCalled();

    const validationFetch = vi
      .fn()
      .mockResolvedValueOnce(
        Response.json({ authorized: true, factories: [{ id: factoryId }] }),
      );
    vi.stubGlobal("fetch", validationFetch);
    const invalid = await POST(request({
      projectId,
      stationId,
      effectiveStart: "2026-07-29T09:15:00Z",
      effectiveEnd: "2026-07-29T09:00:00Z",
      reasonCode: "changeover",
    }));
    expect(invalid.status).toBe(422);
    expect(validationFetch).toHaveBeenCalledTimes(1);
  });
});
