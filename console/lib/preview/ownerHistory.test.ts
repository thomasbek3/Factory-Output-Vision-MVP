import { describe, expect, it } from "vitest";
import { defaultOwnerHistoryFilters } from "@/lib/ownerHistoryModel";
import { ownerPreviewHistory } from "@/lib/preview/ownerHistory";

describe("owner History preview reconciliation", () => {
  it("reconciles every displayed weekly actual series to its closeout", () => {
    const data = ownerPreviewHistory({
      ...defaultOwnerHistoryFilters,
      range: "all",
    });
    expect(data.records).toHaveLength(6);
    for (const record of data.records) {
      expect(
        record.output.reduce(
          (total, bucket) => total + (bucket.actualUnits ?? 0),
          0,
        ),
      ).toBe(record.actualUnits);
      expect(
        record.output.every((bucket) => bucket.plannedUnits === null),
      ).toBe(true);
    }
  });
});
