# CP6 Plan

- [x] Fix TV mode to reuse the same station/count/pace selectors as Live.
- [x] Tag synthesized demo alerts with `source: "demo"` in the alert library.
- [x] Add reviewer tally chunks, lease locking, confirm-to-human-count-event mapping, and tests.
- [x] Build `/review` tally mode with 10x default playback, hotkeys, summary, confirm, and redo.
- [x] Build read-only `/ops` with demo investor chart, reviewer metrics, model ops, and export stub.
- [x] Verify lint/build/test/docs-check, HTTP smoke `/review` + `/ops`, credential gate, self-review, one local commit.

## Review

- Tests: `npm test` passed 23 tests.
- Lint/build: `npm run lint` and `npm run build` passed.
- Docs: `make docs-check` passed with the existing tracked-artifact warning.
- Smoke: `/review` and `/ops` returned 200 with route markers; API proof leased `gate-line-0700`, confirmed 3 clicks, and created 3 `human_tally` events.
- Persistence note: reviewer chunks and human tally events use a console-local in-memory API store for v1 pitch proof, not a Prisma migration.
