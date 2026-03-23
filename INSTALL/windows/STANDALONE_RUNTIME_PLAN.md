# Standalone Runtime Plan

Date: 2026-03-11

This note captures the next packaging step after the current Windows installer.

## Current State

The current Windows installer is a real `Setup.exe`, but it still depends on:

- system Python being installed
- `py` or `python` being on `PATH`
- `ffmpeg.exe` and `ffprobe.exe` being on `PATH`

That means install reliability is better than a script folder alone, but it is not yet a true appliance-style package.

## Target State

Build a Windows installer that does not rely on system Python.

Preferred design:

- bundle a private Python runtime inside the install package
- preinstall all required Python dependencies into that private runtime
- update start scripts to use the bundled runtime only
- bundle `ffmpeg.exe` and `ffprobe.exe` with the app
- keep the application code as normal Python source files for easier debugging

## Why This Path

This keeps debugging practical:

- logs remain normal
- stack traces remain readable
- app files stay editable
- support can still run the bundled Python directly

This is safer than freezing everything into a single PyInstaller-style executable, which is usually harder to debug and patch.

## Planned Packaging Shape

Install tree should eventually look like:

```text
FactoryCounter/
  runtime/
    python/
    ffmpeg/
  app/
  frontend/
  demo/
  data/
  INSTALL/windows/
```

Runtime launch should become:

- bundled `python.exe -m uvicorn app.main:app ...`
- bundled `ffmpeg.exe` and `ffprobe.exe`
- no `.venv` creation on customer machines
- no `pip install` during install or first launch

## Work Items

1. Pick a bundled Python strategy.
- likely embedded CPython or a private copied runtime

2. Build a staging pipeline for the private runtime.
- install all app dependencies into the bundled runtime ahead of time
- verify `ultralytics`, `torch`, OpenCV, and `uvicorn` load correctly

3. Bundle `ffmpeg` and `ffprobe`.
- change scripts to prefer local binaries before PATH

4. Update installer scripts.
- remove customer-machine venv creation
- remove customer-machine `pip install`
- point start/stop scripts at the bundled runtime

5. Validate on a clean Windows target.
- no system Python
- no system ffmpeg
- install
- first launch
- `/api/status`
- `/dashboard`
- stop/uninstall

## Risks

- installer size will grow
- bundled dependency curation becomes a build responsibility
- `torch` and `ultralytics` increase packaging weight

## Recommendation

Do this next only after the current installer path is considered stable enough.

It is the right move if the goal is:

- easier customer installs
- fewer environment issues
- more appliance-like behavior
