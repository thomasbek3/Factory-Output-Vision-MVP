Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-RepoRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}

function Get-DefaultVenvPath {
    param(
        [string]$RepoRoot
    )

    return Join-Path $RepoRoot ".venv"
}

function Get-VenvPythonPath {
    param(
        [string]$VenvPath
    )

    return Join-Path $VenvPath "Scripts\python.exe"
}

function Ensure-Directory {
    param(
        [string]$Path
    )

    if (-not (Test-Path $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }

    return (Resolve-Path $Path).Path
}

function Assert-Command {
    param(
        [string]$Name,
        [string]$InstallHint = ""
    )

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        if ($InstallHint) {
            throw "Required command '$Name' was not found. $InstallHint"
        }
        throw "Required command '$Name' was not found on PATH."
    }
}

function Import-EnvFile {
    param(
        [string]$Path
    )

    $values = @{}
    if (-not (Test-Path $Path)) {
        return $values
    }

    foreach ($line in Get-Content $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) {
            continue
        }

        $separatorIndex = $trimmed.IndexOf("=")
        if ($separatorIndex -lt 1) {
            continue
        }

        $key = $trimmed.Substring(0, $separatorIndex).Trim()
        $value = $trimmed.Substring($separatorIndex + 1).Trim()

        if (
            ($value.StartsWith('"') -and $value.EndsWith('"')) -or
            ($value.StartsWith("'") -and $value.EndsWith("'"))
        ) {
            $value = $value.Substring(1, $value.Length - 2)
        }

        Set-Item -Path "Env:$key" -Value $value
        $values[$key] = $value
    }

    return $values
}

function Get-EnvValue {
    param(
        [hashtable]$EnvValues,
        [string]$Name,
        [string]$DefaultValue = ""
    )

    if ($EnvValues.ContainsKey($Name) -and $EnvValues[$Name] -ne "") {
        return [string]$EnvValues[$Name]
    }

    $item = Get-Item -Path "Env:$Name" -ErrorAction SilentlyContinue
    if ($null -ne $item -and $item.Value -ne "") {
        return [string]$item.Value
    }

    return $DefaultValue
}

function Resolve-BootstrapPython {
    $candidates = @(
        @{ Command = "py"; Arguments = @("-3.14") },
        @{ Command = "py"; Arguments = @("-3.13") },
        @{ Command = "py"; Arguments = @("-3.12") },
        @{ Command = "py"; Arguments = @("-3.11") },
        @{ Command = "py"; Arguments = @("-3.10") },
        @{ Command = "python"; Arguments = @() }
    )

    foreach ($candidate in $candidates) {
        if (-not (Get-Command $candidate.Command -ErrorAction SilentlyContinue)) {
            continue
        }

        try {
            $json = & $candidate.Command @($candidate.Arguments) -c "import json,sys; print(json.dumps({'major':sys.version_info[0],'minor':sys.version_info[1],'executable':sys.executable}))"
            if ($LASTEXITCODE -ne 0) {
                continue
            }

            $info = $json | ConvertFrom-Json
            if ($info.major -eq 3 -and $info.minor -ge 10) {
                return [pscustomobject]@{
                    Command    = [string]$candidate.Command
                    Arguments  = [string[]]$candidate.Arguments
                    Executable = [string]$info.executable
                    Version    = "$($info.major).$($info.minor)"
                }
            }
        }
        catch {
            continue
        }
    }

    throw "Python 3.10+ was not found. Install Python and ensure 'py' or 'python' is on PATH."
}

function Invoke-External {
    param(
        [string]$Command,
        [string[]]$Arguments = @(),
        [string]$WorkingDirectory = ""
    )

    $originalLocation = Get-Location
    try {
        if ($WorkingDirectory) {
            Set-Location $WorkingDirectory
        }

        & $Command @Arguments
        $exitCode = if ($null -eq $LASTEXITCODE) { 0 } else { [int]$LASTEXITCODE }
        if ($exitCode -ne 0) {
            throw "Command failed with exit code ${exitCode}: $Command $($Arguments -join ' ')"
        }
    }
    finally {
        Set-Location $originalLocation
    }
}

function Get-FrontendIndexPath {
    param(
        [string]$RepoRoot
    )

    return Join-Path $RepoRoot "frontend\dist\index.html"
}

function Get-RunDir {
    param(
        [string]$RepoRoot
    )

    return Ensure-Directory (Join-Path $RepoRoot "data\run")
}

function Get-InstallMarkerPath {
    param(
        [string]$RepoRoot
    )

    return Join-Path (Get-RunDir -RepoRoot $RepoRoot) "install-complete.txt"
}

function Get-BootstrapLockPath {
    param(
        [string]$RepoRoot
    )

    return Join-Path (Get-RunDir -RepoRoot $RepoRoot) "bootstrap-in-progress.lock"
}

function Get-PidFilePath {
    param(
        [string]$RepoRoot
    )

    return Join-Path (Get-RunDir -RepoRoot $RepoRoot) "factory_counter.pid"
}

function Get-StdoutLogPath {
    param(
        [string]$RepoRoot
    )

    return Join-Path (Ensure-Directory (Join-Path $RepoRoot "data\logs")) "uvicorn.stdout.log"
}

function Get-StderrLogPath {
    param(
        [string]$RepoRoot
    )

    return Join-Path (Ensure-Directory (Join-Path $RepoRoot "data\logs")) "uvicorn.stderr.log"
}

function Test-ProcessRunning {
    param(
        [int]$ProcessId
    )

    try {
        Get-Process -Id $ProcessId -ErrorAction Stop | Out-Null
        return $true
    }
    catch {
        return $false
    }
}

function Test-VenvReady {
    param(
        [string]$PythonExe
    )

    if (-not (Test-Path $PythonExe)) {
        return $false
    }

    try {
        & $PythonExe -c "import fastapi, uvicorn; print('ok')" | Out-Null
        return ($LASTEXITCODE -eq 0)
    }
    catch {
        return $false
    }
}
