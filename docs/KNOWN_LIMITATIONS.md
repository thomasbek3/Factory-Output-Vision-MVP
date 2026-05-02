# Known Limitations

- Reolink/RTSP operation has not yet been validated through the same real app proof path on a live camera.
- File-backed live demo proof is legitimate app-path evidence, but it is not field-stream proof.
- Per-video model selection and detector tuning are still required for new part types.
- Some current model files are candidate-specific.
- The validation pipeline is now registry-backed, but some historical Factory2 research scripts still live at top-level `scripts/` because tests import those paths.
- The app is designed for offline LAN operation and does not assume cloud services or Docker.
- Operator correction controls exist for production oversight; they are not validation proof.
- Active-learning/VLM tooling is offline/audit only. It creates evidence windows, review frames, dry-run teacher labels, local Moondream Station audit labels, and dataset safety checks, but it does not integrate cloud providers or make VLMs runtime count authority.
- Teacher/VLM labels are not validation truth unless separately promoted through reviewed gold artifacts; current validation tooling rejects raw teacher outputs as truth.
