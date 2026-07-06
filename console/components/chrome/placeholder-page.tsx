import { Panel } from "@/components/ui/panel";

export function PlaceholderPage({ title }: { title: string }) {
  return (
    <Panel className="min-h-[320px]">
      <div className="mb-4 text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--text-dim)]">
        Console tab
      </div>
      <h1 className="text-[32px] font-semibold tracking-[-0.01em] text-[var(--text)]">
        {title}
      </h1>
      <p className="mt-3 max-w-2xl text-[14px] leading-6 text-[var(--text-mut)]">
        This checkpoint proves the FactoryVision shell, locked design tokens, role
        switcher, data spine, and demo-time engine. The next checkpoint fills this
        panel with live counting surfaces.
      </p>
    </Panel>
  );
}
