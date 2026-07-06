import { Panel } from "@/components/ui/panel";

export default function TvPage() {
  return (
    <main className="min-h-screen bg-[var(--bg)] p-6 text-[var(--text)]">
      <Panel className="flex min-h-[calc(100vh-48px)] items-center justify-center">
        <h1 className="text-[64px] font-semibold tracking-[-0.01em]">TV</h1>
      </Panel>
    </main>
  );
}
