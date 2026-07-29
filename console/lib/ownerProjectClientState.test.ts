import { describe, expect, it } from "vitest";
import {
  mergeOwnerProjectFormState,
  type OwnerProjectFormState,
} from "@/lib/ownerProjectClientState";

const fallback: OwnerProjectFormState = {
  name: "",
  client: "",
  targetUnits: "",
  valueMode: "per_unit",
  valueUsd: "",
  materialMode: "per_unit",
  materialUsd: "",
  stationId: "",
  stationSuggested: false,
  stationConfirmed: false,
  projectStartDate: "2026-07-29",
  projectStartTime: "13:00",
  deadlineDate: "2026-07-30",
  deadlineTime: "17:00",
  shiftStartTime: "07:00",
  shiftEndTime: "16:30",
  shiftDays: [1, 2, 3, 4, 5],
  workerIds: [],
  loadedLaborRateUsd: "",
  targetMarginPercent: "",
};

describe("mergeOwnerProjectFormState", () => {
  it("rejects malformed arrays while preserving safe defaults", () => {
    const result = mergeOwnerProjectFormState(
      { shiftDays: "weekdays", workerIds: [1, "worker-a"], name: "Gate run" },
      fallback,
    );
    expect(result.shiftDays).toEqual([1, 2, 3, 4, 5]);
    expect(result.workerIds).toEqual(["worker-a"]);
    expect(result.name).toBe("Gate run");
  });

  it("migrates a legacy startTime without coupling an explicit shift start", () => {
    const result = mergeOwnerProjectFormState(
      { startTime: "09:00", shiftStartTime: "06:30" },
      fallback,
    );
    expect(result.projectStartTime).toBe("09:00");
    expect(result.shiftStartTime).toBe("06:30");
  });
});
