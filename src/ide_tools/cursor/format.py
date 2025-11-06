"""
Cursor-specific output formatting
"""

import json
from typing import Optional


def cursor_output_formatter(hook_type: str, allowed: bool, user_msg: Optional[str], agent_msg: Optional[str]) -> str:
    """
    Format output for Cursor IDE
    
    Args:
        hook_type: "permission" or "continue"
        allowed: True for allow/continue, False for deny/block
        user_msg: Message for user
        agent_msg: Message for agent/logs
    
    Returns:
        JSON string in Cursor format
    """
    if hook_type == "permission":
        result = {"permission": "allow" if allowed else "deny"}
        if user_msg:
            result["user_message"] = user_msg
        if agent_msg:
            result["agent_message"] = agent_msg
    else:  # continue
        result = {"continue": allowed}
        if user_msg:
            result["user_message"] = user_msg
        if agent_msg:
            result["agent_message"] = agent_msg

    return json.dumps(result)
