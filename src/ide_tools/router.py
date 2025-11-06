"""
IDE Tools Router

Routes hook calls to appropriate IDE-specific routers based on --ide flag.
"""

import sys
from typing import Optional

from modules.logs.audit_trail import AuditTrailLogger
from modules.logs.logger import MCPLogger


def main(logger: MCPLogger, audit_logger: AuditTrailLogger, ide: str, context: Optional[str]):
    """
    Main entry point for IDE tools - routes to appropriate IDE router
    
    Args:
        logger: MCPLogger instance
        audit_logger: AuditTrailLogger instance
        ide: IDE name (e.g., "cursor")
        context: Additional context (to be verified as optional by the associated --ide handler)
    """
    # Monkey patch sys.exit to log exit code
    original_exit = sys.exit

    def logged_exit(code=0):
        logger.info(f"sys.exit called with code: {code}")
        original_exit(code)

    sys.exit = logged_exit

    logger.info(f"IDE Tools router: ide={ide}, context={context}")

    # Read stdin input once at the top level (raw string)
    # Each handler will parse it according to its own schema
    stdin_input = sys.stdin.read()

    # Route to appropriate IDE handler with the raw input string
    if ide == "cursor":
        from ide_tools.cursor import route_cursor_hook
        route_cursor_hook(logger, audit_logger, stdin_input)
    elif ide == "claude-code":
        from ide_tools.claude_code import route_claude_code_hook
        route_claude_code_hook(logger, audit_logger, stdin_input)
    else:
        logger.error(f"Unknown IDE: {ide}")
        sys.exit(1)
