import { Panel } from "@/components/ui/panel";

export default function ReviewPage() {
  return (
    <main className="min-h-screen bg-[var(--bg)] p-6 text-[var(--text)]">
      <Panel>
        <div className="text-[11px] font-semibold uppercase tracking-[0.06em] text-[var(--text-dim)]">
          Reviewer console
        </div>
        <h1 className="mt-4 text-[32px] font-semibold">Review</h1>
      </Panel>
    </main>
  );
}
