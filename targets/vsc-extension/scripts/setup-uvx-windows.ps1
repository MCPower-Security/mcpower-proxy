Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Log($Message) {
    Write-Host $Message
}

function Ensure-Git {
    if (Get-Command git -ErrorAction SilentlyContinue) {
        return
    }

    Write-Log "Git not found; installing via official installer"
    $gitUrl = "https://github.com/git-for-windows/git/releases/download/v2.47.1.windows.1/Git-2.47.1-64-bit.exe"
    $installerPath = Join-Path $env:TEMP "git-installer.exe"
    
    Invoke-WebRequest -Uri $gitUrl -OutFile $installerPath -UseBasicParsing
    Start-Process $installerPath -ArgumentList '/VERYSILENT','/NORESTART','/NOCANCEL','/SP-' -Wait
    Remove-Item $installerPath -Force -ErrorAction SilentlyContinue

    $gitPath = "C:\Program Files\Git\cmd"
    
    # Add Git to system PATH permanently
    $currentPath = [Environment]::GetEnvironmentVariable("PATH", "User")
    if ($currentPath -notlike "*$gitPath*") {
        Write-Log "Adding Git to system PATH"
        [Environment]::SetEnvironmentVariable("PATH", "$gitPath;$currentPath", "User")
    }
    
    # Update current session PATH for verification
    $env:PATH = "$gitPath;$env:PATH"

    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        throw "Git installation succeeded but command not found; new shells will have Git in PATH"
    }
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

Write-Log "Ensuring Git and uvx are installed (Windows)"
Ensure-Git
Ensure-Uv
Ensure-Uvx
Write-Log "Git and uvx ready"

