# UX_SPEC — Blue-Collar Setup Wizard + Dashboard + Troubleshooting

---

## 1) UX rules (non-negotiable)
DO NOT show these words in UI:
- RTSP
- FFmpeg
- MOG2
- contours
- baseline window
- centroid
- blob
- threshold
- count line

Use plain words:
- Camera
- Parts
- Output zone
- Running
- Slowing
- Stopped
- Reconnecting
- Beam sensor (v1.5)

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

### Step 0.5 — Camera Mounting Guide
Show a simple visual diagram with 3 key rules:
1) Mount camera above the line, angled down at 30–45°
2) Make sure the full width of the belt/conveyor is visible
3) Don't aim the camera toward windows or bright lights

Show a "good" example and a "bad" example side by side.

This is critical. Bad camera positioning causes more accuracy failures than bad algorithms.

Button: Got it, Next

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

### v1.5 addition — Step 1.5: How do you count?
Not in v1.0. In v1.5, insert here:

Option A: "Camera counts parts" (icon: camera)
  - "Easiest setup. Camera watches parts cross a line."
Option B: "I have a beam sensor" (icon: laser beam)
  - "Most accurate. Sensor counts, camera watches for problems."

If B selected:
  - Auto-detect USB device or show dropdown
  - Test button: "Break the beam with your hand" → ✅ "Sensor working"

### Step 2 — Mark Output Area
Instruction: "Draw a shape around where output accumulates. Objects detected here get counted."

Buttons:
- Clear
- Next

### Step 3 — Operator Zone (optional)
Checkbox: "Only check for operator when line slows down."
If enabled: draw polygon.

Buttons:
- Skip
- Next

### Step 4 — Calibrate
Instruction: "Run the line like normal for 5 minutes."
Button: Start Calibrating
Show:
- progress bar
- current parts/min
- live preview with detected objects highlighted in green

Calibration should auto-detect:
- Detection confidence (for filtering noise/false positives)

If calibration detects <95% confidence (very few or very inconsistent detections):
- Show warning: "We're having trouble seeing parts. Try adjusting the camera angle."
- Link back to mounting guide

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

### v1.5 addition:
- Small badge below status light: "Counting: Camera" or "Counting: Beam Sensor"

Tiles:
- Parts this minute
- Parts this hour (includes +1/-1 manual correction buttons)
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

### v1.5 addition — Beam Sensor section:
- Beam status: Connected / Disconnected
- Last beam event: X seconds ago
- Total beam events this session: N

Button: Test Beam (break and check)

### Support
Button:
- Download Support Bundle

---

## 5) Reset rules
- Recalibrate resets baseline only (keeps drawings)
- Reset Setup wipes everything and returns to Step 0 (confirm dialog)

---
