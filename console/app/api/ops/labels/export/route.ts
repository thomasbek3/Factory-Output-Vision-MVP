import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { opsSnapshot } from "@/lib/reviewStore";
import { demoNowIso } from "@/lib/demoData";

export const dynamic = "force-dynamic";

export async function POST() {
  const snapshot = opsSnapshot(new Date(demoNowIso));
  const outputDir = path.join(process.cwd(), "tmp");
  await mkdir(outputDir, { recursive: true });
  const outputPath = path.join(outputDir, `label-export-${Date.now()}.json`);
  const manifest = {
    schema: "factoryvision-label-export-v1",
    exported_at: new Date().toISOString(),
    source: "console-demo-human-tally",
    event_count: snapshot.humanEvents.length,
    events: snapshot.humanEvents,
  };
  await writeFile(outputPath, JSON.stringify(manifest, null, 2));

  return Response.json({ path: outputPath, eventCount: snapshot.humanEvents.length });
}
