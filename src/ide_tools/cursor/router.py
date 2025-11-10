"""
Cursor Router

Routes Cursor hook calls to appropriate handlers.
"""

import asyncio
import json
import sys
import uuid

from ide_tools.common.hooks.init import handle_init
from ide_tools.common.hooks.prompt_submit import handle_prompt_submit
from ide_tools.common.hooks.read_file import handle_read_file
from ide_tools.common.hooks.shell_execution import handle_shell_execution
from modules.logs.audit_trail import AuditTrailLogger
from modules.logs.logger import MCPLogger
from .constants import CURSOR_HOOKS, CURSOR_CONFIG
from ..common.hooks.output import output_result

MASK_AFTER_SHELL_EXEC = True


def route_cursor_hook(logger: MCPLogger, audit_logger: AuditTrailLogger, stdin_input: str):
    """
    Route Cursor hook to appropriate shared handler
    
    Args:
        logger: MCPLogger instance
        audit_logger: AuditTrailLogger instance
        stdin_input: Raw input string from stdin
    """
    try:
        input_data = json.loads(stdin_input)

        hook_event_name = input_data.get("hook_event_name")
        if not hook_event_name:
            logger.error("Missing required field 'hook_event_name' in input")
            sys.exit(1)

        conversation_id = input_data.get("conversation_id")
        if not conversation_id:
            logger.error("Missing required field 'conversation_id' in input")
            sys.exit(1)

        generation_id = input_data.get("generation_id")
        if not generation_id:
            logger.error("Missing required field 'generation_id' in input")
            sys.exit(1)

        workspace_roots = input_data.get("workspace_roots")
        if workspace_roots is None:
            logger.error("Missing required field 'workspace_roots' in input")
            sys.exit(1)

        if not isinstance(workspace_roots, list):
            logger.error("Invalid 'workspace_roots': must be a list")
            sys.exit(1)

        prompt_id = conversation_id[:8]
        event_id = uuid.uuid4().hex[:8]
        cwd = workspace_roots[0] if workspace_roots else None

        logger.info(
            f"Cursor router: routing to {hook_event_name} handler "
            f"(prompt_id={prompt_id}, event_id={event_id}, cwd={cwd})")

        # Route to appropriate handler
        if hook_event_name == "init":
            asyncio.run(handle_init(
                logger=logger,
                audit_logger=audit_logger,
                event_id=event_id,
                prompt_id=prompt_id,
                cwd=cwd,
                server_name=CURSOR_CONFIG.server_name,
                client_name="cursor",
                hooks=CURSOR_HOOKS
            ))
        elif hook_event_name == "beforeShellExecution":
            asyncio.run(
                handle_shell_execution(logger, audit_logger, stdin_input, prompt_id, event_id, cwd, CURSOR_CONFIG,
                                       hook_event_name, is_request=True))
        elif hook_event_name == "afterShellExecution":
            if not MASK_AFTER_SHELL_EXEC:
                asyncio.run(
                    handle_shell_execution(logger, audit_logger, stdin_input, prompt_id, event_id, cwd, CURSOR_CONFIG,
                                           hook_event_name, is_request=False))
            else:
                output_result(logger, CURSOR_CONFIG.output_format, "permission", True, "", "")
        elif hook_event_name == "beforeReadFile":
            asyncio.run(handle_read_file(logger, audit_logger, stdin_input, prompt_id, event_id, cwd, CURSOR_CONFIG,
                                         hook_event_name))
        elif hook_event_name == "beforeSubmitPrompt":
            asyncio.run(
                handle_prompt_submit(logger, audit_logger, stdin_input, prompt_id, event_id, cwd, CURSOR_CONFIG,
                                     hook_event_name))
        else:
            logger.error(f"Unknown hook_event_name: {hook_event_name}")
            sys.exit(1)

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse input JSON: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Routing error: {e}", exc_info=True)
        sys.exit(1)
