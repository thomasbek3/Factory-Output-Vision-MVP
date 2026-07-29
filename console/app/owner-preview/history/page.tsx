import { OwnerShell } from "@/components/owner-v2/owner-shell";
import { HistorySurface } from "@/components/owner-v2/history-surface";
import { parseOwnerHistoryFilters } from "@/lib/ownerHistoryModel";
import { ownerPreviewDashboard } from "@/lib/preview/ownerDashboard";
import { ownerPreviewHistory } from "@/lib/preview/ownerHistory";

export default async function OwnerHistoryPreviewPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const params = await searchParams;
  return (
    <OwnerShell
      factories={[{ id: ownerPreviewDashboard.factoryId, name: "ForgeWorks Plant" }]}
      preview
    >
      <HistorySurface
        data={ownerPreviewHistory(parseOwnerHistoryFilters(params))}
        preview
      />
    </OwnerShell>
  );
}
