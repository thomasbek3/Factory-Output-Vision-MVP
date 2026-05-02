# Artifact Storage

Updated: 2026-05-02

This project uses GitHub as the source of truth for the index, proof summaries, docs, scripts, and validation manifests. Heavy factory artifacts live outside normal Git.

## Current Local Artifact Root

The primary local artifact root on Thomas's Mac is:

```text
/Users/thomas/FactoryVisionArtifacts
```

Directory layout:

```text
/Users/thomas/FactoryVisionArtifacts/
  videos/
    raw/
  reports/
  models/
  frames/
  embeddings/
  backups/
```

The repo's existing `data/` and `models/` paths remain the working cache used by scripts and manifests. Do not break those paths during validation. Copy or sync durable artifacts into the local artifact root, then record hashes and relative artifact paths in versioned manifests.

## Storage Roles

| Location | Role | Store |
| --- | --- | --- |
| GitHub repo | Brain and proof index | Code, docs, manifests, schemas, small scorecards, registry entries |
| `/Users/thomas/FactoryVisionArtifacts` | Local artifact warehouse | Raw videos, model checkpoints, reports, selected frames, embedding backups |
| Future object bucket | Durable remote warehouse | Same heavy artifacts when local-only storage becomes limiting |
| Repo `data/` and `models/` | Working cache | Files needed for current local scripts and visible app validation |

## What Goes Where

Store in GitHub:

- `validation/registry.json`
- `validation/test_cases/*.json`
- `validation/detectors/*.json` when detector cards exist
- `validation/artifact_storage.json`
- docs, scripts, tests, and schemas
- small proof reports or selected screenshots when they are part of review

Store outside normal Git:

- raw `.MOV` and `.MP4` videos
- full extracted frame dumps
- generated training datasets
- embedding/search databases
- large model checkpoints as the library grows
- large review-frame folders unless intentionally selected as proof evidence

## Artifact Reference Rule

Every heavy artifact should be referenced by a manifest entry with:

```json
{
  "local_path": "data/videos/from-pc/IMG_2628.MOV",
  "artifact_root": "/Users/thomas/FactoryVisionArtifacts",
  "artifact_relpath": "videos/raw/IMG_2628.MOV",
  "sha256": "b8fa676e3ee7200eb3fecfa112e8e679992b356a0129ff96f78fd949cedf8139"
}
```

This lets GitHub remember what exists and verify integrity without storing the raw video in normal Git.

## Current Raw Video Copies

The current local artifact root contains these raw video copies:

| Artifact | SHA-256 |
| --- | --- |
| `videos/raw/IMG_2628.MOV` | `b8fa676e3ee7200eb3fecfa112e8e679992b356a0129ff96f78fd949cedf8139` |
| `videos/raw/IMG_3254.MOV` | `f9b72e2a48e96f1f008a0b750504fde13c8ea43ab62f562bacd715c5b19b19cd` |
| `videos/raw/IMG_3262.MOV` | `4cb1d274cd2a53ca792bd3b7b217b84bf7734c780a7e43a1b7cc77557a32bf6e` |
| `videos/raw/factory2.MOV` | `f9cd9dcc71cc9e02c0f5a5ba65094510f5ac4cfbe3a39a4eb1e9cae32e69c3d8` |
| `videos/raw/real_factory.MOV` | `48b4aa0543ac65409b11ee4ab93fd13e5f132a218b4303096ff131da42fb9f86` |
| `videos/raw/demo_counter.mp4` | `19152678b424629195b2af542f9372adfdf5b4caa401ffcb8ce06d5db3785783` |

## Future Cloud Storage

When local-only storage becomes limiting, use a private S3-compatible object bucket as the durable remote artifact store. Cloudflare R2 is the preferred first option because it is S3-compatible, has a free tier, and avoids egress fees for normal downloads. Backblaze B2 is the backup option. AWS S3 is the enterprise/compliance option.

Use URI placeholders like this until a real bucket is configured:

```text
r2://factory-vision-artifacts/videos/raw/IMG_2628.MOV
```

Do not silently upload factory footage to cloud storage. Cloud artifact sync requires explicit permission.

## Sync Pattern

For now, keep raw videos in both places:

```text
repo working cache: data/videos/from-pc/IMG_2628.MOV
durable local copy: /Users/thomas/FactoryVisionArtifacts/videos/raw/IMG_2628.MOV
```

When adding a new video:

1. Copy it into `data/videos/from-pc/` for the app path.
2. Copy or clone it into `/Users/thomas/FactoryVisionArtifacts/videos/raw/`.
3. Record SHA-256 in the test-case manifest and artifact storage index.
4. Keep generated diagnostics under repo `data/` while working.
5. Preserve only useful reports, selected frames, models, and embeddings in the artifact root after validation.
