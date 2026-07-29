"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  AlertTriangle,
  Factory,
  FolderKanban,
  History,
  LayoutDashboard,
  LogOut,
  MoreHorizontal,
  Settings,
  Users,
  Workflow,
} from "lucide-react";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { signOutOwner } from "@/lib/ownerClient";

type FactorySummary = {
  id?: string;
  name?: string;
};

export type OwnerSurfaceStatus =
  | "preview"
  | "connected"
  | "delayed"
  | "unavailable";

const OwnerStatusContext = createContext<
  ((status: OwnerSurfaceStatus) => void) | null
>(null);

export function useOwnerSurfaceStatus(status: OwnerSurfaceStatus) {
  const reportStatus = useContext(OwnerStatusContext);
  useEffect(() => {
    reportStatus?.(status);
  }, [reportStatus, status]);
}

const statusAppearance: Record<
  OwnerSurfaceStatus,
  { label: string; container: string; dot: string }
> = {
  preview: {
    label: "Preview data",
    container: "border-accent/40 bg-accent-tint text-accent",
    dot: "bg-accent",
  },
  connected: {
    label: "Connected",
    container: "border-border text-text-mut",
    dot: "bg-text-mut",
  },
  delayed: {
    label: "Data delayed",
    container: "border-warn/40 bg-warn-tint text-warn",
    dot: "bg-warn",
  },
  unavailable: {
    label: "Data unavailable",
    container: "border-bad/40 bg-bad-tint text-bad",
    dot: "bg-bad",
  },
};

const navigation = [
  { href: "/", label: "Today", icon: LayoutDashboard },
  { href: "/projects", label: "Projects", icon: FolderKanban },
  { href: "/stations", label: "Stations", icon: Workflow },
  { href: "/workforce", label: "Workforce", icon: Users },
  { href: "/history", label: "History", icon: History },
  { href: "/alerts", label: "Alerts", icon: AlertTriangle },
  { href: "/settings", label: "Settings", icon: Settings },
] as const;

const previewNavigation: Record<(typeof navigation)[number]["href"], string> = {
  "/": "/owner-preview",
  "/projects": "/owner-preview/projects",
  "/stations": "/owner-preview/stations",
  "/workforce": "/owner-preview/workforce",
  "/history": "/owner-preview/history",
  "/alerts": "/owner-preview/alerts",
  "/settings": "/owner-preview/settings",
};

export function OwnerShell({
  children,
  factories,
  preview = false,
  status,
}: {
  children: React.ReactNode;
  factories: FactorySummary[];
  preview?: boolean;
  status?: OwnerSurfaceStatus;
}) {
  const pathname = usePathname();
  const [signOutError, setSignOutError] = useState("");
  const [signingOut, setSigningOut] = useState(false);
  const [mobileMoreOpen, setMobileMoreOpen] = useState(false);
  const baseStatus = status ?? (preview ? "preview" : "connected");
  const [surfaceStatus, setSurfaceStatus] =
    useState<OwnerSurfaceStatus>(baseStatus);
  useEffect(() => {
    setSurfaceStatus(baseStatus);
  }, [baseStatus, pathname]);
  const reportStatus = useCallback(
    (nextStatus: OwnerSurfaceStatus) => {
      if (preview && status === undefined) return;
      setSurfaceStatus(nextStatus);
    },
    [preview, status],
  );
  const appearance = statusAppearance[surfaceStatus];

  async function signOut() {
    setSigningOut(true);
    setSignOutError("");
    try {
      const response = await signOutOwner();
      if (!response.ok) {
        setSignOutError("Sign out failed. Your session is still active.");
        return;
      }
      window.location.replace("/sign-in");
    } catch {
      setSignOutError("Sign out failed. Your session is still active.");
    } finally {
      setSigningOut(false);
    }
  }

  return (
    <OwnerStatusContext.Provider value={reportStatus}>
    <div className="min-h-screen bg-bg text-text">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-[88px] border-r border-border bg-bg-rail lg:flex lg:flex-col">
        <Link
          href={preview ? "/owner-preview" : "/"}
          aria-label="FactoryVision Today"
          className="grid h-16 place-items-center border-b border-border text-accent"
        >
          <Factory size={25} strokeWidth={1.8} aria-hidden="true" />
        </Link>
        <nav className="flex flex-1 flex-col py-2" aria-label="Owner navigation">
          {navigation.map((item) => {
            const href = preview ? previewNavigation[item.href] : item.href;
            const active = preview
              ? pathname === previewNavigation[item.href]
              : item.href === "/"
                ? pathname === "/"
                : pathname === item.href || pathname.startsWith(`${item.href}/`);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={href}
                aria-current={active ? "page" : undefined}
                data-owner-nav-active={active ? "true" : undefined}
                className={`relative flex h-[72px] flex-col items-center justify-center gap-1 text-[11px] ${
                  active ? "bg-panel text-accent" : "text-text-mut hover:text-text"
                }`}
              >
                {active ? (
                  <span className="absolute inset-y-0 left-0 w-[3px] bg-accent" />
                ) : null}
                <Icon size={21} strokeWidth={1.65} aria-hidden="true" />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>
      </aside>

      <div className="min-h-screen lg:pl-[88px]">
        <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-border bg-bg/95 px-4 backdrop-blur sm:px-6 lg:pr-[150px]">
          <Link
            href={preview ? "/owner-preview" : "/"}
            className="flex min-h-11 items-center gap-2 text-lg font-semibold lg:min-h-0"
          >
            <Factory
              size={21}
              strokeWidth={1.8}
              className="text-accent lg:hidden"
              aria-hidden="true"
            />
            <span>Factory<span className="text-accent">Vision</span></span>
          </Link>
          <div className="flex items-center gap-3">
            <span
              className={`inline-flex h-7 items-center gap-2 border px-2.5 text-[11px] font-medium ${appearance.container}`}
              data-owner-surface-status={surfaceStatus}
            >
              <span className={`size-2 rounded-full ${appearance.dot}`} />
              {appearance.label}
            </span>
            <span className="hidden text-xs text-text-mut sm:inline">
              {factories.length === 1
                ? factories[0]?.name ?? "Factory workspace"
                : `${factories.length} factories`}
            </span>
            {!preview ? (
              <button
                type="button"
                onClick={() => void signOut()}
                disabled={signingOut}
                title="Sign out"
                aria-label="Sign out"
                className="grid size-11 place-items-center border border-border text-text-mut hover:text-text disabled:cursor-wait disabled:opacity-60 lg:size-9"
              >
                <LogOut size={16} strokeWidth={1.7} aria-hidden="true" />
              </button>
            ) : null}
          </div>
          {signOutError ? (
            <p
              role="alert"
              className="absolute right-4 top-[58px] border border-bad/50 bg-bg px-3 py-2 text-xs text-bad"
            >
              {signOutError}
            </p>
          ) : null}
        </header>
        <main className="mx-auto w-full max-w-[1536px] px-3 pb-24 pt-3 sm:px-4 lg:pb-4 lg:pt-0">
          {children}
        </main>
      </div>
      {mobileMoreOpen ? (
        <div className="fixed inset-x-0 bottom-16 z-30 border-t border-border bg-bg p-2 shadow-2xl lg:hidden">
          {navigation.slice(5).map((item) => {
            const href = preview ? previewNavigation[item.href] : item.href;
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={href}
                aria-current={
                  pathname === href ? "page" : undefined
                }
                onClick={() => setMobileMoreOpen(false)}
                className="flex h-12 items-center gap-3 border-b border-border px-3 text-sm text-text-mut last:border-b-0 hover:text-text"
              >
                <Icon size={18} aria-hidden="true" />
                {item.label}
              </Link>
            );
          })}
        </div>
      ) : null}
      <nav
        className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-6 border-t border-border bg-bg lg:hidden"
        aria-label="Owner mobile navigation"
      >
        {navigation.slice(0, 5).map((item) => {
          const href = preview ? previewNavigation[item.href] : item.href;
          const active = preview
            ? pathname === previewNavigation[item.href]
            : item.href === "/"
              ? pathname === "/"
              : pathname === item.href || pathname.startsWith(`${item.href}/`);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={href}
              aria-current={active ? "page" : undefined}
              data-owner-nav-active={active ? "true" : undefined}
              className={`flex h-16 flex-col items-center justify-center gap-1 text-[10px] ${
                active ? "text-accent" : "text-text-mut"
              }`}
            >
              <Icon size={19} strokeWidth={1.7} aria-hidden="true" />
              {item.label}
            </Link>
          );
        })}
        <button
          type="button"
          onClick={() => setMobileMoreOpen((current) => !current)}
          aria-expanded={mobileMoreOpen}
          className={`flex h-16 flex-col items-center justify-center gap-1 text-[10px] ${
            mobileMoreOpen
            || ["/alerts", "/settings"].some((href) =>
              preview
                ? pathname === previewNavigation[href as "/alerts" | "/settings"]
                : pathname === href,
            )
              ? "text-accent"
              : "text-text-mut"
          }`}
        >
          <MoreHorizontal size={19} strokeWidth={1.7} aria-hidden="true" />
          More
        </button>
      </nav>
    </div>
    </OwnerStatusContext.Provider>
  );
}
