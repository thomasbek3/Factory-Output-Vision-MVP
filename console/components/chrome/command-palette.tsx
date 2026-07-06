"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  BriefcaseBusiness,
  Clock,
  Columns3,
  History,
  MonitorPlay,
  Radio,
  Search,
  Settings,
} from "lucide-react";
import { jobs as seedJobs, stations } from "@/lib/demoData";
import { cn } from "@/lib/utils";

type Command = {
  id: string;
  label: string;
  hint: string;
  icon: typeof Radio;
  keywords: string;
  run: (router: ReturnType<typeof useRouter>) => void;
};

const navCommands: Command[] = [
  { id: "nav-live", label: "Live", hint: "Camera wall", icon: Radio, keywords: "live cameras home", run: (r) => r.push("/") },
  { id: "nav-replay", label: "Replay", hint: "The tapes", icon: MonitorPlay, keywords: "replay tapes footage video", run: (r) => r.push("/replay") },
  { id: "nav-jobs", label: "Jobs", hint: "Active work", icon: BriefcaseBusiness, keywords: "jobs projects clients", run: (r) => r.push("/jobs") },
  { id: "nav-stations", label: "Stations", hint: "Per-station", icon: Columns3, keywords: "stations", run: (r) => r.push("/stations") },
  { id: "nav-history", label: "History", hint: "Money records", icon: History, keywords: "history records finished", run: (r) => r.push("/history") },
  { id: "nav-alerts", label: "Alerts", hint: "Open alerts", icon: AlertTriangle, keywords: "alerts warnings", run: (r) => r.push("/alerts") },
  { id: "nav-settings", label: "Settings", hint: "Preferences", icon: Settings, keywords: "settings", run: (r) => r.push("/settings") },
];

const jobCommands: Command[] = seedJobs.map((job) => ({
  id: `job-${job.id}`,
  label: job.client,
  hint: "Open on Jobs",
  icon: BriefcaseBusiness,
  keywords: `job ${job.client} ${job.id}`,
  run: (r) => r.push("/jobs"),
}));

const stationCommands: Command[] = stations.map((station) => ({
  id: `station-${station.id}`,
  label: station.name,
  hint: "Watch on Replay",
  icon: MonitorPlay,
  keywords: `station ${station.name} ${station.id} replay`,
  run: (r) => r.push(`/replay?station=${station.id}`),
}));

/** "jump to time on Replay" — parse a bare HH:MM from the query. */
function timeCommand(query: string): Command | null {
  const match = query.trim().match(/^(\d{1,2}):(\d{2})$/);
  if (!match) return null;
  const hh = Number(match[1]);
  const mm = Number(match[2]);
  if (hh > 23 || mm > 59) return null;
  const clock = `${String(hh).padStart(2, "0")}:${match[2]}`;
  return {
    id: "jump-time",
    label: `Jump to ${clock} on Replay`,
    hint: "Scrub the day",
    icon: Clock,
    keywords: "time jump replay",
    run: (r) => r.push(`/replay?t=${encodeURIComponent(clock)}`),
  };
}

const baseCommands = [...navCommands, ...jobCommands, ...stationCommands];

export function CommandPalette() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);

  function changeOpen(next: boolean) {
    setOpen(next);
    if (!next) {
      setQuery("");
      setActive(0);
    }
  }

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen((value) => {
          if (value) {
            setQuery("");
            setActive(0);
          }
          return !value;
        });
      }
    };
    const onOpen = () => setOpen(true);
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("factoryvision:open-command-palette", onOpen);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("factoryvision:open-command-palette", onOpen);
    };
  }, []);

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    const time = timeCommand(query);
    const filtered = q
      ? baseCommands.filter(
          (command) =>
            command.label.toLowerCase().includes(q) || command.keywords.toLowerCase().includes(q),
        )
      : navCommands;
    return time ? [time, ...filtered] : filtered;
  }, [query]);

  function runCommand(command: Command) {
    changeOpen(false);
    command.run(router);
  }

  return (
    <Dialog.Root open={open} onOpenChange={changeOpen}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-[70] bg-black/50 backdrop-blur-[2px]" />
        <Dialog.Content
          aria-describedby={undefined}
          className="fixed left-1/2 top-[18vh] z-[71] w-[92vw] max-w-[560px] -translate-x-1/2 overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--panel)] shadow-[0_24px_70px_rgba(0,0,0,.7)] outline-none"
          onKeyDown={(event) => {
            if (event.key === "ArrowDown") {
              event.preventDefault();
              setActive((index) => Math.min(index + 1, results.length - 1));
            } else if (event.key === "ArrowUp") {
              event.preventDefault();
              setActive((index) => Math.max(index - 1, 0));
            } else if (event.key === "Enter") {
              event.preventDefault();
              const command = results[active];
              if (command) runCommand(command);
            }
          }}
        >
          <Dialog.Title className="sr-only">Command palette</Dialog.Title>
          <div className="flex items-center gap-3 border-b border-[var(--border-soft)] px-4">
            <Search className="h-4 w-4 text-[var(--text-dim)]" strokeWidth={1.75} />
            <input
              autoFocus
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                setActive(0);
              }}
              placeholder="Search jobs, stations, times…"
              aria-label="Command search"
              className="h-12 flex-1 bg-transparent text-[14px] text-[var(--text)] outline-none placeholder:text-[var(--text-dim)]"
            />
            <span className="rounded border border-[var(--border)] px-1.5 py-0.5 text-[11px] text-[var(--text-dim)]">
              Esc
            </span>
          </div>
          <div className="max-h-[46vh] overflow-y-auto p-2">
            {results.length === 0 ? (
              <div className="px-3 py-6 text-center text-[13px] text-[var(--text-dim)]">
                No matches.
              </div>
            ) : (
              results.map((command, index) => {
                const Icon = command.icon;
                return (
                  <button
                    key={command.id}
                    type="button"
                    data-command={command.id}
                    className={cn(
                      "flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-[13px] transition-colors",
                      index === active
                        ? "bg-white/[.06] text-[var(--text)]"
                        : "text-[var(--text-mut)] hover:bg-white/[.03]",
                    )}
                    onMouseEnter={() => setActive(index)}
                    onClick={() => runCommand(command)}
                  >
                    <Icon className="h-4 w-4 text-[var(--text-dim)]" strokeWidth={1.75} />
                    <span className="flex-1 font-semibold text-[var(--text)]">{command.label}</span>
                    <span className="text-[11px] text-[var(--text-dim)]">{command.hint}</span>
                  </button>
                );
              })
            )}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
