"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
  AlertTriangle,
  BriefcaseBusiness,
  CircleHelp,
  Columns3,
  History,
  Menu,
  MonitorPlay,
  Radio,
  Search,
  Settings,
  X,
} from "lucide-react";
import { TimeProvider } from "@/components/providers/time-provider";
import { useTime } from "@/components/providers/time-provider";
import { ClipDrawerProvider } from "@/components/live/clip-drawer-provider";
import { ToastProvider } from "@/components/providers/toast-provider";
import { CommandPalette } from "@/components/chrome/command-palette";
import { HelpSheet } from "@/components/chrome/help-sheet";
import { AvatarMenu } from "@/components/chrome/avatar-menu";
import { TrustLine } from "@/components/chrome/trust-line";
import { Wordmark } from "@/components/chrome/wordmark";
import { useConsoleJobs } from "@/components/jobs/use-console-jobs";
import { evaluateDemoAlerts, openAlertCount } from "@/lib/alerts";
import { selectRunningJobSnapshots } from "@/lib/jobSelectors";
import { cn } from "@/lib/utils";

const resolvedAlertStorageKey = "factoryvision.resolvedAlertIds";

const baseNavItems = [
  { href: "/", label: "Live", icon: Radio },
  { href: "/replay", label: "Replay", icon: MonitorPlay },
  { href: "/jobs", label: "Jobs", icon: BriefcaseBusiness },
  { href: "/stations", label: "Stations", icon: Columns3 },
  { href: "/history", label: "History", icon: History },
  { href: "/alerts", label: "Alerts", icon: AlertTriangle },
  { href: "/settings", label: "Settings", icon: Settings },
];

function readResolvedAlertIds() {
  if (typeof window === "undefined") return new Set<string>();
  try {
    const value = window.localStorage.getItem(resolvedAlertStorageKey);
    return new Set(value ? (JSON.parse(value) as string[]) : []);
  } catch {
    return new Set<string>();
  }
}

function useNavItems() {
  const { now } = useTime();
  const { jobs } = useConsoleJobs();
  const [resolvedIds, setResolvedIds] = useState<Set<string>>(new Set());
  const alerts = evaluateDemoAlerts(now(), selectRunningJobSnapshots(now(), jobs));
  const alertCount = openAlertCount(alerts, resolvedIds);

  useEffect(() => {
    const sync = () => setResolvedIds(readResolvedAlertIds());
    sync();
    window.addEventListener("storage", sync);
    window.addEventListener("factoryvision:alerts-resolved", sync);
    return () => {
      window.removeEventListener("storage", sync);
      window.removeEventListener("factoryvision:alerts-resolved", sync);
    };
  }, []);

  return baseNavItems.map((item) =>
    item.href === "/alerts" && alertCount > 0 ? { ...item, badge: String(alertCount) } : item,
  );
}

function isActivePath(pathname: string, href: string) {
  return href === "/" ? pathname === "/" : pathname.startsWith(href);
}

function NavRail() {
  const pathname = usePathname();
  const navItems = useNavItems();

  return (
    <aside className="fixed inset-y-0 left-0 z-20 hidden w-[88px] flex-col border-r border-[var(--border-soft)] bg-[var(--bg-rail)] lg:flex">
      <Link
        href="/"
        aria-label="FactoryVision live"
        className="flex h-16 items-center justify-center border-b border-[var(--border-soft)]"
      >
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--accent)] text-[18px] font-bold text-[#11100d]">
          F
        </div>
      </Link>
      <nav className="flex flex-1 flex-col items-stretch gap-1 px-2 py-4">
        {navItems.map((item) => {
          const isActive = isActivePath(pathname, item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "relative flex h-[64px] flex-col items-center justify-center gap-1 rounded-lg text-[11px] font-semibold text-[var(--text-dim)] transition-colors hover:bg-white/[.03] hover:text-[var(--text)]",
                isActive && "text-[var(--accent)]",
              )}
            >
              {isActive ? (
                <span className="absolute left-[-8px] top-3 h-10 w-1 rounded-r-full bg-[var(--accent)]" />
              ) : null}
              <Icon className="h-5 w-5" strokeWidth={1.75} />
              <span>{item.label}</span>
              {"badge" in item && item.badge ? (
                <span className="absolute right-2 top-2 min-w-4 rounded-full bg-[var(--bad)] px-1 text-center text-[10px] font-bold leading-4 text-white">
                  {item.badge}
                </span>
              ) : null}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}

function MobileNav({ open, onClose }: { open: boolean; onClose: () => void }) {
  const pathname = usePathname();
  const navItems = useNavItems();

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-label="Navigation">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-[2px]" onClick={onClose} />
      <div className="absolute inset-y-0 left-0 flex w-[260px] flex-col border-r border-[var(--border)] bg-[var(--bg-rail)] p-3">
        <div className="mb-4 flex items-center justify-between px-2 pt-1">
          <Wordmark />
          <button
            type="button"
            aria-label="Close navigation"
            onClick={onClose}
            className="flex h-9 w-9 items-center justify-center rounded-lg border border-[var(--border)] text-[var(--text-mut)]"
          >
            <X className="h-4 w-4" strokeWidth={1.75} />
          </button>
        </div>
        <nav className="flex flex-col gap-1">
          {navItems.map((item) => {
            const isActive = isActivePath(pathname, item.href);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={onClose}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2.5 text-[14px] font-semibold text-[var(--text-mut)] hover:bg-white/[.04]",
                  isActive && "bg-white/[.04] text-[var(--accent)]",
                )}
              >
                <Icon className="h-5 w-5" strokeWidth={1.75} />
                <span className="flex-1">{item.label}</span>
                {"badge" in item && item.badge ? (
                  <span className="min-w-5 rounded-full bg-[var(--bad)] px-1.5 text-center text-[11px] font-bold leading-5 text-white">
                    {item.badge}
                  </span>
                ) : null}
              </Link>
            );
          })}
        </nav>
      </div>
    </div>
  );
}

function dispatch(name: string) {
  window.dispatchEvent(new Event(name));
}

export function OwnerChrome({ children }: { children: React.ReactNode }) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  return (
    <TimeProvider>
      <div className="min-h-screen bg-[var(--bg)] text-[var(--text)]">
        <NavRail />
        <MobileNav open={mobileNavOpen} onClose={() => setMobileNavOpen(false)} />
        <CommandPalette />
        <HelpSheet />

        <div className="flex min-h-screen flex-col lg:pl-[88px]">
          <header className="sticky top-0 z-10 flex h-16 items-center justify-between border-b border-[var(--border-soft)] bg-[rgba(12,14,16,.94)] px-4 backdrop-blur sm:px-6">
            <div className="flex items-center gap-4">
              <button
                type="button"
                onClick={() => setMobileNavOpen(true)}
                className="flex h-9 w-9 items-center justify-center rounded-lg border border-[var(--border)] text-[var(--text-mut)] lg:hidden"
                aria-label="Open navigation"
              >
                <Menu className="h-4 w-4" strokeWidth={1.75} />
              </button>
              <Wordmark />
            </div>

            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => dispatch("factoryvision:open-command-palette")}
                aria-label="Search"
                className="hidden h-9 min-w-[280px] items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--panel-2)] px-3 text-[13px] text-[var(--text-dim)] hover:border-[var(--border-soft)] md:flex"
              >
                <Search className="h-4 w-4" strokeWidth={1.75} />
                <span className="flex-1 text-left">Search jobs, stations, times</span>
                <span className="rounded border border-[var(--border)] px-1.5 py-0.5 text-[11px]">
                  ⌘K
                </span>
              </button>
              <span
                title="All cameras connected"
                className="flex h-9 items-center gap-2 rounded-full border border-[var(--border)] bg-[var(--panel-2)] px-3 text-[13px] font-semibold"
              >
                <span className="h-2 w-2 rounded-full bg-[var(--good)] shadow-[0_0_12px_rgba(70,194,107,.7)]" />
                Live
              </span>
              <button
                type="button"
                onClick={() => dispatch("factoryvision:open-help")}
                className="flex h-9 w-9 items-center justify-center rounded-lg border border-[var(--border)] text-[var(--text-mut)] hover:bg-white/[.04] hover:text-[var(--text)]"
                aria-label="Help"
              >
                <CircleHelp className="h-4 w-4" strokeWidth={1.75} />
              </button>
              <AvatarMenu />
            </div>
          </header>

          <ToastProvider>
            <ClipDrawerProvider>
              <main className="mx-auto flex w-full max-w-[1440px] flex-1 flex-col px-4 py-6 sm:px-6">
                <div className="flex-1">{children}</div>
              </main>
              <TrustLine />
            </ClipDrawerProvider>
          </ToastProvider>
        </div>
      </div>
    </TimeProvider>
  );
}
