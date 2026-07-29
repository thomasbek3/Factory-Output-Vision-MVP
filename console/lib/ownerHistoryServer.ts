import "server-only";

import {
  buildOwnerHistoryRecords,
  filterOwnerHistoryRecords,
  summarizeOwnerHistory,
  type OwnerAuditRow,
  type OwnerCloseoutRow,
} from "@/lib/ownerHistoryModel";
import type {
  OwnerHistoryData,
  OwnerHistoryFilters,
} from "@/lib/ownerHistoryTypes";
import { ownerRestAll, ownerRpc } from "@/lib/ownerServer";

function query(values: Record<string, string>) {
  return new URLSearchParams(values).toString();
}

export async function loadOwnerHistoryData(input: {
  accessToken: string;
  factoryId: string;
  timezone: string;
  filters: OwnerHistoryFilters;
  nowIso?: string;
}): Promise<OwnerHistoryData> {
  const nowIso = input.nowIso ?? new Date().toISOString();
  const closeoutQuery: Record<string, string> = {
      factory_id: `eq.${input.factoryId}`,
      select:
        "id,project_id,revision,planned_units,planned_direct_labor_cents,planned_material_cost_cents,planned_margin_after_direct_costs_cents,deadline_at,completed_at,factory_timezone,verified_good_units,material_cost_cents,direct_labor_cents,margin_after_direct_costs_cents,snapshot,created_at",
      order: "completed_at.desc,revision.desc,id.asc",
  };
  if (input.filters.range !== "all") {
    closeoutQuery.completed_at = `gte.${new Date(
      Date.parse(nowIso) - Number(input.filters.range) * 86_400_000,
    ).toISOString()}`;
  }
  const [closeouts, options] = await Promise.all([
    ownerRestAll<OwnerCloseoutRow>(
      input.accessToken,
      `owner_project_closeouts?${query(closeoutQuery)}`,
    ),
    ownerRpc<OwnerHistoryData["options"]>(
      input.accessToken,
      "owner_history_filter_options",
      { p_factory_id: input.factoryId },
    ),
  ]);
  const projectIds = [...new Set(closeouts.map((row) => row.project_id))];
  const audits: OwnerAuditRow[] = [];
  for (let offset = 0; offset < projectIds.length; offset += 100) {
    const projectIdBatch = projectIds.slice(offset, offset + 100);
    audits.push(...await ownerRestAll<OwnerAuditRow>(
      input.accessToken,
      `owner_project_audit?${query({
        factory_id: `eq.${input.factoryId}`,
        project_id: `in.(${projectIdBatch.join(",")})`,
        select: "id,project_id,actor_type,action,metadata,created_at",
        order: "created_at.desc,id.desc",
      })}`,
    ));
  }
  const allRecords = buildOwnerHistoryRecords({
    closeouts,
    audits,
    nowIso,
  });
  const records = filterOwnerHistoryRecords(
    allRecords,
    input.filters,
    nowIso,
  );
  return {
    factoryId: input.factoryId,
    timezone: input.timezone,
    filters: input.filters,
    records,
    summary: summarizeOwnerHistory(records),
    options,
  };
}
