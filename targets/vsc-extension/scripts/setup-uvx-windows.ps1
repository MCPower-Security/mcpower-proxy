Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Log($Message) {
    Write-Host $Message
}

function Ensure-Uv {
    if (Get-Command uv -ErrorAction SilentlyContinue) {
        return
    }

    Write-Log "uv not found; installing via Astral installer"
    $installer = "https://astral.sh/uv/install.ps1"
    Invoke-RestMethod $installer | Invoke-Expression

    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        $localBin = Join-Path $HOME ".local\bin"
        $env:PATH = "$localBin;$env:PATH"
    }

    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        throw "uv installation succeeded but command not found; ensure $HOME\.local\bin is on PATH"
    }
}

function Ensure-Uvx {
    if (Get-Command uvx -ErrorAction SilentlyContinue) {
        return
    }

    Write-Log "uvx shim missing; refreshing uv installation"
    uv self install | Out-Null

    if (-not (Get-Command uvx -ErrorAction SilentlyContinue)) {
        throw "uvx still unavailable; ensure uv is on PATH"
    }
}

function Cache-McpowerProxy {
    param($BundledPath)
    
    if (-not $BundledPath -or -not (Test-Path $BundledPath)) {
        Write-Log "Bundled proxy path not provided or invalid; skipping cache"
        return
    }

    Write-Log "Pre-warming mcpower-proxy cache from bundled source..."
    Push-Location $BundledPath
    try {
        uv sync 2>&1 | Out-Null
    } catch {
        # Ignore errors during cache warming
    }
    Pop-Location
}

Write-Log "Ensuring uvx is installed (Windows)"
Ensure-Uv
Ensure-Uvx

# Cache dependencies if bundled path provided
if ($args.Count -gt 0) {
    Cache-McpowerProxy $args[0]
}

Write-Log "uvx ready"

