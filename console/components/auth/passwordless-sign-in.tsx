"use client";

import { FormEvent, useEffect, useState } from "react";
import { ArrowRight, Factory, Loader2, Mail } from "lucide-react";

type PasswordlessSignInProps = {
  role: "owner" | "ops";
};

function safeClientReturnTo(value: string | null, fallback: string) {
  if (!value?.startsWith("/") || value.startsWith("//") || value.includes("\\")) {
    return fallback;
  }
  try {
    const resolved = new URL(value, window.location.origin);
    return resolved.origin === window.location.origin
      ? `${resolved.pathname}${resolved.search}`
      : fallback;
  } catch {
    return fallback;
  }
}

export function PasswordlessSignIn({ role }: PasswordlessSignInProps) {
  const [email, setEmail] = useState("");
  const [state, setState] = useState<
    "idle" | "submitting" | "sent" | "completing" | "error"
  >("idle");
  const [message, setMessage] = useState("");
  const endpoint = role === "owner" ? "/api/owner/session" : "/api/ops/session";
  const defaultDestination = role === "owner" ? "/" : "/ops";

  useEffect(() => {
    const values = new URLSearchParams(window.location.hash.slice(1));
    const accessToken = values.get("access_token");
    const refreshToken = values.get("refresh_token");
    if (!accessToken || !refreshToken) return;
    const destination = safeClientReturnTo(
      new URLSearchParams(window.location.search).get("return_to"),
      defaultDestination,
    );

    let active = true;
    void (async () => {
      await Promise.resolve();
      if (!active) return;
      setState("completing");
      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "completePasswordless",
          accessToken,
          refreshToken,
          expiresIn: Number(values.get("expires_in") ?? 3600),
        }),
      });
      if (!active) return;
      if (!response.ok) {
        setState("error");
        setMessage(
          role === "owner"
            ? "This account does not have owner access."
            : "This account does not have operations access.",
        );
        return;
      }
      window.history.replaceState(null, "", window.location.pathname);
      window.location.replace(destination);
    })();
    return () => {
      active = false;
    };
  }, [defaultDestination, endpoint, role]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setState("submitting");
    setMessage("");
    try {
      const returnTo = safeClientReturnTo(
        new URLSearchParams(window.location.search).get("return_to"),
        defaultDestination,
      );
      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "requestPasswordless",
          email,
          returnTo,
        }),
      });
      const payload = (await response.json().catch(() => ({}))) as {
        error?: string;
      };
      if (!response.ok) {
        setState("error");
        setMessage(payload.error ?? "Sign-in is temporarily unavailable.");
        return;
      }
      setState("sent");
      setMessage(`Check ${email} for your secure sign-in link.`);
    } catch {
      setState("error");
      setMessage("Sign-in is temporarily unavailable.");
    }
  }

  const busy = state === "submitting" || state === "completing";

  return (
    <main className="flex min-h-screen items-center justify-center bg-bg px-5 py-12">
      <section className="w-full max-w-[420px]" aria-labelledby="sign-in-title">
        <div className="mb-10 flex items-center gap-3 text-text">
          <span className="grid size-9 place-items-center border border-accent bg-accent-tint text-accent">
            <Factory size={19} strokeWidth={1.8} aria-hidden="true" />
          </span>
          <span className="text-[15px] font-semibold">FactoryVision</span>
        </div>

        <p className="mb-2 text-xs font-semibold uppercase text-accent">
          {role === "owner" ? "Factory owner" : "Internal operations"}
        </p>
        <h1 id="sign-in-title" className="text-3xl font-semibold text-text">
          Sign in to your workspace
        </h1>
        <p className="mt-3 text-sm leading-6 text-text-mut">
          Enter your approved work email. We will send a secure sign-in link.
        </p>

        <form className="mt-8" onSubmit={submit}>
          <label className="mb-2 block text-sm font-medium text-text" htmlFor="email">
            Work email
          </label>
          <div className="relative">
            <Mail
              size={17}
              aria-hidden="true"
              className="absolute left-3 top-1/2 -translate-y-1/2 text-text-dim"
            />
            <input
              id="email"
              type="email"
              autoComplete="email"
              required
              disabled={busy}
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="h-12 w-full border border-border bg-panel pl-10 pr-3 text-sm text-text outline-none placeholder:text-text-dim focus:border-accent"
              placeholder="you@company.com"
            />
          </div>
          <button
            type="submit"
            disabled={busy}
            className="mt-4 flex h-12 w-full items-center justify-center gap-2 bg-accent px-4 text-sm font-semibold text-black disabled:cursor-wait disabled:opacity-70"
          >
            {busy ? (
              <Loader2 size={17} className="animate-spin" aria-hidden="true" />
            ) : (
              <ArrowRight size={17} aria-hidden="true" />
            )}
            {state === "completing" ? "Opening workspace" : "Email sign-in link"}
          </button>
        </form>

        {message ? (
          <p
            className={`mt-4 border px-3 py-3 text-sm ${
              state === "error"
                ? "border-bad/40 bg-bad-tint text-bad"
                : "border-good/40 bg-good-tint text-good"
            }`}
            role={state === "error" ? "alert" : "status"}
          >
            {message}
          </p>
        ) : null}
      </section>
    </main>
  );
}
