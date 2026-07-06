"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  AlertTriangle,
  BriefcaseBusiness,
  ChevronDown,
  CircleHelp,
  Columns3,
  History,
  Menu,
  MonitorPlay,
  PanelLeftClose,
  Radio,
  Search,
  Settings,
} from "lucide-react";
import { RoleSwitcher } from "@/components/providers/role-switcher";
import { TimeProvider } from "@/components/providers/time-provider";
import { ClipDrawerProvider } from "@/components/live/clip-drawer-provider";
import { TrustLine } from "@/components/chrome/trust-line";
import { Wordmark } from "@/components/chrome/wordmark";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/", label: "Live", icon: Radio },
  { href: "/replay", label: "Replay", icon: MonitorPlay },
  { href: "/jobs", label: "Jobs", icon: BriefcaseBusiness },
  { href: "/stations", label: "Stations", icon: Columns3 },
  { href: "/history", label: "History", icon: History },
  { href: "/alerts", label: "Alerts", icon: AlertTriangle, badge: "3" },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function OwnerChrome({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <TimeProvider>
      <div className="min-h-screen bg-[var(--bg)] text-[var(--text)]">
        <aside className="fixed inset-y-0 left-0 z-20 flex w-[88px] flex-col border-r border-[var(--border-soft)] bg-[var(--bg-rail)]">
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
              const isActive =
                item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
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
                  {item.badge ? (
                    <span className="absolute right-2 top-2 min-w-4 rounded-full bg-[var(--bad)] px-1 text-center text-[10px] font-bold leading-4 text-white">
                      {item.badge}
                    </span>
                  ) : null}
                </Link>
              );
            })}
          </nav>
          <button
            type="button"
            className="mb-4 flex h-[58px] flex-col items-center justify-center gap-1 text-[11px] font-semibold text-[var(--text-dim)] hover:text-[var(--text)]"
          >
            <PanelLeftClose className="h-5 w-5" strokeWidth={1.75} />
            Collapse
          </button>
        </aside>

        <div className="flex min-h-screen flex-col pl-[88px]">
          <header className="sticky top-0 z-10 flex h-16 items-center justify-between border-b border-[var(--border-soft)] bg-[rgba(12,14,16,.94)] px-6 backdrop-blur">
            <div className="flex items-center gap-4">
              <button
                type="button"
                className="flex h-9 w-9 items-center justify-center rounded-lg border border-[var(--border)] text-[var(--text-mut)] lg:hidden"
                aria-label="Open navigation"
              >
                <Menu className="h-4 w-4" strokeWidth={1.75} />
              </button>
              <Wordmark />
            </div>

            <div className="flex items-center gap-3">
              <div className="hidden h-9 min-w-[280px] items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--panel-2)] px-3 text-[13px] text-[var(--text-dim)] md:flex">
                <Search className="h-4 w-4" strokeWidth={1.75} />
                <span className="flex-1">Search jobs, stations, times</span>
                <span className="rounded border border-[var(--border)] px-1.5 py-0.5 text-[11px]">
                  ⌘K
                </span>
              </div>
              <RoleSwitcher />
              <button
                type="button"
                className="flex h-9 items-center gap-2 rounded-full border border-[var(--border)] bg-[var(--panel-2)] px-3 text-[13px] font-semibold"
              >
                <span className="h-2 w-2 rounded-full bg-[var(--good)] shadow-[0_0_12px_rgba(70,194,107,.7)]" />
                Live
                <ChevronDown className="h-4 w-4 text-[var(--text-dim)]" strokeWidth={1.75} />
              </button>
              <button
                type="button"
                className="flex h-9 w-9 items-center justify-center rounded-lg border border-[var(--border)] text-[var(--text-mut)]"
                aria-label="Help"
              >
                <CircleHelp className="h-4 w-4" strokeWidth={1.75} />
              </button>
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[var(--panel)] text-[12px] font-bold text-[var(--text)] ring-1 ring-[var(--border)]">
                TB
              </div>
            </div>
          </header>

          <ClipDrawerProvider>
            <main className="mx-auto flex w-full max-w-[1440px] flex-1 flex-col px-6 py-6">
              <div className="flex-1">{children}</div>
            </main>
            <TrustLine />
          </ClipDrawerProvider>
        </div>
      </div>
    </TimeProvider>
  );
}
