Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot "Common.ps1")

$repoRoot = Get-RepoRoot
$pidFile = Get-PidFilePath -RepoRoot $repoRoot

if (-not (Test-Path $pidFile)) {
    Write-Host "Factory Counter is not running."
    exit 0
}

$pidRaw = (Get-Content $pidFile -Raw).Trim()
if (-not $pidRaw) {
    Remove-Item $pidFile -Force
    Write-Host "Removed stale PID file."
    exit 0
}

$processId = [int]$pidRaw
if (-not (Test-ProcessRunning -ProcessId $processId)) {
    Remove-Item $pidFile -Force
    Write-Host "Removed stale PID file for process $processId."
    exit 0
}

Stop-Process -Id $processId -Force
Remove-Item $pidFile -Force
Write-Host "Stopped Factory Counter process $processId."
