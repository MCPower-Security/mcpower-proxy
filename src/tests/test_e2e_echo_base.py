#!/usr/bin/env python3
"""
E2E Test Base: MCP Protocol with tools/list and tools/call

Base test logic that can test either main.py or built executable.
"""

import asyncio
import json
import logging
import os
import platform
import subprocess
import threading

logging.basicConfig(level=logging.WARNING, format='%(message)s')
logger = logging.getLogger(__name__)


class SimpleMCPClient:
    """Minimal MCP client for testing"""

    def __init__(self, process):
        self.process = process
        self.request_id = 0

    def _next_id(self):
        self.request_id += 1
        return self.request_id

    def send_json(self, obj):
        """Send a JSON object"""
        msg = json.dumps(obj) + "\n"
        self.process.stdin.write(msg.encode())
        self.process.stdin.flush()

    def read_json(self, timeout=10):
        """Read one JSON message, handling server requests"""

        if platform.system() == "Windows":
            return self._read_json_windows(timeout)
        else:
            return self._read_json_unix(timeout)

    def _read_json_unix(self, timeout):
        """Unix implementation using select"""
        import select

        while True:
            ready, _, _ = select.select([self.process.stdout], [], [], timeout)
            if not ready:
                raise TimeoutError(f"No response within {timeout}s")

            line = self.process.stdout.readline().decode('utf-8', errors='replace').strip()
            if not line:
                continue

            try:
                msg = json.loads(line)

                # Handle server-initiated requests
                if "method" in msg and "id" in msg:
                    method = msg["method"]
                    msg_id = msg["id"]

                    # Respond based on method
                    if method == "roots/list":
                        self.send_json({"jsonrpc": "2.0", "id": msg_id, "result": {"roots": []}})
                    else:
                        self.send_json({"jsonrpc": "2.0", "id": msg_id, "result": {}})
                    continue

                # Skip notifications (method but no id)
                if "method" in msg and "id" not in msg:
                    continue

                return msg
            except json.JSONDecodeError:
                continue

    def _read_json_windows(self, timeout):
        """Windows implementation using threading"""
        result = []
        exception = []

        def read_thread():
            try:
                while True:
                    line = self.process.stdout.readline().decode('utf-8', errors='replace').strip()
                    if not line:
                        continue

                    try:
                        msg = json.loads(line)

                        # Handle server-initiated requests
                        if "method" in msg and "id" in msg:
                            method = msg["method"]
                            msg_id = msg["id"]

                            # Respond based on method
                            if method == "roots/list":
                                self.send_json({"jsonrpc": "2.0", "id": msg_id, "result": {"roots": []}})
                            else:
                                self.send_json({"jsonrpc": "2.0", "id": msg_id, "result": {}})
                            continue

                        # Skip notifications (method but no id)
                        if "method" in msg and "id" not in msg:
                            continue

                        result.append(msg)
                        return
                    except json.JSONDecodeError:
                        continue
            except Exception as e:
                exception.append(e)

        thread = threading.Thread(target=read_thread, daemon=True)
        thread.start()
        thread.join(timeout)

        if exception:
            raise exception[0]

        if thread.is_alive():
            raise TimeoutError(f"No response within {timeout}s")

        if not result:
            raise TimeoutError(f"No response within {timeout}s")

        return result[0]


async def run_test(command: list[str], test_name: str):
    """
    Run E2E test with specified command.
    
    Args:
        command: Command and args to execute (e.g., [sys.executable, "main.py", ...])
        test_name: Name for logging purposes
    """
    print(f"Starting E2E test ({test_name})...")

    # Create config string
    config = {
        "mcpServers": {
            "server-everything": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-everything"]
            }
        }
    }

    config_json = json.dumps(config)

    # Build full command with args
    full_command = command + [
        "python",
        "-m",
        "main",
        "--name",
        "server-everything",
        "--wrapped-config",
        config_json,
    ]

    # Capture stderr in a thread to see what's happening
    stderr_lines = []
    def capture_stderr():
        for line in iter(process.stderr.readline, b''):
            decoded = line.decode('utf-8', errors='replace').strip()
            if decoded:
                stderr_lines.append(decoded)
                print(f"[STDERR] {decoded}", flush=True)

    process = subprocess.Popen(
        full_command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**os.environ, "MCPOWER_DEBUG": "1"},
        bufsize=0
    )

    try:
        import threading
        stderr_thread = threading.Thread(target=capture_stderr, daemon=True)
        stderr_thread.start()

        await asyncio.sleep(3)

        if process.poll() is not None:
            stderr = '\n'.join(stderr_lines)
            raise Exception(f"Server failed to start: {stderr}")

        print("Server started")

        client = SimpleMCPClient(process)

        # Initialize
        print("Testing initialize...")
        client.send_json({
            "jsonrpc": "2.0",
            "id": client._next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"}
            }
        })

        init_response = client.read_json(timeout=60)
        if "result" not in init_response:
            raise Exception("Initialize failed: no result in response")

        server_name = init_response["result"]["serverInfo"]["name"]
        print(f"Initialize OK (server: {server_name})")

        # Send initialized notification
        client.send_json({"jsonrpc": "2.0", "method": "notifications/initialized"})

        # tools/list (triggers backend /init)
        print("Testing tools/list...")
        client.send_json({
            "jsonrpc": "2.0",
            "id": client._next_id(),
            "method": "tools/list"
        })

        tools_response = client.read_json(timeout=60)
        if "result" not in tools_response:
            raise Exception("tools/list failed: no result in response")

        tools = tools_response["result"].get("tools", [])
        print(f"tools/list OK ({len(tools)} tools)")

        if not tools:
            raise Exception("No tools returned")

        # Find echo tool and check for wrapper arguments in schema
        echo_tool = next((t for t in tools if t["name"] == "echo"), None)
        if not echo_tool:
            raise Exception("Echo tool not found")

        schema = echo_tool.get("inputSchema", {})
        props = schema.get("properties", {})
        if "__wrapper_userPrompt" not in props:
            raise Exception("Wrapper arguments not added to schema")

        print("Schema enhancement OK")

        # tools/call - echo with "Hello world"
        print("Testing tools/call (echo)...")

        args = {
            "message": "Hello world",
            "__wrapper_userPrompt": "Echo hello world",
            "__wrapper_userPromptId": "test-prompt-1",
            "__wrapper_contextSummary": "Testing echo tool",
            "__wrapper_modelIntent": "Test echo functionality",
            "__wrapper_modelPlan": "Call echo with Hello world",
            "__wrapper_modelExpectedOutputs": "Hello world echoed back"
        }

        client.send_json({
            "jsonrpc": "2.0",
            "id": client._next_id(),
            "method": "tools/call",
            "params": {"name": "echo", "arguments": args}
        })

        call_response = client.read_json(timeout=60)

        if "error" in call_response:
            error = call_response["error"]
            error_msg = error.get('message', 'Unknown')
            raise Exception(f"tools/call failed: {error_msg}")
        elif "result" in call_response:
            result = call_response["result"]
            content = result.get("content", [])
            if content and content[0].get("type") == "text":
                text = content[0].get("text", "")
                if "Hello world" in text:
                    print(f"tools/call OK - Response: {text}")
                else:
                    raise Exception(f"Expected 'Hello world' in response, got: {text}")
            else:
                raise Exception(f"Unexpected response format: {result}")
        else:
            raise Exception("tools/call: unexpected response format")

        print("\nAll tests passed")

        # Cleanup
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)

    except Exception:
        if process.poll() is None:
            process.kill()
        raise

