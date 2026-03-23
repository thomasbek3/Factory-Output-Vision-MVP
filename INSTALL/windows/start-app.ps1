param(
    [switch]$Foreground,
    [switch]$OpenBrowser,
    [switch]$DemoMode,
    [string]$ListenHost = "",
    [int]$Port = 0,
    [string]$LogLevel = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot "Common.ps1")

$repoRoot = Get-RepoRoot
$envValues = Import-EnvFile -Path (Join-Path $repoRoot ".env")
$venvPath = Get-DefaultVenvPath -RepoRoot $repoRoot
$pythonExe = Get-VenvPythonPath -VenvPath $venvPath
$pidFile = Get-PidFilePath -RepoRoot $repoRoot
$stdoutLog = Get-StdoutLogPath -RepoRoot $repoRoot
$stderrLog = Get-StderrLogPath -RepoRoot $repoRoot
$installMarkerPath = Get-InstallMarkerPath -RepoRoot $repoRoot
$bootstrapLockPath = Get-BootstrapLockPath -RepoRoot $repoRoot

if ((-not (Test-Path $pythonExe)) -or (-not (Test-VenvReady -PythonExe $pythonExe)) -or (-not (Test-Path $installMarkerPath))) {
    if (Test-Path $bootstrapLockPath) {
        Write-Host "Another bootstrap is already running. Waiting for it to finish..."
        $deadline = (Get-Date).AddMinutes(10)
        while ((Get-Date) -lt $deadline) {
            Start-Sleep -Seconds 5
            if ((-not (Test-Path $bootstrapLockPath)) -and (Test-Path $pythonExe) -and (Test-VenvReady -PythonExe $pythonExe) -and (Test-Path $installMarkerPath)) {
                break
            }
        }
    }

    if ((-not (Test-Path $pythonExe)) -or (-not (Test-VenvReady -PythonExe $pythonExe)) -or (-not (Test-Path $installMarkerPath))) {
        Write-Host "Python environment is not ready. Running installer bootstrap first..."
        & (Join-Path $PSScriptRoot "install.ps1")
        if ((-not (Test-Path $pythonExe)) -or (-not (Test-VenvReady -PythonExe $pythonExe)) -or (-not (Test-Path $installMarkerPath))) {
            throw "Installer bootstrap failed."
        }
    }
}

Assert-Command -Name "ffmpeg" -InstallHint "Install ffmpeg and ensure ffmpeg.exe is on PATH."
Assert-Command -Name "ffprobe" -InstallHint "Install ffmpeg and ensure ffprobe.exe is on PATH."

if (-not (Test-Path (Get-FrontendIndexPath -RepoRoot $repoRoot))) {
    throw "frontend/dist is missing. Run npm run build in frontend/ or re-run the installer with -BuildFrontendIfMissing."
}

$defaultHost = Get-EnvValue -EnvValues $envValues -Name "FC_HOST" -DefaultValue "127.0.0.1"
$defaultPort = Get-EnvValue -EnvValues $envValues -Name "FC_PORT" -DefaultValue "8080"
$defaultLogLevel = Get-EnvValue -EnvValues $envValues -Name "FC_LOG_LEVEL" -DefaultValue "info"

if (-not $ListenHost) {
    $ListenHost = $defaultHost
}

if ($Port -le 0) {
    $Port = [int]$defaultPort
}

if (-not $LogLevel) {
    $LogLevel = $defaultLogLevel
}

Set-Item -Path "Env:FC_FRONTEND_DIST" -Value (Join-Path $repoRoot "frontend\dist")

if ($DemoMode) {
    Set-Item -Path "Env:FC_DEMO_MODE" -Value "1"
    if (-not (Get-EnvValue -EnvValues $envValues -Name "FC_DEMO_VIDEO_PATH")) {
        Set-Item -Path "Env:FC_DEMO_VIDEO_PATH" -Value (Join-Path $repoRoot "demo\demo.mp4")
    }
}

if (Test-Path $pidFile) {
    $existingPidRaw = (Get-Content $pidFile -Raw).Trim()
    if ($existingPidRaw) {
        $existingPid = [int]$existingPidRaw
        if (Test-ProcessRunning -ProcessId $existingPid) {
            Write-Host "Factory Counter is already running with PID $existingPid"
            Write-Host "UI URL: http://127.0.0.1:$Port/dashboard"
            exit 0
        }
    }

    Remove-Item $pidFile -Force
}

$uvicornArgs = @(
    "-m", "uvicorn",
    "app.main:app",
    "--host", $ListenHost,
    "--port", "$Port",
    "--log-level", $LogLevel
)

if ($Foreground) {
    Write-Host "Starting Factory Counter in the current terminal..."
    Write-Host "UI URL: http://127.0.0.1:$Port/dashboard"
    Push-Location $repoRoot
    try {
        & $pythonExe @uvicornArgs
        exit $LASTEXITCODE
    }
    finally {
        Pop-Location
    }
}

Write-Host "Starting Factory Counter in the background..."
$process = Start-Process -FilePath $pythonExe `
    -ArgumentList $uvicornArgs `
    -WorkingDirectory $repoRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput $stdoutLog `
    -RedirectStandardError $stderrLog `
    -PassThru

Start-Sleep -Seconds 2
if ($process.HasExited) {
    throw "Factory Counter exited immediately. Check $stdoutLog and $stderrLog"
}

Set-Content -Path $pidFile -Value "$($process.Id)"
Write-Host "Factory Counter started with PID $($process.Id)"
Write-Host "UI URL: http://127.0.0.1:$Port/dashboard"
Write-Host "PID file: $pidFile"

if ($OpenBrowser) {
    Start-Process "http://127.0.0.1:$Port/dashboard" | Out-Null
}
