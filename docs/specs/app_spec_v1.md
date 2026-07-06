# FactoryVision App — Full Spec v1 (2026-07-05)

Status: APPROVED DIRECTION — build target for the investor-pitch demo and pilot product.
Design law: `DESIGN.md` (repo root) + reference render `docs/design/fv-live-a-approved.png`. No UI deviates.
Product doctrine: video-first; every count is human-verified and evidence-backed; plain-English money verdicts.

One codebase, one deploy, three role-gated faces:
- **OWNER** (`/`) — the factory owner's console. 95% of design effort.
- **REVIEWER** (`/review`) — verification workers' clip queue. Speed-optimized, invisible to owners.
- **OPS** (`/ops`) — FactoryVision internal. Read-only v1.

---

## 0. Foundations

### 0.1 Stack
- Next.js (App Router) + TypeScript + Tailwind + shadcn/ui + Tremor (charts) + lucide-react (icons, stroke 1.75).
- Tokens from DESIGN.md mapped 1:1 into the Tailwind theme. Dark only (v1).
- Realtime: single SSE channel (`/api/stream`) pushing `count_event`, `alert`, `camera_status` messages.
- Video: HLS (hls.js) served from the segment store; live tiles = low-latency HLS from RTSP relay (pilot: ffmpeg RTSP→HLS per camera; demo mode: looped playlist of recorded segments).
- Auth v1: stubbed role switcher (querystring/localStorage) behind a single shared factory token. Real auth post-pitch.

### 0.2 Data model (SQLite via Prisma; one factory v1, `factory_id` on everything anyway)
- **Camera**: id, name, rtsp_url (encrypted at rest), station_id, status(online/offline), last_frame_at.
- **Station**: id, name, camera_id, zone_polygon(json, normalized coords), baseline_rate(units/hr, learned or manual), active(bool).
- **Job**: id, client, title, units_required, quote_usd, cogs_usd, labor_budget_usd, deadline(date), station_ids[], status(active/finished/paused), created_at, finished_at, notes.
- **CountEvent** (the atom): id, station_id, job_id(nullable), ts, clip_id, source(tripwire), verdict(placed/not/unsure), verified_by(user_id|model), verified_at, model_verdict(placed/not, confidence), disputed(bool).
- **Clip**: id, station_id, t_start, t_end, hls_uri, thumb_uri, segment_refs[].
- **Alert**: id, type(behind_pace|station_quiet|camera_offline), severity(crit|warn), station_id, job_id?, ts, message, clip_id?, resolved(bool).
- **User**: id, role(owner|reviewer|ops), name, email.
- **ReviewTask**: id, clip_id, station_id, ts, tripwire_score, status(pending|done|escalated), decided_by, decided_at, decision.
- **LaborConfig**: work_hours per weekday (e.g. 07:00–17:30), hourly_rate_usd, workers_per_station(default 1).

### 0.3 The Evidence Primitive — ClipDrawer (GLOBAL)
Right-side overlay drawer, 480px, available on EVERY screen. Anything with a timestamp opens it.
- Content: video player (the event clip, default ±5s around the moment, loop), station + wall-clock, job chip, "Verified by M. Reyes · 14:31:52" line, model shadow-verdict chip, tripwire score (ops/reviewer roles only).
- Actions: ⏮ prev event / next event ⏭ (within station+day), "Open in Replay" (deep-link, seeks timeline), "Dispute this count" (owner → flags event, queues re-review), speed 0.5×/1×/2×.
- Keyboard: `Esc` close, `←/→` prev/next, `space` play/pause.
- Invoked from: camera-tile count & last-count line, KPI units number, alert rows, replay diamonds & chapter cards, job pace sentences, station chart points, history row drill-ins, reviewer queue (is natively this).
- URL-addressable: `?clip=<id>` so any view can be shared/linked with the drawer open.

### 0.4 Time & demo engine
- `TimeProvider` abstracts "now": live mode = wall clock; **demo mode** = virtual clock over a recorded day (2026-06-26 events + segments), speeds 1× and 60×, jump-to-time. All views read time/events through it — the pitch demo and dev environment ARE demo mode; zero special-casing in components.
- Demo data: `demo_events_0626.json` (pipeline output) + segment store on disk; jobs seeded from `demo_jobs.json`.

### 0.5 The math (single source: `lib/paceMath.ts`, unit-tested)
- `elapsed_work_ratio(job, now)` = worked hours elapsed since job start ÷ total worked hours between start and deadline (work-hours calendar from LaborConfig — NOT wall-clock).
- `expected_units_by_now` = units_required × elapsed_work_ratio.
- `pace_delta` = units_done − expected_units_by_now (drives AHEAD/BEHIND chips: label = abs+direction, e.g. "18 AHEAD").
- `labor_burned_usd` = Σ per station-day (active worked hours × hourly_rate × workers). v1 proxy for "active hours": scheduled work hours while job assigned; v2 uses camera-derived presence.
- `projected_labor_usd` = labor_burned ÷ max(units_done,1) × units_required (units-based projection), clamped by remaining scheduled hours.
- `projected_margin` = quote − cogs − projected_labor.
- **Verdicts** (job): `IN THE GREEN` = projected_margin ≥ 0.9 × planned_margin; `GETTING TIGHT` = 0.5–0.9×; `LOSING MONEY` = < 0.5× or negative. (planned_margin = quote − cogs − labor_budget). Thresholds in config, shown in Settings later.
- **Grades** (finished job): A = margin ≥ planned AND on time; B = margin ≥ 0.8× planned OR ≤1 day late; C = margin ≥ 0; C− = negative margin. (v1 formula; tune with real data.)
- Money strip total = Σ projected_margin over active jobs.

---

## 1. OWNER VIEW

Nav rail (DESIGN.md chrome): **Live · Replay · Jobs · Stations · History · Alerts(badge) · Settings**. Header: wordmark, Live status pill, search (⌘K → jump to job/station/time), help, avatar. Footer trust line on every tab.

### 1.1 LIVE (home)
Layout per approved render.
- **Money strip**: hero `+$532` (Σ projected margins, live-updating) + sentence naming the worst job if any is TIGHT/LOSING ("You're in the green — but Alvarez Gates is losing money."), else "All N jobs on pace." Ghost area-chart of today's cumulative projected margin. KPI cards: Units verified today (+delta vs same weekday last week, sparkline of per-hour counts) · Counts verified 100% HUMAN+AI.
- **Camera wall**: one tile per active station (grid auto-fit 2×N). Tile = DESIGN.md camera card: header (name, CAM-ID · location, red LIVE pill, kebab: open replay / station page / hide), clean live video, scoreboard below (count today → opens ClipDrawer at latest event; `today · last count 14:31`; per-hour area sparkline colored by pace; pace pill).
- Offline camera state: tile keeps header, video area shows dark slate + "camera offline since 14:07" + amber pill; alert auto-raised.
- **Flags rail** (alerts, latest 3 unresolved): severity icon, time, station, sentence, `▶ Watch replay` (ClipDrawer at trigger moment), "View all alerts →".
- Empty states: no jobs → money strip shows "No active jobs — add one in Jobs" with CTA; no cameras → onboarding pointer to Settings.

### 1.2 REPLAY
- **Controls row**: station pills (real station names; active orange), date pager (◀ date ▶, default Today), jump-to-time field.
- **Viewer**: HLS player of the selected chapter/moment. Caption bottom-left: current event ("PLACEMENT #14 · 12:40:22 · Verified by M. Reyes") when paused on/near an event. Speed pills: 1× 4× 15× 60×. Implementation: 1×/4× native playbackRate on source; **15×/60× play pre-rendered timelapse renditions** (pipeline already renders 15×; 60× derived) with the same timeline mapping — seamless to the user.
- **Day timeline**: work-hours span; activity heat band (event density per 15-min, green/amber/idle); **orange diamond per verified CountEvent** (click → seek viewer + open ClipDrawer); white NOW needle (live/demo clock). Hover: tooltip with time + event id.
- **Chapters grid**: 15-min cards (thumb from segment mid-frame, time range, `6 PLACED`/`0 QUIET`); click = load chapter into viewer at 15×; active card orange-outlined. Lazy-load thumbs.
- **Download/share**: kebab on viewer → "Save clip" (mp4 of current event clip) — owners share proof.
- Edge: gaps in footage (camera drop) render as hatched gray band on timeline with tooltip "no footage 14:07–14:19".

### 1.3 JOBS
- **Active job cards** (DESIGN.md job card): verdict block, name+spec+deadline, pace bar with NOW tick + `52%` label, ONE sentence (auto-written: done/needed-by-now + finish projection), YOU KEEP/LOSE money column with planned comparison. Card kebab: Edit, Pause, Mark finished, View on Replay (jumps filtered to its stations).
- Sentence generator rules: `"{done} of {units} done — you need {expected} by now. {Finishes {day} {am/pm} | Needs {rate}/day, doing {rate_actual} | Overdue — at this pace labor eats the margin.}"`. Plain words only.
- **+ New Job** (primary button): form drawer — Client, Title/what (free text), Units required, Quote $, Cost of goods $, Labor budget $ (or days × rate helper), Deadline (date), Stations (multi-chip). 60-second fill target. Validation: numbers > 0; stations required. On save: appears in wall + money strip instantly.
- Pause state: card dims, excluded from money strip, banner "paused".
- Finished flow: "Mark finished" → confirm → moves to History with computed actuals + grade; toast links there.

### 1.4 STATIONS
- One card per station (full-width, stacked): header (name, camera link, current job chip, pace pill) · **today curve** (Tremor area: cumulative units vs expected-pace dashed line; click any point → ClipDrawer nearest event) · hour-strip (colored 15-min blocks like replay heat) · 7-day mini-bars (units/day vs baseline) · stats row (units today, units/hr now, baseline, active %).
- Purpose: answer "is the station slow or is the job hard" — comparison vs its own baseline.
- Kebab: rename, adjust baseline, open replay.

### 1.5 HISTORY (projects)
- **Table**: PROJECT (client — spec, finished date, stations) / QUOTED (days) / ACTUAL (days) / MARGIN PLAN → REAL / GRADE (letter chip). Sort by finish date desc; search by client.
- **Expanded row** (accordion): daily-output bar chart (value labels, gridlines), station contribution split, labor $ planned vs actual, and the **NEXT TIME box** (orange): `"You quoted {q} days. Your crew did it in {a}. Quote the next {client} {product} order at {suggest} days — same price keeps ${delta} more margin."` where `suggest = round_half(actual × 1.05)`; if actual > quoted: `"...ran {pct}% over — price the next one up or fix the bottleneck (see Station X)."`
- Aggregate header chips: lifetime jobs, avg quote error %, total margin recovered (sum of positive deltas) — the retention number.

### 1.6 ALERTS
- Feed grouped by day: severity icon, time, station, sentence, `▶ Watch replay`, Resolve button. Filters: open/resolved, station, type.
- **Rules v1 (hardcoded, values in config):** `behind_pace`: pace_delta ≤ −15% of expected at check (evaluated per 15 min) → crit if job verdict LOSING, else warn. `station_quiet`: no CountEvent for 25 work-minutes while a job is assigned → warn. `camera_offline`: no frames 60s → warn (crit after 10 min).
- Each alert stores the trigger moment's clip ref → drawer opens right at the problem.

### 1.7 SETTINGS
- **Cameras**: list (name, station, status, last frame); Add camera = paste RTSP URL (+ label) → test connection → snapshot preview → assign/create station. (Reolink autodiscovery: post-pitch.)
- **Stations**: name, camera, zone preview (v1: static image of zone polygon from calibration file; polygon EDITOR is v2), baseline units/hr (auto-learned after 3 days, manual override).
- **Work & labor**: work hours per weekday, hourly labor rate, workers per station.
- **Users**: owner emails; reviewer accounts (ops-managed later).
- **Danger**: nothing destructive in v1 beyond removing a camera (soft-delete).

### 1.8 TV MODE (`/tv`)
- No nav. Rotates: camera wall (all tiles, larger) → money strip full-screen → back, 20s cadence, or pinned via `?view=wall`. Giant type (counts ~96px). Auto-reconnect. Meant for breakroom/office TV. Reuses Live components with a `scale` variant.

---

## 2. REVIEWER CONSOLE (`/review`)

Purpose: verify candidate events FAST; every decision = a verified count for owners AND a training label. Target ≤3s/decision, event→verified latency <2 min during covered shifts.

- **Layout**: single-column focus. Header: queue depth, today's reviewed count, session rate/hr, "caught up ✓" state. Body: **auto-playing looped clip** (the candidate window, 2–6s, zone-cropped large + full-frame toggle `f`). Context line: station, wall-clock, factory. NO model verdict shown before decision (anchoring bias); shown after as "model agreed/disagreed" toast.
- **Decision keys**: `Y` = PLACED · `N` = NOT PLACED · `U` = UNSURE (escalates to senior queue). Giant on-screen buttons for mouse/touch parity. `Z` = undo last (10s window). Auto-advance on decision.
- Every decision writes: CountEvent(verdict, verified_by, verified_at) + appends to the training-labels manifest (respecting the exam firewall — clips inside exam windows are NEVER served to the queue; enforced server-side by the existing `training_eligible`/guard logic).
- **Dispute queue**: owner-disputed events re-enter at top, flagged, served to a different reviewer; second verdict wins, ops sees disagreements.
- **Fairness/quality**: golden clips (known answers) injected ~2% for accuracy scoring; per-reviewer accuracy visible only in ops.
- Empty state: "Queue clear — next candidates arrive automatically." with live listener.
- Chrome: same tokens, minimal; must run well on a cheap laptop + spotty connection (clips preloaded n+2 ahead).

---

## 3. OPS VIEW (`/ops`) — v1 read-only

- **Factories table**: factory, cameras up/down, stations active, events today, verification latency p50/p95, open queue depth, reviewers online.
- **The Investor Chart**: model shadow-agreement % vs human verdicts, weekly trend per station + overall ("automation share rising"). Data: CountEvent.model_verdict vs verdict.
- **Reviewer metrics**: per reviewer — decisions today, rate/hr, golden-clip accuracy, disagreement rate.
- **Model ops**: exam results log (from pipeline runs), label export button → training manifest (calls existing scripts), drift flag when weekly agreement drops >5pts.
- v1 = tables + one chart; no write actions except label-export trigger.

---

## 4. Build plan (pitch cut)

Priority order (each independently demoable):
1. Scaffold + tokens + chrome + role switcher + TimeProvider/demo engine (seeded events).
2. LIVE tab complete (tiles on looped demo video, money math, flags) + ClipDrawer.
3. JOBS (+form, pace math lib w/ tests) — money strip goes real.
4. REPLAY (timeline + diamonds + chapters on demo day; 15× via prerendered renditions).
5. HISTORY (seeded finished jobs + NEXT TIME calc).
6. REVIEWER v0 (queue on real candidate clips from the pipeline).
7. ALERTS (3 hardcoded rules on demo stream) + TV mode + OPS stub.
Division: UI/components/design-system = Claude (taste-gated); API routes, ffmpeg/HLS relay, pipeline glue (events→DB, clips), demo-data packaging = Codex, Claude reviews. `/design-review` pass before pitch.
Out of v1: real auth, multi-tenant, alert-rule editor, zone polygon editor, Reolink autodiscovery, emails/Coffee-Cup report, mobile apps (responsive web only), light mode.

## 5. Open items
- Pilot factory station count (drives tile grid + seed data): currently 2 real cameras (pallet, garage).
- 60× rendition generation joins the nightly pipeline.
- Job↔CountEvent attribution when multiple jobs share a station: v1 = single active job per station at a time (enforced in Jobs form); queue real multi-job attribution for v2.
