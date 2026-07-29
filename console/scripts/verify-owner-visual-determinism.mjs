import { createHash } from "node:crypto";
import { mkdir, readFile, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import sharp from "sharp";

const root = process.cwd();
const firstDir = path.resolve(root, process.argv[2] ?? "");
const secondDir = path.resolve(root, process.argv[3] ?? "");
if (!process.argv[2] || !process.argv[3]) {
  throw new Error(
    "Usage: node scripts/verify-owner-visual-determinism.mjs <first-dir> <second-dir>",
  );
}
const files = [
  "owner-v2-today-desktop.png",
  "owner-v2-new-project-desktop.png",
  "owner-v2-station-desktop.png",
  "owner-v2-history-desktop.png",
];
const results = [];
for (const filename of files) {
  const firstPath = path.join(firstDir, filename);
  const secondPath = path.join(secondDir, filename);
  const [first, second, firstStat, secondStat, firstMeta, secondMeta] =
    await Promise.all([
      readFile(firstPath),
      readFile(secondPath),
      stat(firstPath),
      stat(secondPath),
      sharp(firstPath).metadata(),
      sharp(secondPath).metadata(),
    ]);
  const separationSeconds = (secondStat.mtimeMs - firstStat.mtimeMs) / 1000;
  if (separationSeconds < 90) {
    throw new Error(
      `${filename} captures are only ${separationSeconds.toFixed(1)} seconds apart`,
    );
  }
  const firstSha256 = createHash("sha256").update(first).digest("hex");
  const secondSha256 = createHash("sha256").update(second).digest("hex");
  if (firstSha256 !== secondSha256) {
    throw new Error(`${filename} is not byte-identical across captures`);
  }
  if (
    firstMeta.width !== 1536
    || firstMeta.height !== 1024
    || secondMeta.width !== 1536
    || secondMeta.height !== 1024
  ) {
    throw new Error(`${filename} is not 1536x1024 at both captures`);
  }
  results.push({
    file: filename,
    sha256: firstSha256,
    separationSeconds: Number(separationSeconds.toFixed(1)),
  });
}
const outputDir = path.join(root, "e2e-audit/determinism");
await mkdir(outputDir, { recursive: true });
await writeFile(
  path.join(outputDir, "owner-v2-determinism.receipt.json"),
  `${JSON.stringify({ captures: results }, null, 2)}\n`,
);
process.stdout.write(`${JSON.stringify({ captures: results })}\n`);
