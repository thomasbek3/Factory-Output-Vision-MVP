import { describe, expect, it } from "vitest";
import {
  invitationIdempotencyKey,
  invitationRedirectUrl,
  invitationTokenHash,
} from "./reviewerInviteSecurity";

describe("reviewer invitation security", () => {
  it("binds the one-time token and locale to the welcome redirect", () => {
    const url = new URL(
      invitationRedirectUrl(
        "https://review.factoryvision.example",
        "secure-token",
        "es-419",
      ),
    );
    expect(url.pathname).toBe("/review/welcome");
    expect(url.searchParams.get("invitation")).toBe("secure-token");
    expect(url.searchParams.get("lang")).toBe("es");
  });

  it("hashes invitation tokens without storing the raw token", () => {
    expect(invitationTokenHash("secure-token")).toMatch(/^[0-9a-f]{64}$/);
    expect(invitationTokenHash("secure-token")).not.toContain("secure-token");
  });

  it("uses a stable provider idempotency key", () => {
    expect(invitationIdempotencyKey("invite-id")).toBe(
      "factoryvision-invite/invite-id",
    );
  });
});
