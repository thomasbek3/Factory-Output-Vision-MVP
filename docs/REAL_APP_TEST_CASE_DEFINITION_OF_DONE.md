# Real App Test Case Definition Of Done

This is the proof bar for promoting any factory video into a verified app-counting test case.

For the registry-backed product path, every verified candidate should also have a manifest under `validation/test_cases/` and a registry entry in `validation/registry.json`.

## End Goal

The real Factory Vision app must visibly count completed product placements from real ordered processed frames at `1.0x` speed. A user should be able to open the dashboard, click `Start monitoring`, see the candidate video, watch Runtime Total start at `0`, and see Runtime Total increment at the correct completed-placement moments until it reaches the reviewed human truth total.

## Required Runtime Path

A valid run must use the actual FastAPI + VisionWorker + React dashboard path:

- `FC_DEMO_COUNT_MODE=live_reader_snapshot`
- `FC_COUNTING_MODE=event_based`
- `FC_DEMO_PLAYBACK_SPEED=1.0`
- one-pass demo source, no timestamp replay
- real ordered frames from the candidate video
- dashboard preview tied to the same backend-counted frame stream
- captured backend count events from the live run

For file-backed demos, measure wall time against source time. A valid real-time claim needs `wall_per_source` near `1.0`, not just an environment variable set to `1.0`.

## Count Rule

Count one completed placement when the worker finishes putting the finished product in the output/resting area.

Do not count:

- worker motion
- machine motion
- walking
- touching or repositioning
- static stacks
- pallets
- partial handling
- duplicate views
- motion alone

If a video begins with a placement already in progress, choose and document the truth definition before verification:

- **Operational truth:** count it if the completion happens after frame `0` and the app should count it in live operation.
- **Clean-cycle truth:** exclude it if the test case intentionally counts only complete pickup-to-placement cycles that begin after video start.

## Valid Evidence

Promotion evidence must include:

- human final total
- reviewed timestamp truth ledger for all counted placements
- launch command or environment showing the real app path
- visible dashboard evidence that the run starts at Runtime Total `0`
- visible dashboard evidence that the candidate video is loaded
- captured app observed-events JSON from the live backend
- app-vs-truth comparison with:
  - `matched_count` equal to the human truth total
  - `missing_truth_count: 0`
  - `unexpected_observed_count: 0`
  - `first_divergence: null`
- wall/source pacing evidence near `1.0`
- regression checks for touched runtime/scripts/frontend
- Test Case 1 recheck if shared runtime/demo code changed

## Invalid Evidence

These do not prove a real app-counting test case:

- timestamp replay
- deterministic receipt reveal
- fake UI count updates
- offline retrospective counting presented as app proof
- hardcoded video filename hacks
- threshold loosening just to force the final total
- final total match with wrong event timing
- accelerated diagnostic success without a later `1.0x` visible app run
- proof-only success while the runtime/dashboard path is still wrong
- looped demo totals

## Promotion Rule

Do not promote a candidate into a named numbered test case until the real app/dashboard run is clean against the reviewed truth ledger.

A candidate can be described as verified only when:

- the expected total is settled
- timestamp truth is reviewed
- Runtime Total starts at `0`
- the dashboard shows the actual candidate video
- the app completes at the expected total
- event timing comparison is clean
- wall/source pacing is measured near `1.0`
- no video-specific hacks were introduced
- Test Case 1 remains intact if shared code changed

Keep failed or rough comparisons as audit artifacts. If a rough truth ledger causes false mismatches, create a reviewed replacement ledger and compare against that; do not hide the mismatch by loosening runtime thresholds.
