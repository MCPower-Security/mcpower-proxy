"""
Cursor Router

Routes Cursor hook calls to appropriate handlers.
"""

import json
import sys
import uuid

from modules.logs.audit_trail import AuditTrailLogger
from modules.logs.logger import MCPLogger


def route_cursor_hook(logger: MCPLogger, audit_logger: AuditTrailLogger, stdin_input: str):
    """
    Route Cursor hook to appropriate handler
    
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
            from .init import main as init_main
            init_main(logger, audit_logger, stdin_input, prompt_id, event_id, cwd)
        elif hook_event_name == "beforeShellExecution":
            from .before_shell_execution import main as before_shell_execution_main
            before_shell_execution_main(logger, audit_logger, stdin_input, prompt_id, event_id, cwd)
        elif hook_event_name == "afterShellExecution":
            from .after_shell_execution import main as after_shell_execution_main
            after_shell_execution_main(logger, audit_logger, stdin_input, prompt_id, event_id, cwd)
        elif hook_event_name == "beforeReadFile":
            from .before_read_file import main as before_read_file_main
            before_read_file_main(logger, audit_logger, stdin_input, prompt_id, event_id, cwd)
        elif hook_event_name == "beforeSubmitPrompt":
            from .before_submit_prompt import main as before_submit_prompt_main
            before_submit_prompt_main(logger, audit_logger, stdin_input, prompt_id, event_id, cwd)
        else:
            logger.error(f"Unknown hook_event_name: {hook_event_name}")
            sys.exit(1)

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse input JSON: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Routing error: {e}", exc_info=True)
        sys.exit(1)
