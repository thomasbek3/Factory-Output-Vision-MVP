param(
    [switch]$BuildFrontendIfMissing,
    [switch]$CreateDesktopShortcuts,
    [switch]$VerifyOnly,
    [string]$VenvPath = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot "Common.ps1")

$repoRoot = Get-RepoRoot
if (-not $VenvPath) {
    $VenvPath = Get-DefaultVenvPath -RepoRoot $repoRoot
}

$venvPython = Get-VenvPythonPath -VenvPath $VenvPath
$requirementsPath = Join-Path $repoRoot "requirements.txt"
$envTemplatePath = Join-Path $repoRoot ".env.example"
$envPath = Join-Path $repoRoot ".env"
$installMarkerPath = Get-InstallMarkerPath -RepoRoot $repoRoot
$bootstrapLockPath = Get-BootstrapLockPath -RepoRoot $repoRoot

Write-Host "Repo root: $repoRoot"

$bootstrapPython = Resolve-BootstrapPython
Write-Host "Using bootstrap Python $($bootstrapPython.Version): $($bootstrapPython.Executable)"

Assert-Command -Name "ffmpeg" -InstallHint "Install ffmpeg and make sure both ffmpeg.exe and ffprobe.exe are on PATH."
Assert-Command -Name "ffprobe" -InstallHint "Install ffmpeg and make sure both ffmpeg.exe and ffprobe.exe are on PATH."

if (-not (Test-Path $requirementsPath)) {
    throw "Missing requirements.txt at $requirementsPath"
}

if (-not (Test-Path (Get-FrontendIndexPath -RepoRoot $repoRoot))) {
    if (-not $BuildFrontendIfMissing) {
        throw "frontend/dist is missing. Re-run with -BuildFrontendIfMissing or build the frontend manually."
    }

    Assert-Command -Name "npm" -InstallHint "Install Node.js only if you need to rebuild the frontend."
    Write-Host "Frontend build missing. Installing frontend dependencies and building dist..."
    Invoke-External -Command "npm" -Arguments @("install") -WorkingDirectory (Join-Path $repoRoot "frontend")
    Invoke-External -Command "npm" -Arguments @("run", "build") -WorkingDirectory (Join-Path $repoRoot "frontend")
}

Ensure-Directory (Join-Path $repoRoot "data") | Out-Null
Ensure-Directory (Join-Path $repoRoot "data\logs") | Out-Null
Ensure-Directory (Join-Path $repoRoot "data\run") | Out-Null

if ($VerifyOnly) {
    Write-Host "Verification passed. No files were installed."
    exit 0
}

Set-Content -Path $bootstrapLockPath -Value "Bootstrap started $(Get-Date -Format o)"

try {
    if (-not (Test-Path $envPath)) {
        Copy-Item -Path $envTemplatePath -Destination $envPath
        Write-Host "Created .env from .env.example"
    }

    if (-not (Test-Path $venvPython)) {
        Write-Host "Creating virtual environment at $VenvPath"
        Invoke-External -Command $bootstrapPython.Command -Arguments @($bootstrapPython.Arguments + @("-m", "venv", $VenvPath))
    }

    Write-Host "Installing Python dependencies..."
    Invoke-External -Command $venvPython -Arguments @("-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel")
    Invoke-External -Command $venvPython -Arguments @("-m", "pip", "install", "-r", $requirementsPath)

    Set-Content -Path $installMarkerPath -Value "Installed $(Get-Date -Format o)"

    if ($CreateDesktopShortcuts) {
        $desktopPath = [Environment]::GetFolderPath("Desktop")
        $shell = New-Object -ComObject WScript.Shell

        $startShortcut = $shell.CreateShortcut((Join-Path $desktopPath "Factory Counter Start.lnk"))
        $startShortcut.TargetPath = "cmd.exe"
        $startShortcut.Arguments = "/c `"$repoRoot\INSTALL\windows\start-app.bat`""
        $startShortcut.WorkingDirectory = $repoRoot
        $startShortcut.Save()

        $stopShortcut = $shell.CreateShortcut((Join-Path $desktopPath "Factory Counter Stop.lnk"))
        $stopShortcut.TargetPath = "cmd.exe"
        $stopShortcut.Arguments = "/c `"$repoRoot\INSTALL\windows\stop-app.bat`""
        $stopShortcut.WorkingDirectory = $repoRoot
        $stopShortcut.Save()

        Write-Host "Created desktop shortcuts."
    }

    Write-Host ""
    Write-Host "Install complete."
    Write-Host "Start the app with: INSTALL\\windows\\start-app.bat"
    Write-Host "Stop the app with:  INSTALL\\windows\\stop-app.bat"
    Write-Host "UI URL: http://127.0.0.1:8080/dashboard"
}
finally {
    if (Test-Path $bootstrapLockPath) {
        Remove-Item $bootstrapLockPath -Force
    }
}
