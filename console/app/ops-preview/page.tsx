import { Radio } from "lucide-react";

export default function OpsPreviewPage() {
  return (
    <main className="min-h-screen bg-bg p-6 text-text">
      <div className="mx-auto max-w-5xl">
        <div className="flex items-center justify-between border-b border-border pb-4">
          <div>
            <p className="text-xs uppercase text-text-dim">Internal operations</p>
            <h1 className="mt-1 text-2xl font-semibold">FactoryVision ops</h1>
          </div>
          <span className="inline-flex h-8 items-center gap-2 border border-accent/40 bg-accent-tint px-3 text-xs text-accent">
            <Radio size={13} />
            Preview data
          </span>
        </div>
        <section className="mt-6 border-y border-border py-16 text-center">
          <p className="font-medium">Read-only operations preview</p>
          <p className="mt-2 text-sm text-text-mut">
            No reviewer, owner, or live operations API is called from this route.
          </p>
        </section>
      </div>
    </main>
  );
}
