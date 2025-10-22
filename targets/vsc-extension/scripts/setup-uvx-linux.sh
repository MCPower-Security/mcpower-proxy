#!/usr/bin/env bash

set -euo pipefail

log() {
    printf '%s\n' "$1"
}

ensure_git() {
    if command -v git >/dev/null 2>&1; then
        return 0
    fi

    log "Git not found; attempting installation"
    
    if command -v apt-get >/dev/null 2>&1; then
        sudo apt-get update && sudo apt-get install -y git
    elif command -v yum >/dev/null 2>&1; then
        sudo yum install -y git
    elif command -v dnf >/dev/null 2>&1; then
        sudo dnf install -y git
    elif command -v pacman >/dev/null 2>&1; then
        sudo pacman -S --noconfirm git
    else
        log "Package manager not detected; cannot auto-install Git"
        return 1
    fi

    if ! command -v git >/dev/null 2>&1; then
        log "Git installation failed"
        return 1
    fi
}

ensure_uv() {
    if command -v uv >/dev/null 2>&1; then
        return 0
    fi

    log "uv not found; installing via Astral installer"
    curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1

    if ! command -v uv >/dev/null 2>&1; then
        export PATH="$HOME/.local/bin:$PATH"
    fi

    if ! command -v uv >/dev/null 2>&1; then
        log "uv still unavailable after installation"
        return 1
    fi
}

ensure_uvx() {
    if command -v uvx >/dev/null 2>&1; then
        return 0
    fi

    log "uvx shim missing; refreshing uv installation"
    uv self install >/dev/null 2>&1

    if ! command -v uvx >/dev/null 2>&1; then
        log "uvx not available; ensure uv is on PATH"
        return 1
    fi
}

cache_mcpower_proxy() {
    local version="0.0.47"
    
    log "Pre-warming mcpower-proxy v${version} cache..."
    uvx --from "git+https://github.com/MCPower-Security/mcpower-proxy.git@v${version}" mcpower-proxy --help >/dev/null 2>&1 || true
}

main() {
    log "Ensuring Git and uvx are installed (Linux)"
    ensure_git
    ensure_uv
    ensure_uvx
    cache_mcpower_proxy
    log "Git and uvx ready"
}

main "$@"

