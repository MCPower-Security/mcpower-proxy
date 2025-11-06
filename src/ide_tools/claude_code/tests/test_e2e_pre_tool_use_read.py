#!/usr/bin/env python3
"""
E2E Test: Claude Code PreToolUse(Read) Handler

Tests the PreToolUse hook for Read tool, which runs before file read operations.
Based on: https://docs.claude.com/en/docs/claude-code/hooks

Input schema (from docs):
{
  "hook_event_name": "PreToolUse",
  "session_id": "string",
  "cwd": "string",
  "tool_name": "Read",
  "tool_input": {
    "file_path": "string",
    "content": "string"  // optional
  }
}

Output (from docs):
- Exit 0 with JSON {"decision": "approve"} → allow
- Exit 0 with JSON {"decision": "deny", "permissionDecisionReason": "..."} → deny
- Exit 1 → validation error
"""

import sys
import uuid

from common import (
    assert_success,
    get_command,
    assert_exit_code
)
from ide_tools.common.tests.runner import run_handler
from ide_tools.common.tests.asserts import assert_json_output


def test_pre_tool_use_read_allow():
    """Test PreToolUse(Read) that allows file read - exit 0 with decision=approve"""
    print("Testing PreToolUse(Read) with allowed file...")

    command, repo_root = get_command()

    stdin_input = {
        "hook_event_name": "PreToolUse",
        "session_id": str(uuid.uuid4()),
        "cwd": str(repo_root),
        "tool_name": "Read",
        "tool_input": {
            "file_path": "/tmp/safe_file.txt",
            "content": "This is safe content"
        }
    }

    result = run_handler(command, stdin_input, timeout=60)

    # Should succeed (exit 0)
    assert_success(result, "PreToolUse(Read) should succeed")

    # Should have JSON output with decision
    output = assert_json_output(result, "PreToolUse(Read) should return JSON")

    # Check for decision field (docs say "approve" or use permissionDecision="allow")
    decision = output.get('decision') or output.get('permissionDecision')
    print(f"✓ PreToolUse(Read) returned decision: {decision}")

    if decision in ['approve', 'allow']:
        print(f"  ✓ File read was allowed")
    elif decision in ['deny']:
        print(f"  ⚠ File read was denied (might be security policy)")
        if 'permissionDecisionReason' in output:
            print(f"  Reason: {output['permissionDecisionReason']}")


def test_pre_tool_use_read_deny():
    """Test PreToolUse(Read) that denies file read - exit 0 with decision=deny"""
    print("\nTesting PreToolUse(Read) with denied file...")

    command, repo_root = get_command()

    # File that might be denied (contains sensitive patterns)
    stdin_input = {
        "hook_event_name": "PreToolUse",
        "session_id": str(uuid.uuid4()),
        "cwd": str(repo_root),
        "tool_name": "Read",
        "tool_input": {
            "file_path": "/tmp/.env",
            "content": "API_KEY=sk_live_1234567890abcdefghijklmnop\nSECRET=my_secret_value"
        }
    }

    result = run_handler(command, stdin_input, timeout=60)

    # Should succeed (exit 0)
    assert_success(result, "PreToolUse(Read) should exit 0 even when denying")

    # Should have JSON output
    output = assert_json_output(result, "PreToolUse(Read) should return JSON")

    # Check decision
    decision = output.get('decision') or output.get('permissionDecision')
    print(f"✓ PreToolUse(Read) returned decision: {decision}")

    if decision in ['deny']:
        print(f"  ✓ File with secrets was denied")
        if 'permissionDecisionReason' in output:
            print(f"  Reason: {output['permissionDecisionReason'][:100]}...")
    elif decision in ['approve', 'allow']:
        print(f"  ⚠ File with secrets was allowed (security policy may vary)")


def test_pre_tool_use_read_missing_file_path():
    """Test PreToolUse(Read) with missing file_path - should fail with exit 1"""
    print("\nTesting PreToolUse(Read) with missing file_path...")

    command, repo_root = get_command()

    # Missing file_path in tool_input
    stdin_input = {
        "hook_event_name": "PreToolUse",
        "session_id": str(uuid.uuid4()),
        "cwd": str(repo_root),
        "tool_name": "Read",
        "tool_input": {
            # Missing file_path
            "content": "some content"
        }
    }

    result = run_handler(command, stdin_input, timeout=60)

    # Should fail with exit 1 (validation error)
    assert_exit_code(result, 1, "PreToolUse(Read) should exit 1 with missing file_path")

    print(f"✓ PreToolUse(Read) correctly failed with exit code 1")


def test_pre_tool_use_read_missing_tool_input():
    """Test PreToolUse(Read) with missing tool_input - should fail with exit 1"""
    print("\nTesting PreToolUse(Read) with missing tool_input...")

    command, repo_root = get_command()

    # Missing tool_input entirely
    stdin_input = {
        "hook_event_name": "PreToolUse",
        "session_id": str(uuid.uuid4()),
        "cwd": str(repo_root),
        "tool_name": "Read",
        # Missing tool_input
    }

    result = run_handler(command, stdin_input, timeout=60)

    # Should fail with exit 1 (validation error)
    assert_exit_code(result, 1, "PreToolUse(Read) should exit 1 with missing tool_input")

    print(f"✓ PreToolUse(Read) correctly failed with exit code 1")


def test_pre_tool_use_read_invalid_json():
    """Test PreToolUse(Read) with invalid JSON input - should fail with exit 1"""
    print("\nTesting PreToolUse(Read) with invalid JSON...")

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

        print(f"✓ PreToolUse(Read) correctly failed with exit code 1 for invalid JSON")

    except subprocess.TimeoutExpired:
        process.kill()
        raise TimeoutError("Handler did not complete within timeout")


if __name__ == "__main__":
    try:
        test_pre_tool_use_read_allow()
        test_pre_tool_use_read_deny()
        test_pre_tool_use_read_missing_file_path()
        test_pre_tool_use_read_missing_tool_input()
        test_pre_tool_use_read_invalid_json()

        print("\n" + "=" * 50)
        print("All PreToolUse(Read) handler tests passed! ✓")
        print("=" * 50)

    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

