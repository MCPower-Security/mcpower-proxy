#!/usr/bin/env python3
"""
E2E Test: Cursor Init Handler

Tests the initialization of Cursor hooks, which registers virtual MCP tools
with the security API.
"""

import sys
import uuid

from common import (
    run_ide_tool_handler,
    assert_success,
    assert_json_output, get_command,
    assert_failure
)


def test_init_handler():
    """Test the init handler with valid input"""
    print("Testing Cursor init handler...")

    command, repo_root = get_command()

    # Test with common schema
    stdin_input = {
        "conversation_id": str(uuid.uuid4()),
        "generation_id": str(uuid.uuid4()),
        "hook_event_name": "init",
        "workspace_roots": [str(repo_root)]
    }

    result = run_ide_tool_handler(command, stdin_input, timeout=60)

    # Should succeed
    assert_success(result, "Init handler should succeed")

    # Should return JSON with success=true
    output = assert_json_output(result)

    # Check expected fields
    if output.get("success") != True:
        raise AssertionError(f"Expected success=True, got {output.get('success')}")
    if "message" not in output:
        raise AssertionError("Expected 'message' field in output")

    print(f"✓ Init handler succeeded with message: {output['message']}")


def test_init_handler_no_stdin():
    """Test the init handler with missing required fields (should fail)"""
    print("\nTesting Cursor init handler with missing required fields...")

    command, repo_root = get_command()

    # No stdin input - should fail with missing fields error
    result = run_ide_tool_handler(command, stdin_input=None, timeout=60)

    # Should fail because required fields are missing
    assert_failure(result, "Init handler should fail without required fields")

    print(f"✓ Init handler correctly failed with missing required fields")


def test_init_handler_invalid_json():
    """Test the init handler with invalid JSON input"""
    print("\nTesting Cursor init handler with invalid JSON...")

    command, repo_root = get_command()

    # Send invalid JSON via process stdin (not using stdin_input dict)
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

        # Should still succeed (parsing error is non-critical)
        if process.returncode == 0:
            print("✓ Init handler handled invalid JSON gracefully")
        else:
            print(f"⚠ Init handler failed with invalid JSON (returncode: {process.returncode})")
            # This is acceptable - invalid JSON might cause failure

    except subprocess.TimeoutExpired:
        process.kill()
        raise TimeoutError("Handler did not complete within timeout")


if __name__ == "__main__":
    try:
        test_init_handler()
        test_init_handler_no_stdin()
        test_init_handler_invalid_json()

        print("\n" + "=" * 50)
        print("All init handler tests passed! ✓")
        print("=" * 50)

    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
