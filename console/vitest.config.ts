import path from "node:path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    // DOM-backed modules (localStorage/window) get jsdom automatically.
    environmentMatchGlobs: [["lib/reviewSessionEngine.test.ts", "jsdom"]],
    // Unit tests only. Playwright specs under e2e/ run via `npm run e2e`.
    exclude: ["**/node_modules/**", "**/dist/**", "**/.next/**", "e2e/**"],
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname),
    },
  },
});
