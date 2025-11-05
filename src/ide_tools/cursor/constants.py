"""
Cursor Hook Constants

Configuration values specific to Cursor hook handlers.
"""

from enum import Enum


class HookPermission(str, Enum):
    """Cursor hook response permission values"""
    ALLOW = "allow"
    DENY = "deny"


cursor_tools_mcp_name = "mcpower_cursor"
