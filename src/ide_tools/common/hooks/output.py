"""
IDE-agnostic output handling
"""

import sys
from typing import Optional

from modules.logs.logger import MCPLogger
from .types import OutputFormat


def output_result(
        logger: MCPLogger,
        output_format: OutputFormat,
        hook_type: str,
        allowed: bool,
        user_message: Optional[str] = None,
        agent_message: Optional[str] = None
) -> None:
    """
    Output hook result in IDE-specific format and exit with appropriate code
    
    Args:
        logger: Logger instance
        output_format: IDE-specific output configuration
        hook_type: "permission" or "continue"
        allowed: True for allow/continue, False for deny/block
        user_message: Optional message for user
        agent_message: Optional message for agent/logs
    """
    # Format output using IDE-specific formatter
    formatted_output = output_format.formatter(hook_type, allowed, user_message, agent_message)

    logger.info(f"Hook output ({hook_type}, allowed={allowed}): {formatted_output}")
    print(formatted_output, flush=True)

    # Exit with appropriate code
    exit_code = output_format.allow_exit_code if allowed else output_format.deny_exit_code
    sys.exit(exit_code)


def output_error(
        logger: MCPLogger,
        output_format: OutputFormat,
        hook_type: str,
        error_message: str
) -> None:
    """
    Output error and exit with error code
    
    Args:
        logger: Logger instance
        output_format: IDE-specific output configuration
        hook_type: "permission" or "continue"
        error_message: Error message
    """
    logger.error(f"Hook error: {error_message}")

    # Output as deny/block with error message
    formatted_output = output_format.formatter(hook_type, False, error_message, error_message)
    print(formatted_output, flush=True)

    sys.exit(output_format.error_exit_code)
