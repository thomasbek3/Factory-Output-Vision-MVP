import {
  FactoryChooser,
  OwnerDataUnavailable,
  OwnerNoFactories,
} from "@/components/owner-v2/owner-surface-state";
import { HistorySurface } from "@/components/owner-v2/history-surface";
import { parseOwnerHistoryFilters } from "@/lib/ownerHistoryModel";
import { resolveOwnerPageContext } from "@/lib/ownerPageContext";
import { loadOwnerHistoryData } from "@/lib/ownerHistoryServer";

export default async function HistoryPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const params = await searchParams;
  const returnQuery = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value) returnQuery.set(key, value);
  }
  const returnTo = returnQuery.size
    ? `/history?${returnQuery.toString()}`
    : "/history";
  const context = await resolveOwnerPageContext({
    requestedFactoryId: params.factory_id,
    returnTo,
  });
  if (context.kind === "unavailable") return <OwnerDataUnavailable />;
  if (context.kind === "none") return <OwnerNoFactories />;
  if (context.kind === "choose") {
    return <FactoryChooser factories={context.factories} basePath="/history" />;
  }
  let data;
  try {
    data = await loadOwnerHistoryData({
      accessToken: context.accessToken,
      factoryId: context.factory.id,
      timezone: context.factory.timezone,
      filters: parseOwnerHistoryFilters(params),
    });
  } catch {
    return <OwnerDataUnavailable />;
  }
  return <HistorySurface data={data} />;
}
