import json
import os
import subprocess
import threading
from typing import Optional, Dict, Any


def run_handler(
        command: list[str],
        stdin_input: Optional[Dict[str, Any]] = None,
        timeout: int = 30
) -> Dict[str, Any]:
    """
    Run a Claude Code handler and return the result.

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
