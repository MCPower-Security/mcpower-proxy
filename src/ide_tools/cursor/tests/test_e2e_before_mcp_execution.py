#!/usr/bin/env python3
"""
E2E Test: Cursor beforeMCPExecution Handler

Tests the beforeMCPExecution hook, which analyzes MCP tool calls
before they are executed by Cursor.
"""

import json
import uuid

from common import get_command
from ide_tools.common.tests.asserts import assert_json_output, assert_failure
from ide_tools.common.tests.runner import run_handler


def test_before_mcp_execution_valid():
    """Test beforeMCPExecution with a valid, safe MCP tool call"""
    print("Testing beforeMCPExecution with safe tool call...")

    command, repo_root = get_command()

    # Test with a safe MCP tool call (Read tool)
    stdin_input = {
        # Common fields
        "conversation_id": str(uuid.uuid4()),
        "generation_id": str(uuid.uuid4()),
        "hook_event_name": "beforeMCPExecution",
        "workspace_roots": [str(repo_root)],
        # Hook-specific fields
        "tool_name": "Read",
        "tool_input": json.dumps({"file_path": "/tmp/test.txt"}),
        "url": "http://localhost:3000"
    }

    result = run_handler(command, stdin_input, timeout=60)

    # Tool call analysis might succeed or fail depending on security policy
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


def test_before_mcp_execution_with_command():
    """Test beforeMCPExecution with command-based MCP server"""
    print("\nTesting beforeMCPExecution with command-based server...")

    command, repo_root = get_command()

    # Test with command-based server
    stdin_input = {
        # Common fields
        "conversation_id": str(uuid.uuid4()),
        "generation_id": str(uuid.uuid4()),
        "hook_event_name": "beforeMCPExecution",
        "workspace_roots": [str(repo_root)],
        # Hook-specific fields
        "tool_name": "Write",
        "tool_input": json.dumps({
            "file_path": "/tmp/output.txt",
            "content": "Hello World"
        }),
        "command": "npx -y @modelcontextprotocol/server-filesystem"
    }

    result = run_handler(command, stdin_input, timeout=60)

    output = assert_json_output(result, "Handler should produce valid JSON output")

    if "permission" in output:
        permission = output["permission"]
        print(f"✓ Handler returned permission: {permission}")
        if "user_message" in output:
            print(f"  User message: {output['user_message']}")
        if "agent_message" in output:
            print(f"  Agent message: {output['agent_message']}")
    else:
        raise AssertionError(f"Output missing 'permission' field: {output}")


def test_before_mcp_execution_complex_input():
    """Test beforeMCPExecution with complex nested tool input"""
    print("\nTesting beforeMCPExecution with complex tool input...")

    command, repo_root = get_command()

    # Test with complex nested input
    complex_input = {
        "query": "SELECT * FROM users WHERE email = ?",
        "params": ["test@example.com"],
        "options": {
            "timeout": 30,
            "retries": 3,
            "metadata": {
                "source": "cursor_agent",
                "session_id": "abc123"
            }
        }
    }

    stdin_input = {
        # Common fields
        "conversation_id": str(uuid.uuid4()),
        "generation_id": str(uuid.uuid4()),
        "hook_event_name": "beforeMCPExecution",
        "workspace_roots": [str(repo_root)],
        # Hook-specific fields
        "tool_name": "query_database",
        "tool_input": json.dumps(complex_input),
        "url": "http://localhost:8080/mcp"
    }

    result = run_handler(command, stdin_input, timeout=60)

    output = assert_json_output(result, "Handler should produce valid JSON output")

    if "permission" in output:
        permission = output["permission"]
        print(f"✓ Handler returned permission: {permission}")
        if "user_message" in output:
            print(f"  User message: {output['user_message']}")
        if "agent_message" in output:
            print(f"  Agent message: {output['agent_message']}")
    else:
        raise AssertionError(f"Output missing 'permission' field: {output}")


def test_before_mcp_execution_sensitive_data():
    """Test beforeMCPExecution with potentially sensitive data"""
    print("\nTesting beforeMCPExecution with sensitive data...")

    command, repo_root = get_command()

    # Test with potentially sensitive data (API key, token)
    sensitive_input = {
        "api_key": "sk-1234567890abcdef",
        "bearer_token": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
        "password": "SuperSecret123!",
        "endpoint": "https://api.example.com/v1/data"
    }

    stdin_input = {
        # Common fields
        "conversation_id": str(uuid.uuid4()),
        "generation_id": str(uuid.uuid4()),
        "hook_event_name": "beforeMCPExecution",
        "workspace_roots": [str(repo_root)],
        # Hook-specific fields
        "tool_name": "authenticate",
        "tool_input": json.dumps(sensitive_input),
        "url": "https://secure-api.example.com"
    }

    result = run_handler(command, stdin_input, timeout=60)

    # This should either be blocked or approved with redaction
    output = assert_json_output(result, "Handler should produce valid JSON output")

    if "permission" in output:
        permission = output["permission"]
        print(f"✓ Handler returned permission: {permission}")
        if "user_message" in output:
            print(f"  User message: {output['user_message']}")
        if "agent_message" in output:
            print(f"  Agent message: {output['agent_message']}")
    else:
        raise AssertionError(f"Output missing 'permission' field: {output}")


def test_before_mcp_execution_missing_tool_name():
    """Test beforeMCPExecution with missing tool_name field"""
    print("\nTesting beforeMCPExecution with missing tool_name...")

    command, repo_root = get_command()

    # Missing required 'tool_name' field
    stdin_input = {
        # Common fields
        "conversation_id": str(uuid.uuid4()),
        "generation_id": str(uuid.uuid4()),
        "hook_event_name": "beforeMCPExecution",
        "workspace_roots": [str(repo_root)],
        # Hook-specific fields (missing tool_name)
        "tool_input": json.dumps({"param": "value"}),
        "url": "http://localhost:3000"
    }

    result = run_handler(command, stdin_input, timeout=60)

    # Should fail with validation error
    assert_failure(result, "Handler should fail with missing tool_name")
    output = assert_json_output(result, "Handler should produce valid JSON error output")

    if "permission" in output:
        assert output["permission"] == "deny", "Permission should be 'deny' for missing tool_name"
        print("✓ Handler correctly denied request with missing tool_name")
    else:
        raise AssertionError(f"Output missing 'permission' field: {output}")


def test_before_mcp_execution_missing_tool_input():
    """Test beforeMCPExecution with missing tool_input field"""
    print("\nTesting beforeMCPExecution with missing tool_input...")

    command, repo_root = get_command()

    # Missing required 'tool_input' field
    stdin_input = {
        # Common fields
        "conversation_id": str(uuid.uuid4()),
        "generation_id": str(uuid.uuid4()),
        "hook_event_name": "beforeMCPExecution",
        "workspace_roots": [str(repo_root)],
        # Hook-specific fields (missing tool_input)
        "tool_name": "Read",
        "url": "http://localhost:3000"
    }

    result = run_handler(command, stdin_input, timeout=60)

    # Should fail with validation error
    assert_failure(result, "Handler should fail with missing tool_input")
    output = assert_json_output(result, "Handler should produce valid JSON error output")

    if "permission" in output:
        assert output["permission"] == "deny", "Permission should be 'deny' for missing tool_input"
        print("✓ Handler correctly denied request with missing tool_input")
    else:
        raise AssertionError(f"Output missing 'permission' field: {output}")


def test_before_mcp_execution_invalid_json_input():
    """Test beforeMCPExecution with invalid JSON in tool_input"""
    print("\nTesting beforeMCPExecution with invalid JSON tool_input...")

    command, repo_root = get_command()

    # Invalid JSON in tool_input
    stdin_input = {
        # Common fields
        "conversation_id": str(uuid.uuid4()),
        "generation_id": str(uuid.uuid4()),
        "hook_event_name": "beforeMCPExecution",
        "workspace_roots": [str(repo_root)],
        # Hook-specific fields
        "tool_name": "Read",
        "tool_input": "{invalid json}",  # Invalid JSON
        "url": "http://localhost:3000"
    }

    result = run_handler(command, stdin_input, timeout=60)

    # Handler should still process it (parse error is logged but not fatal)
    output = assert_json_output(result, "Handler should produce valid JSON output")

    if "permission" in output:
        permission = output["permission"]
        print(f"✓ Handler returned permission: {permission}")
        print("  (Invalid JSON was handled gracefully)")
    else:
        raise AssertionError(f"Output missing 'permission' field: {output}")


def test_before_mcp_execution_both_url_and_command():
    """Test beforeMCPExecution with both url and command provided"""
    print("\nTesting beforeMCPExecution with both url and command...")

    command, repo_root = get_command()

    # Both url and command provided (edge case)
    stdin_input = {
        # Common fields
        "conversation_id": str(uuid.uuid4()),
        "generation_id": str(uuid.uuid4()),
        "hook_event_name": "beforeMCPExecution",
        "workspace_roots": [str(repo_root)],
        # Hook-specific fields
        "tool_name": "Bash",
        "tool_input": json.dumps({"command": "echo 'test'"}),
        "url": "http://localhost:3000",
        "command": "npx -y @modelcontextprotocol/server-filesystem"
    }

    result = run_handler(command, stdin_input, timeout=60)

    output = assert_json_output(result, "Handler should produce valid JSON output")

    if "permission" in output:
        permission = output["permission"]
        print(f"✓ Handler returned permission: {permission}")
        print("  (Both url and command were accepted)")
    else:
        raise AssertionError(f"Output missing 'permission' field: {output}")


def run_all_tests():
    """Run all beforeMCPExecution tests"""
    print("=" * 80)
    print("Running beforeMCPExecution E2E Tests")
    print("=" * 80)

    tests = [
        test_before_mcp_execution_valid,
        test_before_mcp_execution_with_command,
        test_before_mcp_execution_complex_input,
        test_before_mcp_execution_sensitive_data,
        test_before_mcp_execution_missing_tool_name,
        test_before_mcp_execution_missing_tool_input,
        test_before_mcp_execution_invalid_json_input,
        test_before_mcp_execution_both_url_and_command,
    ]

    passed = 0
    failed = 0

    for test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"✗ Test failed: {e}")
            failed += 1

    print("\n" + "=" * 80)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("=" * 80)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
