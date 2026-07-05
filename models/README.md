# Model Artifact Manifest

Weights are never committed to this repository. They live in the local artifact store:

`/Users/thomas/FactoryVisionArtifacts/repo-offload/2026-07-04/`

The checked-in repo keeps code, docs, validation manifests, and this index. To rerun an older validation path, restore the needed weight from the artifact store or point the relevant command/env var at the offload path.

| Weight | Status | Offload path | SHA-256 |
| --- | --- | --- | --- |
| `models/factory2_person_panel_binary_manual_v1.pt` | Factory2 diagnostic/perception-era model; do not use without current verification | `/Users/thomas/FactoryVisionArtifacts/repo-offload/2026-07-04/models/factory2_person_panel_binary_manual_v1.pt` | `522e5fbf1e61a862913d9525c7e42535483e50f227364e66ce2a41b70ce00fdd` |
| `models/img2628_active_panel_diagnostic_v1_wirebase.pt` | IMG_2628 diagnostic-era model; do not use without verification | `/Users/thomas/FactoryVisionArtifacts/repo-offload/2026-07-04/models/img2628_active_panel_diagnostic_v1_wirebase.pt` | `382dc1e45d66d20061cb3e84f5e2640ca010ea6d00c65f32260c3f0e4aff6224` |
| `models/img2628_motion_score_event_diag_v1_yolov8n.pt` | IMG_2628 diagnostic-era model; do not use without verification | `/Users/thomas/FactoryVisionArtifacts/repo-offload/2026-07-04/models/img2628_motion_score_event_diag_v1_yolov8n.pt` | `9676645707696fc26f18f3274a1b936d9ed2658a7e9ba97668324bbffea8da95` |
| `models/img2628_placement_action_diag_v1.pt` | IMG_2628 diagnostic-era model; do not use without verification | `/Users/thomas/FactoryVisionArtifacts/repo-offload/2026-07-04/models/img2628_placement_action_diag_v1.pt` | `37cbb3b9ba9f76aacff08365be3cc93050d003a8bc82db7d63bb34bb12a44ad6` |
| `models/img2628_placement_action_multiclass_diag_v1.pt` | IMG_2628 diagnostic-era model; do not use without verification | `/Users/thomas/FactoryVisionArtifacts/repo-offload/2026-07-04/models/img2628_placement_action_multiclass_diag_v1.pt` | `f81ec3064bd42431dba1c2f6c5bc994dd9c23d6cccac628111d4c8b8885bbbe1` |
| `models/img2628_worksheet_accept_event_diag_v1.pt` | IMG_2628 verified-candidate runtime model; station-specific and not promoted as universal | `/Users/thomas/FactoryVisionArtifacts/repo-offload/2026-07-04/models/img2628_worksheet_accept_event_diag_v1.pt` | `49f37941c113147cbaa732c85165073239cbc6bb8b9f187d34902389744b2c75` |
| `models/img3254_active_panel_v1.pt` | IMG_3254 rejected diagnostic model; broad/static-stack failure mode | `/Users/thomas/FactoryVisionArtifacts/repo-offload/2026-07-04/models/img3254_active_panel_v1.pt` | `5906a3e597ec2b405aaf46a5e00c28159e67c2176bd52f224e56bbdfa8716c41` |
| `models/img3254_active_panel_v4_yolov8n.pt` | IMG_3254 verified-candidate runtime model for clean-cycle 22; station-specific | `/Users/thomas/FactoryVisionArtifacts/repo-offload/2026-07-04/models/img3254_active_panel_v4_yolov8n.pt` | `10e17664969b267824bf23f0820f5fdd8da2a24d18450d49c6d2e0407730334a` |
| `models/img3254_active_panel_v5.pt` | IMG_3254 diagnostic refinement; overcount/broadened detections, do not use without verification | `/Users/thomas/FactoryVisionArtifacts/repo-offload/2026-07-04/models/img3254_active_panel_v5.pt` | `59b60ed957cf7ab837d0698beb87c81e76882629ddfdb8a8aa0dfafb1e7f11ea` |
| `models/img3254_active_panel_v6.pt` | IMG_3254 diagnostic refinement; overfragmented, do not use without verification | `/Users/thomas/FactoryVisionArtifacts/repo-offload/2026-07-04/models/img3254_active_panel_v6.pt` | `e4c0e6f40566b5188d469f94439825ed28648047e4bb5664d8c2dcfbf285cf83` |
| `models/img3254_active_panel_v7_from_yolov8n_v6data.pt` | IMG_3254 diagnostic refinement; undercounted, do not use without verification | `/Users/thomas/FactoryVisionArtifacts/repo-offload/2026-07-04/models/img3254_active_panel_v7_from_yolov8n_v6data.pt` | `cabe0e27c5ffed33f303f8d1f5e4041963bac081b03728a822fbd0ac74bd7fd2` |
| `models/img3262_active_panel_v1.pt` | IMG_3262 diagnostic-era model; do not use without verification | `/Users/thomas/FactoryVisionArtifacts/repo-offload/2026-07-04/models/img3262_active_panel_v1.pt` | `075720abe04f8a0bfbe3a6eb38b8d1de4a41e5dba318843d1212cd3016da73e4` |
| `models/img3262_active_panel_v2.pt` | IMG_3262 verified-candidate runtime model; station-specific | `/Users/thomas/FactoryVisionArtifacts/repo-offload/2026-07-04/models/img3262_active_panel_v2.pt` | `faa337497bbf8d61f28ce894066855bc574202c1760b33683390149c979c8a23` |
| `models/panel_in_transit.onnx` | Track A promoted-era panel-in-transit export; use only with matching validation path | `/Users/thomas/FactoryVisionArtifacts/repo-offload/2026-07-04/models/panel_in_transit.onnx` | `bac10def02c100dcf18125eac12d519fe4d84091fdad24a01bee03938d3211f8` |
| `models/panel_in_transit.pt` | Track A promoted-era Factory2 panel-in-transit model; verified for Factory2 runtime semantics | `/Users/thomas/FactoryVisionArtifacts/repo-offload/2026-07-04/models/panel_in_transit.pt` | `2f9b79c41fed32a615d246607f4244849f6f2ef8e78a89e6edc0c0d0432b107b` |
| `models/real_factory_diagnostic_action_v1.pt` | Real-factory diagnostic model; not validation truth and not registry-promotion eligible | `/Users/thomas/FactoryVisionArtifacts/repo-offload/2026-07-04/models/real_factory_diagnostic_action_v1.pt` | `a140cf56f0705c5564ed68fe1e44127894e996d89dffa88b354f15d9df9e9fec` |
| `models/real_factory_diagnostic_action_v2.pt` | Real-factory diagnostic model; not validation truth and not registry-promotion eligible | `/Users/thomas/FactoryVisionArtifacts/repo-offload/2026-07-04/models/real_factory_diagnostic_action_v2.pt` | `e22beb2c87fa90ec1b349a1ccea113c4e791f64a8350a54ac98ab494d30829a1` |
| `models/wire_mesh_panel.pt` | DO NOT USE for counting; static stack detector with documented overcount/abstention failure | `/Users/thomas/FactoryVisionArtifacts/repo-offload/2026-07-04/models/wire_mesh_panel.pt` | `34557ca5ea24736e67bdb2038f9ac5c76a797be388a469cf1a6858845fadd30d` |
| `runs/detect/training_runs/yolo26n_img3262_eval_v1/weights/best.pt` | YOLO26 evaluation-lane training artifact; station/product-specific, not universal | `/Users/thomas/FactoryVisionArtifacts/repo-offload/2026-07-04/runs/detect/training_runs/yolo26n_img3262_eval_v1/weights/best.pt` | `90a9192e5f6278f2f0430a021bcaaced14242b4762646c33ed444c050f7c70ea` |
| `runs/detect/training_runs/yolo26n_img3262_eval_v1/weights/last.pt` | YOLO26 evaluation-lane training artifact; station/product-specific, not universal | `/Users/thomas/FactoryVisionArtifacts/repo-offload/2026-07-04/runs/detect/training_runs/yolo26n_img3262_eval_v1/weights/last.pt` | `e09228fd8e8e40a50d45a786fc1b0ff563c7b6d7784d1412c6e797986802093e` |
| `yolov8n.pt` | Ultralytics COCO/base model cache; prefer the model name `yolov8n.pt` as an auto-download identifier | `/Users/thomas/FactoryVisionArtifacts/repo-offload/2026-07-04/yolov8n.pt` | `f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36` |
| `yolo11n.pt` | Untracked Ultralytics person/base model cache copied for preservation | `/Users/thomas/FactoryVisionArtifacts/repo-offload/2026-07-04/yolo11n.pt` | `0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1` |
| `yolo11n-cls.pt` | Untracked Ultralytics classifier/base model cache copied for preservation | `/Users/thomas/FactoryVisionArtifacts/repo-offload/2026-07-04/yolo11n-cls.pt` | `c62d41bf9625777760018bf914d2e6cd472420ccd01706d97a61cb6c82502bd7` |

## Offloaded Training Artifacts And Dataset Stubs

The remaining YOLO training artifacts and Roboflow dataset stubs were offloaded
on 2026-07-04 and removed from Git tracking. The full per-file verification log
is appended to `/Users/thomas/FactoryVisionArtifacts/repo-offload/2026-07-04/CHECKSUMS.txt`.

| Repo path | File count | Offload path |
| --- | ---: | --- |
| `training_runs/` | 66 | `/Users/thomas/FactoryVisionArtifacts/repo-offload/2026-07-04/training_runs/` |
| `datasets/` | 8 | `/Users/thomas/FactoryVisionArtifacts/repo-offload/2026-07-04/datasets/` |
| `roboflow_dataset/` | 2 | `/Users/thomas/FactoryVisionArtifacts/repo-offload/2026-07-04/roboflow_dataset/` |
