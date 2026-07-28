"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, Loader2, ShieldAlert } from "lucide-react";
import {
  acceptReviewerInviteSession,
  acceptReviewerPasswordlessSession,
} from "@/lib/reviewSupabase";

export function ReviewerWelcome({
  spanish,
  passwordless,
}: {
  spanish: boolean;
  passwordless: boolean;
}) {
  const [state, setState] = useState<"loading" | "ready" | "failed">("loading");
  const flow = passwordless ? "login" : "invite";

  useEffect(() => {
    const query = new URLSearchParams(window.location.search);
    const invitationToken = query.get("invitation");
    const values = new URLSearchParams(window.location.hash.replace(/^#/, ""));
    const accessToken = values.get("access_token");
    const refreshToken = values.get("refresh_token");
    const parsedExpiresIn = Number(values.get("expires_in"));
    const expiresIn =
      Number.isInteger(parsedExpiresIn) && parsedExpiresIn >= 60
        ? parsedExpiresIn
        : 3600;
    window.history.replaceState(
      null,
      "",
      `${window.location.pathname}${window.location.search}`,
    );
    if (
      !accessToken ||
      !refreshToken ||
      (!passwordless && !invitationToken)
    ) {
      const timer = window.setTimeout(() => setState("failed"), 0);
      return () => window.clearTimeout(timer);
    }
    const complete = passwordless
      ? acceptReviewerPasswordlessSession(
        accessToken,
        refreshToken,
        expiresIn,
      )
      : acceptReviewerInviteSession(
        accessToken,
        refreshToken,
        invitationToken as string,
      );
    void complete
      .then(() => {
        window.history.replaceState(null, "", "/review/welcome");
        setState("ready");
        window.setTimeout(
          () => window.location.assign(passwordless ? "/review" : "/review?welcome=1"),
          800,
        );
      })
      .catch(() => setState("failed"));
  }, [passwordless]);

  return (
    <main className="grid min-h-screen place-items-center bg-[var(--bg)] p-5 text-[var(--text)]">
      <div className="w-full max-w-md border border-[var(--border)] bg-[var(--panel)] p-7 text-center">
        {state === "loading" ? (
          <>
            <Loader2 className="mx-auto h-8 w-8 animate-spin text-[var(--accent)]" />
            <h1 className="mt-5 text-[22px] font-semibold">
              {flow === "login"
                ? (spanish ? "Iniciando sesión" : "Signing you in")
                : (spanish ? "Protegiendo tu invitación" : "Securing your invitation")}
            </h1>
            <p className="mt-2 text-[13px] leading-5 text-[var(--text-mut)]">
              {spanish ? "Esto toma solo un momento." : "This takes only a moment."}
            </p>
          </>
        ) : state === "ready" ? (
          <>
            <CheckCircle2 className="mx-auto h-8 w-8 text-[var(--good)]" />
            <h1 className="mt-5 text-[22px] font-semibold">
              {flow === "login"
                ? (spanish ? "Sesión iniciada" : "Signed in")
                : (spanish ? "Invitación aceptada" : "Invitation accepted")}
            </h1>
            <p className="mt-2 text-[13px] leading-5 text-[var(--text-mut)]">
              {flow === "login"
                ? (spanish ? "Abriendo tu trabajo de hoy." : "Opening today's work.")
                : (spanish ? "Abriendo tu configuración segura." : "Opening your secure setup now.")}
            </p>
          </>
        ) : (
          <>
            <ShieldAlert className="mx-auto h-8 w-8 text-[var(--bad)]" />
            <h1 className="mt-5 text-[22px] font-semibold">
              {flow === "login"
                ? (spanish ? "Este enlace no está disponible" : "This sign-in link is unavailable")
                : (spanish ? "Esta invitación no está disponible" : "This invitation is unavailable")}
            </h1>
            <p className="mt-2 text-[13px] leading-5 text-[var(--text-mut)]">
              {flow === "login"
                ? (spanish
                  ? "Puede haber vencido. Vuelve a Trabajo de hoy y solicita otro enlace."
                  : "It may have expired. Return to Today's work and request another link.")
                : (spanish
                  ? "Puede haber vencido, sido revocada o ya utilizada. Solicita una nueva invitación a soporte."
                  : "It may have expired, been revoked, or already used. Ask FactoryVision support for a new invitation.")}
            </p>
          </>
        )}
      </div>
    </main>
  );
}
