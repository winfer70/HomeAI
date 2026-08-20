# Loads .env.local (repo root, gitignored) into the current PowerShell session's
# environment variables. Usage (from repo root): . .\heimdall\scripts\Load-EnvLocal.ps1
# See .env.local.example for the full list of variables and which scripts need which.

$envFile = Join-Path (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)) ".env.local"

if (-not (Test-Path $envFile)) {
    Write-Error ".env.local not found at $envFile - copy .env.local.example to .env.local and fill in real values first."
    return
}

Get-Content $envFile | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
        $key, $value = $line -split "=", 2
        if ($value) {
            [System.Environment]::SetEnvironmentVariable($key.Trim(), $value.Trim(), "Process")
        }
    }
}

Write-Host "Loaded environment variables from $envFile into this session."
