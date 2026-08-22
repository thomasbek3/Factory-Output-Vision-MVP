import { describe, expect, it } from "vitest";
import { RpcError } from "./reviewSupabase";
import {
  isAssignmentUnavailable,
  isCoverageIncomplete,
} from "./review-tally-console-classifiers";

describe("isAssignmentUnavailable", () => {
  it("is false for a typed MFA failure", () => {
    const err = new RpcError("active reviewer with MFA required", "MF000");
    expect(isAssignmentUnavailable(err)).toBe(false);
  });

  it("is true for a typed lease failure", () => {
    const err = new RpcError("assignment lease is unavailable", "42501");
    expect(err.domainCode).toBe("LEASE_UNAVAILABLE");
    // Legacy bare-42501 prose decides: this message IS a lease failure.
    expect(isAssignmentUnavailable(err)).toBe(true);
  });

  it("classifies legacy bare-42501 MFA prose as NOT unavailable", () => {
    const err = new RpcError("active reviewer with MFA required", "42501");
    expect(isAssignmentUnavailable(err)).toBe(false);
  });

  it("classifies typed non-lease, non-MFA errors as not unavailable", () => {
    const err = new RpcError("at least 98 percent of the video must be reviewed", "CV001");
    expect(isAssignmentUnavailable(err)).toBe(false);
  });

  it("falls back to prose for non-RpcError failures", () => {
    // Legacy server messages (not the UI's own copy).
    expect(isAssignmentUnavailable(new Error("assignment lease is unavailable"))).toBe(true);
    expect(isAssignmentUnavailable("assignment is not submittable")).toBe(true);
    expect(isAssignmentUnavailable(new Error("network down"))).toBe(false);
  });
});

describe("isCoverageIncomplete", () => {
  it("is true for each typed coverage code regardless of message", () => {
    for (const [code, message] of (
      [
        ["CV000", "video coverage has not been saved"],
        ["CV001", "at least 98 percent of the video must be reviewed"],
        ["CV002", "review completed faster than the enabled playback speed permits"],
      ] as const
    )) {
      expect(isCoverageIncomplete(new RpcError(message, code))).toBe(true);
    }
  });

  it("classifies legacy CHECK_VIOLATION coverage prose", () => {
    const err = new RpcError("at least 98 percent of the video must be reviewed", "23514");
    expect(err.domainCode).toBe("CHECK_VIOLATION");
    expect(isCoverageIncomplete(err)).toBe(true);
  });

  it("classifies UNKNOWN with coverage prose (codeless server)", () => {
    const err = new RpcError("at least 98 percent of the video must be reviewed", null);
    expect(err.domainCode).toBe("UNKNOWN");
    expect(isCoverageIncomplete(err)).toBe(true);
  });

  it("rejects unrelated CHECK_VIOLATION and UNKNOWN errors", () => {
    expect(
      isCoverageIncomplete(new RpcError("tally is outside the canonical chunk interval", "23514")),
    ).toBe(false);
    expect(isCoverageIncomplete(new RpcError("something exploded", null))).toBe(false);
  });
});

