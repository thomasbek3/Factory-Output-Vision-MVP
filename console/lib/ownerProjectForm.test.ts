import { describe, expect, it } from "vitest";
import {
  normalizeOwnerProjectDraft,
  ownerProjectRpcPayload,
  validateOwnerProjectDraft,
} from "@/lib/ownerProjectForm";

const completeDraft = {
  factoryId: "10000000-0000-0000-0000-000000000001",
  name: "Lot 42 Fence Panels",
  client: "Acme Fence",
  targetUnits: "400",
  valueMode: "total",
  valueUsd: "1000.00",
  materialMode: "per_unit",
  materialUsd: "0.75",
  stationId: "20000000-0000-0000-0000-000000000001",
  stationSuggested: true,
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
} as const;

describe("ownerProjectForm", () => {
  it("normalizes total and per-unit money into integer cents", () => {
    const draft = normalizeOwnerProjectDraft(completeDraft);
    expect(draft.unitValueCents).toBe(250);
    expect(draft.unitMaterialCostCents).toBe(75);
    expect(draft.loadedLaborRateCentsPerHour).toBe(2250);
    expect(draft.targetMarginBps).toBe(2500);
  });

  it("uses factory timezone for winter instants", () => {
    const payload = ownerProjectRpcPayload(
      normalizeOwnerProjectDraft(completeDraft),
      "open",
    );
    expect(payload.p_start_at).toBe("2026-12-15T17:00:00Z");
    expect(payload.p_deadline).toBe("2026-12-16T01:30:00Z");
    expect(payload.p_station_id).toBe(
      "20000000-0000-0000-0000-000000000001",
    );
    expect(payload.p_worker_ids).toEqual([
      "61000000-0000-0000-0000-000000000001",
    ]);
    expect(payload.p_planned_direct_labor_cents).toBe(19_125);
  });

  it("allows a blank loaded labor rate without inventing labor cost", () => {
    const draft = normalizeOwnerProjectDraft({
      ...completeDraft,
      loadedLaborRateUsd: "",
    });
    const validation = validateOwnerProjectDraft(draft);
    const payload = ownerProjectRpcPayload(draft, "open");

    expect(validation.errors.loadedLaborRateCentsPerHour).toBeUndefined();
    expect(payload.p_loaded_labor_rate_cents_per_hour).toBe(0);
    expect(payload.p_planned_direct_labor_cents).toBe(0);
  });

  it("rejects malformed or negative loaded labor rates", () => {
    for (const loadedLaborRateUsd of ["-1", "abc", "12.345"]) {
      const draft = normalizeOwnerProjectDraft({
        ...completeDraft,
        loadedLaborRateUsd,
      });
      expect(
        validateOwnerProjectDraft(draft).errors.loadedLaborRateCentsPerHour,
      ).toBe("Enter a valid non-negative loaded labor rate.");
    }
  });

  it("requires confirmation for a suggested station", () => {
    const draft = normalizeOwnerProjectDraft({
      ...completeDraft,
      stationConfirmed: false,
    });
    expect(validateOwnerProjectDraft(draft).errors.stationConfirmed).toBe(
      "Confirm or change the suggested station.",
    );
  });

  it("returns step-scoped errors for an incomplete draft", () => {
    const draft = normalizeOwnerProjectDraft({
      ...completeDraft,
      name: "",
      stationId: "",
      workerIds: [],
    });
    const result = validateOwnerProjectDraft(draft);
    expect(result.ok).toBe(false);
    expect(result.steps.what).toBe(false);
    expect(result.steps.whereWhen).toBe(false);
    expect(result.steps.laborGoal).toBe(false);
  });

  it("rejects a deadline that is not after start", () => {
    const draft = normalizeOwnerProjectDraft({
      ...completeDraft,
      deadlineTime: "08:00",
    });
    expect(validateOwnerProjectDraft(draft).errors.deadline).toBe(
      "Deadline must be after the project start.",
    );
  });

  it("preserves an explicitly negative target margin", () => {
    const draft = normalizeOwnerProjectDraft({
      ...completeDraft,
      targetMarginPercent: "-5.25",
    });
    expect(draft.targetMarginBps).toBe(-525);
    expect(validateOwnerProjectDraft(draft).errors.targetMarginBps).toBeUndefined();
  });

  it("rejects malformed and overlapping shift calendars", () => {
    const malformed = normalizeOwnerProjectDraft({
      ...completeDraft,
      shiftCalendar: {
        timezone: "America/Los_Angeles",
        shifts: [{ weekday: 9, start: "25:00", end: "17:30" }],
      },
    });
    expect(validateOwnerProjectDraft(malformed).errors.shiftCalendar).toBe(
      "Enter a valid non-overlapping shift calendar.",
    );

    const overlapping = normalizeOwnerProjectDraft({
      ...completeDraft,
      shiftCalendar: {
        timezone: "America/Los_Angeles",
        shifts: [
          { weekday: 2, start: "09:00", end: "17:30" },
          { weekday: 2, start: "12:00", end: "18:00" },
        ],
      },
    });
    expect(validateOwnerProjectDraft(overlapping).errors.shiftCalendar).toBe(
      "Enter a valid non-overlapping shift calendar.",
    );
  });

  it("rejects a weekend-only project window with no scheduled work", () => {
    const draft = normalizeOwnerProjectDraft({
      ...completeDraft,
      startDate: "2026-12-19",
      startTime: "09:00",
      deadlineDate: "2026-12-20",
      deadlineTime: "17:00",
      shiftCalendar: {
        timezone: "America/Los_Angeles",
        shifts: [
          { weekday: 1, start: "09:00", end: "17:30" },
          { weekday: 2, start: "09:00", end: "17:30" },
          { weekday: 3, start: "09:00", end: "17:30" },
          { weekday: 4, start: "09:00", end: "17:30" },
          { weekday: 5, start: "09:00", end: "17:30" },
        ],
      },
    });

    expect(validateOwnerProjectDraft(draft).errors.shiftCalendar).toBe(
      "Project window must include at least one scheduled working shift.",
    );
    expect(() => ownerProjectRpcPayload(draft, "open")).toThrow(
      "Owner project draft is invalid.",
    );
  });

  it("rejects Friday evening through Monday morning before the next shift", () => {
    const draft = normalizeOwnerProjectDraft({
      ...completeDraft,
      startDate: "2026-12-18",
      startTime: "17:31",
      deadlineDate: "2026-12-21",
      deadlineTime: "08:59",
      shiftCalendar: {
        timezone: "America/Los_Angeles",
        shifts: [
          { weekday: 1, start: "09:00", end: "17:30" },
          { weekday: 2, start: "09:00", end: "17:30" },
          { weekday: 3, start: "09:00", end: "17:30" },
          { weekday: 4, start: "09:00", end: "17:30" },
          { weekday: 5, start: "09:00", end: "17:30" },
        ],
      },
    });

    expect(validateOwnerProjectDraft(draft).errors.shiftCalendar).toBe(
      "Project window must include at least one scheduled working shift.",
    );
  });
});
