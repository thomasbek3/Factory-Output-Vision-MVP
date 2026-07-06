import path from "node:path";
import { describe, expect, it } from "vitest";
import { liveMediaRoot, resolveLivePath } from "@/lib/liveMedia";

const allowed = ["pallet-a", "gate-line"];

describe("resolveLivePath", () => {
  it("serves a valid playlist for an allowed station as no-store m3u8", () => {
    const safe = resolveLivePath("pallet-a", ["stream.m3u8"], allowed);
    expect(safe).not.toBeNull();
    expect(safe!.absPath).toBe(path.join(liveMediaRoot, "pallet-a", "stream.m3u8"));
    expect(safe!.contentType).toBe("application/vnd.apple.mpegurl");
    expect(safe!.cacheControl).toBe("no-store");
  });

  it("serves a numbered segment as short-cached mp2t", () => {
    const safe = resolveLivePath("gate-line", ["seg_00042.ts"], allowed);
    expect(safe).not.toBeNull();
    expect(safe!.absPath).toBe(path.join(liveMediaRoot, "gate-line", "seg_00042.ts"));
    expect(safe!.contentType).toBe("video/mp2t");
    expect(safe!.cacheControl).toMatch(/max-age/);
  });

  it("accepts a Set allowlist as well as an array", () => {
    const safe = resolveLivePath("pallet-a", ["stream.m3u8"], new Set(allowed));
    expect(safe).not.toBeNull();
  });

  it("rejects a station not on the allowlist", () => {
    expect(resolveLivePath("ghost-line", ["stream.m3u8"], allowed)).toBeNull();
  });

  it("rejects a malformed station slug", () => {
    expect(resolveLivePath("../etc", ["stream.m3u8"], allowed)).toBeNull();
    expect(resolveLivePath("Pallet_A", ["stream.m3u8"], allowed)).toBeNull();
    expect(resolveLivePath("", ["stream.m3u8"], allowed)).toBeNull();
  });

  it("rejects filenames that are not the playlist or a segment", () => {
    expect(resolveLivePath("pallet-a", ["secret.env"], allowed)).toBeNull();
    expect(resolveLivePath("pallet-a", ["stream.m3u9"], allowed)).toBeNull();
    expect(resolveLivePath("pallet-a", ["seg_.ts"], allowed)).toBeNull();
    expect(resolveLivePath("pallet-a", ["seg_1.mp4"], allowed)).toBeNull();
  });

  it("rejects path traversal via file parts", () => {
    expect(resolveLivePath("pallet-a", ["..", "stream.m3u8"], allowed)).toBeNull();
    expect(resolveLivePath("pallet-a", ["nested", "stream.m3u8"], allowed)).toBeNull();
    expect(resolveLivePath("pallet-a", ["../../etc/passwd"], allowed)).toBeNull();
    expect(resolveLivePath("pallet-a", [], allowed)).toBeNull();
  });

  it("never resolves outside the per-station media directory", () => {
    const safe = resolveLivePath("pallet-a", ["stream.m3u8"], allowed);
    const stationDir = path.join(liveMediaRoot, "pallet-a");
    expect(safe!.absPath.startsWith(`${stationDir}${path.sep}`)).toBe(true);
  });
});
