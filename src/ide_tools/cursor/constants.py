"""
Cursor Hook Constants

Configuration values specific to Cursor hook handlers.
"""

from enum import Enum

from ide_tools.common.hooks.types import HookConfig, OutputFormat
from ide_tools.cursor.format import cursor_output_formatter


class HookPermission(str, Enum):
    """Cursor hook response permission values"""
    ALLOW = "allow"
    DENY = "deny"


# Cursor-specific configuration
CURSOR_CONFIG = HookConfig(
    output_format=OutputFormat(
        allow_exit_code=0,
        deny_exit_code=1,
        error_exit_code=1,
        formatter=cursor_output_formatter
    ),
    server_name="mcpower_cursor",
    client_name="cursor",
    max_content_length=100000
)

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
