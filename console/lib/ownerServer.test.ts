import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  OwnerDataError,
  ownerRestAll,
} from "@/lib/ownerServer";

describe("ownerRestAll", () => {
  beforeEach(() => {
    process.env.NEXT_PUBLIC_SUPABASE_URL = "https://project.supabase.co";
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY = "publishable-key";
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("retrieves every row across exact-count PostgREST pages", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(
        JSON.stringify([{ id: 1 }, { id: 2 }]),
        { headers: { "Content-Range": "0-1/3" } },
      ))
      .mockResolvedValueOnce(new Response(
        JSON.stringify([{ id: 3 }]),
        { headers: { "Content-Range": "2-2/3" } },
      ));
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      ownerRestAll<{ id: number }>("owner-token", "facts?order=id.asc", {
        pageSize: 2,
      }),
    ).resolves.toEqual([{ id: 1 }, { id: 2 }, { id: 3 }]);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[0]?.[1]?.headers).toMatchObject({
      Prefer: "count=exact",
      Range: "0-1",
      "Range-Unit": "items",
    });
    expect(fetchMock.mock.calls[1]?.[1]?.headers).toMatchObject({
      Range: "2-3",
    });
  });

  it("does not truncate a 1,400-row production result", async () => {
    const first = Array.from({ length: 1_000 }, (_, id) => ({ id }));
    const second = Array.from({ length: 400 }, (_, index) => ({
      id: index + 1_000,
    }));
    vi.stubGlobal("fetch", vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(first), {
        headers: { "Content-Range": "0-999/1400" },
      }))
      .mockResolvedValueOnce(new Response(JSON.stringify(second), {
        headers: { "Content-Range": "1000-1399/1400" },
      })));

    const rows = await ownerRestAll<{ id: number }>(
      "owner-token",
      "owner_production_events?order=occurred_at.asc,id.asc",
    );
    expect(rows).toHaveLength(1_400);
    expect(rows.at(-1)?.id).toBe(1_399);
  });

  it.each([
    ["missing count", null, [{ id: 1 }, { id: 2 }]],
    ["wrong range", "1-2/3", [{ id: 1 }, { id: 2 }]],
    ["truncated body", "0-1/3", [{ id: 1 }]],
  ])("fails closed for %s responses", async (_label, contentRange, rows) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(
      JSON.stringify(rows),
      {
        headers: contentRange ? { "Content-Range": contentRange } : {},
      },
    )));

    await expect(
      ownerRestAll<{ id: number }>("owner-token", "facts?order=id.asc", {
        pageSize: 2,
      }),
    ).rejects.toEqual(
      expect.objectContaining<Partial<OwnerDataError>>({
        status: 503,
        publicCode: "OWNER_DATA_UNAVAILABLE",
      }),
    );
  });

  it("fails closed when the exact total exceeds the bounded read", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(
      JSON.stringify([{ id: 1 }, { id: 2 }]),
      { headers: { "Content-Range": "0-1/1400" } },
    )));

    await expect(
      ownerRestAll<{ id: number }>("owner-token", "facts?order=id.asc", {
        pageSize: 2,
        maxRows: 1_000,
      }),
    ).rejects.toBeInstanceOf(OwnerDataError);
  });
});
