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
    param($Version, $CleanCache)

    if (-not $Version) {
        Write-Log "Version parameter is required; skipping cache"
        return
    }

    $refreshFlag = @()
    if ($CleanCache -eq "-CleanCache") {
        Write-Log "Pre-warming mcpower-proxy==$Version from PyPI (forcing refresh)..."
        $refreshFlag = @("--refresh")
    } else {
        Write-Log "Pre-warming mcpower-proxy==$Version from PyPI..."
    }

    try {
        $args = $refreshFlag + @("mcpower-proxy==$Version", "--help")
        & uvx $args 2>&1 | Out-Null
    } catch {
        # Ignore errors during cache warming
    }
}

Write-Log "Ensuring uvx is installed (Windows)"
Ensure-Uv
Ensure-Uvx

# Cache dependencies if version provided
if ($args.Count -gt 0) {
    $cleanCacheFlag = if ($args.Count -gt 1) { $args[1] } else { $null }
    Cache-McpowerProxy $args[0] $cleanCacheFlag
}

Write-Log "uvx ready"
