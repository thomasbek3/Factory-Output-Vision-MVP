import { dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { FlatCompat } from "@eslint/eslintrc";
import { defineConfig, globalIgnores } from "eslint/config";

const compat = new FlatCompat({
  baseDirectory: dirname(fileURLToPath(import.meta.url)),
});

const eslintConfig = defineConfig([
  ...compat.extends("next/core-web-vitals", "next/typescript"),
  // live-media/ holds HLS transport-stream segments (*.ts) written by the RTSP
  // relay — video, not TypeScript. It's gitignored build output; keep eslint out
  // of it so `npm run lint` doesn't choke parsing binary .ts segments.
  globalIgnores([".next/**", "out/**", "build/**", "live-media/**", "next-env.d.ts"]),
]);

export default eslintConfig;
