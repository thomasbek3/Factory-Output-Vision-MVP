import { describe, expect, it } from "vitest";
import { reviewerInviteEmail } from "./reviewerEmail";

describe("reviewerInviteEmail", () => {
  const input = {
    displayName: "Ana Rivera",
    actionUrl: "https://review.factoryvision.example/review/welcome?token=safe",
    expiresAt: "2026-07-28T18:00:00Z",
    supportEmail: "support@factoryvision.example",
  };

  it("renders a complete Spanish invitation without leaking internal terminology", () => {
    const email = reviewerInviteEmail({ ...input, locale: "es-419" });
    expect(email.subject).toContain("FactoryVision");
    expect(email.html).toContain("Activar mi cuenta");
    expect(email.html).toContain("aplicación de autenticación");
    expect(email.html).toContain(input.actionUrl);
    expect(email.html).not.toMatch(/Supabase|service role|consensus|AI count/i);
    expect(email.text).toContain("1.");
  });

  it("renders English and escapes worker-controlled values", () => {
    const email = reviewerInviteEmail({
      ...input,
      displayName: "<script>alert(1)</script>",
      locale: "en",
    });
    expect(email.html).toContain("Activate my account");
    expect(email.html).not.toContain("<script>");
    expect(email.html).toContain("&lt;script&gt;");
  });
});

