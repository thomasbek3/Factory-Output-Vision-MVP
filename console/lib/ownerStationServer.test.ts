import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("server-only", () => ({}));
vi.mock("@/lib/ownerServer", () => ({
  ownerRestAll: vi.fn(),
  ownerRpc: vi.fn(),
}));

import { ownerRestAll, ownerRpc } from "@/lib/ownerServer";
import { loadOwnerStationData } from "@/lib/ownerStationServer";

const mockedOwnerRestAll = vi.mocked(ownerRestAll);
const mockedOwnerRpc = vi.mocked(ownerRpc);

function calendar(weekday: number, start: string, end: string) {
  return {
    timezone: "America/New_York",
    shifts: [{ weekday, start, end }],
  };
}

describe("owner station server loader", () => {
  beforeEach(() => {
    mockedOwnerRestAll.mockReset();
    mockedOwnerRpc.mockReset();
    mockedOwnerRpc.mockResolvedValue([]);
  });

  it("uses the requested assignment and scopes project-owned facts to it", async () => {
    const paths: string[] = [];
    mockedOwnerRestAll.mockImplementation(async (_token, path) => {
      paths.push(path);
      if (path.startsWith("stations?")) {
        return [
          { id: "station-1", alias: "Press Bay", status: "active" },
        ] as never;
      }
      if (path.startsWith("owner_project_station_assignments?")) {
        return [
          {
            id: "assignment-night",
            project_id: "project-night",
            station_id: "station-1",
            effective_start: "2026-05-07T22:00:00Z",
            effective_end: "2026-05-08T06:00:00Z",
          },
          {
            id: "assignment-day",
            project_id: "project-day",
            station_id: "station-1",
            effective_start: "2026-05-07T12:00:00Z",
            effective_end: "2026-05-07T16:00:00Z",
          },
        ] as never;
      }
      if (path.startsWith("owner_projects?")) {
        return [
          {
            id: "project-day",
            name: "Day Project",
            target_units: 160,
            start_at: "2026-05-07T10:00:00Z",
            deadline: "2026-05-07T18:00:00Z",
            shift_calendar: calendar(4, "06:00", "14:00"),
            status: "open",
          },
          {
            id: "project-night",
            name: "Night Project",
            target_units: 160,
            start_at: "2026-05-07T22:00:00Z",
            deadline: "2026-05-08T06:00:00Z",
            shift_calendar: calendar(4, "18:00", "02:00"),
            status: "open",
          },
        ] as never;
      }
      return [] as never;
    });

    const result = await loadOwnerStationData({
      accessToken: "owner-token",
      factoryId: "factory-1",
      timezone: "America/New_York",
      stationId: "station-1",
      assignmentId: "assignment-day",
      selectedDate: "2026-05-07",
    });

    expect(result.kind).toBe("ready");
    if (result.kind !== "ready") throw new Error("Expected station data");
    expect(result.data.project?.name).toBe("Day Project");
    expect(result.data.selectedAssignmentId).toBe("assignment-day");
    expect(result.data.shiftOptions).toHaveLength(2);
    expect(result.data.windowStartIso).toBe("2026-05-07T12:00:00.000Z");
    expect(result.data.windowEndIso).toBe("2026-05-07T16:00:00.000Z");
    expect(mockedOwnerRpc).toHaveBeenCalledWith(
      "owner-token",
      "owner_station_event_buckets",
      {
        p_factory_id: "factory-1",
        p_station_id: "station-1",
        p_project_id: "project-day",
        p_window_start: "2026-05-07T12:00:00.000Z",
        p_window_end: "2026-05-07T16:00:00.000Z",
      },
    );
    for (const table of [
      "owner_worker_station_intervals",
      "owner_station_downtime_intervals",
      "owner_output_adjustments",
    ]) {
      const path = paths.find((candidate) => candidate.startsWith(`${table}?`));
      expect(path, table).toContain("project_id=eq.project-day");
    }
  });
});
