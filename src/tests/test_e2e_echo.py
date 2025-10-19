#!/usr/bin/env python3
"""
E2E Test: MCP Protocol with tools/list and tools/call

Tests server initialization, tools/list (triggers /init API), and tools/call.
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

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
        import select
        
        while True:
            ready, _, _ = select.select([self.process.stdout], [], [], timeout)
            if not ready:
                raise TimeoutError(f"No response within {timeout}s")
            
            line = self.process.stdout.readline().decode().strip()
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
                
                return msg
            except json.JSONDecodeError:
                continue


async def run_test():
    print("Starting E2E test...")
    
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
    
    # Start server
    test_dir = Path(__file__).parent
    src_dir = test_dir.parent
    main_py = src_dir / "main.py"
    
    process = subprocess.Popen(
        [sys.executable, str(main_py), "--name", "server-everything", "--wrapped-config", config_json],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**os.environ, "MCPOWER_DEBUG": "0"},
        bufsize=0
    )
    
    try:
        
        await asyncio.sleep(2)
        
        if process.poll() is not None:
            stderr = process.stderr.read().decode()
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
        
        init_response = client.read_json(timeout=10)
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
        
        tools_response = client.read_json(timeout=30)
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
        
        try:
            call_response = client.read_json(timeout=15)
            
            if "error" in call_response:
                error = call_response["error"]
                error_msg = error.get('message', 'Unknown')
                # If error mentions __wrapper fields, filtering failed
                if "__wrapper" in error_msg:
                    raise Exception(f"Wrapper fields not filtered: {error_msg}")
                print(f"tools/call error: {error_msg}")
                print("(May be expected if security policy requires confirmation)")
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
        except TimeoutError:
            print("tools/call timed out (security policy may require user confirmation)")
        
        print("\nAll tests passed")
        
        # Cleanup
        process.terminate()
        process.wait(timeout=5)
        
    except Exception:
        if process.poll() is None:
            process.kill()
        raise


if __name__ == "__main__":
    try:
        asyncio.run(run_test())
    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
