import Link from "next/link";
import { AlertTriangle, ArrowRight, Factory } from "lucide-react";
import { OwnerStatusReporter } from "@/components/owner-v2/owner-status-reporter";

export function OwnerSurfaceState({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <section className="min-h-[calc(100vh-104px)] border-t border-border pt-10">
      <OwnerStatusReporter status="connected" />
      <div className="max-w-xl">
        <Factory size={22} className="text-accent" aria-hidden="true" />
        <h1 className="mt-5 text-2xl font-semibold">{title}</h1>
        <p className="mt-2 max-w-lg text-sm leading-6 text-text-mut">{description}</p>
      </div>
    </section>
  );
}

export function OwnerDataUnavailable() {
  return (
    <section className="grid min-h-[calc(100vh-104px)] place-items-center">
      <OwnerStatusReporter status="unavailable" />
      <div className="max-w-md text-center">
        <AlertTriangle className="mx-auto text-warn" aria-hidden="true" />
        <h1 className="mt-4 text-xl font-semibold">Owner data unavailable</h1>
        <p className="mt-2 text-sm leading-6 text-text-mut">
          FactoryVision could not load verified production data. No demo or
          estimated values have been substituted.
        </p>
      </div>
    </section>
  );
}

export function OwnerNoFactories() {
  return (
    <OwnerSurfaceState
      title="No factory access"
      description="Your account is active, but it is not assigned to a factory yet. Ask a FactoryVision administrator to add an owner membership."
    />
  );
}

export function FactoryChooser({
  factories,
  basePath = "/",
}: {
  factories: { id: string; name: string }[];
  basePath?: string;
}) {
  return (
    <section className="py-8">
      <h1 className="text-2xl font-semibold">Choose a factory</h1>
      <div className="mt-6 divide-y divide-border border-y border-border">
        {factories.map((factory) => (
          <Link
            key={factory.id}
            href={`${basePath}?factory_id=${factory.id}`}
            className="flex min-h-16 items-center justify-between gap-4 px-2 hover:bg-panel"
          >
            <span className="font-medium">{factory.name}</span>
            <ArrowRight size={16} className="text-text-dim" aria-hidden="true" />
          </Link>
        ))}
      </div>
    </section>
  );
}
