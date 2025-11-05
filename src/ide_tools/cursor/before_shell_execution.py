"""
Cursor beforeShellExecution Handler

Processes shell commands from Cursor's beforeShellExecution hook,
analyzes them for safety using inspect_request API, and prompts user for confirmation when needed.
"""

from typing import Optional

from modules.logs.logger import MCPLogger
from .shell_handler_base import handle_shell_operation


def main(logger: MCPLogger, audit_logger, stdin_input: str, prompt_id: str, event_id: str, cwd: Optional[str]):
    """
    Main entry point for beforeShellExecution handler
    
    Args:
        logger: MCPLogger instance
        audit_logger: AuditTrailLogger instance
        stdin_input: Raw input string from stdin
        prompt_id: Prompt ID from conversation_id
        event_id: Event ID from generation_id
        cwd: Current working directory from workspace_roots[0]
    """
    handle_shell_operation(
        logger=logger,
        audit_logger=audit_logger,
        stdin_input=stdin_input,
        prompt_id=prompt_id,
        event_id=event_id,
        cwd=cwd,
        is_request=True,
        required_fields={"command": str, "cwd": str},
        redact_fields=["command"],
        tool_name="beforeShellExecution",
        operation_name="Command",
        audit_event_type="agent_request",
        audit_forwarded_event_type="agent_request_forwarded"
    )
