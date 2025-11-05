#!/usr/bin/env python3
"""
E2E Test commons

Base test utilities for testing IDE tool handlers
"""

import json
import logging
import os
import subprocess
import threading
from typing import Dict, Any, Optional

logging.basicConfig(level=logging.WARNING, format='%(message)s')
logger = logging.getLogger(__name__)


def run_ide_tool_handler(
        command: list[str],
        stdin_input: Optional[Dict[str, Any]] = None,
        timeout: int = 30
) -> Dict[str, Any]:
    """
    Run an IDE tool handler and return the result.
    
    Args:
        command: Command and args to execute (e.g., ["uvx", "--from", ".", "mcpower-proxy", ...])
        stdin_input: Optional dict to send as JSON to stdin
        timeout: Timeout in seconds
        
    Returns:
        Dict containing 'stdout', 'stderr', 'returncode', and optionally 'output' (parsed JSON)
    """
    # Capture stderr in a thread
    stderr_lines = []

    def capture_stderr():
        for line in iter(process.stderr.readline, b''):
            decoded = line.decode('utf-8', errors='replace').strip()
            if decoded:
                stderr_lines.append(decoded)
                # Print stderr for debugging
                print(f"[STDERR] {decoded}", flush=True)

    # Prepare stdin if provided
    stdin_data = None
    if stdin_input is not None:
        stdin_data = json.dumps(stdin_input).encode('utf-8')

    # Start process
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**os.environ, "MCPOWER_DEBUG": "1"},
    )

    # Start stderr capture thread
    stderr_thread = threading.Thread(target=capture_stderr, daemon=True)
    stderr_thread.start()

    try:
        # Send stdin and wait for completion
        stdout_data, _ = process.communicate(input=stdin_data, timeout=timeout)
        stdout = stdout_data.decode('utf-8', errors='replace').strip()

        # Wait for stderr thread to finish
        stderr_thread.join(timeout=1)
        stderr = '\n'.join(stderr_lines)

        # Try to parse stdout as JSON
        output = None
        if stdout:
            try:
                output = json.loads(stdout)
            except json.JSONDecodeError:
                # Not JSON, leave as string
                pass

        return {
            'stdout': stdout,
            'stderr': stderr,
            'returncode': process.returncode,
            'output': output
        }

    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        raise TimeoutError(f"Handler did not complete within {timeout}s")
    except Exception:
        if process.poll() is None:
            process.kill()
        raise


def assert_success(result: Dict[str, Any], message: str = "Handler should succeed"):
    """Assert that the handler succeeded (exit code 0)"""
    if result['returncode'] != 0:
        raise AssertionError(
            f"{message}\n"
            f"Exit code: {result['returncode']}\n"
            f"Stdout: {result['stdout']}\n"
            f"Stderr: {result['stderr']}"
        )


def assert_failure(result: Dict[str, Any], message: str = "Handler should fail"):
    """Assert that the handler failed (non-zero exit code)"""
    if result['returncode'] == 0:
        raise AssertionError(
            f"{message}\n"
            f"Stdout: {result['stdout']}\n"
            f"Stderr: {result['stderr']}"
        )


def assert_json_output(result: Dict[str, Any], message: str = "Output should be valid JSON"):
    """Assert that the handler produced valid JSON output"""
    if result['output'] is None:
        raise AssertionError(
            f"{message}\n"
            f"Stdout: {result['stdout']}"
        )
    return result['output']


def get_command():
    """
    Get uvx command for running a Cursor IDE tool handler
    
    Returns:
        Tuple of (command list, repo_root path)
    """
    from pathlib import Path

    # Get repo root for uvx command
    test_dir = Path(__file__).parent
    cursor_dir = test_dir.parent
    ide_tools_dir = cursor_dir.parent
    src_dir = ide_tools_dir.parent
    repo_root = src_dir.parent

    command = [
        "uvx",
        "--from",
        str(repo_root),
        "mcpower-proxy",
        "--ide-tool",
        "--ide", "cursor",
    ]
    return command, repo_root
