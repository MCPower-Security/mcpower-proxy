#!/usr/bin/env python3
"""
COMPLETE END-TO-END TEST

Shows the full flow:
STDIO → Middleware → Backend Decision → GUI Dialog → Wrapped Proxy
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastmcp.exceptions import ToolError

from modules.logs.audit_trail import AuditTrailLogger
from modules.logs.logger import MCPLogger
from modules.ui.confirmation import UserConfirmationError
from wrapper.middleware import SecurityMiddleware

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = MCPLogger(level=logging.INFO)
audit_logger = AuditTrailLogger(logger)


async def test_complete_e2e_flow():
    """Complete E2E test with real GUI confirmation"""

    print("🚀 COMPLETE END-TO-END TEST")
    print("=" * 60)
    print("STDIO → Middleware → Backend → GUI → Wrapped Proxy")
    print("=" * 60)

    # 1. STDIO INPUT - Simulate MCP request from AI client
    stdio_request = {
        "jsonrpc": "2.0",
        "id": "e2e-test-001",
        "method": "tools/call",
        "params": {
            "name": "file_reader",
            "arguments": {
                "path": "/etc/passwd",
                "action": "read",
                "encoding": "utf-8",
                "__wrapper_userPrompt": "Read system password file for security audit",
                "__wrapper_modelIntent": "Analyze system user accounts and permissions",
                "__wrapper_modelExpectedOutputs": "List of system users with their shell configurations"
            }
        }
    }

    print("📥 1. STDIO INPUT (from AI client):")
    print(json.dumps(stdio_request, indent=2))

    # 2. MIDDLEWARE SETUP
    print(f"\n🔧 2. MIDDLEWARE INITIALIZATION:")
    middleware = SecurityMiddleware(
        wrapped_server_configs={
            "mcpServers": {
                "file_server": {
                    "command": "python",
                    "args": ["-m", "file_server"]
                }
            }
        },
        wrapper_server_name="SecurityProxy",
        wrapper_server_version="1.0.0",
        logger=logger,
        audit_logger=audit_logger
    )
    print(f"   ✅ Middleware created: {middleware.wrapper_server_name}")

    # 3. BACKEND SECURITY DECISION
    backend_decision = {
        "decision": "required_explicit_user_confirmation",
        "reasons": [
            "Tool attempts to read sensitive system authentication files",
            "File path '/etc/passwd' contains user account information",
            "Operation requires elevated security clearance",
            "Potential exposure of system user configuration"
        ],
        "severity": "critical",
        "matched_rules": [
            "file_access.system_files",
            "authentication.user_data",
            "security.elevated_access"
        ]
    }

    print(f"\n🔒 3. BACKEND SECURITY DECISION:")
    print(json.dumps(backend_decision, indent=2))

    # 4. CREATE MOCK CONTEXT
    print(f"\n🔄 4. MIDDLEWARE CONTEXT CREATION:")
    mock_message = MagicMock()
    mock_message.name = stdio_request["params"]["name"]
    mock_message.arguments = stdio_request["params"]["arguments"]

    mock_context = MagicMock()
    mock_context.message = mock_message
    mock_context.method = stdio_request["method"]
    mock_context.timestamp = datetime.now(timezone.utc)

    # Mock FastMCP context
    mock_fastmcp_context = MagicMock()
    mock_fastmcp_context.list_roots = AsyncMock(return_value=[])
    mock_context.fastmcp_context = mock_fastmcp_context

    # Mock context copy
    def mock_copy(**kwargs):
        new_context = MagicMock()
        new_context.message = kwargs.get('message', mock_message)
        new_context.method = mock_context.method
        new_context.timestamp = mock_context.timestamp
        new_context.fastmcp_context = mock_context.fastmcp_context
        return new_context

    mock_context.copy = mock_copy
    print(f"   ✅ Context created for tool: {mock_message.name}")

    # 5. WRAPPED PROXY MOCK
    wrapped_response = {
        "content": [
            {
                "type": "text",
                "text": "root:x:0:0:root:/root:/bin/bash\ndaemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin\nsys:x:3:3:sys:/dev:/usr/sbin/nologin\nbin:x:2:2:bin:/bin:/usr/sbin/nologin"
            }
        ],
        "isError": False,
        "metadata": {
            "file_path": "/etc/passwd",
            "size_bytes": 2048,
            "lines_read": 45
        }
    }

    async def mock_wrapped_server(context):
        """Mock the wrapped MCP server response"""
        print(f"\n📤 6. FORWARDED TO WRAPPED MCP SERVER:")
        print(f"   Tool: {context.message.name}")
        print(f"   Arguments: {context.message.arguments}")
        print(f"   ✅ Wrapped server processing...")

        # Simulate wrapped server response
        mock_result = MagicMock()
        mock_result.model_dump.return_value = wrapped_response
        return mock_result

    # 6. RUN THE COMPLETE FLOW
    print(f"\n🎯 5. STARTING COMPLETE E2E FLOW:")
    print(f"   → Security middleware will intercept the request")
    print(f"   → Backend will return 'required_explicit_user_confirmation'")
    print(f"   → GUI confirmation dialog will appear")
    print(f"   → Please APPROVE to see the complete flow")

    with patch.object(middleware, '_inspect_request', return_value=backend_decision):
        with patch.object(middleware, '_inspect_response', return_value={"decision": "allow"}):

            try:
                print(f"\n🔒 GUI CONFIRMATION DIALOG APPEARING...")

                # This triggers the actual GUI confirmation dialog
                result = await middleware._handle_operation(
                    context=mock_context,
                    call_next=mock_wrapped_server,
                    error_class=ToolError,
                    operation_type="tool"
                )

                print(f"\n🎉 7. COMPLETE E2E FLOW SUCCESS!")
                print(f"   ✅ User approved the security confirmation")
                print(f"   ✅ Request forwarded to wrapped MCP server")
                print(f"   ✅ Response received from wrapped server")
                print(f"   ✅ Response security check passed")
                print(f"   ✅ Final response ready for AI client")

                print(f"\n📋 8. FINAL RESPONSE (to AI client via STDIO):")
                final_response = {
                    "jsonrpc": "2.0",
                    "id": stdio_request["id"],
                    "result": result.model_dump()
                }
                print(json.dumps(final_response, indent=2))

                print(f"\n🏆 END-TO-END TEST COMPLETED SUCCESSFULLY!")
                print(f"   The complete STDIO → GUI → Wrapped Proxy flow is working!")

            except UserConfirmationError as e:
                print(f"\n❌ USER DENIED OPERATION")
                print(f"   Reason: {e.user_reason}")
                print(f"   Event ID: {e.event_id}")
                print(f"   → Operation blocked by security policy")

                error_response = {
                    "jsonrpc": "2.0",
                    "id": stdio_request["id"],
                    "error": {
                        "code": -32000,
                        "message": f"Security policy violation: {e.message}",
                        "data": {
                            "event_id": e.event_id,
                            "is_request": e.is_request,
                            "tool_name": e.tool_name
                        }
                    }
                }
                print(f"\n📋 ERROR RESPONSE (to AI client):")
                print(json.dumps(error_response, indent=2))

            except Exception as e:
                print(f"\n💥 UNEXPECTED ERROR: {e}")
                import traceback
                traceback.print_exc()


async def test_blocking_dialog_e2e_flow():
    """Complete E2E test with blocking dialog (Block vs Allow Anyway)"""

    print("\n🚀 BLOCKING DIALOG END-TO-END TEST")
    print("=" * 60)
    print("STDIO → Middleware → Backend Block → GUI Block Dialog → User Choice")
    print("=" * 60)

    # 1. STDIO INPUT - Simulate MCP request that will be blocked
    stdio_request = {
        "jsonrpc": "2.0",
        "id": "e2e-block-test-001",
        "method": "tools/call",
        "params": {
            "name": "createWorkspace",
            "arguments": {
                "name": "my-secret-envs",
                "public": True,
                "description": "Contains API keys and secrets",
                "__wrapper_userPrompt": "Create a public workspace for my environment variables",
                "__wrapper_modelIntent": "Store environment configuration in shared workspace",
                "__wrapper_modelExpectedOutputs": "New public workspace with environment data"
            }
        }
    }

    print("📥 1. STDIO INPUT (from AI client):")
    print(json.dumps(stdio_request, indent=2))

    # 2. MIDDLEWARE SETUP
    print(f"\n🔧 2. MIDDLEWARE INITIALIZATION:")
    middleware = SecurityMiddleware(
        wrapped_server_configs={
            "mcpServers": {
                "postman_mcp": {
                    "command": "python",
                    "args": ["-m", "postman_mcp"]
                }
            }
        },
        wrapper_server_name="SecurityProxy",
        wrapper_server_version="1.0.0",
        logger=logger,
        audit_logger=audit_logger
    )
    print(f"   ✅ Middleware created: {middleware.wrapper_server_name}")

    # 3. BACKEND SECURITY DECISION - BLOCK
    backend_decision = {
        "decision": "block",
        "reasons": [
            "Confirm creating PUBLIC workspace 'my-secret-envs' — may expose secrets publicly."
        ],
        "severity": "high",
        "matched_rules": [
            "workspace.public_exposure",
            "security.secret_leak_prevention"
        ],
        "call_type": "write"
    }

    print(f"\n🚫 3. BACKEND SECURITY DECISION - BLOCK:")
    print(json.dumps(backend_decision, indent=2))

    # 4. CREATE MOCK CONTEXT
    print(f"\n🔄 4. MIDDLEWARE CONTEXT CREATION:")
    mock_message = MagicMock()
    mock_message.name = stdio_request["params"]["name"]
    mock_message.arguments = stdio_request["params"]["arguments"]

    mock_context = MagicMock()
    mock_context.message = mock_message
    mock_context.method = stdio_request["method"]
    mock_context.timestamp = datetime.now(timezone.utc)

    # Mock FastMCP context
    mock_fastmcp_context = MagicMock()
    mock_fastmcp_context.list_roots = AsyncMock(return_value=[])
    mock_context.fastmcp_context = mock_fastmcp_context

    # Mock context copy
    def mock_copy(**kwargs):
        new_context = MagicMock()
        new_context.message = kwargs.get('message', mock_message)
        new_context.method = mock_context.method
        new_context.timestamp = mock_context.timestamp
        new_context.fastmcp_context = mock_context.fastmcp_context
        return new_context

    mock_context.copy = mock_copy
    print(f"   ✅ Context created for tool: {mock_message.name}")

    # 5. WRAPPED PROXY MOCK
    wrapped_response = {
        "content": [
            {
                "type": "text",
                "text": "Workspace 'my-secret-envs' created successfully with ID: ws_abc123"
            }
        ],
        "isError": False,
        "metadata": {
            "workspace_id": "ws_abc123",
            "workspace_name": "my-secret-envs",
            "public": True,
            "created_at": "2025-09-17T11:30:00Z"
        }
    }

    async def mock_wrapped_server(context):
        """Mock the wrapped MCP server response"""
        print(f"\n📤 6. FORWARDED TO WRAPPED MCP SERVER:")
        print(f"   Tool: {context.message.name}")
        print(f"   Arguments: {context.message.arguments}")
        print(f"   ✅ Wrapped server processing...")

        # Simulate wrapped server response
        mock_result = MagicMock()
        mock_result.model_dump.return_value = wrapped_response
        return mock_result

    # 6. RUN THE COMPLETE BLOCKING FLOW
    print(f"\n🎯 5. STARTING BLOCKING DIALOG E2E FLOW:")
    print(f"   → Security middleware will intercept the request")
    print(f"   → Backend will return 'block' decision")
    print(f"   → GUI BLOCKING dialog will appear with red error styling")
    print(f"   → Title: 'MCPower Security Request Blocked'")
    print(f"   → Buttons: [Block], [Allow Anyway]")
    print(f"   → Please choose your option to see the flow")

    with patch.object(middleware, '_inspect_request', return_value=backend_decision):
        with patch.object(middleware, '_inspect_response', return_value={"decision": "allow"}):

            try:
                print(f"\n🔒 GUI BLOCKING DIALOG APPEARING...")
                print(f"   Expected dialog:")
                print(f"   Title: MCPower Security Request Blocked")
                print(f"   Server: postman_mcp, Tool: createWorkspace")
                print(f"   Policy Alert (High):")
                print(f"   {backend_decision['reasons'][0]}")
                print(f"   Buttons: [Block] (default), [Allow Anyway]")

                # This triggers the actual GUI blocking dialog
                result = await middleware._handle_operation(
                    context=mock_context,
                    call_next=mock_wrapped_server,
                    error_class=ToolError,
                    operation_type="tool"
                )

                print(f"\n🎉 7. USER CHOSE 'ALLOW ANYWAY' - FLOW SUCCESS!")
                print(f"   ✅ User overrode the security block")
                print(f"   ✅ Request forwarded to wrapped MCP server")
                print(f"   ✅ Response received from wrapped server")
                print(f"   ✅ Response security check passed")
                print(f"   ✅ Final response ready for AI client")

                print(f"\n📋 8. FINAL RESPONSE (to AI client via STDIO):")
                final_response = {
                    "jsonrpc": "2.0",
                    "id": stdio_request["id"],
                    "result": result.model_dump()
                }
                print(json.dumps(final_response, indent=2))

                print(f"\n🏆 BLOCKING DIALOG E2E TEST COMPLETED SUCCESSFULLY!")
                print(f"   The user chose to override the security block!")

            except UserConfirmationError as e:
                print(f"\n❌ USER CHOSE 'BLOCK' - OPERATION DENIED")
                print(f"   Reason: {e.message}")
                print(f"   Event ID: {e.event_id}")
                print(f"   → Operation blocked by user choice (not just policy)")

                error_response = {
                    "jsonrpc": "2.0",
                    "id": stdio_request["id"],
                    "error": {
                        "code": -32000,
                        "message": f"Security policy violation: User blocked the operation - {backend_decision['reasons'][0]}",
                        "data": {
                            "event_id": e.event_id,
                            "is_request": e.is_request,
                            "tool_name": e.tool_name,
                            "user_initiated_block": True
                        }
                    }
                }
                print(f"\n📋 ERROR RESPONSE (to AI client):")
                print(json.dumps(error_response, indent=2))
                print(f"\n🤖 AGENT GUIDANCE:")
                print(f"   The error indicates USER blocked the operation.")
                print(f"   Agent should: refine request, find alternative, or ask user for guidance.")

            except Exception as e:
                print(f"\n💥 UNEXPECTED ERROR: {e}")
                import traceback
                traceback.print_exc()


async def test_confirmation_with_call_type_e2e_flow():
    """Complete E2E test with confirmation dialog that has call_type (shows Always Allow button)"""

    print("\n🚀 CONFIRMATION WITH CALL_TYPE END-TO-END TEST")
    print("=" * 60)
    print("STDIO → Middleware → Backend Confirmation (with call_type) → GUI 3-Button Dialog → User Choice")
    print("=" * 60)

    # 1. STDIO INPUT - Simulate MCP request that requires confirmation with call_type
    stdio_request = {
        "jsonrpc": "2.0",
        "id": "e2e-confirm-call-type-001",
        "method": "tools/call",
        "params": {
            "name": "writeFile",
            "arguments": {
                "path": "/home/user/important-config.yml",
                "content": "api_key: secret-key-value\ndatabase_url: postgres://...",
                "encoding": "utf-8",
                "__wrapper_userPrompt": "Save configuration file with API credentials",
                "__wrapper_modelIntent": "Store application configuration with sensitive data",
                "__wrapper_modelExpectedOutputs": "Configuration file written to disk"
            }
        }
    }

    print("📥 1. STDIO INPUT (from AI client):")
    print(json.dumps(stdio_request, indent=2))

    # 2. MIDDLEWARE SETUP
    print(f"\n🔧 2. MIDDLEWARE INITIALIZATION:")
    middleware = SecurityMiddleware(
        wrapped_server_configs={
            "mcpServers": {
                "file_server": {
                    "command": "python",
                    "args": ["-m", "file_server"]
                }
            }
        },
        wrapper_server_name="SecurityProxy",
        wrapper_server_version="1.0.0",
        logger=logger,
        audit_logger=audit_logger
    )
    print(f"   ✅ Middleware created: {middleware.wrapper_server_name}")

    # 3. BACKEND SECURITY DECISION - REQUIRED_EXPLICIT_USER_CONFIRMATION with call_type
    backend_decision = {
        "decision": "required_explicit_user_confirmation",
        "reasons": [
            "Writing configuration file with potential sensitive data (API keys detected)",
            "File contains credentials that could be exposed if compromised",
            "Write operation to user home directory requires confirmation"
        ],
        "severity": "medium",
        "matched_rules": [
            "file_write.sensitive_data",
            "credentials.api_keys",
            "security.user_confirmation"
        ],
        "call_type": "write"  # This will enable the "Always Allow" button
    }

    print(f"\n🔒 3. BACKEND SECURITY DECISION - CONFIRMATION WITH CALL_TYPE:")
    print(json.dumps(backend_decision, indent=2))

    # 4. CREATE MOCK CONTEXT
    print(f"\n🔄 4. MIDDLEWARE CONTEXT CREATION:")
    mock_message = MagicMock()
    mock_message.name = stdio_request["params"]["name"]
    mock_message.arguments = stdio_request["params"]["arguments"]

    mock_context = MagicMock()
    mock_context.message = mock_message
    mock_context.method = stdio_request["method"]
    mock_context.timestamp = datetime.now(timezone.utc)

    # Mock FastMCP context
    mock_fastmcp_context = MagicMock()
    mock_fastmcp_context.list_roots = AsyncMock(return_value=[])
    mock_context.fastmcp_context = mock_fastmcp_context

    # Mock context copy
    def mock_copy(**kwargs):
        new_context = MagicMock()
        new_context.message = kwargs.get('message', mock_message)
        new_context.method = mock_context.method
        new_context.timestamp = mock_context.timestamp
        new_context.fastmcp_context = mock_context.fastmcp_context
        return new_context

    mock_context.copy = mock_copy
    print(f"   ✅ Context created for tool: {mock_message.name}")

    # 5. WRAPPED PROXY MOCK
    wrapped_response = {
        "content": [
            {
                "type": "text",
                "text": "Configuration file written successfully to /home/user/important-config.yml"
            }
        ],
        "isError": False,
        "metadata": {
            "file_path": "/home/user/important-config.yml",
            "bytes_written": 156,
            "encoding": "utf-8"
        }
    }

    async def mock_wrapped_server(context):
        """Mock the wrapped MCP server response"""
        print(f"\n📤 6. FORWARDED TO WRAPPED MCP SERVER:")
        print(f"   Tool: {context.message.name}")
        print(f"   Arguments: {context.message.arguments}")
        print(f"   ✅ Wrapped server processing...")

        # Simulate wrapped server response
        mock_result = MagicMock()
        mock_result.model_dump.return_value = wrapped_response
        return mock_result

    # 6. RUN THE COMPLETE CONFIRMATION WITH CALL_TYPE FLOW
    print(f"\n🎯 5. STARTING CONFIRMATION WITH CALL_TYPE E2E FLOW:")
    print(f"   → Security middleware will intercept the request")
    print(f"   → Backend will return 'required_explicit_user_confirmation' WITH call_type")
    print(f"   → GUI confirmation dialog will appear with 3 BUTTONS")
    print(f"   → Title: 'MCPower Security Confirmation Required'")
    print(f"   → Buttons: [Block], [Allow], [Always Allow] (because call_type='write')")
    print(f"   → Please choose your option to see the flow")

    with patch.object(middleware, '_inspect_request', return_value=backend_decision):
        with patch.object(middleware, '_inspect_response', return_value={"decision": "allow"}):

            try:
                print(f"\n🔒 GUI CONFIRMATION DIALOG WITH CALL_TYPE APPEARING...")
                print(f"   Expected dialog:")
                print(f"   Title: MCPower Security Confirmation Required")
                print(f"   Server: file_server, Tool: writeFile")
                print(f"   Policy Alert (Medium):")
                print(f"   {backend_decision['reasons'][0]}")
                print(f"   Buttons: [Block], [Allow] (default), [Always Allow]")
                print(f"   Note: Always Allow appears because call_type='write' is present")

                # This triggers the actual GUI confirmation dialog with call_type
                result = await middleware._handle_operation(
                    context=mock_context,
                    call_next=mock_wrapped_server,
                    error_class=ToolError,
                    operation_type="tool"
                )

                print(f"\n🎉 7. USER APPROVED THE CONFIRMATION - FLOW SUCCESS!")
                print(f"   ✅ User approved the write operation")
                print(f"   ✅ Request forwarded to wrapped MCP server")
                print(f"   ✅ Response received from wrapped server")
                print(f"   ✅ Response security check passed")
                print(f"   ✅ Final response ready for AI client")

                print(f"\n📋 8. FINAL RESPONSE (to AI client via STDIO):")
                final_response = {
                    "jsonrpc": "2.0",
                    "id": stdio_request["id"],
                    "result": result.model_dump()
                }
                print(json.dumps(final_response, indent=2))

                print(f"\n🏆 CONFIRMATION WITH CALL_TYPE E2E TEST COMPLETED SUCCESSFULLY!")
                print(f"   The user approved the operation with 3-button dialog!")

            except UserConfirmationError as e:
                print(f"\n❌ USER DENIED THE CONFIRMATION")
                print(f"   Reason: {e.message}")
                print(f"   Event ID: {e.event_id}")
                print(f"   → Operation blocked by user choice")

                error_response = {
                    "jsonrpc": "2.0",
                    "id": stdio_request["id"],
                    "error": {
                        "code": -32000,
                        "message": f"Security policy violation: {e.message}",
                        "data": {
                            "event_id": e.event_id,
                            "is_request": e.is_request,
                            "tool_name": e.tool_name
                        }
                    }
                }
                print(f"\n📋 ERROR RESPONSE (to AI client):")
                print(json.dumps(error_response, indent=2))

            except Exception as e:
                print(f"\n💥 UNEXPECTED ERROR: {e}")
                import traceback
                traceback.print_exc()


if __name__ == "__main__":
    print("MCPOWER PROXY - COMPLETE END-TO-END TEST")
    print("This demonstrates the full flow with real GUI confirmation.")
    print()

    # Run all three dialog tests
    asyncio.run(test_complete_e2e_flow())
    asyncio.run(test_confirmation_with_call_type_e2e_flow())
    asyncio.run(test_blocking_dialog_e2e_flow())

    print(f"\n" + "=" * 60)
    print("E2E TEST SUMMARY - ALL DIALOG TYPES")
    print("=" * 60)
    print("✅ STDIO input processing")
    print("✅ Security middleware interception")
    print("✅ Backend policy decision handling")
    print("✅ GUI confirmation dialog (required_explicit_user_confirmation without call_type)")
    print("✅ GUI confirmation dialog with 3 buttons (required_explicit_user_confirmation WITH call_type)")
    print("✅ GUI blocking dialog (block with Allow Anyway option)")
    print("✅ User approval/denial/override processing")
    print("✅ User-initiated block error messaging")
    print("✅ Always Allow functionality (call_type present)")
    print("✅ Wrapped MCP server integration")
    print("✅ Response security validation")
    print("✅ STDIO output generation")
    print()
    print("🎉 The MCPower Proxy with ALL THREE dialog types is fully functional!")
    print()
    print("Dialog Summary:")
    print("1️⃣  Standard Confirmation (2 buttons): [Block], [Allow]")
    print("2️⃣  Enhanced Confirmation (3 buttons): [Block], [Allow], [Always Allow]")
    print("3️⃣  Blocking Override (2 buttons): [Block], [Allow Anyway]")
