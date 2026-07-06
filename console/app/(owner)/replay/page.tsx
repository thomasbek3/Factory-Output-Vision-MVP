import { ReplayDashboard } from "@/components/replay/replay-dashboard";

type ReplayPageProps = {
  searchParams: Promise<{
    station?: string;
    t?: string;
  }>;
};

export default async function ReplayPage({ searchParams }: ReplayPageProps) {
  const params = await searchParams;
  const station = params.station ?? "pallet-a";

  return (
    <div data-replay-route="ready" data-selected-station={station}>
      <ReplayDashboard initialStation={station} initialTime={params.t ?? null} />
    </div>
  );
}
