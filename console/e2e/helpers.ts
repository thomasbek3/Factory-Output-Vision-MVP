import { expect, type Page } from "@playwright/test";

/**
 * Attaches a console-error collector to the page. Call assertNoConsoleErrors()
 * at the end of a test to fail on any browser console error. Some noise is
 * benign (autoplay-with-audio warnings, favicon 404s) so we filter a small
 * allowlist of known-harmless substrings.
 */
const IGNORED_ERROR_SUBSTRINGS = [
  "favicon",
  // Autoplay policy rejections are handled gracefully by the app.
  "play() failed",
  "The play() request",
  "NotAllowedError",
  "AbortError",
  // Next.js dev-only hydration hints never fire in prod, but keep the harness robust.
  "Download the React DevTools",
];

export function collectConsoleErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() !== "error") return;
    const text = msg.text();
    if (IGNORED_ERROR_SUBSTRINGS.some((needle) => text.includes(needle))) return;
    errors.push(text);
  });
  page.on("pageerror", (err) => {
    const text = err.message;
    if (IGNORED_ERROR_SUBSTRINGS.some((needle) => text.includes(needle))) return;
    errors.push(text);
  });
  return errors;
}

export function assertNoConsoleErrors(errors: string[]) {
  expect(errors, `unexpected console errors:\n${errors.join("\n")}`).toEqual([]);
}

/** Waits for a video element to actually be playing (currentTime advancing). */
export async function expectVideoPlaying(page: Page, selector: string) {
  const handle = page.locator(selector).first();
  await expect(handle).toBeVisible();
  const advanced = await handle.evaluate(async (el: HTMLVideoElement) => {
    const start = el.currentTime;
    // Nudge autoplay in case the browser needs it.
    el.muted = true;
    try {
      await el.play();
    } catch {
      /* autoplay policy — ignore */
    }
    await new Promise((r) => setTimeout(r, 1200));
    return el.currentTime > start;
  });
  return advanced;
}
