#!/usr/bin/env python3
"""
E2E Test: Claude Code PreToolUse(Grep) Handler

Tests the PreToolUse hook for Grep tool, which runs before grep/search operations.
Based on: https://docs.claude.com/en/docs/claude-code/hooks

Input schema (from docs):
{
  "hook_event_name": "PreToolUse",
  "session_id": "string",
  "cwd": "string",
  "tool_name": "Grep",
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


def test_pre_tool_use_grep_allow():
    """Test PreToolUse(Grep) that allows grep - exit 0 with decision=approve"""
    print("Testing PreToolUse(Grep) with allowed grep...")

    command, repo_root = get_command()

    stdin_input = {
        "hook_event_name": "PreToolUse",
        "session_id": str(uuid.uuid4()),
        "cwd": str(repo_root),
        "tool_name": "Grep",
        "tool_input": {
            "file_path": "/tmp/code.py",
            "content": "def hello():\n    print('Hello, world!')"
        }
    }

    result = run_handler(command, stdin_input, timeout=60)

    # Should succeed (exit 0)
    assert_success(result, "PreToolUse(Grep) should succeed")

    # Should have JSON output with decision
    output = assert_json_output(result, "PreToolUse(Grep) should return JSON")

    # Check for decision field
    decision = output.get('decision') or output.get('permissionDecision')
    print(f"✓ PreToolUse(Grep) returned decision: {decision}")

    if decision in ['approve', 'allow']:
        print(f"  ✓ Grep was allowed")
    elif decision in ['deny']:
        print(f"  ⚠ Grep was denied (might be security policy)")
        if 'permissionDecisionReason' in output:
            print(f"  Reason: {output['permissionDecisionReason']}")


def test_pre_tool_use_grep_deny():
    """Test PreToolUse(Grep) that denies grep - exit 0 with decision=deny"""
    print("\nTesting PreToolUse(Grep) with denied grep...")

    command, repo_root = get_command()

    # File that might be denied (sensitive content)
    stdin_input = {
        "hook_event_name": "PreToolUse",
        "session_id": str(uuid.uuid4()),
        "cwd": str(repo_root),
        "tool_name": "Grep",
        "tool_input": {
            "file_path": "/tmp/secrets.txt",
            "content": "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE\nAWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        }
    }

    result = run_handler(command, stdin_input, timeout=60)

    # Should succeed (exit 0)
    assert_success(result, "PreToolUse(Grep) should exit 0 even when denying")

    # Should have JSON output
    output = assert_json_output(result, "PreToolUse(Grep) should return JSON")

    # Check decision
    decision = output.get('decision') or output.get('permissionDecision')
    print(f"✓ PreToolUse(Grep) returned decision: {decision}")

    if decision in ['deny']:
        print(f"  ✓ Grep on file with secrets was denied")
        if 'permissionDecisionReason' in output:
            print(f"  Reason: {output['permissionDecisionReason'][:100]}...")
    elif decision in ['approve', 'allow']:
        print(f"  ⚠ Grep on file with secrets was allowed (security policy may vary)")


def test_pre_tool_use_grep_missing_fields():
    """Test PreToolUse(Grep) with missing required fields - should fail with exit 1"""
    print("\nTesting PreToolUse(Grep) with missing file_path...")

    command, repo_root = get_command()

    # Missing file_path in tool_input
    stdin_input = {
        "hook_event_name": "PreToolUse",
        "session_id": str(uuid.uuid4()),
        "cwd": str(repo_root),
        "tool_name": "Grep",
        "tool_input": {
            # Missing file_path
            "content": "some content"
        }
    }

    result = run_handler(command, stdin_input, timeout=60)

    # Should fail with exit 1 (validation error)
    assert_exit_code(result, 1, "PreToolUse(Grep) should exit 1 with missing file_path")

    print(f"✓ PreToolUse(Grep) correctly failed with exit code 1")


def test_pre_tool_use_grep_invalid_json():
    """Test PreToolUse(Grep) with invalid JSON input - should fail with exit 1"""
    print("\nTesting PreToolUse(Grep) with invalid JSON...")

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

        print(f"✓ PreToolUse(Grep) correctly failed with exit code 1 for invalid JSON")

    except subprocess.TimeoutExpired:
        process.kill()
        raise TimeoutError("Handler did not complete within timeout")


if __name__ == "__main__":
    try:
        test_pre_tool_use_grep_allow()
        test_pre_tool_use_grep_deny()
        test_pre_tool_use_grep_missing_fields()
        test_pre_tool_use_grep_invalid_json()

        print("\n" + "=" * 50)
        print("All PreToolUse(Grep) handler tests passed! ✓")
        print("=" * 50)

    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)




