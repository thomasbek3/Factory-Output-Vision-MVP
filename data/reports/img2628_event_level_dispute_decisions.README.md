# IMG_2628 Event Dispute Decisions

Use `img2628_event_level_dispute_review.visible_dashboard_candidate25_v1.html` to review the six disputed windows.
Then fill `img2628_event_level_dispute_decisions.template_v1.csv`.

Allowed `decision` values:

- `accept_app_event`: add the app event as reviewed truth.
- `reject_app_event`: keep the app event out of reviewed truth.
- `keep_truth_event`: keep an existing draft truth timestamp as reviewed truth.
- `remove_truth_event`: remove an existing draft truth timestamp.
- `match_app_to_truth`: replace an existing draft truth timestamp with a reviewed app/track timestamp for the same physical placement.

Every row must include:

- `decision`
- `reviewer`
- `review_notes`

Build the reviewed truth CSV only after every dispute row is filled:

```bash
.venv/bin/python scripts/apply_img2628_event_dispute_decisions.py \
  --base-truth data/reports/img2628_codex_visual_truth_event_times.draft_v1.csv \
  --decisions data/reports/img2628_event_level_dispute_decisions.template_v1.csv \
  --disputes data/reports/img2628_event_level_dispute_review.visible_dashboard_candidate25_v1.csv \
  --output data/reports/img2628_human_truth_event_times.reviewed_v1.csv \
  --expected-total 25 \
  --force
```

Then build the reviewed ledger:

```bash
.venv/bin/python scripts/build_human_truth_ledger_from_csv.py \
  --csv data/reports/img2628_human_truth_event_times.reviewed_v1.csv \
  --output data/reports/img2628_human_truth_ledger.reviewed_v1.json \
  --video data/videos/from-pc/IMG_2628.MOV \
  --expected-total 25 \
  --video-sha256 b8fa676e3ee7200eb3fecfa112e8e679992b356a0129ff96f78fd949cedf8139 \
  --count-rule "Count one completed placement when the worker finishes putting the finished product in the output/resting area." \
  --force
```

Finally compare the visible app run to reviewed truth:

```bash
.venv/bin/python scripts/compare_factory2_app_run_to_truth_ledger.py \
  --truth-ledger data/reports/img2628_human_truth_ledger.reviewed_v1.json \
  --observed-events data/reports/img2628_app_observed_events.run8092.visible_dashboard_1x_candidate25_v1.json \
  --output data/reports/img2628_app_vs_truth.run8092.visible_dashboard_1x_candidate25_v1.json \
  --tolerance-sec 8 \
  --force
```
