"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { EyeOff, ListVideo, MonitorPlay, MoreHorizontal } from "lucide-react";
import { useClipDrawer } from "@/components/live/clip-drawer-provider";

export function CameraTileMenu({
  stationId,
  stationName,
  latestClipId,
  onHide,
}: {
  stationId: string;
  stationName: string;
  latestClipId?: string;
  onHide: () => void;
}) {
  const router = useRouter();
  const { openClip } = useClipDrawer();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const onClick = (event: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) setOpen(false);
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

  return (
    <div className="relative" ref={rootRef}>
      <button
        type="button"
        aria-label={`${stationName} menu`}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        className="flex h-8 w-8 items-center justify-center rounded-lg text-[var(--text-dim)] hover:bg-white/[.04] hover:text-[var(--text)]"
      >
        <MoreHorizontal className="h-4 w-4" strokeWidth={1.75} />
      </button>
      {open ? (
        <div
          role="menu"
          className="absolute right-0 top-9 z-30 w-52 overflow-hidden rounded-lg border border-[var(--border)] bg-[var(--panel)] p-1 shadow-[0_18px_42px_rgba(0,0,0,.55)]"
        >
          <MenuItem
            icon={MonitorPlay}
            label="Open in Replay"
            onClick={() => {
              setOpen(false);
              router.push(`/replay?station=${stationId}`);
            }}
          />
          <MenuItem
            icon={ListVideo}
            label="View events today"
            disabled={!latestClipId}
            onClick={() => {
              setOpen(false);
              if (latestClipId) openClip(latestClipId);
            }}
          />
          <MenuItem
            icon={EyeOff}
            label="Hide tile"
            onClick={() => {
              setOpen(false);
              onHide();
            }}
          />
        </div>
      ) : null}
    </div>
  );
}

function MenuItem({
  icon: Icon,
  label,
  onClick,
  disabled,
}: {
  icon: typeof MonitorPlay;
  label: string;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="menuitem"
      disabled={disabled}
      onClick={onClick}
      className="flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left text-[13px] font-medium text-[var(--text-mut)] transition-colors hover:bg-white/[.04] hover:text-[var(--text)] disabled:cursor-not-allowed disabled:opacity-50"
    >
      <Icon className="h-4 w-4" strokeWidth={1.75} />
      {label}
    </button>
  );
}
