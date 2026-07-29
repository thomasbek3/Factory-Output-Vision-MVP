import { describe, expect, it } from "vitest";
import { ownerPaceChartIsValid } from "@/lib/ownerDashboardTypes";
import {
  ownerPreviewDashboard,
  ownerPreviewStation,
} from "@/lib/preview/ownerDashboard";

describe("owner preview pace fixtures", () => {
  it("keeps every actual series bounded by NOW on the full deadline timeline", () => {
    for (const project of ownerPreviewDashboard.projects) {
      expect(ownerPaceChartIsValid(project.chart), project.name).toBe(true);
      if (!project.chart) throw new Error(`${project.name} has no chart`);
      expect(project.chart.actual).toHaveLength(project.chart.nowIndex + 1);
      expect(project.chart.required).toHaveLength(project.chart.labels.length);
    }
  });

  it("keeps station good units net of preview scrap and rework", () => {
    expect(ownerPreviewStation.kpis.verifiedGoodUnits.value).toBe(212);
    expect(ownerPreviewStation.summary).toMatchObject({
      scrapUnits: 6,
      reworkUnits: 3,
    });
  });
});
