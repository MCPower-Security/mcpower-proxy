"""
Cursor Init Handler

Registers Cursor hooks as tools with the security API during extension initialization.
"""

import asyncio
import sys
from typing import Optional

from ide_tools.cursor.constants import cursor_tools_mcp_name
from mcpower_shared.mcp_types import InitRequest, EnvironmentContext, ServerRef, ToolRef
from modules.apis.security_policy import SecurityPolicyClient
from modules.logs.logger import MCPLogger
from modules.utils.ids import get_session_id, read_app_uid, get_project_mcpower_dir
from modules.utils.json import safe_json_dumps
from wrapper.__version__ import __version__

# Hook descriptions from https://cursor.com/docs/agent/hooks#hook-events
CURSOR_HOOKS = {
    "beforeShellExecution": {
        "name": "beforeShellExecution",
        "description": "Triggered before a shell command is executed by the agent. "
                       "Allows inspection and potential blocking of shell commands.",
        "version": "1.0.0"
    },
    "afterShellExecution": {
        "name": "afterShellExecution",
        "description": "Triggered after a shell command completes execution. "
                       "Provides access to command output and exit status.",
        "version": "1.0.0"
    },
    "beforeReadFile": {
        "name": "beforeReadFile",
        "description": "Triggered before the agent reads a file. "
                       "Allows inspection and potential blocking of file read operations.",
        "version": "1.0.0"
    },
    "beforeSubmitPrompt": {
        "name": "beforeSubmitPrompt",
        "description": "Triggered before a prompt is submitted to the AI model. "
                       "Allows inspection and modification of prompts.",
        "version": "1.0.0"
    }
}


def output_result(success: bool, message: str):
    """
    Output result to stdout
    
    Args:
        success: True if initialization succeeded
        message: Status message
    """
    result = {
        "success": success,
        "message": message
    }

    print(safe_json_dumps(result), flush=True)


def main(logger: MCPLogger, audit_logger, stdin_input: str, prompt_id: str, event_id: str, cwd: Optional[str]):
    """
    Main entry point for cursor init handler
    
    Args:
        logger: MCPLogger instance
        audit_logger: AuditTrailLogger instance
        stdin_input: Raw input string from stdin
        prompt_id: Prompt ID from conversation_id
        event_id: Event ID from generation_id
        cwd: Optional, current working directory from workspace_roots[0]
    """
    session_id = get_session_id()

    logger.info(f"Cursor init handler started (prompt_id={prompt_id}, event_id={event_id}, cwd={cwd})")

    try:
        app_uid = read_app_uid(logger, get_project_mcpower_dir(cwd))
        audit_logger.set_app_uid(app_uid)

        audit_logger.log_event("mcpower_start", {
            "wrapper_version": __version__,
            "wrapped_server_name": cursor_tools_mcp_name
        })

        try:
            async def call_api():
                tools = [
                    ToolRef(
                        name=hook_info["name"],
                        description=hook_info["description"],
                        version=hook_info["version"]
                    )
                    for hook_info in CURSOR_HOOKS.values()
                ]

                init_request = InitRequest(
                    environment=EnvironmentContext(
                        session_id=session_id,
                        workspace={
                            "roots": [cwd],
                            "current_files": []
                        },
                        client="cursor",
                        client_version=__version__,
                        selection_hash=""  # Could be enhanced later
                    ),
                    server=ServerRef(
                        name=cursor_tools_mcp_name,
                        transport="stdio",
                        version="1.0.0",
                        context="ide"
                    ),
                    tools=tools
                )

                async with SecurityPolicyClient(
                        session_id=session_id,
                        logger=logger,
                        audit_logger=audit_logger,
                        app_id=app_uid
                ) as client:
                    return await client.init_tools(init_request, event_id=event_id)

            result = asyncio.run(call_api())
        except Exception as e:
            # API failed - error is audit-logged via normal logging
            logger.error(f"API initialization failed: {e}")
            output_result(False, f"Error: {str(e)}")
            sys.exit(0)

        # Initialization successful
        output_result(True, "Cursor hooks registered successfully")

    except Exception as e:
        # Unexpected error
        logger.error(f"Unexpected error in cursor init handler: {e}", exc_info=True)
        # Error is audit-logged via normal logging
        output_result(False, f"Initialization failed: {str(e)}")
        sys.exit(1)
