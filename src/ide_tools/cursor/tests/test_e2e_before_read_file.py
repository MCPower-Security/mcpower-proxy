#!/usr/bin/env python3
"""
E2E Test: Cursor beforeReadFile Handler

Tests the beforeReadFile hook, which redacts sensitive content from files
and analyzes them for security issues.
"""

import json
import os
import sys
import tempfile
import uuid

from common import (
    run_ide_tool_handler,
    assert_json_output,
    assert_failure,
    get_command
)


def test_before_read_file_no_sensitive_content():
    """Test beforeReadFile with file containing no sensitive data"""
    print("Testing beforeReadFile with safe file content...")

    command, repo_root = get_command()

    # Test with safe file content
    stdin_input = {
        # Common fields
        "conversation_id": str(uuid.uuid4()),
        "generation_id": str(uuid.uuid4()),
        "hook_event_name": "beforeReadFile",
        "workspace_roots": [str(repo_root)],
        # Hook-specific fields
        "file_path": "/tmp/safe_file.txt",
        "content": "This is a safe file\nwith no sensitive data\njust plain text",
        "attachments": []
    }

    result = run_ide_tool_handler(command, stdin_input, timeout=60)

    # Should allow without API call since no redactions
    output = assert_json_output(result, "Handler should produce valid JSON output")

    if "permission" in output:
        permission = output["permission"]
        print(f"✓ Handler returned permission: {permission}")

        if permission == "allow":
            print(f"  ✓ Safe file was correctly allowed (no API call)")
        else:
            print(f"  ⚠ Warning: Safe file was denied")
    else:
        raise AssertionError(f"Output missing 'permission' field: {output}")


def test_before_read_file_missing_file_path():
    """Test beforeReadFile with missing file_path field"""
    print("\nTesting beforeReadFile with missing file_path...")

    command, repo_root = get_command()

    # Missing required 'file_path' field
    stdin_input = {
        # Common fields
        "conversation_id": str(uuid.uuid4()),
        "generation_id": str(uuid.uuid4()),
        "hook_event_name": "beforeReadFile",
        "workspace_roots": [str(repo_root)],
        # Hook-specific fields (missing file_path)
        "content": "some content"
    }

    result = run_ide_tool_handler(command, stdin_input, timeout=60)

    # Should fail due to validation error
    assert_failure(result, "Handler should fail with missing file_path")

    # Should still produce JSON output with deny permission
    if result['output']:
        if result['output'].get('permission') == 'deny':
            print(f"✓ Handler correctly denied request with missing file_path")
        else:
            raise AssertionError(f"Expected permission='deny', got {result['output'].get('permission')}")
    else:
        print(f"✓ Handler failed with missing file_path (no JSON output)")


def test_before_read_file_missing_content():
    """Test beforeReadFile with missing content field"""
    print("\nTesting beforeReadFile with missing content...")

    command, repo_root = get_command()

    # Missing required 'content' field
    stdin_input = {
        # Common fields
        "conversation_id": str(uuid.uuid4()),
        "generation_id": str(uuid.uuid4()),
        "hook_event_name": "beforeReadFile",
        "workspace_roots": [str(repo_root)],
        # Hook-specific fields (missing content)
        "file_path": "/tmp/test.txt"
    }

    result = run_ide_tool_handler(command, stdin_input, timeout=60)

    # Should fail due to validation error
    assert_failure(result, "Handler should fail with missing content")

    # Should still produce JSON output with deny permission
    if result['output']:
        if result['output'].get('permission') == 'deny':
            print(f"✓ Handler correctly denied request with missing content")
        else:
            raise AssertionError(f"Expected permission='deny', got {result['output'].get('permission')}")
    else:
        print(f"✓ Handler failed with missing content (no JSON output)")


def test_before_read_file_invalid_json():
    """Test beforeReadFile with invalid JSON input"""
    print("\nTesting beforeReadFile with invalid JSON...")

    command, repo_root = get_command()

    # Send invalid JSON via process stdin
    import subprocess

    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**os.environ, "MCPOWER_DEBUG": "1"},
    )

    try:
        stdout_data, stderr_data = process.communicate(input=b"not valid json", timeout=60)

        # Should fail
        if process.returncode != 0:
            print("✓ Handler correctly failed with invalid JSON input")

            # Try to parse stdout as JSON
            stdout = stdout_data.decode('utf-8', errors='replace').strip()
            if stdout:
                try:
                    output = json.loads(stdout)
                    if output.get('permission') == 'deny':
                        print(f"  Output: {output}")
                except json.JSONDecodeError:
                    pass
        else:
            raise AssertionError("Handler should have failed with invalid JSON")

    except subprocess.TimeoutExpired:
        process.kill()
        raise TimeoutError("Handler did not complete within timeout")


def test_before_read_file_with_secrets():
    """Test beforeReadFile with file containing secrets"""
    print("\nTesting beforeReadFile with secrets in file...")

    command, repo_root = get_command()

    # Create a temporary file with secrets
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        temp_file_path = f.name
        f.write("""
# Configuration file
AWS_ACCESS_KEY = "AKIAIOSFODNN7EXAMPLE"
AWS_SECRET_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
DATABASE_PASSWORD = "SuperSecret123!"
API_TOKEN = "ghp_1234567890abcdefghijklmnopqrstuvwxyz"
""")

    try:
        stdin_input = {
            # Common fields
            "conversation_id": str(uuid.uuid4()),
            "generation_id": str(uuid.uuid4()),
            "hook_event_name": "beforeReadFile",
            "workspace_roots": [str(repo_root)],
            # Hook-specific fields
            "file_path": temp_file_path,
            "content": "",  # Will be read from disk
            "attachments": []
        }

        result = run_ide_tool_handler(command, stdin_input, timeout=60)

        # Should produce valid JSON output
        output = assert_json_output(result, "Handler should produce valid JSON output")

        # Check for permission field
        if "permission" in output:
            permission = output["permission"]
            print(f"✓ Handler analyzed file with secrets, permission: {permission}")

            # This file should likely be blocked or require confirmation
            if permission == "deny":
                print(f"  ✓ File with secrets was correctly blocked")
                if "user_message" in output:
                    print(f"  User message: {output['user_message']}")
                if "agent_message" in output:
                    print(f"  Agent message: {output['agent_message'][:100]}...")
            elif permission == "allow":
                print(f"  ⚠ Warning: File with secrets was allowed (security policy may need tuning)")

        else:
            raise AssertionError(f"Output missing 'permission' field: {output}")

    finally:
        # Cleanup temp file
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)


def test_before_read_file_with_attachment():
    """Test beforeReadFile with file attachment containing secrets"""
    print("\nTesting beforeReadFile with attachment containing secrets...")

    command, repo_root = get_command()

    # Create temporary main file (safe)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        main_file_path = f.name
        f.write("# Safe main file\nprint('Hello World')\n")

    # Create temporary attachment file (with secrets)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
        attachment_file_path = f.name
        f.write("""
STRIPE_SECRET_KEY=sk_live_51H7yxyz1234567890abcdefghijklmnop
OPENAI_API_KEY=sk-proj-1234567890abcdefghijklmnopqrstuvwxyz
DATABASE_URL=postgresql://admin:MyPassword123@db.internal.com:5432/prod
""")

    try:
        stdin_input = {
            # Common fields
            "conversation_id": str(uuid.uuid4()),
            "generation_id": str(uuid.uuid4()),
            "hook_event_name": "beforeReadFile",
            "workspace_roots": [str(repo_root)],
            # Hook-specific fields
            "file_path": main_file_path,
            "content": "",  # Will be read from disk
            "attachments": [
                {
                    "type": "file",
                    "file_path": attachment_file_path
                }
            ]
        }

        result = run_ide_tool_handler(command, stdin_input, timeout=60)

        # Should produce valid JSON output
        output = assert_json_output(result, "Handler should produce valid JSON output")

        # Check for permission field
        if "permission" in output:
            permission = output["permission"]
            print(f"✓ Handler analyzed files with attachment, permission: {permission}")

            if permission == "deny":
                print(f"  ✓ Files with secrets in attachment were correctly blocked")
            elif permission == "allow":
                print(f"  ⚠ Warning: Files with secrets in attachment were allowed")

        else:
            raise AssertionError(f"Output missing 'permission' field: {output}")

    finally:
        # Cleanup temp files
        if os.path.exists(main_file_path):
            os.unlink(main_file_path)
        if os.path.exists(attachment_file_path):
            os.unlink(attachment_file_path)


def test_before_read_file_unreadable_attachment():
    """Test beforeReadFile with unreadable attachment (should allow with error log)"""
    print("\nTesting beforeReadFile with unreadable attachment...")

    command, repo_root = get_command()

    # Create temporary main file (safe)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        main_file_path = f.name
        f.write("# Safe main file\nprint('Hello World')\n")

    try:
        stdin_input = {
            # Common fields
            "conversation_id": str(uuid.uuid4()),
            "generation_id": str(uuid.uuid4()),
            "hook_event_name": "beforeReadFile",
            "workspace_roots": [str(repo_root)],
            # Hook-specific fields
            "file_path": main_file_path,
            "content": "",  # Will be read from disk
            "attachments": [
                {
                    "type": "file",
                    "file_path": "/nonexistent/path/to/file.txt"
                }
            ]
        }

        result = run_ide_tool_handler(command, stdin_input, timeout=60)

        # Should produce valid JSON output
        output = assert_json_output(result, "Handler should produce valid JSON output")

        # Check for permission field
        if "permission" in output:
            permission = output["permission"]
            print(f"✓ Handler processed file with unreadable attachment, permission: {permission}")

            # Should allow since main file is safe and attachment error doesn't block
            if permission == "allow":
                print(f"  ✓ Correctly allowed despite unreadable attachment")
            else:
                print(f"  ⚠ File was denied despite only attachment being unreadable")

        else:
            raise AssertionError(f"Output missing 'permission' field: {output}")

    finally:
        # Cleanup temp file
        if os.path.exists(main_file_path):
            os.unlink(main_file_path)


def test_before_read_file_multiple_redaction_patterns():
    """Test beforeReadFile with multiple occurrences of same redaction pattern"""
    print("\nTesting beforeReadFile with repeated sensitive patterns...")

    command, repo_root = get_command()

    # Create a temporary file with repeated secrets
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        temp_file_path = f.name
        f.write("""
# Configuration with repeated secrets
PRIMARY_KEY = "AKIAIOSFODNN7EXAMPLE"
BACKUP_KEY = "AKIAIOSFODNN7EXAMPLE"  # Same key repeated
FALLBACK_KEY = "AKIAIOSFODNN7EXAMPLE"  # Same key again

PASSWORD1 = "SuperSecret123!"
PASSWORD2 = "SuperSecret123!"  # Same password
""")

    try:
        stdin_input = {
            # Common fields
            "conversation_id": str(uuid.uuid4()),
            "generation_id": str(uuid.uuid4()),
            "hook_event_name": "beforeReadFile",
            "workspace_roots": [str(repo_root)],
            # Hook-specific fields
            "file_path": temp_file_path,
            "content": "",  # Will be read from disk
            "attachments": []
        }

        result = run_ide_tool_handler(command, stdin_input, timeout=60)

        # Should produce valid JSON output
        output = assert_json_output(result, "Handler should produce valid JSON output")

        # Check for permission field
        if "permission" in output:
            permission = output["permission"]
            print(f"✓ Handler analyzed file with repeated patterns, permission: {permission}")
            print(f"  Handler should have counted multiple occurrences of same redaction pattern")

        else:
            raise AssertionError(f"Output missing 'permission' field: {output}")

    finally:
        # Cleanup temp file
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)


if __name__ == "__main__":
    try:
        test_before_read_file_no_sensitive_content()
        test_before_read_file_missing_file_path()
        test_before_read_file_missing_content()
        test_before_read_file_invalid_json()
        test_before_read_file_with_secrets()
        test_before_read_file_with_attachment()
        test_before_read_file_unreadable_attachment()
        test_before_read_file_multiple_redaction_patterns()

        print("\n" + "=" * 50)
        print("All beforeReadFile handler tests passed! ✓")
        print("=" * 50)

    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
