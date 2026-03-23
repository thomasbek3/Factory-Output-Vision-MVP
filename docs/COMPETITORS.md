# COMPETITORS — Positioning and What We Are NOT Building

---

## The market splits into 3 worlds

### 1) Industrial machine vision hardware (Enterprise)
Examples:
- Cognex ($5K–$50K+ per station, 4.5M+ installs)
- Keyence ($5K–$30K+ per station)
- Omron ($3K–$20K+)
- SICK ($3K–$20K+)
- Custom integrators like ScienceSoft, Abto ($150K–$400K+)

Strengths:
- Extremely robust inspection
- Industrial IO / PLC integration
- Deterministic setups

Weakness:
- Not plug-and-play for a small shop in 15 minutes
- Often requires integrators, lighting, triggers, and tuning
- Priced 10–100x above our target

### 2) MES / OEE / MOM platforms
Examples:
- Siemens / Rockwell / Plex (enterprise licensing)
- Guidewheel (SaaS, clamp-on power sensor, cloud required)
- MachineMetrics (SaaS, requires PLC/API integration)
- Tulip (SaaS, tablet-based operator data entry)
- Autodesk Fusion Operations / Prodsmart (SaaS, manual entry)

#### Vorne XL (closest competitor, detailed)
- Price: $3,990–$4,990 per unit (one unit per machine)
- No monthly fees. No recurring costs. No user charges.
- Free software updates. Free technical support. 3-year warranty.
- 42,000+ installations in 45+ countries
- 92.8% trial-to-purchase conversion rate
- Cloud layer (XL Enterprise) is optional and mostly free
- Sensor-based only: wires to photo-eye, proximity switch, or encoder
- 140+ metrics, 60+ built-in reports, OEE, TEEP, Six Big Losses
- Cannot see the line (no camera, no vision)
- Cannot detect operator presence/absence
- Cannot provide visual context for why output dropped
- Cannot detect jams, backups, or line conditions visually

Strengths:
- Great dashboards and enterprise reporting
- Vorne has excellent ease-of-install reputation and proven market traction
- 50+ years of trust in manufacturing

Weakness:
- Vorne requires physical sensor wiring — it cannot "see" the line
- MES/OEE platforms require process adoption and integrations
- None are "one camera + one box + one screen"
- None offer operator-absent detection
- None provide visual timeline for troubleshooting

### 3) Developer CV/Edge AI platforms
Examples:
- Edge Impulse (ML model training + edge deploy)
- Roboflow (dataset management + model training)
- OpenMV ($65–$85, microcontroller, hobbyist grade)
- PTZOptics Detect-IT (AI model builder, requires building your own models)

Strengths:
- Powerful developer tools

Weakness:
- Not for blue-collar shops
- Requires ML lifecycle / engineering

### 4) Dumb counter displays
Examples:
- Chinese LED boards (Cosycom, Sunpn: $50–$300)
- Impec Solutions ($100–$500)

Strengths:
- Cheap, simple, proven in garment/packaging factories

Weakness:
- Zero intelligence. No stop/drop/operator detection.
- No historical data, no web access, no alerts.

---

## Differentiation wedge (this product)
"One camera. One box. One screen. 15 minutes."

We win by:
- No integrator
- No PLC
- No cloud
- No training
- Clear troubleshooting
- Operator-absent detection (unique in this price tier)
- Uses existing IP cameras (no proprietary hardware)

---

## Our dual-mode advantage (v1.5)
Vorne: beam-only (blind counting, no visual context)
Us: camera-only (v1.0) OR beam + camera (v1.5)

With beam + camera:
- Same deterministic count accuracy as Vorne
- Plus: operator detection
- Plus: visual timeline (what was happening when output dropped?)
- Plus: jam/backup detection
- Plus: snapshot-based troubleshooting
- At 1/8th to 1/10th the price per line

---

## What NOT to build (avoid platform creep)

### Never build:
- Full MES/ERP features
- Deep inspection/metrology
- General-purpose edge AI tooling
- Custom integrator services

### Not in v1.0:
- Beam sensor support (v1.5)
- OEE metrics engine (v2.0)
- Downtime reason tagging (v2.0)
- Shift reports (v2.0)
- Multi-line dashboard (v2.0)
- Custom ML models (v3.0)
- Cloud fleet management (v4.0)

See ROADMAP.md for the full phased plan.

---

## Best first verticals (high success likelihood)
- Packaging / bagging / boxing conveyors
- Labeling / printing output lines
- Injection molding outfeed conveyors
- Metal stamping outfeed
- Food packaging lines
- Bottling / canning lines

Avoid for MVP:
- chaotic pile flow
- high-speed tiny parts
- extremely reflective metal with flicker
- transparent product on transparent conveyor

---
