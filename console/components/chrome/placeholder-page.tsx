import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Panel } from "@/components/ui/panel";

export function PlaceholderPage({
  title,
  body,
  actionLabel,
  actionHref,
}: {
  title: string;
  body: string;
  actionLabel: string;
  actionHref: string;
}) {
  return (
    <Panel className="min-h-[320px]">
      <h1 className="text-[32px] font-semibold tracking-[-0.01em] text-[var(--text)]">
        {title}
      </h1>
      <p className="mt-3 max-w-2xl text-[14px] leading-6 text-[var(--text-mut)]">
        {body}
      </p>
      <Link
        href={actionHref}
        className="mt-6 inline-flex h-10 items-center gap-2 rounded-lg bg-[var(--accent)] px-4 text-[13px] font-semibold text-[#11100d] hover:bg-[var(--accent-hi)]"
      >
        {actionLabel}
        <ArrowRight className="h-4 w-4" strokeWidth={1.75} />
      </Link>
    </Panel>
  );
}
