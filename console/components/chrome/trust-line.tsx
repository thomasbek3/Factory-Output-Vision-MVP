import { ShieldCheck } from "lucide-react";

export function TrustLine() {
  return (
    <div className="flex items-center gap-2 border-t border-[var(--border-soft)] px-6 py-4 text-[12px] text-[var(--text-dim)]">
      <ShieldCheck className="h-4 w-4 text-[var(--good)]" strokeWidth={1.75} />
      <span>Every count verified by a person, live.</span>
    </div>
  );
}
