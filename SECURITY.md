# Security And Data Handling

Factory Vision may handle customer footage, camera credentials, model weights, and production-count data. Treat all of it as sensitive.

## Rules

- Never commit `.env`, credentials, tokens, private keys, or camera passwords.
- Never upload customer footage, review frames, labels, or model artifacts to cloud services without explicit permission.
- Redact stream URLs and credentials in docs, reports, screenshots, and support bundles.
- Keep raw videos and large artifacts in the local artifact root unless a manifest explicitly says otherwise.
- Rotate any credential that appears in terminal output, screenshots, commits, or shared reports.

## Local Artifact Root

```text
/Users/thomas/FactoryVisionArtifacts
```

## Reporting

This is currently a private/local project. Report security or data-handling issues directly to the project owner. Do not file public issues or share customer footage externally.

## Dependency And Licensing Notes

Detector, model, and vendor-runtime choices may carry commercial licensing or cloud-processing implications. Any production adoption of Ultralytics, Roboflow, RF-DETR variants, Cosmos, Hailo, Jetson, or similar tooling must include a licensing and offline-data review.
