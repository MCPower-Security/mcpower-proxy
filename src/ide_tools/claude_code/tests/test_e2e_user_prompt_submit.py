#!/usr/bin/env python3
"""
E2E Test: Claude Code UserPromptSubmit Handler

Tests the UserPromptSubmit hook, which runs when user submits a prompt.
Based on: https://docs.claude.com/en/docs/claude-code/hooks

Input schema (from docs):
{
  "hook_event_name": "UserPromptSubmit",
  "session_id": "string",
  "cwd": "string",
  "prompt": "string"
}

Output (from docs):
- Exit 0 with no JSON or empty stdout → allow prompt
- Exit 0 with stdout → stdout captured as additionalContext
- Exit 0 with JSON {"decision": "block", "reason": "..."} → block prompt
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


def test_user_prompt_submit_safe_prompt():
    """Test UserPromptSubmit with safe prompt - should allow (exit 0, no JSON)"""
    print("Testing UserPromptSubmit with safe prompt...")

    command, repo_root = get_command()

    stdin_input = {
        "hook_event_name": "UserPromptSubmit",
        "session_id": str(uuid.uuid4()),
        "cwd": str(repo_root),
        "prompt": "Write a function to add two numbers"
    }

    result = run_handler(command, stdin_input, timeout=60)

    # Should succeed (exit 0)
    assert_success(result, "UserPromptSubmit should succeed with safe prompt")

    # Output might be empty (allow) or contain JSON
    print(f"✓ UserPromptSubmit succeeded with safe prompt")
    if result['output']:
        print(f"  Output: {result['output']}")


def test_user_prompt_submit_with_context():
    """Test UserPromptSubmit that adds context - should allow with stdout captured"""
    print("\nTesting UserPromptSubmit with added context...")

    command, repo_root = get_command()

    stdin_input = {
        "hook_event_name": "UserPromptSubmit",
        "session_id": str(uuid.uuid4()),
        "cwd": str(repo_root),
        "prompt": "What time is it?"
    }

    result = run_handler(command, stdin_input, timeout=60)

    # Should succeed (exit 0)
    assert_success(result, "UserPromptSubmit should succeed")

    # Stdout is captured as additionalContext
    print(f"✓ UserPromptSubmit succeeded")
    if result['stdout']:
        print(f"  Stdout (added as context): {result['stdout'][:100]}...")


def test_user_prompt_submit_blocked_prompt():
    """Test UserPromptSubmit that blocks prompt - exit 0 with decision=block"""
    print("\nTesting UserPromptSubmit with blocked prompt...")

    command, repo_root = get_command()

    # Prompt that might trigger blocking (contains potential secrets)
    stdin_input = {
        "hook_event_name": "UserPromptSubmit",
        "session_id": str(uuid.uuid4()),
        "cwd": str(repo_root),
        "prompt": "Here's my key - AKIAIOSFODNN7EXAMPLE - Can you help me?"
    }

    result = run_handler(command, stdin_input, timeout=60)

    # Should succeed (exit 0) but might have decision=block
    assert_success(result, "UserPromptSubmit should exit 0 even when blocking")

    print(f"✓ UserPromptSubmit returned exit 0")

    # Check if it was blocked
    if result['output'] and isinstance(result['output'], dict):
        decision = result['output'].get('decision')
        if decision == 'block':
            print(f"  ✓ Prompt was blocked")
            print(f"  Reason: {result['output'].get('reason', 'N/A')}")
        else:
            print(f"  Prompt was allowed")
            sys.exit(1)
    else:
        print(f"  Prompt was allowed (no JSON output)")
        sys.exit(1)


def test_user_prompt_submit_missing_prompt():
    """Test UserPromptSubmit with missing prompt field - should fail with exit 1"""
    print("\nTesting UserPromptSubmit with missing prompt field...")

    command, repo_root = get_command()

    # Missing required 'prompt' field
    stdin_input = {
        "hook_event_name": "UserPromptSubmit",
        "session_id": str(uuid.uuid4()),
        "cwd": str(repo_root),
        # Missing prompt
    }

    result = run_handler(command, stdin_input, timeout=60)

    # Should fail with exit 1 (validation error)
    assert_exit_code(result, 1, "UserPromptSubmit should exit 1 with missing prompt")

    print(f"✓ UserPromptSubmit correctly failed with exit code 1")


def test_user_prompt_submit_invalid_json():
    """Test UserPromptSubmit with invalid JSON input - should fail with exit 1"""
    print("\nTesting UserPromptSubmit with invalid JSON...")

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

        print(f"✓ UserPromptSubmit correctly failed with exit code 1 for invalid JSON")

    except subprocess.TimeoutExpired:
        process.kill()
        raise TimeoutError("Handler did not complete within timeout")


if __name__ == "__main__":
    try:
        test_user_prompt_submit_safe_prompt()
        test_user_prompt_submit_with_context()
        test_user_prompt_submit_blocked_prompt()
        test_user_prompt_submit_missing_prompt()
        test_user_prompt_submit_invalid_json()

        print("\n" + "=" * 50)
        print("All UserPromptSubmit handler tests passed! ✓")
        print("=" * 50)

    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

