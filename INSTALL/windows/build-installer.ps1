param(
    [string]$AppVersion = "0.1.0",
    [switch]$BuildFrontendIfMissing
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot "Common.ps1")

$repoRoot = Get-RepoRoot
$stageRoot = Join-Path $repoRoot "build\windows-installer\payload"
$outputRoot = Join-Path $repoRoot "dist\windows-installer"
$frontendDist = Join-Path $repoRoot "frontend\dist"
$scriptPath = Join-Path $PSScriptRoot "installer.iss"

function Resolve-IsccPath {
    $candidates = @(
        (Get-Command "ISCC.exe" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue),
        "C:\Program Files\Inno Setup 6\ISCC.exe",
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe")
    ) | Where-Object { $_ }

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    throw "Inno Setup compiler was not found. Install Inno Setup 6 first."
}

function Reset-Directory {
    param(
        [string]$Path
    )

    if (Test-Path $Path) {
        Remove-Item -Path $Path -Recurse -Force
    }
    New-Item -ItemType Directory -Path $Path -Force | Out-Null
}

function Copy-Tree {
    param(
        [string]$Source,
        [string]$Destination
    )

    if (-not (Test-Path $Source)) {
        throw "Missing source path: $Source"
    }

    Ensure-Directory $Destination | Out-Null
    Copy-Item -Path (Join-Path $Source "*") -Destination $Destination -Recurse -Force
}

function Remove-PathIfPresent {
    param(
        [string]$Path
    )

    if (Test-Path $Path) {
        Remove-Item -Path $Path -Recurse -Force
    }
}

if (-not (Test-Path $scriptPath)) {
    throw "Missing installer script: $scriptPath"
}

$isccPath = Resolve-IsccPath

if (-not (Test-Path (Join-Path $frontendDist "index.html"))) {
    if (-not $BuildFrontendIfMissing) {
        throw "frontend/dist is missing. Re-run with -BuildFrontendIfMissing or build the frontend first."
    }

    Assert-Command -Name "npm" -InstallHint "Install Node.js to rebuild the frontend."
    Invoke-External -Command "npm" -Arguments @("install") -WorkingDirectory (Join-Path $repoRoot "frontend")
    Invoke-External -Command "npm" -Arguments @("run", "build") -WorkingDirectory (Join-Path $repoRoot "frontend")
}

Reset-Directory -Path $stageRoot
Ensure-Directory $outputRoot | Out-Null

Copy-Tree -Source (Join-Path $repoRoot "app") -Destination (Join-Path $stageRoot "app")
Copy-Tree -Source (Join-Path $repoRoot "demo") -Destination (Join-Path $stageRoot "demo")
Copy-Tree -Source (Join-Path $repoRoot "frontend\dist") -Destination (Join-Path $stageRoot "frontend\dist")
Copy-Tree -Source (Join-Path $repoRoot "INSTALL\windows") -Destination (Join-Path $stageRoot "INSTALL\windows")

Copy-Item -Path (Join-Path $repoRoot "requirements.txt") -Destination (Join-Path $stageRoot "requirements.txt") -Force
Copy-Item -Path (Join-Path $repoRoot ".env.example") -Destination (Join-Path $stageRoot ".env.example") -Force
Copy-Item -Path (Join-Path $repoRoot "README.md") -Destination (Join-Path $stageRoot "README.md") -Force

Get-ChildItem -Path $stageRoot -Directory -Filter "__pycache__" -Recurse | ForEach-Object {
    Remove-Item -Path $_.FullName -Recurse -Force
}

Remove-PathIfPresent -Path (Join-Path $stageRoot "INSTALL\windows\build-installer.ps1")
Remove-PathIfPresent -Path (Join-Path $stageRoot "INSTALL\windows\build-installer.bat")
Remove-PathIfPresent -Path (Join-Path $stageRoot "INSTALL\windows\installer.iss")

Write-Host "Compiling installer..."
Invoke-External -Command $isccPath -Arguments @(
    "/DSourcePath=$stageRoot",
    "/DAppVersion=$AppVersion",
    "/DOutputDir=$outputRoot",
    $scriptPath
)

Write-Host ""
Write-Host "Installer build complete."
Write-Host "Output directory: $outputRoot"
