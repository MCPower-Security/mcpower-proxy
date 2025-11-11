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
        "version": "1.0.0",
        "parameters": '{"type":"object","properties":{"command":{"type":"string","description":"Full terminal '
                      'command"},"cwd":{"type":"string","description":"Current working directory"}},"required":['
                      '"command","cwd"],"additionalProperties":false}'
    },
    "afterShellExecution": {
        "name": "afterShellExecution",
        "description": "Triggered after a shell command completes execution. "
                       "Provides access to command output and exit status.",
        "version": "1.0.0",
        "parameters": '{"type":"object","properties":{"command":{"type":"string","description":"Full terminal '
                      'command"},"output":{"type":"string","description":"Full terminal output"}},"required":['
                      '"command","output"],"additionalProperties":false}'
    },
    "beforeReadFile": {
        "name": "beforeReadFile",
        "description": "Triggered before the agent reads a file. "
                       "Allows inspection and potential blocking of file read operations.",
        "version": "1.0.0",
        "parameters": '{"type":"object","properties":{"file_path":{"type":"string","description":"Absolute path to '
                      'the file being read"},"content":{"type":"string","description":"File contents"},'
                      '"attachments":{"type":"array","description":"Additional related attachments",'
                      '"items":{"type":"object","properties":{"type":{"type":"string","description":"Attachment '
                      'type"},"file_path":{"type":"string","description":"Absolute path to the attachment"}},'
                      '"required":["type","file_path"],"additionalProperties":false}}},"required":["file_path",'
                      '"content"],"additionalProperties":false}'
    },
    "beforeSubmitPrompt": {
        "name": "beforeSubmitPrompt",
        "description": "Triggered before a prompt is submitted to the AI model. "
                       "Allows inspection and modification of prompts.",
        "version": "1.0.0",
        "parameters": '{"type":"object","properties":{"prompt":{"type":"string","description":"User prompt text"},'
                      '"attachments":{"type":"array","description":"Attachments associated with the prompt",'
                      '"items":{"type":"object","properties":{"type":{"type":"string","enum":["file","rule"],'
                      '"description":"Attachment type"},"filePath":{"type":"string","description":"Absolute path to '
                      'the attached file or rule"}},"required":["type","filePath"],"additionalProperties":false}}},'
                      '"required":["prompt"],"additionalProperties":false}'
    }
}
