import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("server-only", () => ({}));
vi.mock("@/lib/ownerServer", () => ({
  ownerRestAll: vi.fn(),
  ownerRpc: vi.fn(),
}));

import { ownerRestAll, ownerRpc } from "@/lib/ownerServer";
import { loadOwnerHistoryData } from "@/lib/ownerHistoryServer";

const mockedOwnerRestAll = vi.mocked(ownerRestAll);
const mockedOwnerRpc = vi.mocked(ownerRpc);

describe("owner history server loader", () => {
  beforeEach(() => {
    mockedOwnerRestAll.mockReset();
    mockedOwnerRpc.mockReset();
    mockedOwnerRpc.mockResolvedValue({
      projects: [],
      customers: [],
      stations: [],
      shifts: [],
      teams: [],
    });
  });

  it("pushes a finite selected range into the closeout query", async () => {
    const paths: string[] = [];
    mockedOwnerRestAll.mockImplementation(async (_token, path) => {
      paths.push(path);
      return [] as never;
    });

    await loadOwnerHistoryData({
      accessToken: "owner-token",
      factoryId: "factory-1",
      timezone: "UTC",
      filters: {
        range: "30",
        project: "all",
        customer: "all",
        station: "all",
        shift: "all",
        team: "all",
        status: "all",
      },
      nowIso: "2026-05-31T00:00:00Z",
    });

    expect(paths[0]).toContain(
      `completed_at=${encodeURIComponent("gte.2026-05-01T00:00:00.000Z")}`,
    );
    expect(mockedOwnerRpc).toHaveBeenCalledWith(
      "owner-token",
      "owner_history_filter_options",
      { p_factory_id: "factory-1" },
    );
  });

  it("batches audit ids so history never builds an unbounded URL", async () => {
    const closeouts = Array.from({ length: 201 }, (_, index) => ({
      id: `closeout-${index}`,
      project_id: `00000000-0000-0000-0000-${String(index).padStart(12, "0")}`,
      revision: 1,
      planned_units: 1,
      planned_direct_labor_cents: 1,
      planned_material_cost_cents: 1,
      planned_margin_after_direct_costs_cents: 1,
      deadline_at: "2026-05-01T12:00:00Z",
      completed_at: "2026-05-01T12:00:00Z",
      verified_good_units: 1,
      material_cost_cents: 1,
      direct_labor_cents: 1,
      margin_after_direct_costs_cents: 1,
      snapshot: {},
      created_at: "2026-05-01T12:00:00Z",
    }));
    const paths: string[] = [];
    mockedOwnerRestAll.mockImplementation(async (_token, path) => {
      paths.push(path);
      return (path.startsWith("owner_project_closeouts?")
        ? closeouts
        : []) as never;
    });

    await loadOwnerHistoryData({
      accessToken: "owner-token",
      factoryId: "factory-1",
      timezone: "UTC",
      filters: {
        range: "all",
        project: "all",
        customer: "all",
        station: "all",
        shift: "all",
        team: "all",
        status: "all",
      },
      nowIso: "2026-05-02T00:00:00Z",
    });

    const auditPaths = paths.filter((path) =>
      path.startsWith("owner_project_audit?"),
    );
    expect(paths[0]).toContain("factory_timezone");
    expect(auditPaths).toHaveLength(3);
    expect(auditPaths.every((path) => path.length < 5_000)).toBe(true);
  });
});
