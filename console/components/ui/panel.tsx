import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export function Panel({
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <section
      className={cn(
        "rounded-[12px] border border-[var(--border)] bg-[linear-gradient(180deg,var(--panel),var(--panel-2))] p-6 shadow-[0_10px_28px_rgba(0,0,0,.42),inset_0_1px_0_rgba(255,255,255,.05)]",
        className,
      )}
      {...props}
    />
  );
}
