# FactoryVision — Design System (LOCKED)

**Source of truth:** the approved render `fv-live-a.png`
(`~/.gstack/projects/thomasbek3-Factory-Output-Vision-MVP/designs/owner-console-20260705/fv-live-a.png`),
approved by Thomas 2026-07-05 ("A. thats it").
Every screen, mockup, render brief, and line of UI code follows THIS file. When in doubt, open the render.

Product surfaces: **TODAY** (active-project pacing) · **PROJECTS** (setup
and project detail) · **STATIONS** (station and team productivity) ·
**WORKFORCE** (assignment context) · **HISTORY** (closed operational and
financial records) · **ALERTS** · **SETTINGS**. Camera evidence and replay are
available from the records they support; they are not the owner navigation
hierarchy.

**Verification-copy amendment (2026-07-25):** the visual contract remains
locked, but verification copy must state its source and verified-through time.
Never claim live human verification or `100% HUMAN+AI` unless production data
proves both claims. This amendment is required by
`docs/specs/worker_ground_truth_portal_v1.md`.
Reviewer identity, individual votes, model evidence, and tripwire scores are not
owner- or reviewer-facing design elements. Where older component examples
conflict, the worker-portal privacy and capability contract controls.

**Owner V2 approval amendment (2026-07-29):** Thomas approved the four Owner V2
concepts under `docs/design/owner-v2/`. Those images and §9 of this document
supersede the older owner information hierarchy and owner component examples.
The original `fv-live-a-approved.png` remains authoritative for the
FactoryVision brand, palette, typography, manufacturing imagery, camera-card
language, and any visual detail not explicitly changed by Owner V2. The
reviewer `/review` and internal `/ops` products remain separate role-gated
surfaces and do not inherit the owner navigation or project economics.

---

## 1. Brand

- Wordmark: **Factory** in white + **Vision** in accent orange. Always "FactoryVision", never any other name.
- Logo mark: minimal orange "F" glyph in a rounded square, top of the nav rail.
- Product line under nothing — no taglines in the app chrome.
- Voice: plain English a factory owner reads in one pass. Project pace labels
  are `AHEAD`, `ON TRACK`, and `BEHIND`; money is labeled `margin after direct
  costs`, never profit. Every negative state includes a recovery sentence, such
  as "Need 63 units/day to recover." Trust line everywhere: "Verification
  source and through-time are shown with every resolved count."

## 2. Color tokens

Sampled from the approved render (solid fills) and normalized. These are THE palette — no substitutions, no extra hues.

```css
/* ground */
--bg:          #0C0E10;   /* page background */
--bg-rail:     #0A0B0D;   /* left nav rail, slightly darker than page */
--panel:       #14171B;   /* card surface (top of subtle vertical gradient) */
--panel-2:     #101317;   /* card surface (bottom of gradient) */
--border:      rgba(255,255,255,0.07);
--border-soft: rgba(255,255,255,0.045);

/* ink */
--text:        #F2F4F5;   /* headings, key numbers */
--text-mut:    #9AA1A9;   /* secondary text, captions */
--text-dim:    #6F7476;   /* tertiary labels (sampled #6F7172) */

/* accent — exactly one hot hue */
--accent:      #E8742F;   /* orange; sampled from Watch-replay button #E57737 */
--accent-hi:   #F98A3C;   /* hover/active */
--accent-tint: rgba(232,116,47,0.14);

/* semantics */
--good:        #46C26B;   /* positive direct-cost margin, AHEAD */
--good-tint:   rgba(70,194,107,0.14);
--bad:         #E5484D;   /* LIVE pill, BEHIND, losses */
--bad-tint:    rgba(229,72,77,0.14);
--warn:        #E7A13B;   /* amber, GETTING TIGHT */
--warn-tint:   rgba(231,161,59,0.13);
--idle:        #3A3F45;   /* offline/no-shift */
```

Rules:
- Red is reserved for LIVE pills + genuinely bad states (BEHIND, losing money, critical alerts). Never decorative.
- Orange is brand + interaction (active nav, primary buttons, replay markers). Never a status color.
- Glow is allowed only on LIVE/status LEDs and the legacy camera-wall money
  figure. Owner V2 has no giant money hero and no glow.

## 3. Typography

- **UI face:** Inter (build) / clean neutral grotesque (renders). NO condensed faces, NO stencil, NO letter-spaced-caps body text.
- Caps usage: ONLY small section labels (`ACTIVE PROJECTS`, `VERIFIED GOOD
  UNITS`, `MARGIN AFTER DIRECT COSTS`, `ALERTS`) at 11–12px, weight 600,
  letter-spacing 0.06em, color `--text-dim`.
- Numbers: semibold (600–700), `font-variant-numeric: tabular-nums`, tight letter-spacing (-0.01em). Hero money ~56–64px; camera-card counts ~36–40px; KPI values ~28–32px.
- Body/captions: 13–14.5px sentence case, `--text-mut`. Timestamps and IDs 11–12px `--text-dim` (regular sans, NOT monospace-everywhere; small mono is allowed only for clock/timestamps).
- Minimum text size anywhere: 11px. Minimum contrast: secondary text ≥ 4.5:1 on panels.

## 4. Layout & chrome

- **Left nav rail:** 88px wide, `--bg-rail`, icon + 11px label stacked, items:
  Today, Projects, Stations, Workforce, History, Alerts (with count badge),
  Settings; Collapse at bottom. Active item = orange icon + orange label + soft
  orange left-edge indicator.
- **Top header:** wordmark left; right side: Live status pill (green dot + "Live" + chevron), global search field with ⌘K hint, help icon, avatar. Header height ~64px, hairline bottom border.
- Content max-width ~1440px, page padding 24px, gap between cards 16px.
- Card radius **12px**, padding 20–24px, background `linear-gradient(180deg, var(--panel), var(--panel-2))`, 1px `--border`, shadow `0 10px 28px rgba(0,0,0,.42)` + inset top light `rgba(255,255,255,.05)`.
- 8pt spacing grid throughout.

## 5. Components

### KPI hero band (legacy camera-wall surface only)
- Wide money card: caps label, hero figure in `--good` (or `--bad` if negative), one plain-English sentence below with bolded subjects; background carries a large soft green area-chart ghost on the right.
- Compact KPI cards: caps label, big number, green delta badge (`▲ 9%` pill on `--good-tint`), smooth **area sparkline** with gradient fill underneath.

### Camera card (LIVE wall)
- Header ON the card, ABOVE the video: station name (semibold 16px) · camera id + location in `--text-dim` (`CAM-01 · Press Bay North`) · red `LIVE` pill right · kebab menu. **Nothing is ever drawn on the video itself.**
- Video: full-bleed inset, 16:9, small radius (8px) inside the card.
- Scoreboard footer BELOW the video: big count left with caption `today · last count 14:31`; smooth area sparkline center (green when healthy, red when behind); right: pace pill `18 AHEAD` (good-tint) / `21 BEHIND` (bad-tint).
- Card state: healthy vs behind expressed via sparkline color + pill only. No colored card borders.

### Alerts table
- Rows: severity triangle icon (red crit / amber warn), time (12px dim), station (semibold), one plain sentence, orange **Watch replay** button (radius 8px, solid `--accent`, dark text), kebab. Section header `ALERTS` + "View all alerts →" link right.

### Replay surfaces
- Viewer: rounded video, centered orange circular play button (white triangle),
  caption bottom-left `PLACEMENT #14 · 12:40:22 · Human consensus`, speed pills
  bottom-right `1× 4× 15× 60×` (active = solid orange).
- Day timeline: hour labels top, green/amber activity heat band, **orange diamond = one verified placement**, white NOW needle with label. Legend line below.
- Chapter cards: real footage thumbnail, time range, `6 PLACED` in `--good` (`0 QUIET` dimmed); active card gets a 1.5px orange outline.

### Job card (legacy; superseded by Owner V2 project verdict rows)
- Left: solid verdict block (green/amber/red gradient, white bold two-line label). Middle: job name (18–20px semibold, sentence case), spec line dim, slim progress bar (radius-full, semantic fill) with a small white `NOW` tick, then ONE sentence: "208 of 400 done — you need 200 by now. Finishes Tuesday morning."
- Right column: caps label `YOU KEEP` / `YOU LOSE`, money figure 32–38px semantic color, caption `of the $1,000 quote · planned $200`.

### Projects (legacy; superseded by Owner V2 History)
- Table: PROJECT / QUOTED / ACTUAL / MARGIN PLAN → REAL / GRADE. Grades = big letter chips (A green, B amber, C/C− red) in tinted circles. Margin column shows `$200 → +$264` with the real value in semantic color.
- Expanded row: daily-output bar chart (semantic green bars, value labels, hairline gridlines, day labels) + orange-accented **NEXT TIME** insight box: quote-calibration sentence with dollar deltas highlighted in orange.

### Charts (all)
- Sparklines/areas: smooth curves with soft gradient fill fading to transparent; no axes on sparklines; endpoint may carry a value label. Bars: rounded-top, value labels above, faint gridlines. Never plain rectangles butted to a baseline with nothing else.

## 6. Interaction states

- Buttons: primary = solid orange, dark text, radius 8px; hover = `--accent-hi`. Secondary = panel bg + border.
- Focus: 2px orange outline, 2px offset, always visible.
- Hover on cards/rows: background lift `rgba(255,255,255,.02)`.
- Motion: LIVE/status LEDs may pulse; respect `prefers-reduced-motion`. Nothing else animates ambiently.

## 7. Hard rules (the taste contract)

1. Title above video, scoreboard below — video is always clean.
2. One plain-English sentence per money verdict. An owner reads any screen in 5 seconds.
3. One number per card is huge; everything else supports it. Max ~3 data points per glance card.
4. Every count is evidence-backed: any count can deep-link to its clip ("Doubt a number? Tap it — watch the clip.").
5. No condensed/stencil type, no caps-lock paragraphs, no glow spam, no second accent hue, no invented brand names.
6. Investor demo and owner product are the SAME skin; a future light "office mode" may be added but never replaces this as default.

## 8. How to use this file

- **Image-engine briefs** must paste §1–§3 tokens + relevant §5 component specs verbatim and name the reference render. Any render that deviates on brand, palette, or type is rejected regardless of prettiness.
- **UI code** (Next.js + shadcn/ui + Tremor) maps tokens 1:1 into CSS variables/Tailwind theme; components implement §5 exactly; lucide icons, stroke 1.75.
- Real data replaces render placeholder content everywhere (real station names, real counts, real footage).

---

## 9. Owner V2 — Approved Visual Contract

### 9.1 Golden references and precedence

All references are 1536×1024 PNGs:

1. `docs/design/owner-v2/01-today-project-pacing.png`
2. `docs/design/owner-v2/02-new-project-setup.png`
3. `docs/design/owner-v2/03-station-workforce.png`
4. `docs/design/owner-v2/04-history-closeout.png`

They are visual acceptance references, not bitmap backgrounds. The production
UI must use semantic HTML, real controls, real charts, accessible text, and real
data. At 1536×1024 the implementation must match their hierarchy, density,
geometry, typography, palette, and status treatment. Generated text rendering
and isolated raster artifacts are not implementation requirements.

When contracts conflict, use this order:

1. Privacy, authorization, and truthful-data requirements.
2. Owner V2 §9 and the four Owner V2 references.
3. The brand, tokens, typography, and evidence components in §§1–8.
4. The older `fv-live-a-approved.png` owner hierarchy.

### 9.2 Shared owner shell

- Reference viewport: 1536×1024. Desktop acceptance screenshots use this exact
  viewport with device scale factor 1.
- Rail: fixed 88px width. Content begins at x=104px, leaving a 16px gutter.
- Header: 64px high with a 1px bottom border. The wordmark stays in the rail
  area or top-left shell; Live state, search, help, and avatar remain right
  aligned.
- Desktop content: `calc(100vw - 104px)` with 12px right inset, 16px grid gaps,
  and no decorative empty bands.
- Owner navigation order: Today, Projects, Stations, Workforce, History,
  Alerts, Settings. Reviewer and internal operations links never appear.
- Major panels: 8px radius, 1px `--border`, panel token background. Repeated
  rows may use 6px radius. Buttons use 7–8px radius.
- Page text never scales with viewport width. Use the §3 type scale and
  tabular numbers.
- Green, amber, and red communicate status only. Orange communicates brand and
  actions only.
- No nested decorative cards, glassmorphism, ornamental gradients, floating
  shapes, or ambient animation.

### 9.3 Today — project pacing first

Golden reference:
`docs/design/owner-v2/01-today-project-pacing.png`.

Desktop grid:

```text
┌──────────────────────────── main: minmax(0, 1fr) ───────────────────────────┬─ 324px ─┐
│ ACTIVE PROJECTS: 3 verdict rows                                             │ ATTENTION│
├──────────────────────────────────────────────────────────────────────────────┤ rail     │
│ ACTUAL VS REQUIRED PACE                                                     │          │
├──────────────────────────────────────────────────────────────────────────────┴──────────┤
│ STATION TABLE                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

- Active-project panel: minimum 252px high. Each project row is 70–72px high.
- Row order: pace status, project/progress, recovery sentence, projected margin,
  deadline, verified-through time.
- Pace status uses large text, not a pill: `BEHIND`, `ON TRACK`, or `AHEAD`.
- The top row may receive a 1px semantic outline when it is the selected project.
- Margin copy is always `Projected margin` followed by `after direct costs`.
- The selected project's pace chart is approximately 292px high and contains:
  actual cumulative units, required cumulative units, NOW line, required-to-
  recover projection, deadline target, and exact actual/required labels.
- Every chart series comes from real records. No synthetic trend values are
  permitted.
- Attention rail is 324px wide and contains exceptions only: verification lag,
  behind pace, camera offline, missing assignment, or disputed counts.
- Station table fills the remaining width and begins immediately below the
  chart. Columns: station/evidence thumbnail, units/hour, output/labor hour,
  current project, status.
- The primary action is `+ Project` in the top-right shell.
- The first five-second read must answer: what is behind, why, what recovery rate
  is needed, and whether direct-cost margin is threatened.

### 9.4 New production project

Golden reference:
`docs/design/owner-v2/02-new-project-setup.png`.

- Opens from `+ Project` as a right-side drawer over the Owner V2 Today screen.
- Desktop drawer: 640px wide, full viewport height, opaque `--bg`/`--panel`
  surface, 1px left border. The page behind is dimmed but remains recognizable.
- Header contains title, close icon, and a three-step progress control:
  `What`, `Where & when`, `Labor & goal`.
- Maximum three steps and a practical completion target under 60 seconds.
- Step 1 fields: project name, customer, target units, value per unit, material
  cost per unit. Total value/total materials may be entered instead, with the
  paired field derived visibly.
- Step 2 fields: station, start date/time, deadline, and shift calendar.
  Detection may preselect a station only as an explicit suggestion with
  confidence and a `Change` action.
- Step 3 fields: assigned team, loaded hourly labor rate, optional target
  margin.
- On step 3, steps 1 and 2 remain visible as compact summaries with Edit links.
- Feasibility panel states: required units/day or hour, station baseline,
  `Feasible`/`Tight`/`Not feasible`, and projected margin after materials and
  direct labor.
- Footer is fixed inside the drawer: secondary `Save draft`, primary orange
  `Start project`.
- Starting a project requires confirmation of any auto-detected station. The
  project clock begins at the configured start time, not creation time.

### 9.5 Station and workforce

Golden reference:
`docs/design/owner-v2/03-station-workforce.png`.

- Context bar: 60px high with station selector, Live state, verified-through
  time, and current project.
- KPI row: four equal columns for verified good units, units/hour, labor hours,
  and output/labor hour. KPI cards are approximately 152px high.
- Main row: `minmax(0, 2fr) minmax(360px, 1fr)`.
  - Left: production by 15-minute interval, required-pace line, NOW marker, and
    explicit downtime bands.
  - Right: clean station camera/evidence image, station state, and cycle time.
- Lower row uses the same column split:
  - Left: team-on-station table.
  - Right: scrap, rework, and downtime summary.
- Team columns: worker, scheduled interval, labor hours, primary role,
  attribution state.
- Default attribution is `Team contribution only`. Individual output may be
  shown only for an explicit badge/check-in interval with one worker present
  and sufficient camera coverage; label confidence on the figure.
- Permanent explanatory copy: "Output is attributed to the station team unless
  a worker was alone and checked in."
- Never use face recognition, worker rankings, comparative leaderboards, or
  silent individual attribution.

### 9.6 History — permanent operational record

Golden reference:
`docs/design/owner-v2/04-history-closeout.png`.

- Filter bar: 60px high. Filters: date range, project, customer, station, shift,
  team, and status. Export is the orange action at right.
- Summary row: four equal columns, approximately 128px high: projects completed,
  on-time percentage, units/labor hour, and margin after direct costs.
- Main surface is a dense table, not a card grid.
- Columns: project, customer, completed date, units plan→actual, labor
  plan→actual, materials plan→actual, margin plan→actual, on-time result, grade.
- Standard rows are 56–60px high. The selected row uses orange project text and
  expands inline.
- Expanded closeout has three columns:
  1. plan/actual/variance table,
  2. honest weekly output chart,
  3. append-only audit trail.
- Closeout metrics: units, schedule duration, labor cost, materials cost, and
  margin after direct costs.
- Closed records remain fixed. Corrections append an audit entry with timestamp,
  actor type, prior value, and new value.
- `Evidence clips N` opens only clips attached to records or exceptions. History
  is not a raw-footage browser.

### 9.7 Terminology and truthful states

- Never label direct-cost contribution as profit. Use `Margin after direct
  costs` or `Projected margin after direct costs`.
- The calculation is production value minus material cost minus direct labor.
  State that overhead, indirect labor, rent, freight, taxes, and other expenses
  are excluded.
- Pace math evaluates through `verified_through_at`, not wall-clock now.
- Provisional AI output is visually separate and never included silently in a
  verified total.
- Verification lag receives a visible attention state before it can cause a
  false `BEHIND` verdict.
- Good units exclude verified scrap and duplicate rework.
- Downtime and non-working shift hours pause expected-production accumulation.
- Every owner count links to supporting evidence or a clear reason evidence is
  unavailable.
- Owners never see reviewer identities, votes, model shadow verdicts, tripwire
  scores, reviewer qualification, or labeling controls.

### 9.8 Required interaction states

- Project row: select project and update the pace chart without navigation.
- `+ Project`: open the setup drawer and retain draft state between steps.
- Attention item: open the relevant project, station, or evidence clip.
- Station row/KPI/chart point: open station detail or evidence at that time.
- History filters: URL-addressable and preserved on back navigation.
- History row: expand inline; only one closeout row is expanded at a time.
- Evidence clip: open the global ClipDrawer; closing returns focus to the
  invoking control.
- Loading uses stable skeleton geometry. Empty, offline, pending, lagged,
  disputed, and error states must not collapse the page layout.
- Every interaction supports keyboard use and has a visible focus state.

### 9.9 Responsive contract

- Desktop ≥1280px: match the golden references.
- Tablet 768–1279px: collapse the rail to icons, stack the attention rail below
  active projects, use two KPI columns, and retain horizontally scrollable
  tables with frozen first column.
- Mobile <768px: show project verdict list first. Project detail contains pace,
  recovery sentence, margin, and attention items. Camera wall, complex station
  chart, history comparison table, replay timeline, and settings are not
  squeezed into the first view.
- New Project becomes a full-screen sheet on mobile with one step per screen and
  a fixed action footer.
- No font size is computed from viewport width. Controls remain at least 44px
  tall on touch layouts.

### 9.10 Visual and behavioral acceptance

Each screen is incomplete until all applicable gates pass:

1. Playwright screenshot at 1536×1024 with the approved deterministic fixture.
2. Side-by-side and 50% opacity overlay against its golden PNG.
3. Exact token comparison for colors, typography, spacing, borders, and radii.
4. Geometry within 4px of the reference for shell, major panels, rows, and
   controls. Generated glyph anti-aliasing is excluded from raw pixel scoring.
5. No clipped text, overlap, layout shift, fabricated chart points, or
   unlabelled provisional data.
6. Desktop, tablet, and mobile screenshots inspected visually.
7. Keyboard navigation, focus order, contrast, and accessible names verified.
8. Unit tests cover pace, verification lag, downtime, scrap/rework, labor,
   materials, and margin calculations.
9. End-to-end tests cover project creation, station assignment, Today status,
   history closeout, correction audit, and evidence opening.
10. Production URL opened after forced deployment; expected content,
    interactions, network requests, and console logs verified before release.
