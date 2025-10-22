#!/usr/bin/env bash

set -euo pipefail

log() {
    printf '%s\n' "$1"
}

ensure_git() {
    if command -v git >/dev/null 2>&1; then
        return 0
    fi

    log "Git not found; attempting to install via Xcode Command Line Tools"
    
    # Try Xcode Command Line Tools first (includes Git)
    xcode-select --install 2>/dev/null || true
    
    # Wait for user to complete installation
    log "Waiting for Xcode Command Line Tools installation..."
    sleep 300
    
    if command -v git >/dev/null 2>&1; then
        return 0
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
        # shellcheck disable=SC2016
        log "uv installation succeeded but not on PATH; ensure \"$HOME/.local/bin\" is in PATH"
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

main() {
    log "Ensuring Git and uvx are installed (macOS)"
    ensure_git
    ensure_uv
    ensure_uvx
    log "Git and uvx ready"
}

main "$@"

