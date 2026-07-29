import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { GET, POST } from "@/app/api/owner/projects/route";

const factoryId = "10000000-0000-0000-0000-000000000001";

function request(
  method: "GET" | "POST",
  body?: Record<string, unknown>,
  includeFactory = true,
) {
  const url = new URL("https://factoryvision.example/api/owner/projects");
  if (includeFactory) url.searchParams.set("factory_id", factoryId);
  return new NextRequest(url, {
    method,
    headers: {
      cookie: "fv_owner_access=owner-access-token",
      ...(method === "POST"
        ? { origin: "https://factoryvision.example" }
        : {}),
      ...(body ? { "content-type": "application/json" } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
}

const projectDraft = {
  factoryId,
  name: "Lot 42 Fence Panels",
  client: "Smoke Test Fixtures Inc.",
  targetUnits: "400",
  valueMode: "total",
  valueUsd: "1000.00",
  materialMode: "per_unit",
  materialUsd: "0.75",
  stationId: "20000000-0000-0000-0000-000000000001",
  stationSuggested: false,
  stationConfirmed: true,
  startDate: "2026-12-15",
  startTime: "09:00",
  deadlineDate: "2026-12-15",
  deadlineTime: "17:30",
  timezone: "America/Los_Angeles",
  shiftCalendar: {
    timezone: "America/Los_Angeles",
    shifts: [{ weekday: 2, start: "09:00", end: "17:30" }],
  },
  workerIds: ["61000000-0000-0000-0000-000000000001"],
  loadedLaborRateUsd: "22.50",
  targetMarginPercent: "25",
};

describe("/api/owner/projects", () => {
  beforeEach(() => {
    process.env.NEXT_PUBLIC_SUPABASE_URL = "https://project.supabase.co";
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY = "publishable-key";
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("requires an explicit factory id", async () => {
    const response = await GET(request("GET", undefined, false));
    expect(response.status).toBe(400);
    expect(await response.json()).toEqual({ error: "FACTORY_ID_REQUIRED" });
  });

  it("rejects malformed factory ids before authorization", async () => {
    const malformed = new NextRequest(
      "https://factoryvision.example/api/owner/projects?factory_id=not-a-uuid",
      { headers: { cookie: "fv_owner_access=owner-access-token" } },
    );
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const response = await GET(malformed);
    expect(response.status).toBe(422);
    expect(await response.json()).toEqual({ error: "FACTORY_ID_INVALID" });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("returns durable projects under the owner JWT", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        Response.json({ authorized: true, factories: [{ id: factoryId }] }),
      )
      .mockResolvedValueOnce(
        Response.json([
          {
            id: "project-1",
            factory_id: factoryId,
            client: "Smoke Test Fixtures Inc.",
          },
        ], { headers: { "Content-Range": "0-0/1" } }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const response = await GET(request("GET"));
    expect(response.status).toBe(200);
    expect((await response.json()).projects[0].client).toBe(
      "Smoke Test Fixtures Inc.",
    );
    const [, projectFetch] = fetchMock.mock.calls;
    expect(projectFetch[1].headers.Authorization).toBe(
      "Bearer owner-access-token",
    );
    expect(projectFetch[1].headers.apikey).toBe("publishable-key");
    expect(JSON.stringify(projectFetch[1].headers)).not.toContain("service");
  });

  it("returns a structured 503 instead of fixtures when storage fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(
          Response.json({ authorized: true, factories: [{ id: factoryId }] }),
        )
        .mockResolvedValueOnce(new Response("database unavailable", { status: 500 })),
    );

    const response = await GET(request("GET"));
    expect(response.status).toBe(503);
    expect(await response.json()).toEqual({ error: "OWNER_DATA_UNAVAILABLE" });
  });

  it("returns 403 for a cross-factory owner instead of calling it an outage", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce(
        Response.json({ authorized: false, factories: [] }),
      ),
    );
    const response = await GET(request("GET"));
    expect(response.status).toBe(403);
    expect(await response.json()).toEqual({ error: "OWNER_ACCESS_DENIED" });
  });

  it("returns 401 for an expired Supabase access token", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce(
        Response.json({ message: "JWT expired" }, { status: 401 }),
      ),
    );
    const response = await GET(request("GET"));
    expect(response.status).toBe(401);
    expect(await response.json()).toEqual({ error: "OWNER_AUTH_REQUIRED" });
  });

  it("authorizes before returning project validation details", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce(
        Response.json({ authorized: false, factories: [] }),
      ),
    );
    const response = await POST(
      request("POST", { ...projectDraft, name: "" }),
    );
    expect(response.status).toBe(403);
    expect(await response.json()).toEqual({ error: "OWNER_ACCESS_DENIED" });
  });

  it("rejects a cross-origin project mutation before authorization", async () => {
    const crossOrigin = new NextRequest(
      `https://factoryvision.example/api/owner/projects?factory_id=${factoryId}`,
      {
        method: "POST",
        headers: {
          cookie: "fv_owner_access=owner-access-token",
          origin: "https://attacker.example",
          "content-type": "application/json",
        },
        body: JSON.stringify(projectDraft),
      },
    );
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const response = await POST(crossOrigin);

    expect(response.status).toBe(403);
    expect(await response.json()).toEqual({ error: "OWNER_ORIGIN_INVALID" });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("returns 422 for an authenticated domain validation failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce(
        Response.json({ authorized: true, factories: [{ id: factoryId }] }),
      ),
    );
    const response = await POST(
      request("POST", { ...projectDraft, name: "" }),
    );
    expect(response.status).toBe(422);
    expect((await response.json()).error).toBe("OWNER_PROJECT_INVALID");
  });

  it("creates a project through the owner RPC with cents and PST instants", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        Response.json({ authorized: true, factories: [{ id: factoryId }] }),
      )
      .mockResolvedValueOnce(
        Response.json({
          id: "project-2",
          factory_id: factoryId,
          unit_value_cents: 250,
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const response = await POST(request("POST", projectDraft));
    expect(response.status).toBe(201);
    const rpcBody = JSON.parse(fetchMock.mock.calls[1][1].body);
    expect(fetchMock.mock.calls[1][0]).toContain(
      "/rest/v1/rpc/owner_start_project",
    );
    expect(rpcBody.p_unit_value_cents).toBe(250);
    expect(rpcBody.p_start_at).toBe("2026-12-15T17:00:00Z");
    expect(rpcBody.p_deadline).toBe("2026-12-16T01:30:00Z");
    expect(rpcBody.p_station_id).toBe(projectDraft.stationId);
    expect(rpcBody.p_worker_ids).toEqual(projectDraft.workerIds);
  });

  it("returns 409 for a durable overlap conflict", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(
          Response.json({ authorized: true, factories: [{ id: factoryId }] }),
        )
        .mockResolvedValueOnce(
          Response.json(
            { code: "23P01", message: "conflicting key value violates exclusion constraint" },
            { status: 409 },
          ),
        ),
    );
    const response = await POST(request("POST", projectDraft));
    expect(response.status).toBe(409);
    expect(await response.json()).toEqual({ error: "OWNER_CONFLICT" });
  });
});
