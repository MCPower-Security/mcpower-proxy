#!/usr/bin/env python3
"""
E2E Test: Claude Code SessionStart Handler

Tests the SessionStart hook, which runs when a new Claude Code session begins.
Based on: https://docs.claude.com/en/docs/claude-code/hooks

Input schema (from docs):
{
  "hook_event_name": "SessionStart",
  "session_id": "string",
  "cwd": "string"
}

Output: Exit 0 with stdout captured as context for Claude
"""

import sys
import uuid

from common import (
    assert_success,
    get_command,
    assert_exit_code
)
from ide_tools.common.tests.runner import run_handler


def test_session_start_valid_input():
    """Test SessionStart with valid input - should succeed and capture stdout"""
    print("Testing SessionStart with valid input...")

    command, repo_root = get_command()

    # Valid input per docs
    stdin_input = {
        "hook_event_name": "SessionStart",
        "session_id": str(uuid.uuid4()),
        "cwd": str(repo_root)
    }

    result = run_handler(command, stdin_input, timeout=60)

    # Should succeed (exit 0)
    assert_success(result, "SessionStart should succeed with valid input")

    # Stdout should be captured as context (may be empty or contain output)
    print(f"✓ SessionStart succeeded")
    if result['stdout']:
        print(f"  Stdout (captured as context): {result['stdout'][:100]}...")


def test_session_start_missing_session_id():
    """Test SessionStart with missing session_id - should fail with exit 1"""
    print("\nTesting SessionStart with missing session_id...")

    command, repo_root = get_command()

    # Missing required 'session_id' field
    stdin_input = {
        "hook_event_name": "SessionStart",
        # Missing session_id
        "cwd": str(repo_root)
    }

    result = run_handler(command, stdin_input, timeout=60)

    # Should fail with exit 1 (validation error)
    assert_exit_code(result, 1, "SessionStart should exit 1 with missing session_id")

    print(f"✓ SessionStart correctly failed with exit code 1")


def test_session_start_missing_cwd():
    """Test SessionStart with missing cwd - should fail with exit 1"""
    print("\nTesting SessionStart with missing cwd...")

    command, repo_root = get_command()

    # Missing required 'cwd' field
    stdin_input = {
        "hook_event_name": "SessionStart",
        "session_id": str(uuid.uuid4()),
        # Missing cwd
    }

    result = run_handler(command, stdin_input, timeout=60)

    # Should fail with exit 1 (validation error)
    assert_exit_code(result, 1, "SessionStart should exit 1 with missing cwd")

    print(f"✓ SessionStart correctly failed with exit code 1")


def test_session_start_invalid_json():
    """Test SessionStart with invalid JSON input - should fail with exit 1"""
    print("\nTesting SessionStart with invalid JSON...")

    command, repo_root = get_command()

    # Send invalid JSON via process stdin
    import subprocess
    import os

    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**os.environ, "MCPOWER_DEBUG": "1"},
    )

    try:
        stdout_data, stderr_data = process.communicate(input=b"not valid json", timeout=60)

        # Should fail with exit 1
        assert process.returncode == 1, f"Expected exit code 1, got {process.returncode}"

        print(f"✓ SessionStart correctly failed with exit code 1 for invalid JSON")

    except subprocess.TimeoutExpired:
        process.kill()
        raise TimeoutError("Handler did not complete within timeout")


if __name__ == "__main__":
    try:
        test_session_start_valid_input()
        test_session_start_missing_session_id()
        test_session_start_missing_cwd()
        test_session_start_invalid_json()

        print("\n" + "=" * 50)
        print("All SessionStart handler tests passed! ✓")
        print("=" * 50)

    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
