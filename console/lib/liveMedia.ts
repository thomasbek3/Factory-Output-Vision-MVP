import path from "node:path";

/**
 * Path safety for the live-HLS serving route.
 *
 * The relay (scripts/live-relay.sh) writes per-camera HLS into
 * console/live-media/<station-slug>/{stream.m3u8, seg_NNNNN.ts}. The route must
 * only ever serve those two file shapes, and only for a station slug that
 * actually exists, so an attacker cannot walk out of the media root or read
 * arbitrary files.
 */

/** Absolute directory the relay writes HLS into. */
export const liveMediaRoot = path.join(process.cwd(), "live-media");

/** A station slug is a lowercase kebab id, matching our DB Station ids. */
const STATION_SLUG_RE = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

/** Only a bare playlist or a numbered segment may be requested. */
const ALLOWED_FILE_RE = /^(?:stream\.m3u8|seg_\d{1,10}\.ts)$/;

export type SafeLivePath = {
  absPath: string;
  contentType: string;
  /** m3u8 must never be cached; segments may be cached briefly. */
  cacheControl: string;
};

/**
 * Resolve a requested (station, file-parts) into a safe absolute path, or null
 * if anything about the request is disallowed. `allowedSlugs` is the live
 * allowlist of station ids (from the DB). Rejects:
 *   - unknown / malformed station slugs
 *   - multi-segment file paths (…/../…), empty, or unexpected filenames
 *   - any resolved path that escapes the per-station directory
 */
export function resolveLivePath(
  station: string,
  fileParts: string[],
  allowedSlugs: ReadonlySet<string> | readonly string[],
): SafeLivePath | null {
  const allowed =
    allowedSlugs instanceof Set ? allowedSlugs : new Set(allowedSlugs);

  if (!STATION_SLUG_RE.test(station) || !allowed.has(station)) {
    return null;
  }

  // Exactly one filename segment, matching the allowed shapes. No sub-paths.
  if (fileParts.length !== 1) {
    return null;
  }
  const file = fileParts[0];
  if (!ALLOWED_FILE_RE.test(file)) {
    return null;
  }

  const stationDir = path.join(liveMediaRoot, station);
  const resolved = path.resolve(stationDir, file);
  // Belt-and-suspenders: the resolved path must stay inside the station dir.
  if (
    resolved !== path.join(stationDir, file) ||
    !resolved.startsWith(`${stationDir}${path.sep}`)
  ) {
    return null;
  }

  const isPlaylist = file.endsWith(".m3u8");
  return {
    absPath: resolved,
    contentType: isPlaylist ? "application/vnd.apple.mpegurl" : "video/mp2t",
    cacheControl: isPlaylist ? "no-store" : "public, max-age=10",
  };
}
