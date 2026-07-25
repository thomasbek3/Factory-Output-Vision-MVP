# FactoryVision — Design System (LOCKED)

**Source of truth:** the approved render `fv-live-a.png`
(`~/.gstack/projects/thomasbek3-Factory-Output-Vision-MVP/designs/owner-console-20260705/fv-live-a.png`),
approved by Thomas 2026-07-05 ("A. thats it").
Every screen, mockup, render brief, and line of UI code follows THIS file. When in doubt, open the render.

Product surfaces: **LIVE** (camera wall) · **REPLAY** (DVR + placement markers) · **TODAY** (jobs + stations) · **PROJECTS** (job history + quote calibration).

**Verification-copy amendment (2026-07-25):** the visual contract remains
locked, but verification copy must state its source and verified-through time.
Never claim live human verification or `100% HUMAN+AI` unless production data
proves both claims. This amendment is required by
`docs/specs/worker_ground_truth_portal_v1.md`.

---

## 1. Brand

- Wordmark: **Factory** in white + **Vision** in accent orange. Always "FactoryVision", never any other name.
- Logo mark: minimal orange "F" glyph in a rounded square, top of the nav rail.
- Product line under nothing — no taglines in the app chrome.
- Voice: plain English a factory owner reads in one pass. Money verdicts as sentences: "You're in the green — but Alvarez Gates is losing money." Verdict labels: `IN THE GREEN` / `GETTING TIGHT` / `LOSING MONEY`. Trust line everywhere: "Verification source and through-time are shown with every resolved count."

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
--good:        #46C26B;   /* profit green, AHEAD */
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
- Glow is allowed ONLY on: the hero money figure (soft green bloom) and LIVE/status LEDs. Nothing else glows.

## 3. Typography

- **UI face:** Inter (build) / clean neutral grotesque (renders). NO condensed faces, NO stencil, NO letter-spaced-caps body text.
- Caps usage: ONLY small section labels (`PROJECTED PROFIT (TODAY)`, `UNITS VERIFIED TODAY`, `ALERTS`) at 11–12px, weight 600, letter-spacing 0.06em, color `--text-dim`.
- Numbers: semibold (600–700), `font-variant-numeric: tabular-nums`, tight letter-spacing (-0.01em). Hero money ~56–64px; camera-card counts ~36–40px; KPI values ~28–32px.
- Body/captions: 13–14.5px sentence case, `--text-mut`. Timestamps and IDs 11–12px `--text-dim` (regular sans, NOT monospace-everywhere; small mono is allowed only for clock/timestamps).
- Minimum text size anywhere: 11px. Minimum contrast: secondary text ≥ 4.5:1 on panels.

## 4. Layout & chrome

- **Left nav rail:** ~88px wide, `--bg-rail`, icon + 11px label stacked, items: Overview, Cameras, Lines, Counts, Replay, Alerts (with count badge), Reports, Settings; Collapse at bottom. Active item = orange icon + orange label + soft orange left-edge indicator.
- **Top header:** wordmark left; right side: Live status pill (green dot + "Live" + chevron), global search field with ⌘K hint, help icon, avatar. Header height ~64px, hairline bottom border.
- Content max-width ~1440px, page padding 24px, gap between cards 16px.
- Card radius **12px**, padding 20–24px, background `linear-gradient(180deg, var(--panel), var(--panel-2))`, 1px `--border`, shadow `0 10px 28px rgba(0,0,0,.42)` + inset top light `rgba(255,255,255,.05)`.
- 8pt spacing grid throughout.

## 5. Components

### KPI hero band (top of every tab)
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
- Viewer: rounded video, centered orange circular play button (white triangle), caption bottom-left `PLACEMENT #14 · 12:40:22 · Verified by M. Reyes`, speed pills bottom-right `1× 4× 15× 60×` (active = solid orange).
- Day timeline: hour labels top, green/amber activity heat band, **orange diamond = one verified placement**, white NOW needle with label. Legend line below.
- Chapter cards: real footage thumbnail, time range, `6 PLACED` in `--good` (`0 QUIET` dimmed); active card gets a 1.5px orange outline.

### Job card (TODAY)
- Left: solid verdict block (green/amber/red gradient, white bold two-line label). Middle: job name (18–20px semibold, sentence case), spec line dim, slim progress bar (radius-full, semantic fill) with a small white `NOW` tick, then ONE sentence: "208 of 400 done — you need 200 by now. Finishes Tuesday morning."
- Right column: caps label `YOU KEEP` / `YOU LOSE`, money figure 32–38px semantic color, caption `of the $1,000 quote · planned $200`.

### Projects
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
