# Live Recording Runbook

## Purpose

Production footage is Track B training fuel. The recorder captures camera-only
evidence from the live overhead station so the tripwire can propose clips, humans
can label them, and the clip student can learn the placement action.

Plain-English version: this rig is the factory's tape recorder. It does not count
by itself; it saves the raw video the model learns from later.

## Files

- `~/.factory_camera.env`: local-only camera contract and credentials. This file
  must be mode `0600` and must never be committed.
- `~/rec_cam.sh`: live recorder on this Mac.
- `~/wd_today.sh`: live watchdog on this Mac.
- `scripts/ops/rec_cam.sh`: sanitized repo copy of the recorder.
- `scripts/ops/wd_today.sh`: sanitized repo copy of the watchdog.

## Env File Contract

`~/.factory_camera.env` must define these names only; keep the values out of Git:

- `FACTORY_RTSP_USER`
- `FACTORY_RTSP_PASS`
- `CAM1_IP`
- `CAM2_IP`
- `CAM1_UUID`
- `CAM2_UUID`

Set permissions with:

```bash
chmod 600 ~/.factory_camera.env
```

## Recorder Invocation

The recorder contract is:

```bash
~/rec_cam.sh CAM_IP STATION_TAG START_EPOCH END_EPOCH
```

It builds an RTSP source from `FACTORY_RTSP_USER`, `FACTORY_RTSP_PASS`, and the
passed camera IP. It runs `ffmpeg` with `-c copy` and writes 60-second Matroska
segments.

Output prefers the SSD artifact tree:

```text
/Volumes/Crucial X9 Pro For Mac/Archive/FactoryVisionArtifacts/onboarding
```

If that path is unavailable or cannot be created, it falls back to:

```text
~/factory_local_recordings/onboarding
```

## Watchdog Behavior

The watchdog is armed to one end epoch. Until that end time, it sleeps for 120
seconds, checks whether each recorder process is alive, and relaunches any dead
camera recorder under `nohup caffeinate -i bash`.

Plain-English version: the watchdog is the person tapping the recorder every two
minutes. If a camera recorder stopped, it presses record again until the shift
window ends.

## Known Failure Mode

The factory Windows desktop running the Tailscale subnet route can die
mid-afternoon. When that happens, both camera streams drop at the same time. The
fix is factory-side: restore the Windows desktop/subnet route, then verify both
recorders resume. Local script changes on the Mac do not repair that shared
network path.

## Cold-Start Checklist For A New Mac

1. Clone this repo and copy `scripts/ops/rec_cam.sh` and
   `scripts/ops/wd_today.sh` to `~/rec_cam.sh` and `~/wd_today.sh`.
2. Create `~/.factory_camera.env` with the variable names listed above and run
   `chmod 600 ~/.factory_camera.env`.
3. Install `ffmpeg` at `/opt/homebrew/bin/ffmpeg` or update the recorder path.
4. Mount the Crucial X9 Pro SSD and confirm the artifact root exists.
5. Confirm Tailscale can reach both factory camera IPs through the factory subnet
   route.
6. Launch one short recorder window for each camera and confirm new `.mkv`
   segments appear.
7. Start the watchdog for the planned capture window and tail
   `/Users/thomas/rec_<station-tag>.log`.
