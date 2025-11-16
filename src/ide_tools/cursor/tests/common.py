#!/usr/bin/env python3
"""
E2E Test commons

Base test utilities for testing IDE tool handlers
"""

import logging
from typing import Dict, Any

logging.basicConfig(level=logging.WARNING, format='%(message)s')
logger = logging.getLogger(__name__)


def assert_success(result: Dict[str, Any], message: str = "Handler should succeed"):
    """Assert that the handler succeeded (exit code 0)"""
    if result['returncode'] != 0:
        raise AssertionError(
            f"{message}\n"
            f"Exit code: {result['returncode']}\n"
            f"Stdout: {result['stdout']}\n"
            f"Stderr: {result['stderr']}"
        )


def get_command():
    """
    Get uvx command for running a Cursor IDE tool handler
    
    Returns:
        Tuple of (command list, repo_root path)
    """
    from pathlib import Path

    # Get repo root for uvx command
    test_dir = Path(__file__).parent
    cursor_dir = test_dir.parent
    ide_tools_dir = cursor_dir.parent
    src_dir = ide_tools_dir.parent
    repo_root = src_dir.parent

    command = [
        "uvx",
        "--from",
        str(repo_root),
        "defenter-proxy",
        "--ide-tool",
        "--ide", "cursor",
    ]
    return command, repo_root
