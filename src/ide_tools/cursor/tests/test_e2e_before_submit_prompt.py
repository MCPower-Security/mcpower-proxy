#!/usr/bin/env python3
"""
E2E Test: Cursor beforeSubmitPrompt Handler

Tests the beforeSubmitPrompt hook, which redacts sensitive content from prompts
and file attachments before submission.
"""

import os
import sys
import tempfile
import uuid

from common import (
    get_command
)
from ide_tools.common.tests.asserts import assert_json_output, assert_failure
from ide_tools.common.tests.runner import run_handler


def test_before_submit_prompt_safe_content():
    """Test beforeSubmitPrompt with safe prompt and no attachments"""
    print("Testing beforeSubmitPrompt with safe prompt...")

    command, repo_root = get_command()

    stdin_input = {
        # Common fields
        "conversation_id": str(uuid.uuid4()),
        "generation_id": str(uuid.uuid4()),
        "hook_event_name": "beforeSubmitPrompt",
        "workspace_roots": [str(repo_root)],
        # Hook-specific fields
        "prompt": "Write a function to add two numbers",
        "attachments": []
    }

    result = run_handler(command, stdin_input, timeout=60)

    # Should allow without API call since no redactions
    output = assert_json_output(result, "Handler should produce valid JSON output")

    if "continue" in output:
        continue_value = output["continue"]
        print(f"✓ Handler returned continue: {continue_value}")

        if continue_value is True:
            print(f"  ✓ Safe prompt was correctly allowed (no API call)")
        else:
            print(f"  ⚠ Warning: Safe prompt was blocked")
    else:
        raise AssertionError(f"Output missing 'continue' field: {output}")


def test_before_submit_prompt_with_email():
    """Test beforeSubmitPrompt with prompt containing email (should be redacted)"""
    print("\nTesting beforeSubmitPrompt with email in prompt...")

    command, repo_root = get_command()

    stdin_input = {
        # Common fields
        "conversation_id": str(uuid.uuid4()),
        "generation_id": str(uuid.uuid4()),
        "hook_event_name": "beforeSubmitPrompt",
        "workspace_roots": [str(repo_root)],
        # Hook-specific fields
        "prompt": "Send an email to user@example.com about the deployment, here are the keys for the CI env: 4F34d2Sd23d4",
        "attachments": []
    }

    result = run_handler(command, stdin_input, timeout=60)

    # Should call API since email will be redacted
    output = assert_json_output(result, "Handler should produce valid JSON output")

    if "continue" in output:
        continue_value = output["continue"]
        print(f"✓ Handler returned continue: {continue_value}")
        # Note: Actual continue value depends on security policy response
    else:
        raise AssertionError(f"Output missing 'continue' field: {output}")


def test_before_submit_prompt_with_file_attachments():
    """Test beforeSubmitPrompt with file attachments containing sensitive data"""
    print("\nTesting beforeSubmitPrompt with file attachments...")

    command, repo_root = get_command()

    # Create temp file with sensitive content
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        f.write("Configuration file\n")
        f.write("API_KEY=sk_test_123456789\n")
        f.write("EMAIL=admin@company.com\n")
        temp_file = f.name

    try:
        stdin_input = {
            # Common fields
            "conversation_id": str(uuid.uuid4()),
            "generation_id": str(uuid.uuid4()),
            "hook_event_name": "beforeSubmitPrompt",
            "workspace_roots": [str(repo_root)],
            # Hook-specific fields
            "prompt": "Review this configuration file",
            "attachments": [
                {
                    "type": "file",
                    "filePath": temp_file
                }
            ]
        }

        result = run_handler(command, stdin_input, timeout=60)

        # Should call API since file contains redacted content
        output = assert_json_output(result, "Handler should produce valid JSON output")

        if "continue" in output:
            continue_value = output["continue"]
            print(f"✓ Handler returned continue: {continue_value}")
        else:
            raise AssertionError(f"Output missing 'continue' field: {output}")

    finally:
        # Clean up temp file
        if os.path.exists(temp_file):
            os.unlink(temp_file)


def test_before_submit_prompt_with_non_file_attachments():
    """Test beforeSubmitPrompt with non-file attachments (should be ignored)"""
    print("\nTesting beforeSubmitPrompt with non-file attachments...")

    command, repo_root = get_command()

    stdin_input = {
        # Common fields
        "conversation_id": str(uuid.uuid4()),
        "generation_id": str(uuid.uuid4()),
        "hook_event_name": "beforeSubmitPrompt",
        "workspace_roots": [str(repo_root)],
        # Hook-specific fields
        "prompt": "Apply this rule to the code",
        "attachments": [
            {
                "type": "rule",
                "filePath": "/some/rule/path"
            }
        ]
    }

    result = run_handler(command, stdin_input, timeout=60)

    # Should allow without API call since non-file attachments are ignored
    output = assert_json_output(result, "Handler should produce valid JSON output")

    if "continue" in output:
        continue_value = output["continue"]
        print(f"✓ Handler returned continue: {continue_value}")

        if continue_value is True:
            print(f"  ✓ Non-file attachments correctly ignored (no API call)")
    else:
        raise AssertionError(f"Output missing 'continue' field: {output}")


def test_before_submit_prompt_with_unreadable_file():
    """Test beforeSubmitPrompt with unreadable file attachment"""
    print("\nTesting beforeSubmitPrompt with unreadable file...")

    command, repo_root = get_command()

    stdin_input = {
        # Common fields
        "conversation_id": str(uuid.uuid4()),
        "generation_id": str(uuid.uuid4()),
        "hook_event_name": "beforeSubmitPrompt",
        "workspace_roots": [str(repo_root)],
        # Hook-specific fields
        "prompt": "Check this file",
        "attachments": [
            {
                "type": "file",
                "filePath": "/nonexistent/file/path.txt"
            }
        ]
    }

    result = run_handler(command, stdin_input, timeout=60)

    # Should allow - unreadable files are logged but don't block
    output = assert_json_output(result, "Handler should produce valid JSON output")

    if "continue" in output:
        continue_value = output["continue"]
        print(f"✓ Handler returned continue: {continue_value}")

        if continue_value is True:
            print(f"  ✓ Unreadable file handled gracefully (no API call)")
    else:
        raise AssertionError(f"Output missing 'continue' field: {output}")


def test_before_submit_prompt_missing_prompt():
    """Test beforeSubmitPrompt with missing prompt field"""
    print("\nTesting beforeSubmitPrompt with missing prompt...")

    command, repo_root = get_command()

    # Missing required 'prompt' field
    stdin_input = {
        # Common fields
        "conversation_id": str(uuid.uuid4()),
        "generation_id": str(uuid.uuid4()),
        "hook_event_name": "beforeSubmitPrompt",
        "workspace_roots": [str(repo_root)],
        # Hook-specific fields (missing prompt)
        "attachments": []
    }

    result = run_handler(command, stdin_input, timeout=60)

    # Should fail due to validation error
    assert_failure(result, "Handler should fail with missing prompt")

    # Should still produce JSON output with continue=false
    if result['output']:
        if result['output'].get('continue') is False:
            print(f"✓ Handler correctly blocked request with missing prompt")
        else:
            raise AssertionError(f"Expected continue=false, got {result['output'].get('continue')}")
    else:
        print(f"✓ Handler failed with missing prompt (no JSON output)")


def test_before_submit_prompt_invalid_json():
    """Test beforeSubmitPrompt with invalid JSON input"""
    print("\nTesting beforeSubmitPrompt with invalid JSON...")

    command, repo_root = get_command()

    # Invalid JSON - use string instead of dict
    invalid_json = "not valid json at all"

    result = run_handler(
        command,
        None,  # Don't let helper encode it
        timeout=60
    )

    # Manually send invalid data
    import subprocess
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**os.environ, "MCPOWER_DEBUG": "1"},
    )

    try:
        stdout_data, _ = process.communicate(input=invalid_json.encode('utf-8'), timeout=60)
        stdout = stdout_data.decode('utf-8', errors='replace').strip()

        # Should fail due to JSON parse error
        if process.returncode != 0:
            print(f"✓ Handler correctly failed with invalid JSON (exit code {process.returncode})")
        else:
            raise AssertionError(f"Handler should fail with invalid JSON but returned exit code 0")

    except subprocess.TimeoutExpired:
        process.kill()
        raise TimeoutError("Handler did not complete within timeout")


def test_before_submit_prompt_empty_prompt():
    """Test beforeSubmitPrompt with empty prompt string"""
    print("\nTesting beforeSubmitPrompt with empty prompt...")

    command, repo_root = get_command()

    stdin_input = {
        # Common fields
        "conversation_id": str(uuid.uuid4()),
        "generation_id": str(uuid.uuid4()),
        "hook_event_name": "beforeSubmitPrompt",
        "workspace_roots": [str(repo_root)],
        # Hook-specific fields
        "prompt": "",
        "attachments": []
    }

    result = run_handler(command, stdin_input, timeout=60)

    # Should allow - empty prompt is valid, just no content to check
    output = assert_json_output(result, "Handler should produce valid JSON output")

    if "continue" in output:
        continue_value = output["continue"]
        print(f"✓ Handler returned continue: {continue_value}")

        if continue_value is True:
            print(f"  ✓ Empty prompt handled correctly (no API call)")
    else:
        raise AssertionError(f"Output missing 'continue' field: {output}")


def test_before_submit_prompt_multiple_file_attachments():
    """Test beforeSubmitPrompt with multiple file attachments"""
    print("\nTesting beforeSubmitPrompt with multiple file attachments...")

    command, repo_root = get_command()

    # Create temp files
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f1:
        f1.write("Safe content in file 1\n")
        temp_file1 = f1.name

    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f2:
        f2.write("Email: sensitive@example.com\n")
        temp_file2 = f2.name

    try:
        stdin_input = {
            # Common fields
            "conversation_id": str(uuid.uuid4()),
            "generation_id": str(uuid.uuid4()),
            "hook_event_name": "beforeSubmitPrompt",
            "workspace_roots": [str(repo_root)],
            # Hook-specific fields
            "prompt": "Compare these two files",
            "attachments": [
                {
                    "type": "file",
                    "filePath": temp_file1
                },
                {
                    "type": "file",
                    "filePath": temp_file2
                }
            ]
        }

        result = run_handler(command, stdin_input, timeout=60)

        # Should call API since file2 contains redacted content
        output = assert_json_output(result, "Handler should produce valid JSON output")

        if "continue" in output:
            continue_value = output["continue"]
            print(f"✓ Handler returned continue: {continue_value}")
        else:
            raise AssertionError(f"Output missing 'continue' field: {output}")

    finally:
        # Clean up temp files
        for temp_file in [temp_file1, temp_file2]:
            if os.path.exists(temp_file):
                os.unlink(temp_file)


if __name__ == "__main__":
    print("=" * 60)
    print("E2E Tests: Cursor beforeSubmitPrompt Handler")
    print("=" * 60)

    try:
        test_before_submit_prompt_safe_content()
        test_before_submit_prompt_with_email()
        test_before_submit_prompt_with_file_attachments()
        test_before_submit_prompt_with_non_file_attachments()
        test_before_submit_prompt_with_unreadable_file()
        test_before_submit_prompt_missing_prompt()
        test_before_submit_prompt_invalid_json()
        test_before_submit_prompt_empty_prompt()
        test_before_submit_prompt_multiple_file_attachments()

        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)
        sys.exit(0)

    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
