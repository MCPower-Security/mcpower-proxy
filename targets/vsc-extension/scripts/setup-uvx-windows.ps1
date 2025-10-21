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
    $scriptContent = (Invoke-WebRequest -UseBasicParsing $installer).Content
    Invoke-Expression "& { $scriptContent }" | Out-Null

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

Write-Log "Ensuring uvx is installed (Windows)"
Ensure-Uv
Ensure-Uvx
Write-Log "uvx ready"

