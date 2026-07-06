import { describe, expect, it } from "vitest";
import { jobs as seedJobs, demoNowIso } from "@/lib/demoData";
import { selectMoneyStripTotal, selectRunningJobSnapshots } from "@/lib/jobSelectors";
import { pinDemoNarrative } from "@/lib/pinnedJobs";

describe("pinDemoNarrative", () => {
  it("restores the pinned demo jobs to active when the DB has drifted to finished", () => {
    // Simulate a stale dev.db: the three pinned demo jobs marked finished.
    const drifted = seedJobs.map((job) => ({ ...job, status: "finished" as const }));

    const reconciled = pinDemoNarrative(drifted);
    expect(reconciled.every((job) => job.status === "active")).toBe(true);

    // The money strip narrative holds at exactly +$532 with 3 running jobs.
    const now = new Date(demoNowIso);
    const snapshots = selectRunningJobSnapshots(now, reconciled);
    expect(snapshots).toHaveLength(3);
    expect(selectMoneyStripTotal(snapshots)).toBeCloseTo(532, 0);
  });

  it("preserves genuinely new DB jobs and re-adds any dropped pinned job", () => {
    const custom = {
      ...seedJobs[0],
      id: "job-custom-1",
      client: "Custom Co",
      status: "active" as const,
    };
    // DB has only one pinned job plus a custom job (two pinned jobs dropped).
    const reconciled = pinDemoNarrative([{ ...seedJobs[0] }, custom]);

    // Custom job survives untouched.
    expect(reconciled.find((job) => job.id === "job-custom-1")?.client).toBe("Custom Co");
    // All three pinned demo jobs are present.
    for (const seed of seedJobs) {
      expect(reconciled.some((job) => job.id === seed.id)).toBe(true);
    }
  });
});
