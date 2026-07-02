# Current Scripts

These are the live Track B CLIs for the overhead wire-frame action-recognition lane:

- `run_zone_tripwire.py` — mines high-recall output-zone change candidates from video.
- `validate_tripwire_recall.py` — checks tripwire candidate recall against reviewed placement times.
- `extract_clip_dataset.py` — extracts before/during/after candidate clips for labeling and training.
- `label_clips.py` — records human/Codex teacher clip judgments while protecting held-out exam clips.
- `train_clip_student.py` — trains the small clip-student model used by the live Track B counter.
- `run_clip_exam.py` — runs the blind Track B exam gate and reports placement-count pass/fail.

LEGACY: most other scripts are superseded YOLO-era tooling kept for provenance.

run_clip_eval.py is a dead YOLO-era relic — the current exam is run_clip_exam.py.
