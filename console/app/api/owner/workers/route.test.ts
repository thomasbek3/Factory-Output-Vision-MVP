import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";
import { GET, POST } from "@/app/api/owner/workers/route";

const factoryId = "10000000-0000-0000-0000-000000000001";

function request(
  method: "GET" | "POST",
  body?: unknown,
  origin = "https://factoryvision.example",
) {
  return new NextRequest(
    `https://factoryvision.example/api/owner/workers?factory_id=${factoryId}`,
    {
      method,
      headers: {
        cookie: "fv_owner_access=owner-token",
        ...(method === "POST" ? { origin } : {}),
        ...(body ? { "content-type": "application/json" } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
    },
  );
}

describe("/api/owner/workers", () => {
  beforeEach(() => {
    process.env.NEXT_PUBLIC_SUPABASE_URL = "https://project.supabase.co";
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY = "publishable-key";
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("reads workers through the owner JWT", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        Response.json({ authorized: true, factories: [{ id: factoryId }] }),
      )
      .mockResolvedValueOnce(
        Response.json(
          [{ id: "worker-1", display_name: "Ana" }],
          { headers: { "Content-Range": "0-0/1" } },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);
    const response = await GET(request("GET"));
    expect(response.status).toBe(200);
    expect((await response.json()).workers).toHaveLength(1);
    expect(fetchMock.mock.calls[1][0]).toContain("owner_workers?");
  });

  it("authorizes before revealing validation details", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce(
        Response.json({ authorized: false, factories: [] }),
      ),
    );
    const response = await POST(request("POST", { displayName: "" }));
    expect(response.status).toBe(403);
    expect(await response.json()).toEqual({ error: "OWNER_ACCESS_DENIED" });
  });

  it("rejects a cross-origin mutation before authorization", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const response = await POST(
      request(
        "POST",
        { displayName: "Cross-origin worker" },
        "https://attacker.example",
      ),
    );
    expect(response.status).toBe(403);
    expect(await response.json()).toEqual({ error: "OWNER_ORIGIN_INVALID" });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("creates a code-less worker through the audited RPC", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        Response.json({ authorized: true, factories: [{ id: factoryId }] }),
      )
      .mockResolvedValueOnce(
        Response.json({ id: "worker-2", display_name: "Luis" }),
      );
    vi.stubGlobal("fetch", fetchMock);
    const response = await POST(
      request("POST", {
        displayName: "Luis",
        employeeCode: "",
        primaryRole: "Operator",
      }),
    );
    expect(response.status).toBe(201);
    expect(fetchMock.mock.calls[1][0]).toContain(
      "/rest/v1/rpc/owner_upsert_worker",
    );
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({
      p_factory_id: factoryId,
      p_worker_id: null,
      p_display_name: "Luis",
      p_employee_code: null,
      p_primary_role: "Operator",
      p_status: "active",
      p_employee_code_supplied: true,
      p_primary_role_supplied: true,
    });
  });

  it("does not erase an employee code when an update omits the field", async () => {
    const workerId = "30000000-0000-0000-0000-000000000001";
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        Response.json({ authorized: true, factories: [{ id: factoryId }] }),
      )
      .mockResolvedValueOnce(
        Response.json({ id: workerId, display_name: "Luis Updated" }),
      );
    vi.stubGlobal("fetch", fetchMock);
    const response = await POST(
      request("POST", { id: workerId, displayName: "Luis Updated" }),
    );
    expect(response.status).toBe(200);
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toMatchObject({
      p_worker_id: workerId,
      p_employee_code: null,
      p_employee_code_supplied: false,
      p_primary_role: null,
      p_primary_role_supplied: false,
    });
  });

  it("clears an employee code when an update explicitly sends null", async () => {
    const workerId = "30000000-0000-0000-0000-000000000001";
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        Response.json({ authorized: true, factories: [{ id: factoryId }] }),
      )
      .mockResolvedValueOnce(
        Response.json({ id: workerId, display_name: "Luis Updated" }),
      );
    vi.stubGlobal("fetch", fetchMock);
    const response = await POST(
      request("POST", {
        id: workerId,
        displayName: "Luis Updated",
        employeeCode: null,
      }),
    );

    expect(response.status).toBe(200);
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toMatchObject({
      p_worker_id: workerId,
      p_employee_code: null,
      p_employee_code_supplied: true,
    });
  });

  it("rejects a non-string employee code instead of clearing it", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        Response.json({ authorized: true, factories: [{ id: factoryId }] }),
      );
    vi.stubGlobal("fetch", fetchMock);
    const response = await POST(
      request("POST", {
        id: "30000000-0000-0000-0000-000000000001",
        displayName: "Luis",
        employeeCode: 42,
      }),
    );
    expect(response.status).toBe(422);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
