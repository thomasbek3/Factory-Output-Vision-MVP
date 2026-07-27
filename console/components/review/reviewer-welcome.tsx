"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, Loader2, ShieldAlert } from "lucide-react";
import { acceptReviewerInviteSession } from "@/lib/reviewSupabase";

export function ReviewerWelcome({ spanish }: { spanish: boolean }) {
  const [state, setState] = useState<"loading" | "ready" | "failed">("loading");

  useEffect(() => {
    const query = new URLSearchParams(window.location.search);
    const invitationToken = query.get("invitation");
    const values = new URLSearchParams(window.location.hash.replace(/^#/, ""));
    const accessToken = values.get("access_token");
    const refreshToken = values.get("refresh_token");
    if (!accessToken || !refreshToken || !invitationToken) {
      const timer = window.setTimeout(() => setState("failed"), 0);
      return () => window.clearTimeout(timer);
    }
    void acceptReviewerInviteSession(accessToken, refreshToken, invitationToken)
      .then(() => {
        window.history.replaceState(null, "", "/review/welcome");
        setState("ready");
        window.setTimeout(() => window.location.assign("/review?welcome=1"), 800);
      })
      .catch(() => setState("failed"));
  }, []);

  return (
    <main className="grid min-h-screen place-items-center bg-[var(--bg)] p-5 text-[var(--text)]">
      <div className="w-full max-w-md border border-[var(--border)] bg-[var(--panel)] p-7 text-center">
        {state === "loading" ? (
          <>
            <Loader2 className="mx-auto h-8 w-8 animate-spin text-[var(--accent)]" />
            <h1 className="mt-5 text-[22px] font-semibold">
              {spanish ? "Protegiendo tu invitación" : "Securing your invitation"}
            </h1>
            <p className="mt-2 text-[13px] leading-5 text-[var(--text-mut)]">
              {spanish ? "Esto toma solo un momento." : "This takes only a moment."}
            </p>
          </>
        ) : state === "ready" ? (
          <>
            <CheckCircle2 className="mx-auto h-8 w-8 text-[var(--good)]" />
            <h1 className="mt-5 text-[22px] font-semibold">
              {spanish ? "Invitación aceptada" : "Invitation accepted"}
            </h1>
            <p className="mt-2 text-[13px] leading-5 text-[var(--text-mut)]">
              {spanish ? "Abriendo tu configuración segura." : "Opening your secure setup now."}
            </p>
          </>
        ) : (
          <>
            <ShieldAlert className="mx-auto h-8 w-8 text-[var(--bad)]" />
            <h1 className="mt-5 text-[22px] font-semibold">
              {spanish ? "Esta invitación no está disponible" : "This invitation is unavailable"}
            </h1>
            <p className="mt-2 text-[13px] leading-5 text-[var(--text-mut)]">
              {spanish
                ? "Puede haber vencido, sido revocada o ya utilizada. Solicita una nueva invitación a soporte."
                : "It may have expired, been revoked, or already used. Ask FactoryVision support for a new invitation."}
            </p>
          </>
        )}
      </div>
    </main>
  );
}
