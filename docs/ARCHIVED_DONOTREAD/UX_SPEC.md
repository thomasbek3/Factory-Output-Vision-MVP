# UX_SPEC — Blue-Collar Setup Wizard + Dashboard + Troubleshooting

---

## 1) UX rules (non-negotiable)
DO NOT show these words in UI:
- RTSP
- FFmpeg
- MOG2
- contours
- baseline window

Use plain words:
- Camera
- Parts
- Output area
- Count line
- Running
- Slowing
- Stopped
- Reconnecting

Every Yellow/Red screen must say:
- What's happening
- What to do next (1-2 steps)

---

## 2) Setup Wizard (must be <15 minutes)

### Step 0 — Welcome
Checklist:
- Camera mounted and aimed at output
- Camera and mini PC on same network

Button: Next

### Step 1 — Connect Camera
Fields:
- Camera IP
- Username
- Password
- Video quality toggle:
  - "Smoother (recommended)" => sub stream
  - "Sharper (slower)" => main stream

Button: Test Camera

Success: ✅ "Camera connected"
Failure: ❌ "Can't connect. Most often camera streaming is turned off. Here's how to turn it on."

Buttons:
- Next
- Help finding camera

### Step 2 — Mark Output Area
Instruction: "Draw a shape around where parts move."

Buttons:
- Clear
- Next

### Step 3 — Draw Count Line
Instruction: "Draw a line every part crosses."

Direction selector:
- Either direction
- Left to right
- Right to left

Buttons:
- Clear
- Next

### Step 4 — Operator Zone (optional)
Checkbox: "Only check for operator when line slows down."
If enabled: draw polygon.

Buttons:
- Skip
- Next

### Step 5 — Calibrate
Instruction: "Run the line like normal for 5 minutes."
Button: Start Calibrating
Show:
- progress bar
- current parts/min
Finish:
- "Baseline set to XX parts/min"
Buttons:
- Recalibrate
- Start Monitoring

---

## 3) Dashboard layout
Top:
- Big status light:
  - Green: Running normally
  - Yellow: Slowing down OR Reconnecting
  - Red: Stopped

Tiles:
- Parts this minute
- Parts this hour
- Baseline parts/min
- Current rolling parts/min

Right panel:
- Live view (2 fps) with overlays

Events:
- Recent events list (last 20)

Buttons:
- Start/Stop Monitoring
- Recalibrate
- Troubleshooting

---

## 4) Troubleshooting page
Sections:

### Camera
- Last frame received: X seconds ago
- Camera status: Connected / Reconnecting
- Reconnect attempts: N

Button: Restart Video Connection

### Counting
- Last count: timestamp
- Parts detected in output area (last frame): N

Buttons:
- Show what camera sees (mask debug snapshot)
- Reset Calibration

### Support
Button:
- Download Support Bundle

---

## 5) Reset rules
- Recalibrate resets baseline only (keeps drawings)
- Reset Setup wipes everything and returns to Step 1 (confirm dialog)

---