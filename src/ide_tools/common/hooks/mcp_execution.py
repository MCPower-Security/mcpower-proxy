"""
Common MCP execution handler - IDE-agnostic

Handles request (before) inspection for MCP tool calls.
"""

import json
from typing import Optional

from modules.logs.audit_trail import AuditTrailLogger
from modules.logs.logger import MCPLogger
from modules.redaction import redact
from modules.utils.ids import get_session_id, read_app_uid, get_project_mcpower_dir
from modules.utils.string import truncate_at
from .output import output_result, output_error
from .types import HookConfig
from .utils import create_validator, inspect_and_enforce


async def handle_mcp_execution(
        logger: MCPLogger,
        audit_logger: AuditTrailLogger,
        stdin_input: str,
        prompt_id: str,
        event_id: str,
        cwd: Optional[str],
        config: HookConfig,
        tool_name: str
):
    """
    MCP execution handler - handles before inspection

    Args:
        logger: Logger instance
        audit_logger: Audit logger instance
        stdin_input: Raw input string from stdin
        prompt_id: Prompt identifier
        event_id: Event identifier
        cwd: Current working directory
        config: Hook configuration (IDE-specific)
        tool_name: IDE-specific tool name (e.g., "beforeMCPExecution")
    """
    session_id = get_session_id()

    logger.info(
        f"{tool_name} handler started (client={config.client_name}, prompt_id={prompt_id}, "
        f"event_id={event_id}, cwd={cwd})")

    try:
        # Step 1: Validate input
        try:
            validator = create_validator(required_fields={
                "tool_name": str,
                "tool_input": str
            })
            input_data = validator(stdin_input)
        except ValueError as e:
            logger.error(f"Input validation error: {e}")
            output_error(logger, config.output_format, "permission", str(e))
            return

        mcp_tool_name = input_data.get("tool_name")
        tool_input_raw = input_data.get("tool_input")

        # Optional fields - either url or command should be present
        mcp_url = input_data.get("url")
        mcp_command = input_data.get("command")

        logger.info(f"MCP Tool: {mcp_tool_name}")
        logger.info(f"Tool Input: '{truncate_at(tool_input_raw, 200)}'")

        # Step 2: Parse and redact tool input
        redacted_tool_input = redact(json.loads(tool_input_raw))

        # Step 3: Build content data for policy inspection
        content_data = {
            "tool_name": mcp_tool_name,
            "tool_input": redacted_tool_input
        }

        if mcp_url:
            content_data["url"] = redact(mcp_url)
            logger.info(f"Tool's Server URL: {content_data['url']}")
        if mcp_command:
            content_data["command"] = redact(mcp_command)
            logger.info(f"Tool's Server Command: {content_data['command']}")

        # Step 4: Audit log the request
        project_mcpower_dir = get_project_mcpower_dir(cwd)
        app_uid = read_app_uid(logger, project_mcpower_dir)

        def get_audit_data():
            return {
                "server": config.server_name,
                "tool": tool_name,
                "params": {
                    "mcp_tool_name": mcp_tool_name,
                    "tool_input": redacted_tool_input,
                    "url": content_data.get("url"),
                    "command": content_data.get("command")
                }
            }

        audit_logger.log_event(
            "agent_request",
            get_audit_data(),
            event_id=event_id,
            prompt_id=prompt_id
        )

        # Step 5: Inspect and enforce security policy
        try:
            decision = await inspect_and_enforce(
                is_request=True,
                session_id=session_id,
                logger=logger,
                audit_logger=audit_logger,
                app_uid=app_uid,
                event_id=event_id,
                server_name=config.server_name,
                tool_name=tool_name,
                content_data=content_data,
                prompt_id=prompt_id,
                cwd=cwd,
                client_name=config.client_name
            )

            reasons = decision.get("reasons", [])

            audit_logger.log_event(
                "agent_request_forwarded",
                get_audit_data(),
                event_id=event_id,
                prompt_id=prompt_id
            )

            user_message = f"MCP tool '{mcp_tool_name}' approved"
            agent_message = f"MCP tool '{mcp_tool_name}' approved"
            if reasons:
                agent_message += f": {'; '.join(reasons)}"

            output_result(logger, config.output_format, "permission", True, user_message, agent_message)
            logger.info(f"{tool_name} completed successfully: {user_message}")

        except Exception as e:  # Policy enforcement failed or user blocked
            error_msg = str(e)

            # Determine user-friendly message
            user_message = f"MCP tool '{mcp_tool_name}' blocked by security policy"
            if "User blocked" in error_msg or "User denied" in error_msg:
                user_message = f"MCP tool '{mcp_tool_name}' blocked by user"

            output_result(logger, config.output_format, "permission", False, user_message, error_msg)
            logger.warning(f"{tool_name} blocked: {error_msg}")

    except Exception as e:
        logger.error(f"Unexpected error in {tool_name} handler: {e}", exc_info=True)
        output_error(logger, config.output_format, "permission", f"Internal error: {str(e)}")
