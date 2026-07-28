"use client";

import {
  FormEvent,
  type ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import Link from "next/link";
import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  Bot,
  Check,
  ChevronRight,
  ClipboardCheck,
  Clock3,
  FileCheck2,
  Gauge,
  Inbox,
  ListChecks,
  Loader2,
  LogOut,
  Mail,
  MailX,
  MessageSquare,
  MoreHorizontal,
  Pause,
  Plus,
  RadioTower,
  RefreshCw,
  Search,
  ShieldCheck,
  UserRoundX,
  Users,
  X,
} from "lucide-react";
import {
  restoreReviewerSession,
  signInReviewer,
  signOutReviewer,
  type ReviewSession,
} from "@/lib/reviewSupabase";
import { InviteDialog } from "@/components/ops/ops-console";

type OpsTab = "overview" | "queue" | "labels" | "reviewers" | "ai";
type ReviewerState =
  | "invited"
  | "mfa_required"
  | "terms_required"
  | "training"
  | "qualification"
  | "active"
  | "suspended"
  | "offboarded";
type FactoryOption = { id: string; name: string; timezone: string };
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
type SupportRequest = {
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
};
type QueueReviewer = {
  reviewerId: string;
  reviewerName: string;
  status: string;
  assignedAt: string;
  submittedAt: string | null;
};
type QueueRow = {
  chunkId: string;
  factoryId: string;
  factoryName: string;
  factoryTimezone: string;
  stationId: string;
  stationAlias: string;
  sourceStartAt: string;
  sourceEndAt: string;
  chunkState: string;
  reviewRound: number;
  ageMinutes: number;
  requiredReviews: number;
  submittedReviews: number;
  openReviews: number;
  leasedReviews: number;
  reviewers: QueueReviewer[];
};
type HumanTotal = {
  submissionId: string;
  reviewerId: string;
  reviewerName: string;
  resultType: "counted" | "problem";
  totalCount: number | null;
  problemCode: string | null;
  submittedAt: string;
};
type LabelRow = {
  chunkId: string;
  factoryId: string;
  factoryName: string;
  factoryTimezone: string;
  stationId: string;
  stationAlias: string;
  sourceStartAt: string;
  sourceEndAt: string;
  chunkState: string;
  sourceSha256: string;
  reviewRound: number;
  submissionCount: number;
  problemCount: number;
  humanTotals: HumanTotal[];
  consensusStatus: string | null;
  resolvedTotal: number | null;
  supportCount: number | null;
  consensusEventCount: number;
  humanFinalAt: string | null;
  publicationCount: number;
  exceptionType: string | null;
  exceptionReason: string | null;
  aiRunId: string | null;
  aiStatus:
    | "not_run"
    | "locked_until_human_final"
    | "running"
    | "awaiting_comparison"
    | "compared";
  aiCodeVersion: string | null;
  aiEventCount: number;
  comparisonMetrics: Record<string, unknown> | null;
  comparisonCreatedAt: string | null;
};
type FactoryHealth = {
  id: string;
  name: string;
  timezone: string;
  status: string;
  isTest: boolean;
  retentionDays: number;
  stations: Array<{
    id: string;
    alias: string;
    status: string;
    chunkCount: number;
    latestFootageAt: string | null;
    openAssignments: number;
  }>;
};
type CommandCenter = {
  summary: {
    activeReviewers: number;
    submissions24h: number;
    openAssignments: number;
    oldestQueueMinutes: number;
    openSupport: number;
    readyForResolution: number;
    resolvedChunks: number;
    aiRuns: number;
    aiComparisons: number;
  };
  queue: QueueRow[];
  labels: LabelRow[];
  factories: FactoryHealth[];
};
type RosterResponse = {
  factories: FactoryOption[];
  reviewers: ReviewerRow[];
  supportRequests: SupportRequest[];
  metrics: {
    factories: number;
    stationsUp: number;
    stationsTotal: number;
    submissionsToday: number;
    oldestQueueMinutes: number;
    openQueueDepth: number;
    chunksTotal: number;
  };
  commandCenter: CommandCenter;
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

const tabItems: Array<{
  id: OpsTab;
  label: string;
  icon: typeof Gauge;
}> = [
  { id: "overview", label: "Overview", icon: Gauge },
  { id: "queue", label: "Review queue", icon: ListChecks },
  { id: "labels", label: "Label output", icon: FileCheck2 },
  { id: "reviewers", label: "Reviewers", icon: Users },
  { id: "ai", label: "AI evaluation", icon: Bot },
];

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

function formatAge(minutes: number) {
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const remainder = minutes % 60;
  return remainder ? `${hours}h ${remainder}m` : `${hours}h`;
}

function formatFactoryTime(value: string, timezone: string) {
  return new Intl.DateTimeFormat("en-US", {
    timeZone: timezone,
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

function timeAgo(value: string | null) {
  if (!value) return "Never";
  const minutes = Math.max(
    0,
    Math.floor((Date.now() - new Date(value).getTime()) / 60000),
  );
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes}m ago`;
  if (minutes < 1440) return `${Math.floor(minutes / 60)}h ago`;
  return `${Math.floor(minutes / 1440)}d ago`;
}

export function truthStatus(label: LabelRow) {
  if (label.humanFinalAt) return { text: "Human final", tone: "good" };
  if (label.consensusStatus === "resolved") {
    return { text: "Resolved · awaiting final", tone: "info" };
  }
  if (label.consensusStatus === "no_majority") {
    return { text: "No majority", tone: "bad" };
  }
  if (label.consensusStatus === "problem") {
    return { text: "Footage problem", tone: "bad" };
  }
  if (label.consensusStatus === "pending_seam") {
    return { text: "Boundary review", tone: "warn" };
  }
  if (label.submissionCount === 3) {
    return { text: "Ready to resolve", tone: "warn" };
  }
  return { text: `${label.submissionCount}/3 reviews`, tone: "muted" };
}

export function humanSubmissionValue(
  human: Pick<HumanTotal, "resultType" | "totalCount">,
) {
  return human.resultType === "counted" ? human.totalCount : "!";
}

function ToneBadge({
  text,
  tone,
}: {
  text: string;
  tone: "good" | "bad" | "warn" | "muted" | "info";
}) {
  const styles = {
    good: "border-[var(--good)]/35 bg-[var(--good)]/10 text-[var(--good)]",
    bad: "border-[var(--bad)]/35 bg-[var(--bad)]/10 text-[var(--bad)]",
    warn: "border-[var(--warn)]/35 bg-[var(--warn)]/10 text-[var(--warn)]",
    muted: "border-[var(--border)] bg-[var(--panel-2)] text-[var(--text-mut)]",
    info: "border-sky-400/35 bg-sky-400/10 text-sky-300",
  };
  return (
    <span className={`inline-flex border px-2 py-1 text-[10px] font-semibold uppercase ${styles[tone]}`}>
      {text}
    </span>
  );
}

function SectionHeading({
  title,
  meta,
  action,
}: {
  title: string;
  meta?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex min-h-14 flex-wrap items-center justify-between gap-3 border-b border-[var(--border)] px-5 py-3">
      <div>
        <h2 className="text-[15px] font-semibold">{title}</h2>
        {meta ? <div className="mt-0.5 text-[11px] text-[var(--text-dim)]">{meta}</div> : null}
      </div>
      {action}
    </div>
  );
}

export function OpsCommandCenter() {
  const [session, setSession] = useState<ReviewSession | null>(null);
  const [roster, setRoster] = useState<RosterResponse | null>(null);
  const [activeTab, setActiveTab] = useState<OpsTab>("overview");
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [inviteRequestKey, setInviteRequestKey] = useState<string | null>(null);
  const [previewLocale, setPreviewLocale] = useState<"en" | "es-419" | null>(null);
  const [selectedLabel, setSelectedLabel] = useState<LabelRow | null>(null);
  const [search, setSearch] = useState("");
  const [notice, setNotice] = useState<string | null>(null);

  const loadRoster = useCallback(async () => {
    const data = await rosterRequest("GET");
    setRoster(data);
    return data;
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
      setLoading(false);
    });
  }, [loadRoster]);

  const command = roster?.commandCenter;
  const filteredLabels = useMemo(() => {
    if (!command) return [];
    const query = search.trim().toLowerCase();
    if (!query) return command.labels;
    return command.labels.filter((label) =>
      [
        label.factoryName,
        label.stationAlias,
        label.chunkId,
        String(label.reviewRound),
        ...label.humanTotals.map((human) => human.reviewerName),
      ].some((value) => value.toLowerCase().includes(query)),
    );
  }, [command, search]);

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

  async function refresh() {
    setBusy(true);
    try {
      await loadRoster();
      setNotice("Operations data refreshed.");
    } catch {
      setNotice("Refresh failed.");
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

  if (loading) {
    return (
      <main className="grid min-h-screen place-items-center bg-[var(--bg)] text-[var(--text)]" data-ops-route="ready">
        <Loader2 className="h-6 w-6 animate-spin text-[var(--accent)]" />
      </main>
    );
  }

  if (!session || !roster || !command) {
    return (
      <main className="min-h-screen bg-[var(--bg)] text-[var(--text)]" data-ops-route="ready">
        <header className="border-b border-[var(--border)] px-5 py-4">
          <Link href="/" className="inline-flex items-center gap-2 text-[12px] font-semibold text-[var(--text-mut)]">
            <ArrowLeft className="h-4 w-4" />
            Console
          </Link>
        </header>
        <section className="mx-auto flex min-h-[calc(100vh-65px)] max-w-md items-center px-5 py-12">
          <div className="w-full border border-[var(--border)] bg-[var(--panel)] p-6">
            <div className="flex h-10 w-10 items-center justify-center border border-[var(--border)] bg-[var(--panel-2)] text-[var(--accent)]">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <h1 className="mt-6 text-[24px] font-semibold">Sign in to manage reviewers</h1>
            <form className="mt-6 grid gap-4" onSubmit={handleSignIn}>
              <label className="grid gap-1.5 text-[12px] text-[var(--text-mut)]">
                Email
                <input
                  className="h-11 border border-[var(--border)] bg-[var(--bg)] px-3 text-[14px] text-[var(--text)] outline-none focus:border-[var(--accent)]"
                  type="email"
                  value={authEmail}
                  onChange={(event) => setAuthEmail(event.target.value)}
                  required
                />
              </label>
              <label className="grid gap-1.5 text-[12px] text-[var(--text-mut)]">
                Password
                <input
                  className="h-11 border border-[var(--border)] bg-[var(--bg)] px-3 text-[14px] text-[var(--text)] outline-none focus:border-[var(--accent)]"
                  type="password"
                  value={authPassword}
                  onChange={(event) => setAuthPassword(event.target.value)}
                  required
                />
              </label>
              <button
                className="mt-1 inline-flex h-11 items-center justify-center gap-2 bg-[var(--accent)] px-4 text-[14px] font-semibold text-black disabled:opacity-50"
                disabled={busy}
              >
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
                Sign in
              </button>
            </form>
          </div>
        </section>
        {notice ? <StatusNotice notice={notice} /> : null}
      </main>
    );
  }

  const missingCountry = roster.reviewers.filter(
    (reviewer) => reviewer.state === "active" && !reviewer.countryCode,
  ).length;

  return (
    <main className="min-h-screen bg-[var(--bg)] text-[var(--text)]" data-ops-route="ready">
      <header className="sticky top-0 z-30 flex h-16 items-center border-b border-[var(--border)] bg-[var(--bg)]/95 backdrop-blur">
        <div className="flex h-full w-16 shrink-0 items-center justify-center border-r border-[var(--border)] text-[15px] font-black">
          F<span className="text-[var(--accent)]">V</span>
        </div>
        <div className="flex min-w-0 flex-1 items-center justify-between gap-4 px-4 md:px-5">
          <div className="min-w-0">
            <div className="truncate text-[15px] font-semibold">FactoryVision Ops</div>
            <div className="truncate text-[11px] text-[var(--text-dim)]">
              {command.factories[0]?.name ?? "Internal operations"}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => void refresh()}
              disabled={busy}
              title="Refresh operations data"
              className="inline-flex h-9 w-9 items-center justify-center border border-[var(--border)] text-[var(--text-mut)] hover:text-[var(--text)]"
            >
              <RefreshCw className={`h-4 w-4 ${busy ? "animate-spin" : ""}`} />
            </button>
            <button
              type="button"
              onClick={() => {
                setInviteRequestKey(window.crypto.randomUUID());
                setInviteOpen(true);
              }}
              className="hidden h-9 items-center gap-2 bg-[var(--accent)] px-3 text-[12px] font-semibold text-black sm:inline-flex"
            >
              <Plus className="h-4 w-4" />
              Invite reviewer
            </button>
            <button
              type="button"
              onClick={() => void signOutReviewer().then(() => {
                setSession(null);
                setRoster(null);
              })}
              title="Sign out"
              className="inline-flex h-9 w-9 items-center justify-center border border-[var(--border)] text-[var(--text-mut)] hover:text-[var(--text)]"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </header>

      <div className="flex min-h-[calc(100vh-64px)]">
        <aside className="hidden w-56 shrink-0 border-r border-[var(--border)] px-3 py-4 lg:block">
          <nav className="grid gap-1" aria-label="Operations">
            {tabItems.map((item) => {
              const Icon = item.icon;
              const count = item.id === "queue"
                ? command.summary.openAssignments
                : item.id === "reviewers"
                  ? roster.reviewers.length
                  : item.id === "ai"
                    ? command.summary.aiComparisons
                    : null;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setActiveTab(item.id)}
                  className={`flex h-10 items-center gap-3 px-3 text-left text-[12px] font-semibold ${
                    activeTab === item.id
                      ? "bg-[var(--panel-2)] text-[var(--text)]"
                      : "text-[var(--text-mut)] hover:bg-[var(--panel)] hover:text-[var(--text)]"
                  }`}
                >
                  <Icon className={`h-4 w-4 ${activeTab === item.id ? "text-[var(--accent)]" : ""}`} />
                  <span className="flex-1">{item.label}</span>
                  {count !== null ? <span className="text-[10px] text-[var(--text-dim)]">{count}</span> : null}
                </button>
              );
            })}
          </nav>
          <div className="mt-6 border-t border-[var(--border)] pt-4">
            {command.factories.map((factory) => (
              <div key={factory.id} className="px-3 py-2">
                <div className="flex items-center gap-2 text-[11px] font-semibold">
                  <span className="h-1.5 w-1.5 bg-[var(--good)]" />
                  {factory.name}
                </div>
                <div className="mt-1 pl-3.5 text-[10px] text-[var(--text-dim)]">
                  {factory.stations.filter((station) => station.status === "active").length}/{factory.stations.length} stations online
                </div>
              </div>
            ))}
          </div>
        </aside>

        <div className="min-w-0 flex-1 overflow-x-hidden">
          <nav className="flex overflow-x-auto border-b border-[var(--border)] lg:hidden" aria-label="Operations">
            {tabItems.map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setActiveTab(item.id)}
                  className={`flex h-12 shrink-0 items-center gap-2 border-b-2 px-4 text-[11px] font-semibold ${
                    activeTab === item.id
                      ? "border-[var(--accent)] text-[var(--text)]"
                      : "border-transparent text-[var(--text-mut)]"
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  {item.label}
                </button>
              );
            })}
          </nav>

          <section className="border-b border-[var(--border)] px-4 py-5 md:px-6">
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div>
                <div className="text-[10px] font-semibold uppercase tracking-[0.06em] text-[var(--text-dim)]">
                  {tabItems.find((item) => item.id === activeTab)?.label}
                </div>
                <h1 className="mt-1 text-[24px] font-semibold">
                  {activeTab === "overview" ? "Operations command center"
                    : activeTab === "queue" ? "Review queue"
                      : activeTab === "labels" ? "Human label output"
                        : activeTab === "reviewers" ? "Reviewer workforce"
                          : "Human vs AI evaluation"}
                </h1>
              </div>
              <div className="text-right text-[11px] text-[var(--text-dim)]">
                <div>{new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}</div>
                <div className="mt-1">{roster.email.ready ? "Email delivery ready" : "Email setup required"}</div>
              </div>
            </div>
          </section>

          {activeTab === "overview" ? (
            <OverviewView
              roster={roster}
              command={command}
              missingCountry={missingCountry}
              onTab={setActiveTab}
              onSupport={handleSupport}
              busy={busy}
            />
          ) : null}
          {activeTab === "queue" ? <QueueView rows={command.queue} /> : null}
          {activeTab === "labels" ? (
            <LabelsView
              labels={filteredLabels}
              search={search}
              onSearch={setSearch}
              onSelect={setSelectedLabel}
            />
          ) : null}
          {activeTab === "reviewers" ? (
            <ReviewersView
              roster={roster}
              busy={busy}
              onInvite={() => {
                setInviteRequestKey(window.crypto.randomUUID());
                setInviteOpen(true);
              }}
              onState={handleState}
              onRevoke={handleRevokeInvitation}
              onSupport={handleSupport}
            />
          ) : null}
          {activeTab === "ai" ? <AiView labels={command.labels} summary={command.summary} /> : null}
        </div>
      </div>

      {selectedLabel ? (
        <LabelDetail label={selectedLabel} onClose={() => setSelectedLabel(null)} />
      ) : null}
      {notice ? <StatusNotice notice={notice} /> : null}
      {inviteOpen && inviteRequestKey ? (
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
              <div className="flex items-center gap-2 text-[13px] font-semibold">
                <Mail className="h-4 w-4 text-[var(--accent)]" />
                Invitation email preview
              </div>
              <button type="button" title="Close preview" onClick={() => setPreviewLocale(null)} className="p-2">
                <X className="h-4 w-4" />
              </button>
            </div>
            <iframe title="Invitation email" className="min-h-0 flex-1 bg-white" src={`/api/ops/email-preview?locale=${previewLocale === "en" ? "en" : "es-419"}`} />
          </div>
        </div>
      ) : null}
    </main>
  );
}

function OverviewView({
  roster,
  command,
  missingCountry,
  onTab,
  onSupport,
  busy,
}: {
  roster: RosterResponse;
  command: CommandCenter;
  missingCountry: number;
  onTab: (tab: OpsTab) => void;
  onSupport: (id: string, state: "acknowledged" | "closed") => Promise<void>;
  busy: boolean;
}) {
  const latestLabels = command.labels.filter((label) => label.submissionCount > 0).slice(0, 5);
  const stations = command.factories.flatMap((factory) =>
    factory.stations.map((station) => ({ ...station, factoryName: factory.name })),
  );
  const attention = [
    command.summary.oldestQueueMinutes > 120 ? {
      title: "Overdue review work",
      detail: `Oldest assignment is ${formatAge(command.summary.oldestQueueMinutes)}`,
      tone: "bad" as const,
      tab: "queue" as OpsTab,
    } : null,
    command.summary.readyForResolution > 0 ? {
      title: `${command.summary.readyForResolution} round${command.summary.readyForResolution === 1 ? "" : "s"} ready to resolve`,
      detail: "Three human submissions are complete",
      tone: "warn" as const,
      tab: "labels" as OpsTab,
    } : null,
    roster.supportRequests.length > 0 ? {
      title: `${roster.supportRequests.length} worker support request${roster.supportRequests.length === 1 ? "" : "s"}`,
      detail: "Reviewer assistance is waiting",
      tone: "info" as const,
      tab: "reviewers" as OpsTab,
    } : null,
    missingCountry > 0 ? {
      title: `${missingCountry} reviewer${missingCountry === 1 ? "" : "s"} missing country`,
      detail: "Employment profile is incomplete",
      tone: "warn" as const,
      tab: "reviewers" as OpsTab,
    } : null,
    !roster.email.ready ? {
      title: "Invitation email setup required",
      detail: "New reviewer delivery is locked",
      tone: "warn" as const,
      tab: "reviewers" as OpsTab,
    } : null,
  ].filter(Boolean) as Array<{ title: string; detail: string; tone: "bad" | "warn" | "info"; tab: OpsTab }>;

  return (
    <div className="min-w-0 p-4 md:p-6">
      <section className="grid border border-[var(--border)] sm:grid-cols-2 xl:grid-cols-5">
        {[
          ["Reviewers active", command.summary.activeReviewers, Users],
          ["Submissions · 24h", command.summary.submissions24h, ClipboardCheck],
          ["Assignments open", command.summary.openAssignments, ListChecks],
          ["Oldest assignment", formatAge(command.summary.oldestQueueMinutes), Clock3],
          ["Human finals", command.summary.resolvedChunks, ShieldCheck],
        ].map(([label, value, Icon], index) => {
          const MetricIcon = Icon as typeof Users;
          return (
            <div key={String(label)} className={`min-h-24 p-4 ${index ? "border-t border-[var(--border)] sm:border-l sm:border-t-0" : ""}`}>
              <div className="flex items-center justify-between gap-2 text-[10px] font-semibold uppercase tracking-[0.06em] text-[var(--text-dim)]">
                {String(label)}
                <MetricIcon className="h-4 w-4 text-[var(--accent)]" />
              </div>
              <div className="mt-3 text-[25px] font-semibold">{String(value)}</div>
            </div>
          );
        })}
      </section>

      <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1.35fr)_minmax(340px,0.65fr)]">
        <section className="border border-[var(--border)]">
          <SectionHeading title="Attention required" meta={`${attention.length} current exception${attention.length === 1 ? "" : "s"}`} />
          {attention.length ? (
            <div className="divide-y divide-[var(--border)]">
              {attention.map((item) => (
                <button
                  key={item.title}
                  type="button"
                  onClick={() => onTab(item.tab)}
                  className="grid w-full grid-cols-[32px_minmax(0,1fr)_auto] items-center gap-3 px-5 py-4 text-left hover:bg-[var(--panel)]"
                >
                  <span className={`flex h-8 w-8 items-center justify-center border ${
                    item.tone === "bad"
                      ? "border-[var(--bad)]/35 text-[var(--bad)]"
                      : item.tone === "warn"
                        ? "border-[var(--warn)]/35 text-[var(--warn)]"
                        : "border-sky-400/35 text-sky-300"
                  }`}>
                    {item.tone === "info" ? <MessageSquare className="h-4 w-4" /> : <AlertTriangle className="h-4 w-4" />}
                  </span>
                  <span>
                    <span className="block text-[13px] font-semibold">{item.title}</span>
                    <span className="mt-1 block text-[11px] text-[var(--text-dim)]">{item.detail}</span>
                  </span>
                  <ChevronRight className="h-4 w-4 text-[var(--text-dim)]" />
                </button>
              ))}
            </div>
          ) : (
            <div className="flex min-h-40 items-center justify-center gap-2 text-[13px] text-[var(--text-mut)]">
              <Check className="h-4 w-4 text-[var(--good)]" />
              No current exceptions
            </div>
          )}
        </section>

        <section className="border border-[var(--border)]">
          <SectionHeading title="Factory and footage health" meta={`${stations.length} station${stations.length === 1 ? "" : "s"}`} />
          <div className="divide-y divide-[var(--border)]">
            {stations.map((station) => (
              <div key={station.id} className="px-5 py-4">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2 text-[13px] font-semibold">
                    <RadioTower className="h-4 w-4 text-[var(--accent)]" />
                    {station.alias}
                  </div>
                  <ToneBadge text={station.status} tone={station.status === "active" ? "good" : "bad"} />
                </div>
                <div className="mt-3 grid grid-cols-3 gap-3 text-[11px]">
                  <div><span className="block text-[var(--text-dim)]">Factory</span><span className="mt-1 block">{station.factoryName}</span></div>
                  <div><span className="block text-[var(--text-dim)]">Chunks</span><span className="mt-1 block">{station.chunkCount}</span></div>
                  <div><span className="block text-[var(--text-dim)]">Open</span><span className="mt-1 block">{station.openAssignments}</span></div>
                </div>
                <div className="mt-3 text-[10px] text-[var(--text-dim)]">
                  Latest footage: {station.latestFootageAt ? new Date(station.latestFootageAt).toLocaleString() : "None"}
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1.35fr)_minmax(340px,0.65fr)]">
        <section className="min-w-0 max-w-full overflow-hidden border border-[var(--border)]">
          <SectionHeading
            title="Recent label output"
            meta="Latest human submissions"
            action={<button type="button" onClick={() => onTab("labels")} className="text-[11px] font-semibold text-[var(--accent)]">View all</button>}
          />
          <LabelTable labels={latestLabels} compact onSelect={() => onTab("labels")} />
        </section>
        <section className="border border-[var(--border)]">
          <SectionHeading title="Worker support" meta={`${roster.supportRequests.length} open or acknowledged`} />
          {roster.supportRequests.length ? (
            <div className="divide-y divide-[var(--border)]">
              {roster.supportRequests.slice(0, 3).map((request) => (
                <div key={request.id} className="px-5 py-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="text-[12px] font-semibold">{request.reviewerName}</div>
                      <div className="mt-1 text-[10px] text-[var(--text-dim)]">{timeAgo(request.createdAt)}</div>
                    </div>
                    <ToneBadge text={request.status} tone={request.status === "open" ? "warn" : "muted"} />
                  </div>
                  <p className="mt-3 text-[12px] leading-5 text-[var(--text-mut)]">{request.message}</p>
                  <div className="mt-3 flex gap-2">
                    {request.status === "open" ? (
                      <button type="button" disabled={busy} onClick={() => void onSupport(request.id, "acknowledged")} className="h-8 border border-[var(--border)] px-3 text-[11px] font-semibold">
                        Acknowledge
                      </button>
                    ) : null}
                    <button type="button" disabled={busy} onClick={() => void onSupport(request.id, "closed")} className="h-8 border border-[var(--border)] px-3 text-[11px] font-semibold">
                      Close
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex min-h-40 items-center justify-center gap-2 text-[13px] text-[var(--text-mut)]">
              <Inbox className="h-4 w-4" />
              Inbox clear
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

function QueueView({ rows }: { rows: QueueRow[] }) {
  return (
    <div className="p-4 md:p-6">
      <section className="border border-[var(--border)]">
        <SectionHeading title="Assignment queue" meta={`${rows.length} active chunk${rows.length === 1 ? "" : "s"}`} />
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px] border-collapse text-left">
            <thead>
              <tr className="border-b border-[var(--border)] text-[10px] font-semibold uppercase text-[var(--text-dim)]">
                <th className="px-4 py-3">Age</th>
                <th className="px-4 py-3">Factory / station</th>
                <th className="px-4 py-3">Footage window</th>
                <th className="px-4 py-3">Human reviews</th>
                <th className="px-4 py-3">State</th>
                <th className="px-4 py-3">Reviewers</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={`${row.chunkId}-${row.reviewRound}`} className="border-b border-[var(--border)] align-top hover:bg-[var(--panel)]">
                  <td className="px-4 py-4">
                    <div className={`text-[13px] font-semibold ${row.ageMinutes > 120 ? "text-[var(--bad)]" : ""}`}>{formatAge(row.ageMinutes)}</div>
                    <div className="mt-1 text-[10px] text-[var(--text-dim)]">Round {row.reviewRound}</div>
                  </td>
                  <td className="px-4 py-4">
                    <div className="text-[12px] font-semibold">{row.factoryName}</div>
                    <div className="mt-1 text-[11px] text-[var(--text-dim)]">{row.stationAlias}</div>
                  </td>
                  <td className="px-4 py-4 text-[11px]">
                    <div>{formatFactoryTime(row.sourceStartAt, row.factoryTimezone)}</div>
                    <div className="mt-1 text-[var(--text-dim)]">15-minute chunk</div>
                  </td>
                  <td className="px-4 py-4">
                    <div className="text-[12px] font-semibold">{row.submittedReviews}/{row.requiredReviews} complete</div>
                    <div className="mt-2 h-1.5 w-32 bg-[var(--panel-2)]">
                      <div className="h-full bg-[var(--accent)]" style={{ width: `${Math.min(100, row.submittedReviews / row.requiredReviews * 100)}%` }} />
                    </div>
                  </td>
                  <td className="px-4 py-4">
                    <ToneBadge text={row.leasedReviews ? "In progress" : "Waiting"} tone={row.leasedReviews ? "info" : "warn"} />
                  </td>
                  <td className="px-4 py-4">
                    <div className="grid gap-1">
                      {row.reviewers.map((reviewer) => (
                        <div key={reviewer.reviewerId} className="flex items-center justify-between gap-3 text-[11px]">
                          <span>{reviewer.reviewerName}</span>
                          <span className="text-[var(--text-dim)]">{reviewer.status}</span>
                        </div>
                      ))}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!rows.length ? <EmptyRows icon={ListChecks} text="No assignments are waiting or in progress" /> : null}
        </div>
      </section>
    </div>
  );
}

function LabelsView({
  labels,
  search,
  onSearch,
  onSelect,
}: {
  labels: LabelRow[];
  search: string;
  onSearch: (value: string) => void;
  onSelect: (label: LabelRow) => void;
}) {
  return (
    <div className="p-4 md:p-6">
      <section className="border border-[var(--border)]">
        <SectionHeading
          title="Review rounds"
          meta={`${labels.length} rows`}
          action={
            <label className="flex h-9 w-full max-w-64 items-center gap-2 border border-[var(--border)] bg-[var(--bg)] px-3">
              <Search className="h-4 w-4 text-[var(--text-dim)]" />
              <span className="sr-only">Search label output</span>
              <input value={search} onChange={(event) => onSearch(event.target.value)} placeholder="Search labels" className="min-w-0 flex-1 bg-transparent text-[12px] outline-none" />
            </label>
          }
        />
        <LabelTable labels={labels} onSelect={onSelect} />
      </section>
    </div>
  );
}

function LabelTable({
  labels,
  compact = false,
  onSelect,
}: {
  labels: LabelRow[];
  compact?: boolean;
  onSelect: (label: LabelRow) => void;
}) {
  return (
    <>
      <div className="divide-y divide-[var(--border)] md:hidden">
        {labels.map((label) => {
          const status = truthStatus(label);
          return (
            <button
              key={`${label.chunkId}-${label.reviewRound}-mobile`}
              type="button"
              onClick={() => onSelect(label)}
              className="grid w-full grid-cols-[minmax(0,1fr)_auto] gap-3 px-4 py-4 text-left"
            >
              <span className="min-w-0">
                <span className="block text-[12px] font-semibold">
                  {label.stationAlias} · Round {label.reviewRound}
                </span>
                <span className="mt-1 block text-[10px] text-[var(--text-dim)]">
                  {formatFactoryTime(label.sourceStartAt, label.factoryTimezone)}
                </span>
                <span className="mt-3 flex flex-wrap gap-1.5">
                  {label.humanTotals.length ? label.humanTotals.map((human) => (
                    <span key={human.submissionId} className="inline-flex min-w-7 justify-center border border-[var(--border)] bg-[var(--panel-2)] px-2 py-1 text-[11px] font-semibold">
                      {humanSubmissionValue(human)}
                    </span>
                  )) : <span className="text-[11px] text-[var(--text-dim)]">No submissions</span>}
                </span>
              </span>
              <span className="flex flex-col items-end gap-2">
                <ToneBadge text={status.text} tone={status.tone as "good" | "bad" | "warn" | "muted" | "info"} />
                <ChevronRight className="h-4 w-4 text-[var(--text-dim)]" />
              </span>
            </button>
          );
        })}
        {!labels.length ? <EmptyRows icon={FileCheck2} text={compact ? "No human submissions yet" : "No label rounds match this view"} /> : null}
      </div>
      <div className="hidden overflow-x-auto md:block">
        <table className="w-full min-w-[760px] border-collapse text-left">
        <thead>
          <tr className="border-b border-[var(--border)] text-[10px] font-semibold uppercase text-[var(--text-dim)]">
            <th className="px-4 py-3">Footage</th>
            <th className="px-4 py-3">Round</th>
            <th className="px-4 py-3">Human totals</th>
            <th className="px-4 py-3">Truth status</th>
            <th className="px-4 py-3">AI</th>
            <th className="w-10 px-4 py-3"><span className="sr-only">Open</span></th>
          </tr>
        </thead>
        <tbody>
          {labels.map((label) => {
            const status = truthStatus(label);
            return (
              <tr
                key={`${label.chunkId}-${label.reviewRound}`}
                className="cursor-pointer border-b border-[var(--border)] hover:bg-[var(--panel)]"
                onClick={() => onSelect(label)}
              >
                <td className="px-4 py-3">
                  <div className="text-[12px] font-semibold">{label.stationAlias}</div>
                  <div className="mt-1 text-[10px] text-[var(--text-dim)]">{formatFactoryTime(label.sourceStartAt, label.factoryTimezone)}</div>
                </td>
                <td className="px-4 py-3 text-[12px]">{label.reviewRound}</td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap gap-1.5">
                    {label.humanTotals.length ? label.humanTotals.map((human) => (
                      <span key={human.submissionId} className="inline-flex min-w-7 justify-center border border-[var(--border)] bg-[var(--panel-2)] px-2 py-1 text-[11px] font-semibold">
                        {humanSubmissionValue(human)}
                      </span>
                    )) : <span className="text-[11px] text-[var(--text-dim)]">No submissions</span>}
                  </div>
                </td>
                <td className="px-4 py-3"><ToneBadge text={status.text} tone={status.tone as "good" | "bad" | "warn" | "muted" | "info"} /></td>
                <td className="px-4 py-3">
                  <ToneBadge
                    text={label.aiStatus === "not_run" ? "Not run" : label.aiStatus.replaceAll("_", " ")}
                    tone={label.aiStatus === "compared" ? "good" : label.aiStatus === "not_run" ? "muted" : "info"}
                  />
                </td>
                <td className="px-4 py-3"><ChevronRight className="h-4 w-4 text-[var(--text-dim)]" /></td>
              </tr>
            );
          })}
        </tbody>
        </table>
        {!labels.length ? <EmptyRows icon={FileCheck2} text={compact ? "No human submissions yet" : "No label rounds match this view"} /> : null}
      </div>
    </>
  );
}

function ReviewersView({
  roster,
  busy,
  onInvite,
  onState,
  onRevoke,
  onSupport,
}: {
  roster: RosterResponse;
  busy: boolean;
  onInvite: () => void;
  onState: (id: string, state: "suspended" | "offboarded") => Promise<void>;
  onRevoke: (id: string) => Promise<void>;
  onSupport: (id: string, state: "acknowledged" | "closed") => Promise<void>;
}) {
  return (
    <div className="p-4 md:p-6">
      {roster.supportRequests.length ? (
        <section className="mb-4 border border-[var(--border)]">
          <SectionHeading title="Worker support" meta={`${roster.supportRequests.length} request${roster.supportRequests.length === 1 ? "" : "s"}`} />
          <div className="grid divide-y divide-[var(--border)] lg:grid-cols-2 lg:divide-x lg:divide-y-0">
            {roster.supportRequests.map((request) => (
              <article key={request.id} className="p-5">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-[13px] font-semibold">{request.reviewerName}</div>
                    <div className="mt-1 text-[10px] text-[var(--text-dim)]">{request.factoryName} · {timeAgo(request.createdAt)}</div>
                  </div>
                  <ToneBadge text={request.status} tone={request.status === "open" ? "warn" : "muted"} />
                </div>
                <p className="mt-3 text-[12px] leading-5 text-[var(--text-mut)]">{request.message}</p>
                <div className="mt-4 flex gap-2">
                  {request.status === "open" ? (
                    <button type="button" disabled={busy} onClick={() => void onSupport(request.id, "acknowledged")} className="h-8 border border-[var(--border)] px-3 text-[11px] font-semibold">Acknowledge</button>
                  ) : null}
                  <button type="button" disabled={busy} onClick={() => void onSupport(request.id, "closed")} className="h-8 border border-[var(--border)] px-3 text-[11px] font-semibold">Close</button>
                </div>
              </article>
            ))}
          </div>
        </section>
      ) : null}

      <section className="border border-[var(--border)]">
        <SectionHeading
          title="Reviewer accounts"
          meta={`${roster.reviewers.length} total`}
          action={
            <button type="button" onClick={onInvite} className="inline-flex h-9 items-center gap-2 bg-[var(--accent)] px-3 text-[12px] font-semibold text-black">
              <Plus className="h-4 w-4" />
              Invite reviewer
            </button>
          }
        />
        <div className="overflow-x-auto">
          <table className="w-full min-w-[980px] border-collapse text-left">
            <thead>
              <tr className="border-b border-[var(--border)] text-[10px] font-semibold uppercase text-[var(--text-dim)]">
                <th className="px-4 py-3">Reviewer</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Security</th>
                <th className="px-4 py-3">Work</th>
                <th className="px-4 py-3">Last active</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {roster.reviewers.map((reviewer) => (
                <tr key={reviewer.userId} className="border-b border-[var(--border)] hover:bg-[var(--panel)]">
                  <td className="px-4 py-4">
                    <div className="text-[12px] font-semibold">{reviewer.displayName}</div>
                    <div className="mt-1 text-[10px] text-[var(--text-dim)]">{reviewer.email}</div>
                    <div className="mt-1 text-[10px] text-[var(--text-dim)]">{reviewer.factoryName}</div>
                  </td>
                  <td className="px-4 py-4"><ToneBadge text={stateLabel[reviewer.state]} tone={reviewer.state === "active" ? "good" : reviewer.state === "suspended" || reviewer.state === "offboarded" ? "bad" : "warn"} /></td>
                  <td className="px-4 py-4 text-[11px]">
                    <div className="flex items-center gap-1.5">
                      {reviewer.mfaVerifiedAt ? <Check className="h-3.5 w-3.5 text-[var(--good)]" /> : <X className="h-3.5 w-3.5 text-[var(--bad)]" />}
                      MFA
                    </div>
                    <div className={`mt-1 ${reviewer.countryCode ? "text-[var(--text-dim)]" : "text-[var(--warn)]"}`}>{reviewer.countryCode ?? "Country missing"}</div>
                  </td>
                  <td className="px-4 py-4 text-[11px]">
                    <div>{reviewer.submittedAssignments} submitted</div>
                    <div className="mt-1 text-[var(--text-dim)]">{reviewer.queuedAssignments} assigned</div>
                  </td>
                  <td className="px-4 py-4 text-[11px]">{timeAgo(reviewer.lastSeenAt)}</td>
                  <td className="px-4 py-4">
                    <div className="flex justify-end gap-1">
                      {reviewer.state === "invited" ? (
                        <button type="button" title="Revoke invitation" onClick={() => void onRevoke(reviewer.userId)} className="border border-[var(--border)] p-2 hover:border-[var(--bad)] hover:text-[var(--bad)]"><MailX className="h-4 w-4" /></button>
                      ) : null}
                      {reviewer.state === "active" ? (
                        <button type="button" title="Suspend reviewer" onClick={() => void onState(reviewer.userId, "suspended")} className="border border-[var(--border)] p-2 hover:border-[var(--warn)] hover:text-[var(--warn)]"><Pause className="h-4 w-4" /></button>
                      ) : null}
                      {!["offboarded", "invited"].includes(reviewer.state) ? (
                        <button type="button" title="Offboard reviewer" onClick={() => void onState(reviewer.userId, "offboarded")} className="border border-[var(--border)] p-2 hover:border-[var(--bad)] hover:text-[var(--bad)]"><UserRoundX className="h-4 w-4" /></button>
                      ) : null}
                      <button type="button" title="Reviewer details" className="border border-[var(--border)] p-2 text-[var(--text-dim)]" disabled><MoreHorizontal className="h-4 w-4" /></button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function AiView({
  labels,
  summary,
}: {
  labels: LabelRow[];
  summary: CommandCenter["summary"];
}) {
  const aiRows = labels.filter((label) => label.aiRunId);
  return (
    <div className="p-4 md:p-6">
      <section className="grid border border-[var(--border)] sm:grid-cols-3">
        {[
          ["AI runs", summary.aiRuns, Bot],
          ["Blind comparisons", summary.aiComparisons, Activity],
          ["Human finals", summary.resolvedChunks, ShieldCheck],
        ].map(([label, value, Icon], index) => {
          const MetricIcon = Icon as typeof Bot;
          return (
            <div key={String(label)} className={`p-5 ${index ? "border-t border-[var(--border)] sm:border-l sm:border-t-0" : ""}`}>
              <div className="flex items-center justify-between text-[10px] font-semibold uppercase tracking-[0.06em] text-[var(--text-dim)]">
                {String(label)}
                <MetricIcon className="h-4 w-4 text-[var(--accent)]" />
              </div>
              <div className="mt-3 text-[26px] font-semibold">{String(value)}</div>
            </div>
          );
        })}
      </section>
      <section className="mt-4 border border-[var(--border)]">
        <SectionHeading title="Comparison runs" meta="AI results remain blind until human finalization" />
        {aiRows.length ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[800px] border-collapse text-left">
              <thead>
                <tr className="border-b border-[var(--border)] text-[10px] font-semibold uppercase text-[var(--text-dim)]">
                  <th className="px-4 py-3">Footage</th>
                  <th className="px-4 py-3">Model</th>
                  <th className="px-4 py-3">Human final</th>
                  <th className="px-4 py-3">AI events</th>
                  <th className="px-4 py-3">Status</th>
                </tr>
              </thead>
              <tbody>
                {aiRows.map((label) => (
                  <tr key={`${label.chunkId}-${label.reviewRound}-${label.aiRunId}`} className="border-b border-[var(--border)]">
                    <td className="px-4 py-4"><div className="text-[12px] font-semibold">{label.stationAlias}</div><div className="mt-1 text-[10px] text-[var(--text-dim)]">Round {label.reviewRound}</div></td>
                    <td className="px-4 py-4 text-[11px]">{label.aiCodeVersion ?? "Unknown"}</td>
                    <td className="px-4 py-4 text-[12px]">{label.resolvedTotal ?? "Pending"}</td>
                    <td className="px-4 py-4 text-[12px]">{label.aiEventCount}</td>
                    <td className="px-4 py-4"><ToneBadge text={label.aiStatus.replaceAll("_", " ")} tone={label.aiStatus === "compared" ? "good" : "info"} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="flex min-h-64 flex-col items-center justify-center px-5 text-center">
            <div className="flex h-11 w-11 items-center justify-center border border-[var(--border)] bg-[var(--panel-2)] text-[var(--text-mut)]">
              <Bot className="h-5 w-5" />
            </div>
            <h3 className="mt-4 text-[14px] font-semibold">No AI runs ingested yet</h3>
            <div className="mt-2 text-[11px] text-[var(--text-dim)]">Human labels are still visible in Label output.</div>
          </div>
        )}
      </section>
    </div>
  );
}

function LabelDetail({ label, onClose }: { label: LabelRow; onClose: () => void }) {
  const status = truthStatus(label);
  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/70" role="dialog" aria-modal="true" aria-label="Label round details">
      <div className="h-full w-full max-w-[560px] overflow-y-auto border-l border-[var(--border)] bg-[var(--bg)]">
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-[var(--border)] bg-[var(--bg)] px-5 py-4">
          <div>
            <div className="text-[10px] font-semibold uppercase text-[var(--text-dim)]">Label lineage</div>
            <h2 className="mt-1 text-[18px] font-semibold">{label.stationAlias} · Round {label.reviewRound}</h2>
          </div>
          <button type="button" title="Close details" onClick={onClose} className="p-2"><X className="h-4 w-4" /></button>
        </div>
        <div className="p-5">
          <section className="border border-[var(--border)]">
            <SectionHeading title="Footage identity" />
            <dl className="grid grid-cols-2 gap-x-5 gap-y-4 p-5 text-[11px]">
              <div><dt className="text-[var(--text-dim)]">Factory</dt><dd className="mt-1">{label.factoryName}</dd></div>
              <div><dt className="text-[var(--text-dim)]">Station</dt><dd className="mt-1">{label.stationAlias}</dd></div>
              <div><dt className="text-[var(--text-dim)]">Start</dt><dd className="mt-1">{formatFactoryTime(label.sourceStartAt, label.factoryTimezone)}</dd></div>
              <div><dt className="text-[var(--text-dim)]">Duration</dt><dd className="mt-1">15 minutes</dd></div>
              <div className="col-span-2"><dt className="text-[var(--text-dim)]">Source SHA-256</dt><dd className="mt-1 break-all font-mono text-[10px]">{label.sourceSha256}</dd></div>
            </dl>
          </section>
          <section className="mt-4 border border-[var(--border)]">
            <SectionHeading title="Human submissions" meta={`${label.submissionCount}/3 received`} />
            {label.humanTotals.length ? (
              <div className="divide-y divide-[var(--border)]">
                {label.humanTotals.map((human) => (
                  <div key={human.submissionId} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-4 px-5 py-4">
                    <div>
                      <div className="text-[12px] font-semibold">{human.reviewerName}</div>
                      <div className="mt-1 text-[10px] text-[var(--text-dim)]">{timeAgo(human.submittedAt)}</div>
                    </div>
                    <div className="text-right">
                      <div className="text-[22px] font-semibold">{humanSubmissionValue(human)}</div>
                      <div className="text-[10px] text-[var(--text-dim)]">{human.resultType === "counted" ? "outputs" : human.problemCode}</div>
                    </div>
                  </div>
                ))}
              </div>
            ) : <EmptyRows icon={Users} text="No human submissions in this round" />}
          </section>
          <section className="mt-4 border border-[var(--border)]">
            <SectionHeading title="Ground truth" />
            <div className="grid grid-cols-2 gap-4 p-5">
              <div>
                <div className="text-[10px] text-[var(--text-dim)]">Status</div>
                <div className="mt-2"><ToneBadge text={status.text} tone={status.tone as "good" | "bad" | "warn" | "muted" | "info"} /></div>
              </div>
              <div>
                <div className="text-[10px] text-[var(--text-dim)]">Resolved total</div>
                <div className="mt-1 text-[22px] font-semibold">{label.resolvedTotal ?? "—"}</div>
              </div>
              <div>
                <div className="text-[10px] text-[var(--text-dim)]">Human support</div>
                <div className="mt-1 text-[13px]">
                  {label.supportCount
                    ? `${label.supportCount} of 3`
                    : label.consensusStatus === "no_majority"
                      ? "No matching majority"
                      : label.consensusStatus
                        ? "Not finalized"
                        : "Pending resolver"}
                </div>
              </div>
              <div>
                <div className="text-[10px] text-[var(--text-dim)]">Published events</div>
                <div className="mt-1 text-[13px]">{label.publicationCount}</div>
              </div>
            </div>
          </section>
          <section className="mt-4 border border-[var(--border)]">
            <SectionHeading title="AI comparison" />
            <div className="p-5">
              <ToneBadge text={label.aiStatus === "not_run" ? "Not run" : label.aiStatus.replaceAll("_", " ")} tone={label.aiStatus === "compared" ? "good" : label.aiStatus === "not_run" ? "muted" : "info"} />
              {label.aiRunId ? (
                <div className="mt-4 grid grid-cols-2 gap-4 text-[11px]">
                  <div><span className="block text-[var(--text-dim)]">Model version</span><span className="mt-1 block">{label.aiCodeVersion ?? "Unknown"}</span></div>
                  <div><span className="block text-[var(--text-dim)]">AI events</span><span className="mt-1 block">{label.aiEventCount}</span></div>
                </div>
              ) : null}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

function EmptyRows({ icon: Icon, text }: { icon: typeof ListChecks; text: string }) {
  return (
    <div className="flex min-h-40 items-center justify-center gap-2 px-5 text-[12px] text-[var(--text-mut)]">
      <Icon className="h-4 w-4" />
      {text}
    </div>
  );
}

function StatusNotice({ notice }: { notice: string }) {
  return (
    <div role="status" className="fixed bottom-5 right-5 z-[60] max-w-sm border border-[var(--border)] bg-[var(--panel)] px-4 py-3 text-[12px] shadow-xl">
      {notice}
    </div>
  );
}
