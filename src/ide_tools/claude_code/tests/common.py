#!/usr/bin/env python3
"""
E2E Test Commons for Claude Code

Base test utilities for testing Claude Code hook handlers
"""

import logging
from typing import Dict, Any

logging.basicConfig(level=logging.WARNING, format='%(message)s')
logger = logging.getLogger(__name__)


def assert_exit_code(result: Dict[str, Any], expected_code: int, message: str = ""):
    """Assert that the handler exited with the expected code"""
    if result['returncode'] != expected_code:
        raise AssertionError(
            f"{message}\n"
            f"Expected exit code: {expected_code}\n"
            f"Actual exit code: {result['returncode']}\n"
            f"Stdout: {result['stdout']}\n"
            f"Stderr: {result['stderr']}"
        )


def assert_success(result: Dict[str, Any], message: str = "Handler should succeed"):
    """Assert that the handler succeeded (exit code 0)"""
    assert_exit_code(result, 0, message)


def get_command():
    """
    Get uvx command for running a Claude Code IDE tool handler
    
    Returns:
        Tuple of (command list, repo_root path)
    """
    from pathlib import Path

    # Get repo root for uvx command
    test_dir = Path(__file__).parent
    claude_code_dir = test_dir.parent
    ide_tools_dir = claude_code_dir.parent
    src_dir = ide_tools_dir.parent
    repo_root = src_dir.parent

    command = [
        "uvx",
        "--from",
        str(repo_root),
        "defenter-proxy",
        "--ide-tool",
        "--ide", "claude-code",
    ]
    return command, repo_root
