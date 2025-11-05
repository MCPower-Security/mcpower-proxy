"""
Shared logic for shell execution handlers (before/after)
"""
import sys
from typing import Dict, List, Optional

from modules.logs.audit_trail import AuditTrailLogger
from modules.logs.logger import MCPLogger
from modules.redaction import redact
from modules.utils.ids import get_session_id, read_app_uid, get_project_mcpower_dir
from .constants import HookPermission, cursor_tools_mcp_name
from .utils import output_permission_result, create_validator, call_api_and_output, handle_unexpected_error


def handle_shell_operation(
        logger: MCPLogger,
        audit_logger: AuditTrailLogger,
        stdin_input: str,
        prompt_id: str,
        event_id: str,
        cwd: Optional[str],
        is_request: bool,
        required_fields: Dict[str, type],
        redact_fields: List[str],
        tool_name: str,
        operation_name: str,
        audit_event_type: str,
        audit_forwarded_event_type: str,
):
    """
    Common handler logic for shell operations
    
    Args:
        is_request: True for beforeShellExecution, False for afterShellExecution
        required_fields: Fields to validate in input
        redact_fields: Fields to redact for logging and API calls
        tool_name: Hook name (e.g., "beforeShellExecution")
        operation_name: Display name (e.g., "Command", "Command output")
        audit_event_type: Audit event name for incoming operation
        audit_forwarded_event_type: Audit event name for forwarded operation
    """
    session_id = get_session_id()
    deny_exit_code = 126 if not is_request else 1
    logger.info(f"{tool_name} handler started (prompt_id={prompt_id}, event_id={event_id}, cwd={cwd})")

    try:
        validator = create_validator(required_fields)
        try:
            input_data = validator(stdin_input)
        except ValueError as e:
            logger.error(f"Input validation error: {e}")
            error_message = str(e)
            output_permission_result(logger, HookPermission.DENY, error_message, error_message)
            sys.exit(1)

        app_uid = read_app_uid(logger, get_project_mcpower_dir(cwd))
        audit_logger.set_app_uid(app_uid)

        redacted_data = {}
        for k, v in input_data.items():
            if k in required_fields:
                redacted_data[k] = redact(v) if k in redact_fields else v
        logger.info(f"Analyzing {tool_name}: {redacted_data}")

        # Use different structure for request vs response events
        # Requests: params nested, Responses: unpacked at root
        if is_request:
            audit_data = {
                "server": cursor_tools_mcp_name,
                "tool": tool_name,
                "params": redacted_data
            }
        else:
            audit_data = {
                "server": cursor_tools_mcp_name,
                "tool": tool_name,
                **redacted_data
            }

        audit_logger.log_event(
            audit_event_type,
            audit_data,
            event_id=event_id
        )

        call_api_and_output(
            is_request=is_request,
            session_id=session_id,
            logger=logger,
            audit_logger=audit_logger,
            app_uid=app_uid,
            event_id=event_id,
            tool_name=tool_name,
            content_data=redacted_data,
            prompt_id=prompt_id,
            cwd=cwd,
            audit_forwarded_event_type=audit_forwarded_event_type,
            audit_params=redacted_data if is_request else None,
            audit_response_content=redacted_data if not is_request else None,
            operation_name=operation_name,
            deny_exit_code=deny_exit_code
        )

    except Exception as e:
        handle_unexpected_error(e, logger, tool_name, operation_name, exit_code=deny_exit_code)
