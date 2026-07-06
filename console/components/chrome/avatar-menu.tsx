"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Check, LogOut, UserCog } from "lucide-react";
import { cn } from "@/lib/utils";

type Role = "owner" | "reviewer" | "ops";

const roles: { id: Role; label: string; blurb: string; href: string }[] = [
  { id: "owner", label: "Owner", blurb: "The full console", href: "/" },
  { id: "reviewer", label: "Reviewer", blurb: "Counting station", href: "/review" },
  { id: "ops", label: "Ops", blurb: "Internal dashboard", href: "/ops" },
];

const ROLE_KEY = "factoryvision-role";

function readRole(): Role {
  if (typeof window === "undefined") return "owner";
  const saved = window.localStorage.getItem(ROLE_KEY);
  return saved === "reviewer" || saved === "ops" ? saved : "owner";
}

export function AvatarMenu() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [role, setRole] = useState<Role>("owner");
  const rootRef = useRef<HTMLDivElement | null>(null);

  function toggle() {
    setOpen((value) => {
      const next = !value;
      if (next) setRole(readRole());
      return next;
    });
  }

  useEffect(() => {
    if (!open) return;
    const onClick = (event: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("mousedown", onClick);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("mousedown", onClick);
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  function chooseRole(next: Role, href: string) {
    setRole(next);
    window.localStorage.setItem(ROLE_KEY, next);
    setOpen(false);
    router.push(href);
  }

  return (
    <div className="relative" ref={rootRef}>
      <button
        type="button"
        aria-label="Account menu"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={toggle}
        className="flex h-9 w-9 items-center justify-center rounded-full bg-[var(--panel)] text-[12px] font-bold text-[var(--text)] ring-1 ring-[var(--border)] hover:ring-[var(--border-soft)]"
      >
        TB
      </button>
      {open ? (
        <div
          role="menu"
          className="absolute right-0 top-11 z-[60] w-64 overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--panel)] p-1.5 shadow-[0_20px_60px_rgba(0,0,0,.6)]"
        >
          <div className="px-3 py-2">
            <div className="text-[13px] font-semibold text-[var(--text)]">Thomas Bekkers</div>
            <div className="text-[11px] text-[var(--text-dim)]">Apollo Getaways · owner</div>
          </div>
          <div className="my-1 border-t border-[var(--border-soft)]" />
          <div className="flex items-center gap-2 px-3 pb-1 pt-1.5 text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--text-dim)]">
            <UserCog className="h-3.5 w-3.5" strokeWidth={1.75} />
            View as
          </div>
          {roles.map((item) => (
            <button
              key={item.id}
              type="button"
              role="menuitemradio"
              aria-checked={role === item.id}
              onClick={() => chooseRole(item.id, item.href)}
              className={cn(
                "flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-[13px] transition-colors hover:bg-white/[.04]",
                role === item.id ? "text-[var(--text)]" : "text-[var(--text-mut)]",
              )}
            >
              <span className="flex-1">
                <span className="font-semibold text-[var(--text)]">{item.label}</span>
                <span className="ml-2 text-[11px] text-[var(--text-dim)]">{item.blurb}</span>
              </span>
              {role === item.id ? (
                <Check className="h-4 w-4 text-[var(--accent)]" strokeWidth={2} />
              ) : null}
            </button>
          ))}
          <div className="my-1 border-t border-[var(--border-soft)]" />
          <button
            type="button"
            role="menuitem"
            disabled
            className="flex w-full cursor-not-allowed items-center gap-2 rounded-lg px-3 py-2 text-left text-[13px] text-[var(--text-dim)] opacity-60"
          >
            <LogOut className="h-4 w-4" strokeWidth={1.75} />
            Sign out (soon)
          </button>
        </div>
      ) : null}
    </div>
  );
}
