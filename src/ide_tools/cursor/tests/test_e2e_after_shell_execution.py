#!/usr/bin/env python3
"""
E2E Test: Cursor afterShellExecution Handler

Tests the afterShellExecution hook, which analyzes shell command outputs
for security issues like secret exposure or data exfiltration.
"""

import json
import sys
import uuid

from common import (
    get_command
)
from ide_tools.common.tests.asserts import assert_json_output, assert_failure
from ide_tools.common.tests.runner import run_handler
from modules.utils.string import truncate_at


def test_after_shell_execution_valid():
    """Test afterShellExecution with valid, safe output"""
    print("Testing afterShellExecution with safe output...")

    command, repo_root = get_command()

    # Test with safe command output
    stdin_input = {
        # Common fields
        "conversation_id": str(uuid.uuid4()),
        "generation_id": str(uuid.uuid4()),
        "hook_event_name": "afterShellExecution",
        "workspace_roots": [str(repo_root)],
        # Hook-specific fields
        "command": "ls -la",
        "output": "total 48\ndrwxr-xr-x  12 user  staff   384 Nov  3 10:00 .\ndrwxr-xr-x   8 user  staff   256 Nov  2 15:30 .."
    }

    result = run_handler(command, stdin_input, timeout=60)

    # Output analysis might succeed or fail depending on security policy
    # We just verify the handler runs and produces valid JSON output
    output = assert_json_output(result, "Handler should produce valid JSON output")

    # Check for expected fields in output
    if "permission" in output:
        permission = output["permission"]
        print(f"✓ Handler returned permission: {permission}")

        # Check for user_message and agent_message (Cursor hook format)
        if "user_message" in output:
            print(f"  User message: {output['user_message']}")
        if "agent_message" in output:
            print(f"  Agent message: {output['agent_message']}")
    else:
        raise AssertionError(f"Output missing 'permission' field: {output}")


def test_after_shell_execution_missing_command():
    """Test afterShellExecution with missing command field"""
    print("\nTesting afterShellExecution with missing command...")

    command, repo_root = get_command()

    # Missing required 'command' field
    stdin_input = {
        # Common fields
        "conversation_id": str(uuid.uuid4()),
        "generation_id": str(uuid.uuid4()),
        "hook_event_name": "afterShellExecution",
        "workspace_roots": [str(repo_root)],
        # Hook-specific fields (missing command)
        "output": "some output"
    }

    result = run_handler(command, stdin_input, timeout=60)

    # Should fail due to validation error
    assert_failure(result, "Handler should fail with missing command")

    # Should still produce JSON output with deny permission
    if result['output']:
        if result['output'].get('permission') == 'deny':
            print(f"✓ Handler correctly denied request with missing command")
        else:
            raise AssertionError(f"Expected permission='deny', got {result['output'].get('permission')}")
    else:
        print(f"✓ Handler failed with missing command (no JSON output)")


def test_after_shell_execution_missing_output():
    """Test afterShellExecution with missing output field"""
    print("\nTesting afterShellExecution with missing output...")

    command, repo_root = get_command()

    # Missing required 'output' field
    stdin_input = {
        # Common fields
        "conversation_id": str(uuid.uuid4()),
        "generation_id": str(uuid.uuid4()),
        "hook_event_name": "afterShellExecution",
        "workspace_roots": [str(repo_root)],
        # Hook-specific fields (missing output)
        "command": "echo 'test'"
    }

    result = run_handler(command, stdin_input, timeout=60)

    # Should fail due to validation error
    assert_failure(result, "Handler should fail with missing output")

    # Should still produce JSON output with deny permission
    if result['output']:
        if result['output'].get('permission') == 'deny':
            print(f"✓ Handler correctly denied request with missing output")
        else:
            raise AssertionError(f"Expected permission='deny', got {result['output'].get('permission')}")
    else:
        print(f"✓ Handler failed with missing output (no JSON output)")


def test_after_shell_execution_invalid_json():
    """Test afterShellExecution with invalid JSON input"""
    print("\nTesting afterShellExecution with invalid JSON...")

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


def test_after_shell_execution_with_secrets():
    """Test afterShellExecution with output containing secrets/credentials"""
    print("\nTesting afterShellExecution with secrets in output...")

    command, repo_root = get_command()

    # Test with output containing secrets that should be flagged
    stdin_input = {
        # Common fields
        "conversation_id": str(uuid.uuid4()),
        "generation_id": str(uuid.uuid4()),
        "hook_event_name": "afterShellExecution",
        "workspace_roots": [str(repo_root)],
        # Hook-specific fields
        "command": "cat config.yml",
        "output": """
database:
  host: db.example.com
  username: admin
  password: SuperSecret123!
  
api_keys:
  aws_access_key: AKIAIOSFODNN7EXAMPLE
  aws_secret_key: wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
  github_token: ghp_1234567890abcdefghijklmnopqrstuvwxyz

stripe_key: sk_live_51H7yxyz1234567890abcdefghijklmnop
"""
    }

    result = run_handler(command, stdin_input, timeout=60)

    # Should produce valid JSON output
    output = assert_json_output(result, "Handler should produce valid JSON output")

    # Check for permission field
    if "permission" in output:
        permission = output["permission"]
        print(f"✓ Handler analyzed output with secrets, permission: {permission}")

        # This output should likely be blocked or require confirmation
        if permission == "deny":
            print(f"  ✓ Output with secrets was correctly blocked")
            if "user_message" in output:
                print(f"  User message: {output['user_message']}")
            if "agent_message" in output:
                print(f"  Agent message: {truncate_at(output['agent_message'], 100)}")
        elif permission == "allow":
            print(f"  ⚠ Warning: Output with secrets was allowed (security policy may need tuning)")

    else:
        raise AssertionError(f"Output missing 'permission' field: {output}")


def test_after_shell_execution_with_credentials():
    """Test afterShellExecution with output containing credentials"""
    print("\nTesting afterShellExecution with credentials in output...")

    command, repo_root = get_command()

    # Test with output containing various credential patterns
    stdin_input = {
        # Common fields
        "conversation_id": str(uuid.uuid4()),
        "generation_id": str(uuid.uuid4()),
        "hook_event_name": "afterShellExecution",
        "workspace_roots": [str(repo_root)],
        # Hook-specific fields
        "command": "env | grep -i key",
        "output": """
GITHUB_TOKEN=ghp_AbCdEfGhIjKlMnOpQrStUvWxYz1234567890
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
STRIPE_API_KEY=sk_test_51H7yxyzabcdefghijklmnopqrstuvwxyz
OPENAI_API_KEY=sk-proj-1234567890abcdefghijklmnopqrstuvwxyz
DATABASE_URL=postgresql://admin:MyPassword123@db.internal.com:5432/prod
"""
    }

    result = run_handler(command, stdin_input, timeout=60)

    # Should produce valid JSON output
    output = assert_json_output(result, "Handler should produce valid JSON output")

    # Check for permission field
    if "permission" in output:
        permission = output["permission"]
        print(f"✓ Handler analyzed output with credentials, permission: {permission}")

        if permission == "deny":
            print(f"  ✓ Output with credentials was correctly blocked")
        elif permission == "allow":
            print(f"  ⚠ Warning: Output with credentials was allowed")

    else:
        raise AssertionError(f"Output missing 'permission' field: {output}")


def test_after_shell_execution_with_ssh_keys():
    """Test afterShellExecution with output containing SSH private keys"""
    print("\nTesting afterShellExecution with SSH keys in output...")

    command, repo_root = get_command()

    # Test with output containing SSH private key
    stdin_input = {
        # Common fields
        "conversation_id": str(uuid.uuid4()),
        "generation_id": str(uuid.uuid4()),
        "hook_event_name": "afterShellExecution",
        "workspace_roots": [str(repo_root)],
        # Hook-specific fields
        "command": "cat ~/.ssh/id_rsa",
        "output": """-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA1234567890abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMN
OPQRSTUVWXYZ0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQR
STUVWXYZ0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUV
WXYZ0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ
-----END RSA PRIVATE KEY-----"""
    }

    result = run_handler(command, stdin_input, timeout=60)

    # Should produce valid JSON output
    output = assert_json_output(result, "Handler should produce valid JSON output")

    # Check for permission field
    if "permission" in output:
        permission = output["permission"]
        print(f"✓ Handler analyzed output with SSH key, permission: {permission}")

        # SSH private keys should definitely be blocked
        if permission == "deny":
            print(f"  ✓ SSH private key output was correctly blocked")
        elif permission == "allow":
            print(f"  ⚠ Warning: SSH private key output was allowed (SECURITY ISSUE!)")

    else:
        raise AssertionError(f"Output missing 'permission' field: {output}")


if __name__ == "__main__":
    try:
        test_after_shell_execution_valid()
        test_after_shell_execution_missing_command()
        test_after_shell_execution_missing_output()
        test_after_shell_execution_invalid_json()
        test_after_shell_execution_with_secrets()
        test_after_shell_execution_with_credentials()
        test_after_shell_execution_with_ssh_keys()

        print("\n" + "=" * 50)
        print("All afterShellExecution handler tests passed! ✓")
        print("=" * 50)

    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
