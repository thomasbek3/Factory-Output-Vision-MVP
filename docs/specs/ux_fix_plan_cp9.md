# CP9 — UX Fix Plan (goal mode)

Source: full UX audit 2026-07-06 (Opus, 3 personas, every element exercised). Rule: every goal below has a VERIFIABLE acceptance criterion — a Playwright spec or an explicit reviewer check. Nothing is done until its criterion passes. Protected: the audit's §5 "works well" list (ClipDrawer loop, jobs cards, New Job form, History rows, tally loop, alerts) must not regress — existing e2e suite stays green throughout.

## G1 — No lying chrome (audit #4, #6, dead inventory)
Every visible affordance either works or doesn't exist.
- Global search becomes REAL: shadcn Command palette, ⌘K opens it; entries = tabs, jobs by name, stations, "jump to time on Replay". 
- Help "?" opens a "How FactoryVision works" sheet: 3 short sections — the three doors to footage (tap a number / scrub Replay / browse days), History = money records vs Replay = video, "every count has a clip". (This doubles as the fix for owner-question (b).)
- "Live" pill: non-interactive status style (no chevron), tooltip "All cameras connected".
- Avatar: dropdown w/ role switcher (owner/reviewer/ops — restore in prod, it's a demo app) + "Sign out (soon)" disabled item.
- Camera tile kebab: real menu — Open in Replay (station+now), View events today (drawer at latest), Hide tile (session).
- Replay chapter kebabs: REMOVED. Jobs kebab gains Edit (opens pre-filled New Job drawer, PATCH).
✔ Accept: e2e — ⌘K opens palette and navigates to Jobs; every header control click produces visible response; kebab menus enumerate + fire; NO dead interactive elements on / /replay /jobs (spec asserts each).

## G2 — The Tapes archive (owner Q(a)/(b), audit #2, #5)
Replay becomes the footage library.
- Real day navigation: available-days index derived from demo media/events; date pager + a day-strip picker (days with footage = dots; others disabled). EXTEND prepare-demo-media.sh to also cut Jun 25 buckets from /Users/thomas/FactoryVisionArtifacts/onboarding/factory-live-20260625 (+cam2 dir) so "yesterday" genuinely works with real different footage; generate a small events file for Jun 25 (subset schema, clearly derived) so diamonds/chapters populate.
- "Counted moments" panel per selected day/station: chronological list of every CountEvent (time · station · verifier), click → ClipDrawer. This is the "see the different clips easily" surface.
- Save clip: button on Replay viewer AND ClipDrawer → server route /api/clip/[eventId]/download extracts ±5s mp4 via ffmpeg (cache in console/tmp, gitignored) and downloads; plus "Copy link" action (copies the ?clip= deep URL, toast). Saved clips recorded in DB (SavedClip: eventId, savedAt, note) and listed in a "Saved clips" section on Replay.
- History expanded row gains "View footage →" linking /replay?station=…&d=… for that project's window (cross-link money↔video).
✔ Accept: e2e — navigate to Jun 25 and see different chapters; counted-moments list opens drawer; Save clip downloads a file (assert response 200 + content-type video/mp4) and appears under Saved clips after reload; Copy link puts ?clip= URL on clipboard (assert toast); History row links to Replay.

## G3 — Demo/dev language purge (audit #1, #7)
- /stations + /settings: real owner-voice empty states ("Station analytics is coming in the next update — your per-station counts live on the Live tab for now." + primary action linking there). No milestone jargon anywhere.
- ClipDrawer body: replace v0/MP4-bucket/offset copy with "Moment around 2:27:43 PM · Pallet A".
- Replay subtitle → "Every recorded day, every placement — tap a diamond to watch."; "demo gap" → "no footage"; alert sentence likewise.
- History: delete test rows (Fable Review — probe, CP3 Smoke) from DB + seed guard (exclude titles matching /probe|smoke/i from owner surfaces).
- Ops keeps its honest "demo seed"/"Read-only v1" pills (internal surface).
✔ Accept: e2e greps rendered HTML of all owner routes for forbidden strings: /checkpoint|v0|demo (case-insens except ops)|MP4|bucket|probe|smoke/ → zero hits on owner surfaces.

## G4 — Mobile owner layout (audit #3)
- Rail hidden < lg; hamburger sheet owns nav; hero card + KPI stack cleanly at 390px; camera tiles single-column; no horizontal scroll.
✔ Accept: e2e at 390×844 — nav via hamburger reaches all tabs; assert no element wider than viewport (scrollWidth === clientWidth) on / /jobs /replay.

## G5 — Flow feedback & no strandings (audit #8, #9, Back→about:blank)
- Mark finished: confirm dialog ("Finish Ramirez Fencing? It moves to History with its final grade.") → toast "Finished — Grade A · View in History →".
- ?clip drawer open/close uses history.replaceState (Back never lands about:blank; e2e: open drawer from alert, press browser Back → still on the app).
- /ops and /tv: subtle "← Console" link (tv: bottom-left, low-opacity).
✔ Accept: e2e for each.

## G6 — Replay comprehension (audit: default 15×, cluster-everything, chapters all "0 QUIET")
- Default speed 1× (15× stays one tap away).
- Diamonds: individual markers when a 15-min bucket has ≤4 events; clusters (×N) only above that. FIX the chapter-count regression: chapters must show real "N PLACED" from events (this broke — investigate selector; likely CP7 station-selector change).
✔ Accept: unit test on chapter counts vs demo events; e2e asserts ≥1 chapter shows "6 PLACED"-style label and ≥1 individual diamond exists.

## G7 — Reviewer clarity (Maria findings)
- One-line instruction banner: "Tap +1 COUNT every time a finished piece lands on the pallet." with hotkey hints (Space · Z undo · ← back 10s) inline under the button.
- Header copy humanized: "counting 1 h 2 m behind live · 51 chunks waiting".
- Walk-away note in the header tooltip + on lease: "If you leave, this chunk returns to the queue after 5 minutes."
✔ Accept: e2e text assertions.

## G8 — Ops legibility (audit #10)
- Each stat card gets a one-line subtitle (e.g. VERIFICATION LAG — "how far behind live the human counts are"; EVENTS TODAY shows demo-day date context "on Jun 26").
- Exam card: subtitle "held-out recall — the honest score on unseen footage".
✔ Accept: e2e text assertions.

Order: G3 (cheap, biggest pitch risk) → G6 → G1 → G5 → G2 (biggest build) → G4 → G7 → G8. Existing 23 e2e + 23 vitest stay green throughout; new specs added per goal. Commits per goal-cluster; reviewer (Fable) verifies each criterion before push.
