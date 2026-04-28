# ROADMAP — Factory Vision Output Counter → Factory Intelligence Platform

This is the master product roadmap from MVP to full autonomous factory management.

---

## Philosophy

Start with a camera on a shelf counting parts.
End with an operating system that runs the factory.
Every version earns the trust required for the next one.

---

## The Full Vision

```
v1.0   Count parts                          ← camera on a shelf
v1.5   Count parts accurately               ← add beam sensor
v2.0   Understand why things go wrong        ← OEE, downtime reasons
v3.0   See what humans can't                 ← custom ML, defect detection
v4.0   Manage from anywhere                  ← cloud fleet
v5.0   Talk to your factory                  ← natural language copilot
v5.5   Predict before it breaks              ← predictive intelligence
v6.0   Learn from every factory              ← cross-factory network
v7.0   Sense everything                      ← sensor ecosystem, digital twin lite
v8.0   Guide decisions + optimize energy     ← decision support, cobot integration
v9.0   See the industry                      ← supply chain pulse, auto-ordering alerts
v10.0  Supervise the line                    ← system acts, humans override
v11.0+ Run the factory                       ← full autonomy (5-10 year horizon)
```

**The pitch at each stage:**
```
v1.0   "Know when your line stops"
v1.5   "Know when, with exact counts"
v2.0   "Know why your line stops"
v3.0   "Catch what humans miss"
v4.0   "See every factory from anywhere"
v5.0   "Ask your factory a question"
v5.5   "Know before it breaks"
v6.0   "Your factory learns from every factory"
v7.0   "Feel every vibration, every watt, every degree"
v8.0   "The system tells you what to do — and guides your robots"
v9.0   "See what's happening across the entire industry"
v10.0  "The system runs the line. You approve."
v11.0  "The factory runs itself."
```

**Cost to the factory at every stage:**
- Hardware: $500-1,000 (edge PC + camera + optional beam + optional sensors)
- Software: $49-299/mo per line
- vs. millions for Siemens/Rockwell MES + Cognex vision + cobot integration + SCADA

---

## v1.0 — Camera-Only MVP (current build)

**Goal:** Prove that vision-based counting works on real factory lines, including representative source→output delivery workflows where parts can be picked up, repositioned, and partially occluded by workers.

**What it does:**
- Camera watches conveyor, counts parts crossing a line
- Detects stops (zero output), drops (rate decline), operator absent (optional)
- Local web UI, 15-minute setup, no CLI
- Runs on $200 Ubuntu edge PC + Reolink IP camera
- SQLite storage, 90-day retention
- Camera mounting guide in wizard to prevent bad installs
- Calibration with auto-detected blob size and confidence warning

**What it proves:**
- CV accuracy on easy conveyor lines
- Source-token counting works for source→output deliveries on representative footage
- Resident/repositioned output parts do not double-count
- Every count/suppression has auditable evidence receipts
- Setup flow works for non-technical users
- Anomaly detection catches real events
- System runs stable for 8+ hours

**Hardware:** ~$200-260 (edge PC + camera)
**Pricing:** $49/line/mo
**Ship when:** First factory pilot runs a full shift with usable data.
**Success metric:** Count accuracy ≥ 90% on easy lines, zero audited double-counts from resident/repositioned output parts in the proof clips, at least one end-to-end representative footage eval report with accepted/suppressed/uncertain decisions and receipts, and zero crashes in 8 hours.

---

## v1.5 — Beam + Camera (accuracy upgrade)

**Goal:** Achieve deterministic counting accuracy while keeping camera intelligence.

**What it adds:**
- Optional USB photo-eye beam sensor for counting ($20-30)
- Arduino/ESP32 serial bridge ($5-10) reads beam breaks, sends to edge PC
- Camera shifts from counter to intelligence layer
- Dual mode: vision-only or beam+vision, selected in wizard
- Beam provides 99.99% count accuracy
- Camera provides: stop/drop visual confirmation, operator detection, snapshot timeline, jam/backup detection
- Vision processing drops to 2-5 FPS in beam mode (frees CPU)
- Count Accumulator abstraction makes both modes use same downstream logic
- Custom YOLO model training pipeline: Roboflow labeling + Google Colab fine-tuning per customer (~1 hour from footage to counting). Deploys via FC_YOLO_MODEL_PATH env var with zero code changes.

**What it proves:**
- Product works for accuracy-demanding factories
- Hardware kit is simple enough to self-install
- Beam + camera combo is more valuable than either alone

**Hardware:** ~$250-320 (edge PC + camera + beam kit)
**Pricing:** $49/line/mo
**Ship when:** v1.0 has run in at least 1 factory and accuracy gaps are quantified.
**Success metric:** Count accuracy ≥ 99.5% with beam. Camera anomaly detection adds value beam alone cannot provide.

---

## v2.0 — Intelligence Platform (post-funding)

**Goal:** Become the factory intelligence system that matches Vorne's analytics at 1/10th the price.

**What it adds:**

### OEE Metrics Engine
All derived from beam/vision count timestamps + user-configured ideal cycle time + shift schedule:
- Full OEE calculation (Availability × Performance × Quality)
- Ideal cycle time configuration per product/SKU
- Shift scheduling (multiple shifts, break windows)
- Target vs. actual tracking with projected end-of-shift
- Performance loss detection (slow cycles, micro-stops)
- Availability loss detection (categorized downtime)
- Six Big Losses breakdown
- TEEP (Total Effective Equipment Performance)
- MTBF / MTTR calculations

### Downtime Reason Tagging
- When line stops, UI prompts operator: "What happened?"
- Preset categories: material jam, changeover, break, maintenance, upstream starve, other
- Custom categories per factory
- Downtime Pareto reporting (top reasons by time lost)

### Shift Reports & Dashboards
- Automated end-of-shift email/notification
- Shift comparison dashboards
- Trend charts: OEE by day/week/month
- Target vs. actual historical views

### In-App Model Training UI
- Built-in labeling interface: user clicks on parts in frames ("this is a part")
- System auto-extracts frames from production footage
- Background model training triggered from web UI
- Eliminates external Roboflow/Colab step for customer onboarding

### Visual Timeline
- Camera captures snapshot on every state change (stop, drop, recovery)
- Browsable timeline: "What was happening at 2:14pm?"
- Annotated event history with frames

### Multi-Line Dashboard
- Single web UI showing all lines in a factory
- Andon-style overview: green/yellow/red per line
- Aggregated factory-level metrics

**Pricing tiers introduced:**

| Plan | Monthly | What's included |
|------|---------|-----------------|
| Counter | $49/line | Counting, stop/drop, operator zone, basic dashboard |
| Intelligence | $99/line | + OEE, shift reports, downtime Pareto, target tracking, visual timeline |
| Factory | $199/line | + multi-line dashboard, alerts, API access, priority support |

**Ship when:** v1.5 has proven accuracy. Capital raised. 3+ factories running.
**Success metric:** Factory managers use OEE data to make real decisions. Upgrade rate from Counter to Intelligence tier > 30%.

---

## v3.0 — Machine Learning Layer (post-traction)

**Goal:** Use collected factory data to build custom models that handle hard cases.

**What it adds:**
- Custom YOLO models trained on real factory footage collected from v1/v1.5 deployments
- Handle hard cases: shiny parts, overlapping products, irregular shapes
- Per-factory or per-product-type models
- Model versioning and A/B testing on edge
- Reject/defect detection via vision (completes OEE quality factor)
- Predictive end-of-shift output based on current trajectory

**Training pipeline:**
- Cloud-based model training (Vertex AI / PyTorch / Ultralytics)
- Edge inference stays local (ONNX runtime on CPU)
- Factory footage upload (opt-in) for model improvement
- Federated learning across sites (aggregate patterns without sharing raw data)

**Enterprise tier introduced:** $299+/line

**Ship when:** 10+ factories generating enough video data for training sets.
**Success metric:** Custom models improve accuracy on hard cases by 15%+. Defect detection catches real quality issues.

---

## v4.0 — Fleet & Platform

**Goal:** Multi-factory management without integrators.

**What it adds:**
- Cloud fleet dashboard (opt-in, not required for core functionality)
- Remote configuration and monitoring
- Cross-factory benchmarking (your own factories)
- API for ERP/MES integration (REST + webhooks)
- Multi-camera per line support
- Mobile app for plant managers (iOS/Android)
- Alert routing (SMS, Slack, email, PagerDuty)
- White-label / OEM licensing option

**Ship when:** 20+ factories. Need for remote management becomes pain point.
**Success metric:** Plant managers check factory status from phone daily.

---

## v5.0 — Factory Copilot

**Goal:** Plant manager talks to the factory, gets answers in plain language.

**What it adds:**
- Natural language query interface on local data
- Small local LLM running on edge box (no cloud required for queries)
- Queries structured factory data (counts, events, OEE, downtime reasons, trends)

**Example queries:**
- "Why did Line 3 drop yesterday afternoon?"
- "Which shift has the most changeover time this month?"
- "What's my worst performing line this week and why?"
- "If we keep running at this rate, will we hit our order by Friday?"
- "Show me every time we had a material jam on Line 2 in the last 30 days"
- "Compare this week's OEE to last week"

**Why this matters:**
- Plant managers don't want to learn dashboards. They want answers.
- Data is already local in SQLite. LLM just queries it.
- Feels like magic. Costs almost nothing to run.

**Ship when:** v2.0+ data is rich enough to answer meaningful questions.
**Success metric:** Plant managers use copilot daily instead of opening reports.

---

## v5.5 — Predictive Intelligence

**Goal:** Catch problems before they become problems.

**What it adds:**
- Pattern-based stop prediction: "Line 2 usually stops within 20 minutes when it shows this rate decay pattern. Alert now."
- Shift outcome projection: "At current rate, this shift will end 12% under target. Consider checking station 3."
- Maintenance correlation: "Every time changeover exceeds 15 minutes on this line, the next 2 hours have 30% more micro-stops."
- Degradation curve detection: gradual performance decline over days/weeks triggers early warning
- All based on statistical models trained on your own historical data

**No external data needed. No expensive training. Just pattern matching on collected counts, timestamps, and reason codes.**

**Ship when:** Enough historical data from 20+ factories to validate prediction patterns.
**Success metric:** Predictions are actionable and accurate > 70% of the time.

---

## v6.0 — Cross-Factory Intelligence Network

**Goal:** Intelligence no single factory could build alone.

**What it adds:**
- Anonymous benchmarking: "Your packaging line runs at 78% OEE. Similar lines across our network average 84%. Here's what top performers do differently."
- Anomaly pattern sharing: "A new failure pattern was detected across 3 factories using similar equipment. Your line shows early signs."
- Seasonal/demand intelligence: "Factories in your vertical typically see 15% output drops in Q4 due to material supply."
- Best practice recommendations derived from network-wide data
- No factory sees another factory's data. Everything is aggregated anonymously.

**Why this is the moat:**
Network effect — the more factories on the platform, the smarter every box gets. No competitor can replicate this without matching your install base.

**Ship when:** 50+ factories generating diverse data.
**Success metric:** Benchmarking insights drive measurable improvement at participating factories.

---

## v7.0 — Sensor Ecosystem + Digital Twin Lite

**Goal:** Sense everything on the factory floor beyond just vision.

**What it adds:**
- Third-party sensor integration via edge box:
  - Temperature sensors (~$10-15 each)
  - Humidity sensors (~$10 each)
  - Vibration sensors (~$20-30 each)
  - Power monitoring clamps (~$15-25 each)
  - Noise level sensors (~$15 each)
- All sensors connect via USB, I2C, or wireless to the edge box
- Sensor data correlated with production data in real-time
- Digital twin lite: simple real-time model showing line state vs. expected state
- API marketplace for ERP/maintenance/scheduling tools to pull data

**Power monitoring specifically unlocks:**
- Energy cost per unit produced
- Machine efficiency comparison (Line 3 uses 40% more power per unit than Line 1)
- Shift scheduling optimized around time-of-use electricity pricing
- Sustainability/ESG reporting (increasingly required by large buyers)

**Ship when:** Sensor costs drop enough and customer demand for environmental monitoring increases.
**Success metric:** Sensor data prevents at least 1 unplanned downtime event per factory per month.

---

## v8.0 — Decision Support + Cobot Integration + Energy Optimization

**Goal:** The system tells humans and robots what to do. Humans approve.

### Decision Support Mode
The system suggests actions. Humans (or cobots) execute.
- "Batch target reached on Line 2. Begin changeover." → operator taps confirm
- "Maintenance pattern detected on Line 4. Schedule by Friday." → pushes work order to CMMS (Fiix, UpKeep, MaintainX) via API
- "Line 1 down. Lines 2 and 4 have capacity headroom. Suggested rebalance plan:" → manager approves
- "Energy cost spiking in peak window. Suggest shifting Line 3 to next hour." → manager approves

### Cobot Integration Layer
You don't build robots. You become the eyes and brain that robots plug into.
- Your camera already watches the line. Your intelligence engine already knows what's happening.
- Cobot vendors (Universal Robots, FANUC, ABB, Doosan) all have APIs and integration protocols.
- Integration examples:
  - Camera detects jam/backup → signals upstream cobot to pause placement
  - System detects output drop → triggers cobot to adjust cycle speed
  - Operator-absent detection fires → cobot switches to safe/slow mode
  - Quality detection (v3.0) spots defect pattern → cobot adjusts grip/placement
- You are the cobot's situational awareness. It knows how to move. You tell it what's happening.

### Energy Optimization
- Correlate power consumption with output rate across all lines
- Detect machines running inefficiently before they fail
- Recommend shift scheduling around electricity pricing
- Generate sustainability reports

**Key hardware for this version:**
- Modbus/Ethernet gateway ($50-100) — lets edge box talk to industrial equipment (VFDs, PLCs, conveyors)
- This single device bridges monitoring → control

**Ship when:** Factories have enough trust in system intelligence (typically 6-12 months of v5-v7).
**Success metric:** Decision suggestions are followed > 60% of the time. At least 1 cobot integration deployed.

---

## v9.0 — Supply Chain Pulse + Auto-Ordering Alerts

**Goal:** See what's happening across the entire industry and predict supply disruptions.

### Supply Chain Pulse
Your boxes are counting output across hundreds of factories in the same verticals. You know — anonymously and in aggregate — what production looks like in real time.
- Factory sees: "Industry-wide output dropped 12% this week across similar lines — likely ingredient supply disruption"
- Buyers/distributors subscribe to anonymized output indices to predict supply availability
- You've built a Bloomberg Terminal for factory output

### Material Consumption Tracking
- System knows output rate and units-per-material ratio (configured by operator)
- Tracks material consumption in real time
- "At current rate, you'll run out of packaging material in 6.5 hours"
- Sends reorder notification to supplier via email/webhook/API
- Integrates with procurement/ERP system if available

**Ship when:** 100+ factories. Supply chain data becomes statistically meaningful.
**Success metric:** Material stockout alerts prevent at least 1 production interruption per factory per quarter.

---

## v10.0 — Supervised Autonomy

**Goal:** The system acts within approved boundaries. Humans can override.

**Prerequisite:** Factories must have modern-ish equipment with network-accessible controllers. Modbus gateway from v8.0 is already in place.

### What the system can now do (with human-approved limits):

| Action | Physical integration needed | Trust level required |
|--------|---------------------------|---------------------|
| Auto-adjust conveyor speed within approved range | Modbus/Ethernet to VFD controller | Very high (months of proven suggestions) |
| Auto-push work orders to CMMS on maintenance pattern | API to maintenance software | Medium (proven in v8 suggestion mode) |
| Auto-send reorder notifications on material threshold | Supplier email/API + inventory tracking | Medium |
| Auto-trigger changeover notification when batch target met | Webhook to scheduling system | Low-medium (just a notification) |
| Auto-rebalance scheduling across lines | Deep PLC + scheduling integration | Very high (suggestion mode proven first) |

### How it works technically:
- Each autonomous action has a confidence threshold configured by the plant manager
- System only acts when confidence exceeds threshold
- All actions logged with full audit trail
- "Override" button on dashboard instantly reverts any autonomous action
- Daily summary: "Here's what the system did today and why"

### The trust progression:
```
v1-v7:   System watches and reports       → "I see what's happening"
v8:      System suggests actions           → "Here's what I think you should do"
v10:     System acts within boundaries     → "I did this. Here's why. You can undo it."
```

**Ship when:** Multiple factories have run v8 decision support for 6+ months with high follow-through rate.
**Success metric:** Autonomous actions improve throughput by 5%+ with zero safety incidents.

---

## v11.0+ — Full Autonomous Factory Management (5-10 year horizon)

**Goal:** The factory runs itself. Humans handle exceptions and strategy.

**What this looks like:**
- System manages production schedule end-to-end
- Automatic changeover sequencing based on order queue
- Predictive maintenance prevents 90%+ of unplanned stops
- Material ordering is fully automated with supplier APIs
- Energy usage optimized continuously
- Quality inspection catches defects in real-time and adjusts process
- Cobots receive real-time task assignments based on line conditions
- Cross-factory network optimizes production allocation across multiple sites

**Requirements:**
- Factory has modern PLCs with network APIs
- Full sensor suite (v7.0) deployed
- Years of proven decision-making track record from v8-v10
- Deep ERP/MES integration
- Regulatory approval for autonomous operation in some jurisdictions

**This is Siemens/Rockwell territory — except you got there from a $500 box instead of a $5M platform deployment.**

---

## Pricing Evolution

| Version | Counter | Intelligence | Factory | Enterprise |
|---------|---------|-------------|---------|------------|
| v1.0-1.5 | $49/line/mo | — | — | — |
| v2.0 | $49 | $99 | $199 | — |
| v3.0+ | $49 | $99 | $199 | $299+ |
| v8.0+ | $49 | $99 | $199 | Custom |

Volume discounts at every tier:
- 1-3 lines: full price
- 4-9 lines: 10% off
- 10+ lines: 20% off

---

## Revenue Trajectory

| Year | Version | Factories | Avg lines | Avg $/line/mo | ARR |
|------|---------|-----------|-----------|---------------|-----|
| Year 1 | v1.0-1.5 | 10 | 3 | $49 | $17,640 |
| Year 2 | v2.0 | 50 | 4 | $59 mix | $141,600 |
| Year 3 | v2.0-3.0 | 200 | 5 | $79 mix | $948,000 |
| Year 4 | v3.0-4.0 | 500 | 5 | $99 mix | $2,970,000 |
| Year 5 | v4.0-5.0 | 1,000 | 6 | $119 mix | $8,568,000 |
| Year 7 | v6.0-8.0 | 3,000 | 6 | $149 mix | $32,184,000 |
| Year 10 | v9.0-10.0 | 10,000 | 7 | $179 mix | $150,360,000 |

---

## Market Size Reference

| Metric | Number |
|--------|--------|
| Total US manufacturing businesses | ~608,000 |
| Small manufacturers (<500 employees) | ~596,000 (98%) |
| Employer manufacturers (with workers) | ~239,000 |
| In target verticals with production lines | ~40,000-60,000 |
| Using no specialized software at all | ~62% of small businesses |
| Global estimate | 5-10x US numbers |

---

## Hardware Cost at Each Stage

| Version | What's on the edge box | Our cost | Sell price |
|---------|----------------------|----------|------------|
| v1.0 | Edge PC + IP camera | ~$215-265 | $499 |
| v1.5 | + beam sensor + Arduino bridge | ~$250-320 | $599 |
| v7.0 | + temp/humidity/vibration/power sensors | ~$300-400 | $699-799 |
| v8.0 | + Modbus/Ethernet gateway | ~$350-500 | $799-999 |

Hardware stays under $1,000 at every stage. The intelligence is in the software.

---

## Competitive Moat Progression

| Stage | Moat type | Why competitors can't copy easily |
|-------|-----------|----------------------------------|
| v1-2 | Price + simplicity | Incumbents can't go this cheap without cannibalizing |
| v3 | Collected data | Your factory footage trains models competitors don't have |
| v4-5 | User lock-in | Copilot + fleet management = switching cost |
| v6 | Network effect | More boxes = smarter network. Can't replicate without install base |
| v7-8 | Integration depth | Sensor + cobot + ERP integrations create stickiness |
| v9 | Data asset | Industry output indices are unique and proprietary |
| v10+ | Trust | Years of proven autonomous decisions can't be fast-followed |

---

## What We Never Build

- Full MES/ERP replacement (we integrate, not replace)
- General-purpose AI/ML platform
- Custom integrator services (we sell product, not projects)
- Proprietary cameras or sensors (always commodity hardware)
- Robots (we guide them, we don't build them)

---

## The One-Sentence Version

We start with a $500 box that counts parts on a conveyor belt, and we end with a factory operating system that runs the entire production floor — and at every step, we cost 1/10th of the incumbents.

---
