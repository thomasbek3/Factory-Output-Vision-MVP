import { afterEach, describe, expect, it, vi } from "vitest";
import { RpcError, workerRpc } from "./reviewSupabase";

describe("workerRpc typed errors", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  function mockFetch(status: number, body: unknown) {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(typeof body === "string" ? body : JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
      }),
    ) as unknown as typeof fetch;
  }

  it("throws an RpcError carrying the PostgREST SQLSTATE code", async () => {
    mockFetch(403, {
      code: "42501",
      message: "assignment lease is unavailable",
      details: null,
      hint: null,
    });
    const error = await workerRpc({} as never, "submit_worker_assignment_v2", {}).then(
      () => null,
      (err: unknown) => err,
    );
    expect(error).toBeInstanceOf(RpcError);
    expect((error as RpcError).code).toBe("42501");
    expect((error as RpcError).message).toBe("assignment lease is unavailable");
  });

  it("maps known SQLSTATE codes to stable domain codes", async () => {
    const cases: Array<[string, string]> = [
      ["42501", "LEASE_UNAVAILABLE"],
      ["23514", "CHECK_VIOLATION"],
      ["55000", "INVALID_STATE"],
      ["54000", "RATE_LIMITED"],
      ["28000", "AUTH_INVALID"],
      ["CV000", "COVERAGE_MISSING"],
      ["CV001", "COVERAGE_INCOMPLETE"],
      ["CV002", "COVERAGE_TOO_FAST"],
      ["MF000", "MFA_REQUIRED"],
    ];
    for (const [sqlstate, expected] of cases) {
      mockFetch(400, { code: sqlstate, message: "anything" });
      const error = (await workerRpc({} as never, "claim_worker_assignment", {}).then(
        () => null,
        (err: unknown) => err,
      )) as RpcError;
      expect(error.domainCode).toBe(expected);
    }
  });

  it("falls back to UNKNOWN with prose preserved when no code is present", async () => {
    mockFetch(500, { message: "something exploded" });
    const error = (await workerRpc({} as never, "heartbeat_worker_assignment", {}).then(
      () => null,
      (err: unknown) => err,
    )) as RpcError;
    expect(error).toBeInstanceOf(RpcError);
    expect(error.code).toBeNull();
    expect(error.domainCode).toBe("UNKNOWN");
    expect(error.message).toBe("something exploded");
  });

  it("still throws a plain Error for non-JSON bodies", async () => {
    globalThis.fetch = vi
      .fn()
      .mockResolvedValue(new Response("<html>boom</html>", { status: 502 })) as unknown as typeof fetch;
    await expect(
      workerRpc({} as never, "worker_daily_progress", {}),
    ).rejects.toThrow(/RPC_502/);
  });
});
