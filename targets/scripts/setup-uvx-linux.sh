#!/usr/bin/env bash

set -euo pipefail

log() {
    printf '%s\n' "$1"
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

cache_defenter_proxy() {
    local version="$1"
    local clean_cache="$2"

    if [[ -z "$version" ]]; then
        log "Version parameter is required; skipping cache"
        return 0
    fi

    local refresh_flag=""
    if [[ "$clean_cache" == "--clean-cache" ]]; then
        log "Pre-warming defenter-proxy==$version from PyPI (forcing refresh)..."
        refresh_flag="--refresh"
    else
        log "Pre-warming defenter-proxy==$version from PyPI..."
    fi

    uvx $refresh_flag defenter-proxy=="$version" --help >/dev/null 2>&1 || true
}

main() {
    log "Ensuring uvx is installed (Linux)"
    ensure_uv
    ensure_uvx

    # Cache dependencies if version provided
    if [[ $# -gt 0 ]]; then
        cache_defenter_proxy "$1" "${2:-}"
    fi

    log "uvx ready"
}

main "$@"
