import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const ORIGINAL_ENV = { ...process.env };

// The transport reads config lazily via reviewServerConfig(); set env before import.
process.env.NEXT_PUBLIC_SUPABASE_URL = "https://sb.example.com";
process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY = "anon-key";
process.env.SUPABASE_SECRET_KEY = "service-key";

const { authFetch, callWorkerRpc, signStorageUrl, supabaseFetch } = await import("./workerPortalServer");

describe("workerPortalServer transport", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    globalThis.fetch = fetchMock as unknown as typeof fetch;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("supabaseFetch sends dual-anon headers with no-store when anonymous", async () => {
    fetchMock.mockResolvedValue(new Response("{}", { status: 200 }));
    await supabaseFetch("/rest/v1/rpc/some_fn", { method: "POST", body: "{}" });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("https://sb.example.com/rest/v1/rpc/some_fn");
    const headers = init.headers as Record<string, string>;
    expect(headers.apikey).toBe("anon-key");
    expect(headers.Authorization).toBe("Bearer anon-key");
    expect(headers["Content-Type"]).toBe("application/json");
    expect(init.cache).toBe("no-store");
  });

  it("supabaseFetch serviceRole sends the secret as BOTH apikey and Bearer", async () => {
    fetchMock.mockResolvedValue(new Response("{}", { status: 200 }));
    await supabaseFetch("/rest/v1/rpc/service_latest_practice_preview", {
      method: "POST",
      body: "{}",
      serviceRole: true,
    });
    const headers = (fetchMock.mock.calls[0][1] as { headers: Record<string, string> }).headers;
    expect(headers.apikey).toBe("service-key");
    expect(headers.Authorization).toBe("Bearer service-key");
  });

  it("supabaseFetch serviceRole throws when secret key is missing", async () => {
    delete process.env.SUPABASE_SECRET_KEY;
    try {
      await supabaseFetch("/rest/v1/rpc/fn", { method: "POST", body: "{}", serviceRole: true });
      expect.unreachable("should have thrown");
    } catch (error) {
      expect((error as Error).message).toBe("SUPABASE_SECRET_KEY_MISSING");
    }
    process.env.SUPABASE_SECRET_KEY = "service-key";
  });

  it("supabaseFetch attaches Bearer when accessToken given", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
    await supabaseFetch("/rest/v1/rpc/fn", { method: "POST", body: "{}", accessToken: "tok" });
    const [, init] = fetchMock.mock.calls[0];
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer tok");
  });

  it("callWorkerRpc parses JSON and returns null for empty bodies", async () => {
    fetchMock
      .mockResolvedValueOnce(new Response(JSON.stringify({ ok: 1 }), { status: 200 }))
      .mockResolvedValueOnce(new Response("", { status: 200 }));
    expect(await callWorkerRpc("fn_a", {})).toEqual({ ok: 1 });
    expect(await callWorkerRpc("fn_b", {})).toBeNull();
  });

  it("callWorkerRpc throws a typed error carrying status + upstream body", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ message: "assignment lease is unavailable" }), {
        status: 403,
        headers: { "Content-Type": "application/json" },
      }),
    );
    try {
      await callWorkerRpc("fn", {});
      expect.unreachable("should have thrown");
    } catch (error) {
      const err = error as { status?: number; body?: string; message: string };
      expect(err.status).toBe(403);
      expect(err.body).toContain("assignment lease is unavailable");
    }
  });

  it("signStorageUrl signs via storage API and qualifies relative URLs", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ signedURL: "/object/sign/review-renditions/x?token=1" }), {
        status: 200,
      }),
    );
    const result = await signStorageUrl("review-renditions", "a/b.mp4", { kind: "reviewer", token: "t" }, 600);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain("/storage/v1/object/sign/review-renditions/");
    expect((url as string).endsWith("/a/b.mp4")).toBe(true);
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer t");
    expect(init.body).toBe(JSON.stringify({ expiresIn: 600 }));
    expect(result.mediaUrl).toBe("https://sb.example.com/storage/v1/object/sign/review-renditions/x?token=1");
  });

  it("signStorageUrl service role uses SUPABASE_SECRET_KEY", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ signedUrl: "https://already.qualified/x" }), { status: 200 }),
    );
    const result = await signStorageUrl("bucket", "p", { kind: "service" }, 3600);
    const [, init] = fetchMock.mock.calls[0];
    const headers = init.headers as Record<string, string>;
    expect(headers.apikey).toBe("service-key");
    expect(headers.Authorization).toBe("Bearer service-key");
    expect(result.mediaUrl).toBe("https://already.qualified/x");
  });

  it("authFetch admin endpoints use serviceRole credentials", async () => {
    fetchMock.mockResolvedValue(new Response("{}", { status: 200 }));
    await authFetch("/admin/generate_link", { method: "POST", serviceRole: true, body: "{}" });
    const headers = (fetchMock.mock.calls[0][1] as { headers: Record<string, string> }).headers;
    expect(headers.apikey).toBe("service-key");
    expect(headers.Authorization).toBe("Bearer service-key");
  });

  it("authFetch rejects serviceRole when secret key missing", async () => {
    delete process.env.SUPABASE_SECRET_KEY;
    // Re-import to clear module-level nothing; env read is per-call.
    await expect(authFetch("/admin/generate_link", { method: "POST", serviceRole: true })).rejects.toThrow(
      "SUPABASE_SECRET_KEY_MISSING",
    );
    process.env.SUPABASE_SECRET_KEY = "service-key";
  });
});
