# Windows Install Package

This folder is a script-based Windows installer for the Factory Counter app.

It now also includes an Inno Setup project so you can build a normal Windows `Setup.exe`.

Future packaging note:

- `STANDALONE_RUNTIME_PLAN.md` documents the next step for removing the system-Python dependency later.

## What It Does

- creates a Python virtual environment in `.venv`
- installs backend dependencies from `requirements.txt`
- validates `ffmpeg` and `ffprobe`
- uses the built React UI already in `frontend/dist`
- creates `.env` from `.env.example` if it does not exist
- gives you one-click `start` and `stop` scripts
- can be wrapped into a normal Windows installer EXE with Start Menu and desktop shortcuts

## Prerequisites

- Windows 10 or 11
- Python 3.10 or newer available through `py` or `python`
- `ffmpeg.exe` and `ffprobe.exe` on `PATH`
- Node.js only if you need to rebuild `frontend/dist`

## Quick Start

### Option A: Direct script install

From the repo root:

```powershell
INSTALL\windows\install.bat
INSTALL\windows\start-app.bat
```

Then open:

```text
http://127.0.0.1:8080/dashboard
```

To stop it:

```powershell
INSTALL\windows\stop-app.bat
```

### Option B: Build a real Windows installer EXE

1. Install Inno Setup 6
2. Run:

```powershell
INSTALL\windows\build-installer.bat
```

3. The installer EXE will be written to:

```text
dist\windows-installer\
```

4. Run the generated `FactoryCounterSetup-<version>.exe`

Current generated output in this repo:

```text
dist\windows-installer\FactoryCounterSetup-0.1.0.exe
```

## Installer Options

PowerShell installer:

```powershell
INSTALL\windows\install.ps1
```

Useful flags:

- `-VerifyOnly`
  Checks Python, `ffmpeg`, `ffprobe`, `frontend/dist`, and required folders without creating the venv.
- `-BuildFrontendIfMissing`
  Runs `npm install` and `npm run build` in `frontend/` if the built React assets are missing.
- `-CreateDesktopShortcuts`
  Adds desktop shortcuts for Start and Stop.

Examples:

```powershell
INSTALL\windows\install.ps1 -VerifyOnly
INSTALL\windows\install.ps1 -CreateDesktopShortcuts
INSTALL\windows\install.ps1 -BuildFrontendIfMissing
```

## Installer Build Script

The Inno Setup build wrapper stages only the runtime files the app needs:

- `app/`
- `demo/`
- `frontend/dist/`
- `INSTALL/windows/`
- `requirements.txt`
- `.env.example`
- `README.md`

Build command:

```powershell
INSTALL\windows\build-installer.ps1
```

Useful flags:

- `-AppVersion 0.1.0`
- `-BuildFrontendIfMissing`

## Start Script Options

PowerShell start script:

```powershell
INSTALL\windows\start-app.ps1
```

Useful flags:

- `-Foreground`
  Runs `uvicorn` in the current terminal instead of background mode.
- `-OpenBrowser`
  Opens the dashboard after the server starts.
- `-DemoMode`
  Forces demo mode for the launched process.
- `-ListenHost 0.0.0.0`
- `-Port 8080`
- `-LogLevel info`

Example:

```powershell
INSTALL\windows\start-app.ps1 -OpenBrowser
INSTALL\windows\start-app.ps1 -Foreground -DemoMode -Port 8090
```

On a fresh machine, the first launch may take a few minutes because the script will finish the Python environment bootstrap if the installer copy completed before dependency installation did.

## Files Used At Runtime

- PID file: `data/run/factory_counter.pid`
- uvicorn stdout: `data/logs/uvicorn.stdout.log`
- uvicorn stderr: `data/logs/uvicorn.stderr.log`
- app log: `data/logs/factory_counter.log`
- SQLite DB: `data/factory_counter.db`

## Demo Mode

You can either:

- run `INSTALL\windows\start-app.ps1 -DemoMode`
- or set these values in `.env`

```text
FC_DEMO_MODE=1
FC_DEMO_VIDEO_PATH=./demo/demo.mp4
```

## Notes

- The app still needs camera credentials configured in the UI unless you use demo mode.
- If `frontend/dist` is deleted, rebuild it or rerun the installer with `-BuildFrontendIfMissing`.
- If the app exits right away, check `data/logs/uvicorn.stdout.log` and `data/logs/uvicorn.stderr.log`.
- If the installer bootstrap has trouble, check `data/logs/installer-bootstrap.log`.
