"""
Claude Code-specific output formatting
"""

import json
from typing import Optional

from ide_tools.common.hooks.types import OutputFormat


def claude_code_output_formatter(hook_type: str, allowed: bool, user_msg: Optional[str],
                                 agent_msg: Optional[str]) -> str:
    """
    Format output for Claude Code
    
    Args:
        hook_type: "permission" or "continue"
        allowed: True for allow/continue, False for deny/block
        user_msg: Message for user
        agent_msg: Message for agent/logs
    
    Returns:
        JSON string in Claude Code format
    """
    if hook_type == "permission":
        result = {"permissionDecision": "allow" if allowed else "deny"}
        if user_msg or agent_msg:
            result["permissionDecisionReason"] = agent_msg or user_msg
    else:  # continue (UserPromptSubmit)
        result = {}
        if not allowed:
            result["decision"] = "block"
            result["reason"] = agent_msg or user_msg or "Blocked by security policy"
        # If allowed, return empty dict (allows prompt)

    return json.dumps(result)


# Claude Code-specific output format configuration
CLAUDE_CODE_OUTPUT = OutputFormat(
    allow_exit_code=0,
    deny_exit_code=0,  # Claude Code uses structured output, not exit codes
    error_exit_code=1,  # Exit 1 unexpected errors
    formatter=claude_code_output_formatter
)
