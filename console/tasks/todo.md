# CP7 Plan

- [x] Add `AreaSpark` as the single reusable luminous area sparkline.
- [x] Restore owner station tiles to job-attributed demo counts and pin the 14:32 narrative in tests.
- [x] Replace Live/TV charts, scoreboard number scale, pace pills, hero composition, and alert rows to match `DESIGN.md`.
- [x] Keep Stations placeholder as n/a, leave Replay heat untouched, keep Jobs money column unchanged, and update History daily bars to the green gradient.
- [x] Verify lint/build/test/docs-check, browser screenshot/computed styles, credential gate, self-review, and one local commit.

## Review

- Tests: `npm test` passed 23 tests, including the 14:32 station narrative lock.
- Lint/build: `npm run lint` and `npm run build` passed.
- Docs: `make docs-check` passed with the existing tracked-artifact/cache warning.
- Browser: `http://127.0.0.1:3000/` and `/api/media/gate-line/midday.mp4` returned 200; dev server left running on 127.0.0.1:3000.
- Visual proof: Chrome headless screenshot saved to `/tmp/fv-cp7-live.png`; approved render inspected at `docs/design/fv-live-a-approved.png`.
- Computed styles: hero `+$532` 72px/800, KPI `445` 30px/800, camera counts `142` and `58` 46px/800, pace pills tinted with 40% borders.
- Credential gate: no credential-looking strings found in the staged diff scan.
