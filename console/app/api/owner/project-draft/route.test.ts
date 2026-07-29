import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { GET, PUT } from "@/app/api/owner/project-draft/route";

const factoryId = "10000000-0000-0000-0000-000000000001";

function request(method: "GET" | "PUT", body?: unknown) {
  return new NextRequest(
    `https://factoryvision.example/api/owner/project-draft?factory_id=${factoryId}`,
    {
      method,
      headers: {
        cookie: "fv_owner_access=owner-token",
        ...(method === "PUT"
          ? { origin: "https://factoryvision.example" }
          : {}),
        ...(body ? { "content-type": "application/json" } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
    },
  );
}

describe("/api/owner/project-draft", () => {
  beforeEach(() => {
    process.env.NEXT_PUBLIC_SUPABASE_URL = "https://project.supabase.co";
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY = "publishable-key";
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("rejects malformed factory ids before authorization", async () => {
    const malformed = new NextRequest(
      "https://factoryvision.example/api/owner/project-draft?factory_id=not-a-uuid",
      { headers: { cookie: "fv_owner_access=owner-token" } },
    );
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const response = await GET(malformed);
    expect(response.status).toBe(422);
    expect(await response.json()).toEqual({ error: "FACTORY_ID_INVALID" });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("loads the authenticated owner's durable draft", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(Response.json({ authorized: true, factories: [] }))
        .mockResolvedValueOnce(
          Response.json([{ payload: { name: "Partially entered project" } }]),
        ),
    );
    const response = await GET(request("GET"));
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({
      draft: { name: "Partially entered project" },
    });
  });

  it("persists incomplete form state through the owner RPC", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(Response.json({ authorized: true, factories: [] }))
      .mockResolvedValueOnce(
        Response.json({ payload: { name: "Only step one" } }),
      );
    vi.stubGlobal("fetch", fetchMock);
    const response = await PUT(request("PUT", { name: "Only step one" }));
    expect(response.status).toBe(200);
    expect(fetchMock.mock.calls[1][0]).toContain(
      "/rest/v1/rpc/owner_save_project_draft",
    );
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({
      p_factory_id: factoryId,
      p_payload: { name: "Only step one" },
    });
  });

  it("rejects a cross-origin draft mutation before authorization", async () => {
    const crossOrigin = new NextRequest(
      `https://factoryvision.example/api/owner/project-draft?factory_id=${factoryId}`,
      {
        method: "PUT",
        headers: {
          cookie: "fv_owner_access=owner-token",
          origin: "https://attacker.example",
          "content-type": "application/json",
        },
        body: JSON.stringify({ name: "Cross-origin draft" }),
      },
    );
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const response = await PUT(crossOrigin);

    expect(response.status).toBe(403);
    expect(await response.json()).toEqual({ error: "OWNER_ORIGIN_INVALID" });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects non-object draft payloads", async () => {
    const response = await PUT(request("PUT", ["invalid"]));
    expect(response.status).toBe(422);
    expect(await response.json()).toEqual({ error: "OWNER_DRAFT_INVALID" });
  });
});
