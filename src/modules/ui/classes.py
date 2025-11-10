from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any, Optional

from mcpower_shared.mcp_types import UserDecision


@dataclass
class DialogOptions:
    """Options for controlling dialog button visibility"""
    show_always_allow: bool = False
    show_always_block: bool = False


@dataclass
class ConfirmationRequest:
    """Request for user confirmation with all necessary context"""
    is_request: bool              # Which validation stage
    tool_name: str                # Tool being called
    policy_reasons: List[str]     # Security policy reasons
    content_data: Dict[str, Any]  # Arguments or response data
    severity: str                 # Security severity level
    event_id: str                 # Unique event identifier
    operation_type: str           # Type of MCP operation (tool, resource, etc.)
    server_name: str              # Proxied server name


@dataclass
class ConfirmationResponse:
    """User's confirmation decision with metadata"""
    user_decision: UserDecision  # User decision enum
    timestamp: datetime  # Decision timestamp
    event_id: str  # Matching event identifier
    direction: str  # "request" or "response"
    call_type: Optional[str] = None  # From inspect decision ("read", "write")
    timed_out: bool = False  # Whether decision timed out


class UserConfirmationError(Exception):
    """Raised when a user denies confirmation or confirmation fails"""

    def __init__(self, message: str, event_id: str, is_request: bool, tool_name: str):
        self.message = message
        self.event_id = event_id
        self.is_request = is_request
        self.tool_name = tool_name
        super().__init__(message)
