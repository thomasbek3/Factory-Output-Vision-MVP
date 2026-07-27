"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Check,
  Eye,
  Factory,
  ListChecks,
  Loader2,
  LogIn,
  Mail,
  MailX,
  MessageSquare,
  Pause,
  Plus,
  RadioTower,
  ShieldCheck,
  TimerReset,
  UserRoundX,
  Users,
  X,
} from "lucide-react";
import { Panel } from "@/components/ui/panel";
import {
  restoreReviewerSession,
  signInReviewer,
  signOutReviewer,
  type ReviewSession,
} from "@/lib/reviewSupabase";

type OpsSnapshot = {
  factories: number;
  stationsUp: number;
  stationsTotal: number;
  submissionsToday: number;
  oldestQueueMinutes: number;
  openQueueDepth: number;
  chunksTotal: number;
};

type FactoryOption = { id: string; name: string; timezone: string };
type ReviewerState =
  | "invited"
  | "mfa_required"
  | "terms_required"
  | "training"
  | "qualification"
  | "active"
  | "suspended"
  | "offboarded";
type ReviewerRow = {
  userId: string;
  displayName: string;
  email: string;
  locale: "en" | "es-419";
  factoryId: string;
  factoryName: string;
  state: ReviewerState;
  countryCode: string | null;
  employmentClassification: string | null;
  payBasis: string | null;
  mfaVerifiedAt: string | null;
  qualifiedAt: string | null;
  activatedAt: string | null;
  stateReason: string | null;
  queuedAssignments: number;
  submittedAssignments: number;
  lastSeenAt: string | null;
};
type RosterResponse = {
  factories: FactoryOption[];
  reviewers: ReviewerRow[];
  supportRequests: Array<{
    id: string;
    reviewerId: string;
    reviewerName: string;
    reviewerEmail: string;
    factoryName: string;
    assignmentId: string | null;
    reasonCode: string;
    message: string;
    status: "open" | "acknowledged";
    createdAt: string;
  }>;
  metrics: OpsSnapshot;
  email: { ready: boolean; sender: string | null; supportEmail: string | null };
  error?: string;
};

const stateLabel: Record<ReviewerState, string> = {
  invited: "Invited",
  mfa_required: "MFA required",
  terms_required: "Terms required",
  training: "Training",
  qualification: "Qualification",
  active: "Active",
  suspended: "Suspended",
  offboarded: "Offboarded",
};

function StatCard({
  label,
  value,
  subtitle,
  icon: Icon,
}: {
  label: string;
  value: string;
  subtitle?: string;
  icon: typeof Factory;
}) {
  return (
    <Panel className="min-h-[120px]">
      <div className="flex items-center justify-between">
        <div className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--text-dim)]">
          {label}
        </div>
        <Icon className="h-4 w-4 text-[var(--accent)]" strokeWidth={1.75} />
      </div>
      <div className="mt-4 text-[32px] font-bold leading-none text-[var(--text)]">{value}</div>
      {subtitle ? <div className="mt-2 text-[12px] leading-4 text-[var(--text-dim)]">{subtitle}</div> : null}
    </Panel>
  );
}

async function rosterRequest(method: "GET" | "POST" | "PATCH", body?: object) {
  const response = await fetch("/api/ops/reviewers", {
    method,
    credentials: "same-origin",
    cache: "no-store",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const result = (await response.json()) as RosterResponse;
  if (!response.ok) throw new Error(result.error ?? `OPS_${response.status}`);
  return result;
}

export function OpsConsole() {
  const [session, setSession] = useState<ReviewSession | null>(null);
  const [roster, setRoster] = useState<RosterResponse | null>(null);
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [inviteRequestKey, setInviteRequestKey] = useState<string | null>(null);
  const [previewLocale, setPreviewLocale] = useState<"en" | "es-419" | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const loadRoster = useCallback(async () => {
    const data = await rosterRequest("GET");
    setRoster(data);
  }, []);

  useEffect(() => {
    void restoreReviewerSession().then(async (restored) => {
      setSession(restored);
      if (restored) {
        try {
          await loadRoster();
        } catch {
          setRoster(null);
        }
      }
    });
  }, [loadRoster]);

  const cards = useMemo(() => {
    if (!roster) return [];
    const snapshot = roster.metrics;
    return [
      { label: "Factories", value: String(snapshot.factories), subtitle: "active factories you can manage", icon: Factory },
      { label: "Stations up", value: `${snapshot.stationsUp}/${snapshot.stationsTotal}`, subtitle: "active production stations", icon: RadioTower },
      { label: "Submissions today", value: String(snapshot.submissionsToday), subtitle: "human reviews received since midnight", icon: ShieldCheck },
      { label: "Oldest queue item", value: `${snapshot.oldestQueueMinutes}m`, subtitle: "age of the oldest unfinished assignment", icon: TimerReset },
      { label: "Open queue", value: String(snapshot.openQueueDepth), subtitle: "assignments waiting or in progress", icon: ListChecks },
    ];
  }, [roster]);

  async function handleSignIn(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setNotice(null);
    try {
      const authenticated = await signInReviewer(authEmail.trim(), authPassword);
      setSession(authenticated);
      setAuthPassword("");
      await loadRoster();
    } catch {
      setNotice("This account does not have FactoryVision ops access.");
    } finally {
      setBusy(false);
    }
  }

  async function handleState(userId: string, state: "suspended" | "offboarded") {
    const reason = window.prompt(`Reason for ${state}:`)?.trim();
    if (!reason) return;
    setBusy(true);
    try {
      await rosterRequest("PATCH", { userId, state, reason });
      await loadRoster();
      setNotice(`Reviewer ${state}.`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "State change failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleSupport(
    supportRequestId: string,
    supportStatus: "acknowledged" | "closed",
  ) {
    setBusy(true);
    try {
      await rosterRequest("PATCH", { supportRequestId, supportStatus });
      await loadRoster();
      setNotice(
        supportStatus === "closed"
          ? "Support request closed."
          : "Support request acknowledged.",
      );
    } catch {
      setNotice("Support request update failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleRevokeInvitation(userId: string) {
    if (!window.confirm("Revoke this invitation link?")) return;
    setBusy(true);
    try {
      await rosterRequest("PATCH", { revokeInvitationUserId: userId });
      await loadRoster();
      setNotice("Invitation revoked.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Invitation revoke failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-screen bg-[var(--bg)] p-4 text-[var(--text)] md:p-6" data-ops-route="ready">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <Link href="/" className="mb-2 inline-flex items-center gap-1 text-[12px] font-semibold text-[var(--text-dim)] hover:text-[var(--text)]">
            <ArrowLeft className="h-3.5 w-3.5" strokeWidth={1.75} />
            Console
          </Link>
          <div className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--text-dim)]">OPS</div>
          <h1 className="mt-2 text-[28px] font-semibold">FactoryVision internal</h1>
        </div>
        {session && roster ? (
          <div className="flex items-center gap-2">
            <div className={`border px-3 py-2 text-[12px] font-semibold ${roster.email.ready ? "border-[var(--good)] text-[var(--good)]" : "border-[var(--warn)] text-[var(--warn)]"}`}>
              {roster.email.ready ? "Email ready" : "Email setup required"}
            </div>
            <button
              type="button"
              onClick={() => void signOutReviewer().then(() => { setSession(null); setRoster(null); })}
              className="border border-[var(--border)] p-2 text-[var(--text-mut)] hover:text-[var(--text)]"
              title="Sign out"
            >
              <LogIn className="h-4 w-4 rotate-180" />
            </button>
          </div>
        ) : null}
      </div>

      {roster ? (
        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
          {cards.map((card) => <StatCard key={card.label} {...card} />)}
        </section>
      ) : null}

      {!session || !roster ? (
        <section className="mt-6 border-y border-[var(--border)] py-8">
          <div className="mx-auto max-w-md">
            <div className="flex items-center gap-2 text-[13px] font-semibold">
              <ShieldCheck className="h-4 w-4 text-[var(--accent)]" />
              Ops authentication
            </div>
            <h2 className="mt-2 text-[22px] font-semibold">Sign in to manage reviewers</h2>
            <form className="mt-5 grid gap-3" onSubmit={handleSignIn}>
              <label className="grid gap-1 text-[12px] text-[var(--text-mut)]">
                Email
                <input className="h-11 border border-[var(--border)] bg-[var(--panel)] px-3 text-[14px] text-[var(--text)]" type="email" value={authEmail} onChange={(event) => setAuthEmail(event.target.value)} required />
              </label>
              <label className="grid gap-1 text-[12px] text-[var(--text-mut)]">
                Password
                <input className="h-11 border border-[var(--border)] bg-[var(--panel)] px-3 text-[14px] text-[var(--text)]" type="password" value={authPassword} onChange={(event) => setAuthPassword(event.target.value)} required />
              </label>
              <button className="mt-1 inline-flex h-11 items-center justify-center gap-2 bg-[var(--accent)] px-4 text-[14px] font-semibold text-black disabled:opacity-50" disabled={busy}>
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <LogIn className="h-4 w-4" />}
                Sign in
              </button>
            </form>
          </div>
        </section>
      ) : (
        <>
          <section className="mt-6 border-y border-[var(--border)] py-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--text-dim)]">
                  <Users className="h-4 w-4 text-[var(--accent)]" />
                  Reviewer workforce
                </div>
                <h2 className="mt-2 text-[22px] font-semibold">{roster.reviewers.length} reviewer accounts</h2>
              </div>
              <button
                type="button"
                onClick={() => {
                  setInviteRequestKey(window.crypto.randomUUID());
                  setInviteOpen(true);
                }}
                className="inline-flex h-10 items-center gap-2 bg-[var(--accent)] px-4 text-[13px] font-semibold text-black"
              >
                <Plus className="h-4 w-4" />
                Invite reviewer
              </button>
            </div>
          </section>

          {roster.supportRequests.length ? (
            <section className="border-b border-[var(--border)] py-5">
              <div className="mb-4 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--text-dim)]">
                <MessageSquare className="h-4 w-4 text-[var(--accent)]" />
                Worker support
              </div>
              <div className="grid gap-px bg-[var(--border)] lg:grid-cols-2">
                {roster.supportRequests.map((request) => (
                  <article key={request.id} className="bg-[var(--bg)] p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="text-[13px] font-semibold">{request.reviewerName}</div>
                        <div className="mt-1 text-[11px] text-[var(--text-dim)]">
                          {request.factoryName} · {request.reasonCode.replaceAll("_", " ")}
                        </div>
                      </div>
                      <span className="border border-[var(--border)] px-2 py-1 text-[10px] font-semibold uppercase">
                        {request.status}
                      </span>
                    </div>
                    <p className="mt-3 text-[13px] leading-5 text-[var(--text-mut)]">
                      {request.message}
                    </p>
                    <div className="mt-4 flex justify-end gap-2">
                      {request.status === "open" ? (
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => void handleSupport(request.id, "acknowledged")}
                          className="inline-flex h-9 items-center gap-2 border border-[var(--border)] px-3 text-[12px] font-semibold"
                        >
                          <Check className="h-3.5 w-3.5" />
                          Acknowledge
                        </button>
                      ) : null}
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => void handleSupport(request.id, "closed")}
                        className="inline-flex h-9 items-center gap-2 border border-[var(--border)] px-3 text-[12px] font-semibold"
                      >
                        <X className="h-3.5 w-3.5" />
                        Close
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            </section>
          ) : null}

          <section className="overflow-x-auto">
            <table className="w-full min-w-[900px] border-collapse text-left">
              <thead>
                <tr className="border-b border-[var(--border)] text-[11px] uppercase text-[var(--text-dim)]">
                  <th className="px-3 py-3 font-semibold">Reviewer</th>
                  <th className="px-3 py-3 font-semibold">Factory</th>
                  <th className="px-3 py-3 font-semibold">Status</th>
                  <th className="px-3 py-3 font-semibold">Security</th>
                  <th className="px-3 py-3 font-semibold">Work</th>
                  <th className="px-3 py-3 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {roster.reviewers.map((reviewer) => (
                  <tr key={reviewer.userId} className="border-b border-[var(--border)]">
                    <td className="px-3 py-4">
                      <div className="text-[14px] font-semibold">{reviewer.displayName}</div>
                      <div className="mt-1 text-[12px] text-[var(--text-dim)]">{reviewer.email}</div>
                    </td>
                    <td className="px-3 py-4">
                      <div className="text-[13px]">{reviewer.factoryName}</div>
                      <div className="mt-1 text-[11px] uppercase text-[var(--text-dim)]">{reviewer.locale}</div>
                    </td>
                    <td className="px-3 py-4">
                      <span className="inline-flex border border-[var(--border)] bg-[var(--panel-2)] px-2 py-1 text-[11px] font-semibold">
                        {stateLabel[reviewer.state]}
                      </span>
                      {reviewer.stateReason ? <div className="mt-1 max-w-[220px] text-[11px] text-[var(--text-dim)]">{reviewer.stateReason}</div> : null}
                    </td>
                    <td className="px-3 py-4 text-[12px]">
                      <div className="inline-flex items-center gap-1.5">
                        {reviewer.mfaVerifiedAt ? <Check className="h-3.5 w-3.5 text-[var(--good)]" /> : <X className="h-3.5 w-3.5 text-[var(--bad)]" />}
                        MFA
                      </div>
                      <div className="mt-1 text-[11px] text-[var(--text-dim)]">{reviewer.countryCode ?? "Country missing"}</div>
                    </td>
                    <td className="px-3 py-4 text-[12px]">
                      <div>{reviewer.submittedAssignments} submitted</div>
                      <div className="mt-1 text-[11px] text-[var(--text-dim)]">{reviewer.queuedAssignments} assigned</div>
                    </td>
                    <td className="px-3 py-4">
                      <div className="flex justify-end gap-1">
                        {reviewer.state === "invited" ? (
                          <button
                            type="button"
                            title="Revoke invitation"
                            onClick={() => void handleRevokeInvitation(reviewer.userId)}
                            className="border border-[var(--border)] p-2 hover:border-[var(--bad)] hover:text-[var(--bad)]"
                          >
                            <MailX className="h-4 w-4" />
                          </button>
                        ) : null}
                        {reviewer.state === "active" ? (
                          <button type="button" title="Suspend reviewer" onClick={() => void handleState(reviewer.userId, "suspended")} className="border border-[var(--border)] p-2 hover:border-[var(--warn)] hover:text-[var(--warn)]">
                            <Pause className="h-4 w-4" />
                          </button>
                        ) : null}
                        {!["offboarded", "invited"].includes(reviewer.state) ? (
                          <button type="button" title="Offboard reviewer" onClick={() => void handleState(reviewer.userId, "offboarded")} className="border border-[var(--border)] p-2 hover:border-[var(--bad)] hover:text-[var(--bad)]">
                            <UserRoundX className="h-4 w-4" />
                          </button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </>
      )}

      {notice ? <div role="status" className="fixed bottom-5 right-5 max-w-sm border border-[var(--border)] bg-[var(--panel)] px-4 py-3 text-[12px] shadow-xl">{notice}</div> : null}

      {inviteOpen && roster && inviteRequestKey ? (
        <InviteDialog
          factories={roster.factories}
          requestKey={inviteRequestKey}
          emailReady={roster.email.ready}
          busy={busy}
          onClose={() => {
            setInviteOpen(false);
            setInviteRequestKey(null);
          }}
          onPreview={setPreviewLocale}
          onSubmit={async (payload) => {
            setBusy(true);
            setNotice(null);
            try {
              await rosterRequest("POST", payload);
              await loadRoster();
              setInviteOpen(false);
              setInviteRequestKey(null);
              setNotice(`Invitation sent to ${payload.email}.`);
            } catch (error) {
              setNotice(error instanceof Error ? error.message : "Invitation failed.");
            } finally {
              setBusy(false);
            }
          }}
        />
      ) : null}

      {previewLocale ? (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/75 p-4" role="dialog" aria-modal="true" aria-label="Invitation email preview">
          <div className="flex h-[88vh] w-full max-w-[720px] flex-col border border-[var(--border)] bg-[var(--panel)]">
            <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-3">
              <div className="flex items-center gap-2 text-[13px] font-semibold"><Mail className="h-4 w-4 text-[var(--accent)]" /> Invitation email preview</div>
              <button type="button" title="Close preview" onClick={() => setPreviewLocale(null)} className="p-2"><X className="h-4 w-4" /></button>
            </div>
            <iframe title="Invitation email" className="min-h-0 flex-1 bg-white" src={`/api/ops/email-preview?locale=${previewLocale === "en" ? "en" : "es-419"}`} />
          </div>
        </div>
      ) : null}
    </main>
  );
}

function InviteDialog({
  factories,
  requestKey,
  emailReady,
  busy,
  onClose,
  onPreview,
  onSubmit,
}: {
  factories: FactoryOption[];
  requestKey: string;
  emailReady: boolean;
  busy: boolean;
  onClose: () => void;
  onPreview: (locale: "en" | "es-419") => void;
  onSubmit: (payload: Record<string, string>) => Promise<void>;
}) {
  const [locale, setLocale] = useState<"en" | "es-419">("es-419");
  const [form, setForm] = useState({
    displayName: "",
    email: "",
    countryCode: "",
    factoryId: factories[0]?.id ?? "",
    employmentClassification: "",
    payBasis: "",
  });
  return (
    <div className="fixed inset-0 z-40 grid place-items-center bg-black/75 p-4" role="dialog" aria-modal="true" aria-label="Invite reviewer">
      <form
        className="max-h-[92vh] w-full max-w-[620px] overflow-y-auto border border-[var(--border)] bg-[var(--panel)]"
        onSubmit={(event) => {
          event.preventDefault();
          void onSubmit({ ...form, locale, requestKey });
        }}
      >
        <div className="flex items-center justify-between border-b border-[var(--border)] px-5 py-4">
          <div>
            <div className="text-[11px] font-semibold uppercase text-[var(--text-dim)]">Reviewer account</div>
            <h2 className="mt-1 text-[20px] font-semibold">Send invitation</h2>
          </div>
          <button type="button" title="Close" onClick={onClose} className="p-2"><X className="h-4 w-4" /></button>
        </div>
        <div className="grid gap-4 p-5 sm:grid-cols-2">
          <label className="grid gap-1 text-[12px] text-[var(--text-mut)] sm:col-span-2">
            Full name
            <input required className="h-11 border border-[var(--border)] bg-[var(--bg)] px-3 text-[14px] text-[var(--text)]" value={form.displayName} onChange={(event) => setForm({ ...form, displayName: event.target.value })} />
          </label>
          <label className="grid gap-1 text-[12px] text-[var(--text-mut)] sm:col-span-2">
            Email
            <input required type="email" className="h-11 border border-[var(--border)] bg-[var(--bg)] px-3 text-[14px] text-[var(--text)]" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} />
          </label>
          <label className="grid gap-1 text-[12px] text-[var(--text-mut)]">
            Factory
            <select required className="h-11 border border-[var(--border)] bg-[var(--bg)] px-3 text-[14px] text-[var(--text)]" value={form.factoryId} onChange={(event) => setForm({ ...form, factoryId: event.target.value })}>
              {factories.map((factory) => <option key={factory.id} value={factory.id}>{factory.name}</option>)}
            </select>
          </label>
          <label className="grid gap-1 text-[12px] text-[var(--text-mut)]">
            Country code
            <input required maxLength={2} placeholder="MX" className="h-11 border border-[var(--border)] bg-[var(--bg)] px-3 text-[14px] uppercase text-[var(--text)]" value={form.countryCode} onChange={(event) => setForm({ ...form, countryCode: event.target.value.toUpperCase() })} />
          </label>
          <label className="grid gap-1 text-[12px] text-[var(--text-mut)]">
            Worker classification
            <select required className="h-11 border border-[var(--border)] bg-[var(--bg)] px-3 text-[14px] text-[var(--text)]" value={form.employmentClassification} onChange={(event) => setForm({ ...form, employmentClassification: event.target.value })}>
              <option value="">Choose</option>
              <option value="employee">Employee</option>
              <option value="contractor">Contractor</option>
            </select>
          </label>
          <label className="grid gap-1 text-[12px] text-[var(--text-mut)]">
            Pay basis
            <select required className="h-11 border border-[var(--border)] bg-[var(--bg)] px-3 text-[14px] text-[var(--text)]" value={form.payBasis} onChange={(event) => setForm({ ...form, payBasis: event.target.value })}>
              <option value="">Choose</option>
              <option value="hourly">Hourly</option>
              <option value="per_chunk">Per completed video</option>
            </select>
          </label>
          <div className="sm:col-span-2">
            <div className="mb-2 text-[12px] text-[var(--text-mut)]">Invitation language</div>
            <div className="inline-flex border border-[var(--border)] p-1">
              {(["es-419", "en"] as const).map((value) => (
                <button key={value} type="button" onClick={() => setLocale(value)} className={`h-8 px-3 text-[12px] font-semibold ${locale === value ? "bg-[var(--accent)] text-black" : "text-[var(--text-mut)]"}`}>
                  {value === "es-419" ? "Español" : "English"}
                </button>
              ))}
            </div>
          </div>
          {!emailReady ? (
            <div className="sm:col-span-2 border-l-4 border-[var(--warn)] bg-[var(--warn-tint)] px-4 py-3 text-[12px] leading-5 text-[var(--warn)]">
              Sending is locked until the Supabase server key, verified sender, support address and Resend credential are configured.
            </div>
          ) : null}
        </div>
        <div className="flex flex-wrap justify-end gap-2 border-t border-[var(--border)] px-5 py-4">
          <button type="button" onClick={() => onPreview(locale)} className="inline-flex h-10 items-center gap-2 border border-[var(--border)] px-4 text-[13px] font-semibold">
            <Eye className="h-4 w-4" /> Preview email
          </button>
          <button type="submit" disabled={busy || !emailReady} className="inline-flex h-10 items-center gap-2 bg-[var(--accent)] px-4 text-[13px] font-semibold text-black disabled:cursor-not-allowed disabled:opacity-40">
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Mail className="h-4 w-4" />} Send invitation
          </button>
        </div>
      </form>
    </div>
  );
}
