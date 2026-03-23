# FUNDING — $500K Seed Round Deployment Plan

---

## 1) Founder Arrangement

Two co-founders. Zero salary for both during seed stage. This stretches runway and signals commitment to investors.

- **Founder 1 (Thomas):** Product, UI/UX (built with AI tools), coding v1.0, vision, investor relations
- **Founder 2 (Partner):** Sales, operations, finance, factory relationships, customer success

Founders take salary only when revenue hits $25K+ MRR or Series A closes, whichever comes first.

---

## 2) Hires

### Hire #1 — Lead Engineer ($190K)

**Title:** Lead Engineer

**Profile:**
- 6-10 years experience, likely age 28-35
- Has shipped production edge systems, IoT, or industrial software
- Python + OpenCV + Linux + FastAPI (or similar)
- Comfortable with hardware-software integration (serial, USB, sensors)
- Uses AI coding tools daily (Claude Code, Cursor, Copilot) — non-negotiable
- Ideally Georgia-based (Atlanta area) for weekly in-person days
- Georgia Tech grad pipeline or alumni of Flock Safety, NCR, Delta tech, Home Depot tech, or similar Atlanta companies

**Compensation:**
- $190,000 salary + standard benefits
- 2% equity, 4-year vest, 1-year cliff
- All dev tools paid (Claude Max, Claude Code, Cursor, GitHub, etc.)

**Working arrangement:**
- Remote with 1x/week in-person at WeWork (Atlanta or Gainesville area)
- Factory visits 2-3x/month during pilot phase
- Daily Loom demos showing what shipped
- Weekly test plan runs against BUILD_PLAN milestones

**What they own:**
- Entire technical stack from prototype to production
- Hardening v1.0, building v1.5, architecting v2.0
- .deb packaging, systemd deployment, 8-hour stability
- Reconnect logic, threading, SQLite persistence, edge cases
- Grows into VP Engineering / CTO as team scales

**Where to find them:**
- Georgia Tech alumni job boards and Slack communities
- Atlanta Tech Village network
- Flock Safety / NCR / Bakkt / Greenlight / OneTrust alumni
- TAG (Technology Association of Georgia) events and meetups
- Python, OpenCV, and embedded Linux open-source communities on GitHub
- Direct outreach on LinkedIn targeting Atlanta-based senior engineers at IoT/edge companies

**The pitch to them:**
"You're employee #1 on engineering at a company building the factory intelligence platform that makes Vorne obsolete. Full ownership of the technical stack. 2% equity. The roadmap goes from a counting box to an autonomous factory operating system. If this works, you're the CTO."

**How to validate them (you don't need to read code):**
- Daily Loom demos: 2-3 min video showing what they built, running live
- Weekly test plan runs: you open a browser and test the product yourself
- Git commits: daily commits with descriptive messages
- Claude as code reviewer: paste their code into Claude weekly, ask "is this production quality?"
- Factory floor test: if it runs for 8 hours in a real factory, the code is solid
- Health metrics: check /api/diagnostics/sysinfo yourself — reader alive, vision loop alive, last frame age
- BUILD_PLAN milestones are pass/fail — either the thing works or it doesn't

**Red flags:**
- "Setting up architecture" for 2+ weeks with no working demo
- One commit on Friday that says "updates"
- Adding Docker, Kubernetes, Redis, or anything not in the spec
- Can't show something working every single day
- Doesn't use AI tools without being reminded

**Protection:**
- 1-year cliff means zero equity if they leave or are fired before month 12
- Daily demos and weekly test runs mean you know within 2-3 months if they're performing
- At-will employment in Georgia — you can fire fast if milestones aren't shipping

**Start:** Month 1

---

### Hire #2 — Field Sales / Technical Installer ($80K + commission)

**Title:** Field Sales Engineer

**Profile:**
- Manufacturing background, technically curious
- Comfortable on a factory floor AND with a laptop
- Former field service engineer, applications engineer, or technical sales rep from industrial equipment company
- Doesn't need to code — needs to install a box, train a plant manager, and close a deal
- Southeast US based (ideally Georgia, Alabama, Tennessee, Carolinas)
- Owns a car and is willing to drive to factories

**Compensation:**
- $80,000 base salary
- Commission: 10-15% of first-year contract value per factory closed
- 0.5-1% equity, 4-year vest, 1-year cliff

**What they own:**
- Factory outreach, pilot scheduling, and installations
- On-site training for plant managers
- Ground-truth data collection (manual count vs. system count)
- Test video library (recording real factory footage for regression testing)
- Customer feedback loop back to engineering
- Closing deals on-site (show up, install, prove value, get signature)

**Start:** Month 4 (founders do first 3-4 installs themselves to learn what breaks)

---

## 3) Budget — 18-Month Runway

| Line item | Monthly | 18-month total |
|-----------|---------|---------------|
| Lead Engineer (salary + ~15% benefits) | $12,200 | $219,600 |
| Field Sales Engineer (starts month 4, 14 months) | $6,700 | $93,800 |
| Field Sales commissions (estimated on 20 factories) | — | $15,000 |
| WeWork day passes (1x/week) | $200 | $3,600 |
| Hardware inventory (50 kits at ~$300 cost) | — | $15,000 |
| Cloud infrastructure (minimal — mostly edge) | $500 | $9,000 |
| Legal (incorporation, stock options, IP) | — | $10,000 |
| Insurance (general liability + E&O) | $400 | $7,200 |
| Travel (factory visits, installs, 1-2 trade shows) | $1,500 | $27,000 |
| Marketing (landing page, LinkedIn ads, content) | $800 | $14,400 |
| Dev tools & subscriptions (Claude, Cursor, GitHub, etc.) | $500 | $9,000 |
| Misc (unexpected, supplies, equipment) | — | $12,400 |
| **Total** | | **$436,000** |
| **Buffer remaining** | | **$64,000** |

$64K buffer = 3 extra months of runway if revenue is slower than expected, or second hardware batch for scaling past 50 factories.

---

## 4) Timeline

### Months 1-3: Build + First Pilots
- Lead Engineer starts month 1
- Thomas + Engineer ship v1.0 together
- Founders do first 3-4 factory installs themselves
- Collect ground-truth accuracy data
- Iterate based on real factory feedback

### Months 4-6: Prove Product-Market Fit
- Field Sales Engineer starts month 4
- Scale to 5-10 factory pilots
- v1.5 (beam + camera) in development
- First paying customers ($49/line/mo)
- Build test video regression library from real factory footage

### Months 7-12: Scale + Ship v1.5
- Ship v1.5 beam + camera upgrade
- Expand to 20-30 factories
- Target: $5K-$10K MRR by month 10
- Begin v2.0 OEE engine development
- Collect case studies and testimonials for fundraising

### Months 13-18: Revenue Growth + Series A Prep
- 30-50 factories onboarded
- Target: $15K-$25K MRR
- v2.0 Intelligence tier in beta
- Prepare Series A deck with real revenue, real customers, real data
- Target Series A: $2-5M at $15-25M valuation

---

## 5) Revenue Targets

| Month | Factories | Lines | MRR | Cumulative hardware revenue |
|-------|-----------|-------|-----|-----------------------------|
| 3 | 2 | 4 | $196 | $2,000 |
| 6 | 8 | 20 | $980 | $10,000 |
| 9 | 15 | 45 | $2,205 | $22,500 |
| 12 | 25 | 75 | $3,675 | $37,500 |
| 15 | 35 | 120 | $5,880 | $60,000 |
| 18 | 50 | 175 | $8,575 | $87,500 |

By month 18: ~$8.5K MRR ($102K ARR) + $87.5K hardware sold = real traction for Series A.

Conservative estimates. If Intelligence tier ($99) launches by month 14 and 30% upgrade, MRR jumps significantly.

---

## 6) What $500K Buys

- 18 months of runway with zero founder salary
- v1.0 shipped and piloted in real factories
- v1.5 shipped with beam accuracy upgrade
- v2.0 in development
- 50 factories onboarded
- Proven revenue model ($49-99/line/mo)
- Real customer case studies
- Test video regression library from 10+ factory environments
- Position to raise $2-5M Series A

---

## 7) What We Don't Spend On

- **Office space.** Remote + weekly WeWork day. Overhead should be people, hardware, and travel.
- **Designer.** Thomas builds all UI with AI tools.
- **Marketing team.** Founders handle LinkedIn, content, and YouTube. Manufacturing is word-of-mouth. Happy customers are the marketing department.
- **Customer support person.** Field Sales Engineer handles this. Hire dedicated support at 100+ factories.
- **Data scientist / ML engineer.** Not until v3.0. Not enough data yet.
- **Second engineer.** Not until revenue justifies it or Series A closes.

---

## 8) Series A Target (Month 18-24)

**Raise:** $2-5M
**Valuation:** $15-25M (based on traction, ARR trajectory, market size)

**What Series A funds:**
- 2-3 additional engineers (v2.0 OEE + v3.0 ML)
- Dedicated customer success / support hire
- Hardware inventory for 500+ kits
- Cloud infrastructure for fleet management (v4.0)
- Sales expansion beyond Southeast US
- Optional: founder salaries at market rate

**The Series A pitch:**
"We have 50 factories paying $49-99/month per production line for the only sub-$1,000 factory intelligence system that exists. Our roadmap goes from counting to autonomous factory management. The market is 40,000-60,000 US factories with zero automation, and we've proven they'll buy. We need $3M to ship the OEE platform, build the ML layer, and scale to 500 factories."

---
