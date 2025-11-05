"""
Cursor afterShellExecution Handler

Processes shell command results from Cursor's afterShellExecution hook,
analyzes them for security issues using inspect_response API, and prompts user for confirmation when needed.
"""

from typing import Optional

from modules.logs.logger import MCPLogger
from .shell_handler_base import handle_shell_operation


def main(logger: MCPLogger, audit_logger, stdin_input: str, prompt_id: str, event_id: str, cwd: Optional[str]):
    """
    Main entry point for afterShellExecution handler
    
    Args:
        logger: MCPLogger instance
        audit_logger: AuditTrailLogger instance
        stdin_input: Raw input string from stdin
        prompt_id: Prompt ID from conversation_id
        event_id: Event ID from generation_id
        cwd: Optional, current working directory from workspace_roots[0]
    """

    handle_shell_operation(
        logger=logger,
        audit_logger=audit_logger,
        stdin_input=stdin_input,
        prompt_id=prompt_id,
        event_id=event_id,
        cwd=cwd,
        is_request=False,
        required_fields={"command": str, "output": str},
        redact_fields=["command", "output"],
        tool_name="afterShellExecution",
        operation_name="Command output",
        audit_event_type="mcp_response",
        audit_forwarded_event_type="mcp_response_forwarded"
    )
