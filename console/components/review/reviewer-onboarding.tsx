"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  Check,
  ChevronRight,
  KeyRound,
  Loader2,
  LockKeyhole,
  PlayCircle,
  ShieldCheck,
  Smartphone,
} from "lucide-react";
import {
  reviewerLifecycle,
  type ReviewerLifecycle,
  type ReviewSession,
} from "@/lib/reviewSupabase";
import { reviewerDeviceHash } from "@/lib/reviewerDevice";
import { ReviewerQualification } from "@/components/review/reviewer-qualification";

async function api(path: string, method: "GET" | "POST", body?: object) {
  const response = await fetch(path, {
    method,
    credentials: "same-origin",
    cache: "no-store",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error ?? `${path}_${response.status}`);
  return result;
}

export function ReviewerOnboarding({
  lifecycle,
  session,
  onChange,
  onSignOut,
}: {
  lifecycle: ReviewerLifecycle;
  session: ReviewSession;
  onChange: (next: ReviewerLifecycle) => void;
  onSignOut: () => void;
}) {
  const spanish = lifecycle.locale !== "en";
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [passwordSet, setPasswordSet] = useState(lifecycle.state !== "invited");
  const [password, setPassword] = useState("");
  const [factorId, setFactorId] = useState<string | null>(null);
  const [qrCode, setQrCode] = useState<string | null>(null);
  const [secret, setSecret] = useState<string | null>(null);
  const [code, setCode] = useState("");

  useEffect(() => {
    if (
      !passwordSet ||
      lifecycle.isTestAccount ||
      lifecycle.mfaVerifiedAt ||
      factorId
    ) return;
    setBusy(true);
    void api("/api/review/mfa", "POST", { action: "enroll" })
      .then((result) => {
        setFactorId(result.factorId);
        setQrCode(result.qrCode);
        setSecret(result.secret);
      })
      .catch((caught) => setError(caught instanceof Error ? caught.message : "MFA setup failed."))
      .finally(() => setBusy(false));
  }, [
    factorId,
    lifecycle.isTestAccount,
    lifecycle.mfaVerifiedAt,
    passwordSet,
  ]);

  useEffect(() => {
    if (
      !passwordSet ||
      !lifecycle.isTestAccount ||
      lifecycle.mfaVerifiedAt
    ) return;
    setBusy(true);
    void reviewerDeviceHash()
      .then((deviceIdHash) => reviewerLifecycle("POST", {
        step: "mfa_verified",
        deviceIdHash,
      }))
      .then(onChange)
      .catch((caught) => setError(
        caught instanceof Error
          ? caught.message
          : "Could not open the test workspace.",
      ))
      .finally(() => setBusy(false));
  }, [
    lifecycle.isTestAccount,
    lifecycle.mfaVerifiedAt,
    onChange,
    passwordSet,
  ]);

  useEffect(() => {
    if (
      lifecycle.isTestAccount ||
      !lifecycle.mfaVerifiedAt ||
      lifecycle.currentAal === "aal2" ||
      factorId
    ) return;
    setBusy(true);
    void api("/api/review/mfa", "GET")
      .then((result) => {
        const factor = result.factors?.find((candidate: { status?: string }) => candidate.status === "verified");
        if (!factor?.id) throw new Error("No verified authenticator was found.");
        setFactorId(factor.id);
      })
      .catch((caught) => setError(caught instanceof Error ? caught.message : "MFA challenge failed."))
      .finally(() => setBusy(false));
  }, [
    factorId,
    lifecycle.currentAal,
    lifecycle.isTestAccount,
    lifecycle.mfaVerifiedAt,
  ]);

  async function run(action: () => Promise<ReviewerLifecycle>) {
    setBusy(true);
    setError(null);
    try {
      onChange(await action());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not save this step.");
    } finally {
      setBusy(false);
    }
  }

  async function savePassword(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api("/api/review/password", "POST", { password });
      setPassword("");
      setPasswordSet(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Password update failed.");
    } finally {
      setBusy(false);
    }
  }

  async function verifyMfa(event: FormEvent) {
    event.preventDefault();
    if (!factorId) return;
    setBusy(true);
    setError(null);
    try {
      await api("/api/review/mfa", "POST", { action: "verify", factorId, code });
      const next = lifecycle.mfaVerifiedAt
        ? await reviewerLifecycle("GET")
        : await reviewerLifecycle("POST", {
            step: "mfa_verified",
            deviceIdHash: await reviewerDeviceHash(),
          });
      onChange(next);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Code verification failed.");
    } finally {
      setBusy(false);
    }
  }

  const shell = (content: React.ReactNode) => (
    <main className="min-h-screen bg-[var(--bg)] p-5 text-[var(--text)]" data-review-route="onboarding">
      <div className="mx-auto max-w-3xl">
        <header className="flex items-center justify-between border-b border-[var(--border)] pb-4">
          <div>
            <div className="text-[11px] font-semibold uppercase text-[var(--text-dim)]">FactoryVision</div>
            <h1 className="mt-1 text-[22px] font-semibold">{spanish ? "Configuración segura" : "Secure setup"}</h1>
          </div>
          <button type="button" onClick={onSignOut} className="text-[12px] font-semibold text-[var(--text-mut)]">
            {spanish ? "Cerrar sesión" : "Sign out"}
          </button>
        </header>
        <div className="py-8">{content}</div>
        {error ? <div role="alert" className="border-l-4 border-[var(--bad)] bg-[var(--bad-tint)] px-4 py-3 text-[13px] text-[var(--bad)]">{error}</div> : null}
      </div>
    </main>
  );

  if (lifecycle.state === "suspended" || lifecycle.state === "offboarded") {
    return shell(
      <div className="mx-auto max-w-lg text-center">
        <LockKeyhole className="mx-auto h-9 w-9 text-[var(--warn)]" />
        <h2 className="mt-5 text-[24px] font-semibold">{spanish ? "El acceso está pausado" : "Access is paused"}</h2>
        <p className="mt-3 text-[14px] leading-6 text-[var(--text-mut)]">
          {spanish ? "Comunícate con soporte de FactoryVision antes de continuar." : "Contact FactoryVision support before continuing."}
        </p>
      </div>,
    );
  }

  if (!passwordSet) {
    return shell(
      <form className="mx-auto max-w-md" onSubmit={savePassword}>
        <KeyRound className="h-8 w-8 text-[var(--accent)]" />
        <h2 className="mt-5 text-[24px] font-semibold">{spanish ? "Crea tu contraseña" : "Create your password"}</h2>
        <p className="mt-2 text-[13px] leading-5 text-[var(--text-mut)]">
          {spanish ? "Usa por lo menos 12 caracteres que no uses en otro lugar." : "Use at least 12 characters that you do not use anywhere else."}
        </p>
        <input aria-label={spanish ? "Nueva contraseña" : "New password"} className="mt-5 h-12 w-full border border-[var(--border)] bg-[var(--panel)] px-3" type="password" autoComplete="new-password" minLength={12} value={password} onChange={(event) => setPassword(event.target.value)} required />
        <button className="mt-3 inline-flex h-12 w-full items-center justify-center gap-2 bg-[var(--accent)] font-semibold text-black disabled:opacity-50" disabled={busy}>
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <ChevronRight className="h-4 w-4" />}
          {spanish ? "Continuar" : "Continue"}
        </button>
      </form>,
    );
  }

  if (!lifecycle.mfaVerifiedAt && lifecycle.isTestAccount) {
    return shell(
      <div className="mx-auto max-w-md text-center">
        <Loader2 className="mx-auto h-8 w-8 animate-spin text-[var(--accent)]" />
        <h2 className="mt-5 text-[24px] font-semibold">
          {spanish ? "Abriendo tu espacio de trabajo" : "Opening your workspace"}
        </h2>
      </div>,
    );
  }

  if (!lifecycle.mfaVerifiedAt) {
    return shell(
      <form className="mx-auto max-w-xl" onSubmit={verifyMfa}>
        <Smartphone className="h-8 w-8 text-[var(--accent)]" />
        <h2 className="mt-5 text-[24px] font-semibold">{spanish ? "Protege tu cuenta" : "Protect your account"}</h2>
        <p className="mt-2 text-[13px] leading-5 text-[var(--text-mut)]">
          {spanish ? "Escanea el código con Google Authenticator, Microsoft Authenticator, 1Password u otra aplicación compatible." : "Scan the code with Google Authenticator, Microsoft Authenticator, 1Password, or another compatible app."}
        </p>
        <div className="mt-5 grid gap-5 sm:grid-cols-[190px_1fr]">
          <div className="grid aspect-square place-items-center bg-white p-3">
            {/* The Supabase MFA API returns an inline SVG data URL, not an optimizable asset. */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            {qrCode ? <img src={qrCode} alt={spanish ? "Código QR de autenticación" : "Authenticator QR code"} className="h-full w-full" /> : <Loader2 className="h-6 w-6 animate-spin text-black" />}
          </div>
          <div>
            <label className="text-[12px] font-semibold text-[var(--text-mut)]">
              {spanish ? "Código de 6 dígitos" : "6-digit code"}
              <input className="mt-2 h-12 w-full border border-[var(--border)] bg-[var(--panel)] px-3 text-[20px] tracking-[0.2em]" inputMode="numeric" pattern="[0-9]{6}" maxLength={6} value={code} onChange={(event) => setCode(event.target.value.replace(/\D/g, ""))} required />
            </label>
            {secret ? <details className="mt-3 text-[11px] text-[var(--text-dim)]"><summary>{spanish ? "No puedo escanear" : "I cannot scan"}</summary><code className="mt-2 block break-all border border-[var(--border)] p-2">{secret}</code></details> : null}
            <button className="mt-4 inline-flex h-11 w-full items-center justify-center gap-2 bg-[var(--accent)] font-semibold text-black disabled:opacity-50" disabled={busy || code.length !== 6}>
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
              {spanish ? "Verificar" : "Verify"}
            </button>
          </div>
        </div>
      </form>,
    );
  }

  if (!lifecycle.isTestAccount && lifecycle.currentAal !== "aal2") {
    return shell(
      <form className="mx-auto max-w-md" onSubmit={verifyMfa}>
        <Smartphone className="h-8 w-8 text-[var(--accent)]" />
        <h2 className="mt-5 text-[24px] font-semibold">{spanish ? "Confirma que eres tú" : "Confirm it is you"}</h2>
        <p className="mt-2 text-[13px] leading-5 text-[var(--text-mut)]">
          {spanish ? "Escribe el código de 6 dígitos de tu aplicación de autenticación." : "Enter the 6-digit code from your authenticator app."}
        </p>
        <input aria-label={spanish ? "Código de 6 dígitos" : "6-digit code"} className="mt-5 h-12 w-full border border-[var(--border)] bg-[var(--panel)] px-3 text-center text-[20px] tracking-[0.2em]" inputMode="numeric" pattern="[0-9]{6}" maxLength={6} value={code} onChange={(event) => setCode(event.target.value.replace(/\D/g, ""))} required />
        <button className="mt-3 inline-flex h-12 w-full items-center justify-center gap-2 bg-[var(--accent)] font-semibold text-black disabled:opacity-50" disabled={busy || !factorId || code.length !== 6}>
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
          {spanish ? "Verificar" : "Verify"}
        </button>
      </form>,
    );
  }

  if (!lifecycle.termsAcceptedAt) {
    return shell(
      <div className="mx-auto max-w-xl">
        <ShieldCheck className="h-8 w-8 text-[var(--accent)]" />
        <h2 className="mt-5 text-[24px] font-semibold">{spanish ? "Protege la información" : "Protect the information"}</h2>
        <div className="mt-5 border-y border-[var(--border)] py-4 text-[14px] leading-6 text-[var(--text-mut)]">
          <p>{spanish ? "Usa los videos únicamente para el trabajo asignado dentro de FactoryVision." : "Use videos only for assigned work inside FactoryVision."}</p>
          <p className="mt-3">{spanish ? "No descargues, grabes, fotografíes ni compartas videos, nombres de fábricas o información de producción." : "Do not download, record, photograph, or share videos, factory names, or production information."}</p>
          <p className="mt-3">{spanish ? "Reporta inmediatamente cualquier acceso extraño, cuenta compartida o dispositivo perdido." : "Immediately report unusual access, shared accounts, or a lost device."}</p>
        </div>
        <button disabled={busy} onClick={() => void run(() => reviewerLifecycle("POST", { step: "terms_accepted", termsVersion: "reviewer-data-handling-v1" }))} className="mt-5 inline-flex h-12 w-full items-center justify-center gap-2 bg-[var(--accent)] font-semibold text-black">
          <Check className="h-4 w-4" /> {spanish ? "Acepto y continuar" : "Accept and continue"}
        </button>
      </div>,
    );
  }

  if (!lifecycle.walkthroughCompletedAt) {
    return shell(
      <div>
        <PlayCircle className="h-8 w-8 text-[var(--accent)]" />
        <h2 className="mt-5 text-[24px] font-semibold">{spanish ? "Cómo revisar un video" : "How to review a video"}</h2>
        <div className="mt-6 grid gap-4 md:grid-cols-3">
          {[
            spanish ? ["1", "Mira todo el video", "Puedes usar 1x, 2x, 5x, 10x, 15x o 20x."] : ["1", "Watch the full video", "You can use 1x, 2x, 5x, 10x, 15x, or 20x."],
            spanish ? ["2", "Marca cada pieza", "Presiona +1 cuando la pieza queda en el área de salida."] : ["2", "Mark every piece", "Press +1 when the piece remains in the output area."],
            spanish ? ["3", "Revisa y confirma", "Corrige tus marcas antes de enviar."] : ["3", "Review and confirm", "Correct your marks before submitting."],
          ].map(([number, title, detail]) => (
            <div key={number} className="border-t-4 border-[var(--accent)] bg-[var(--panel)] p-5">
              <div className="text-[28px] font-bold text-[var(--accent)]">{number}</div>
              <div className="mt-3 text-[15px] font-semibold">{title}</div>
              <div className="mt-2 text-[13px] leading-5 text-[var(--text-mut)]">{detail}</div>
            </div>
          ))}
        </div>
        <button disabled={busy} onClick={() => void run(() => reviewerLifecycle("POST", { step: "walkthrough_completed" }))} className="mt-5 inline-flex h-12 items-center gap-2 bg-[var(--accent)] px-5 font-semibold text-black">
          {spanish ? "Entendido" : "I understand"} <ChevronRight className="h-4 w-4" />
        </button>
      </div>,
    );
  }

  if (!lifecycle.practiceCompletedAt) {
    return shell(
      <div className="mx-auto max-w-xl">
        <PlayCircle className="h-8 w-8 text-[var(--accent)]" />
        <h2 className="mt-5 text-[24px] font-semibold">{spanish ? "Comprobación rápida" : "Quick check"}</h2>
        <p className="mt-3 text-[14px] leading-6 text-[var(--text-mut)]">
          {spanish ? "¿Cuándo debes presionar +1?" : "When should you press +1?"}
        </p>
        <div className="mt-5 grid gap-2">
          <button type="button" className="border border-[var(--border)] bg-[var(--panel)] px-4 py-4 text-left text-[13px] hover:border-[var(--accent)]" onClick={() => setError(spanish ? "Todavía no. La pieza debe quedar en el área de salida." : "Not yet. The piece must remain in the output area.")}>
            {spanish ? "Cuando el trabajador toca la pieza" : "When the worker touches the piece"}
          </button>
          <button type="button" className="border border-[var(--border)] bg-[var(--panel)] px-4 py-4 text-left text-[13px] hover:border-[var(--good)]" onClick={() => void run(() => reviewerLifecycle("POST", { step: "practice_completed" }))}>
            {spanish ? "Cuando la suelta y queda en el área de salida" : "When it is released and remains in the output area"}
          </button>
          <button type="button" className="border border-[var(--border)] bg-[var(--panel)] px-4 py-4 text-left text-[13px] hover:border-[var(--accent)]" onClick={() => setError(spanish ? "No cuentes una pieza que todavía está en movimiento." : "Do not count a piece that is still moving.")}>
            {spanish ? "Mientras la pieza todavía se mueve" : "While the piece is still moving"}
          </button>
        </div>
      </div>,
    );
  }

  return shell(
    <ReviewerQualification
      lifecycle={lifecycle}
      session={session}
      onChange={onChange}
    />,
  );
}
