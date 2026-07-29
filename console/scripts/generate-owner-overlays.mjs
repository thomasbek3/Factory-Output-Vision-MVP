import { createHash } from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import sharp from "sharp";

const root = process.cwd();
const surfaces = {
  today: {
    golden: "01-today-project-pacing.png",
    shot: "owner-v2-today-desktop.png",
  },
  project: {
    golden: "02-new-project-setup.png",
    shot: "owner-v2-new-project-desktop.png",
  },
  station: {
    golden: "03-station-workforce.png",
    shot: "owner-v2-station-desktop.png",
  },
  history: {
    golden: "04-history-closeout.png",
    shot: "owner-v2-history-desktop.png",
  },
};
const requested = process.argv[2];
if (requested && !(requested in surfaces)) {
  throw new Error(`Unknown owner overlay surface: ${requested}`);
}
const entries = requested
  ? [[requested, surfaces[requested]]]
  : Object.entries(surfaces);
const outputDir = path.join(root, "e2e-audit/overlays");
await mkdir(outputDir, { recursive: true });

function sha256(input) {
  return createHash("sha256").update(input).digest("hex");
}

function meanAbsoluteDistance(left, right) {
  if (left.length !== right.length) {
    throw new Error("Owner visual buffers differ in length.");
  }
  let distance = 0;
  for (let index = 0; index < left.length; index += 1) {
    distance += Math.abs(left[index] - right[index]);
  }
  return distance / left.length;
}

const receipts = [];
for (const [name, files] of entries) {
  const goldenPath = path.join(root, "../docs/design/owner-v2", files.golden);
  const shotPath = path.join(root, "e2e-audit/shots", files.shot);
  const overlayPath = path.join(
    outputDir,
    `owner-v2-${name}-overlay.png`,
  );
  const receiptPath = path.join(
    outputDir,
    `owner-v2-${name}-overlay.receipt.json`,
  );
  const [goldenMetadata, shotMetadata] = await Promise.all([
    sharp(goldenPath).metadata(),
    sharp(shotPath).metadata(),
  ]);
  if (
    goldenMetadata.width !== shotMetadata.width
    || goldenMetadata.height !== shotMetadata.height
  ) {
    throw new Error(
      `${name} visual inputs differ in size: golden ${goldenMetadata.width}x${goldenMetadata.height}, shot ${shotMetadata.width}x${shotMetadata.height}`,
    );
  }
  const width = goldenMetadata.width;
  const height = goldenMetadata.height;
  if (!width || !height) {
    throw new Error(`${name} visual inputs have no dimensions.`);
  }
  const [goldenPixels, shotPixels] = await Promise.all([
    sharp(goldenPath).removeAlpha().raw().toBuffer(),
    sharp(shotPath).removeAlpha().raw().toBuffer(),
  ]);
  const overlayPixels = Buffer.allocUnsafe(goldenPixels.length);
  for (let index = 0; index < goldenPixels.length; index += 1) {
    overlayPixels[index] = Math.round(
      (goldenPixels[index] + shotPixels[index]) / 2,
    );
  }
  const overlay = await sharp(overlayPixels, {
    raw: { width, height, channels: 3 },
  }).png().toBuffer();
  const distanceFromGolden = meanAbsoluteDistance(
    overlayPixels,
    goldenPixels,
  );
  const distanceFromShot = meanAbsoluteDistance(overlayPixels, shotPixels);
  if (distanceFromGolden <= 0.5 || distanceFromShot <= 0.5) {
    throw new Error(
      `${name} overlay is not a real composite: golden distance ${distanceFromGolden}, shot distance ${distanceFromShot}`,
    );
  }
  await writeFile(overlayPath, overlay);
  const receipt = {
    surface: name,
    golden: {
      path: path.relative(root, goldenPath),
      sha256: sha256(await sharp(goldenPath).png().toBuffer()),
    },
    shot: {
      path: path.relative(root, shotPath),
      sha256: sha256(await sharp(shotPath).png().toBuffer()),
    },
    overlay: {
      path: path.relative(root, overlayPath),
      sha256: sha256(overlay),
    },
    dimensions: { width, height },
    opacity: 0.5,
    meanAbsoluteDistance: {
      fromGolden: Number(distanceFromGolden.toFixed(4)),
      fromShot: Number(distanceFromShot.toFixed(4)),
    },
  };
  if (
    receipt.overlay.sha256 === receipt.golden.sha256
    || receipt.overlay.sha256 === receipt.shot.sha256
  ) {
    throw new Error(`${name} overlay hash matches an input.`);
  }
  await writeFile(receiptPath, `${JSON.stringify(receipt, null, 2)}\n`);
  receipts.push(receipt);
}
process.stdout.write(`${JSON.stringify(receipts)}\n`);
