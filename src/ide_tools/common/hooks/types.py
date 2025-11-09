"""
Common types for IDE hooks - IDE-agnostic
"""

from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class OutputFormat:
    """
    Defines how to format hook output for a specific IDE.
    This is a generic interface - IDEs provide their own implementations.
    """
    # Exit codes
    allow_exit_code: int
    deny_exit_code: int
    error_exit_code: int

    # Output formatter function
    # Args: (hook_type: str, allowed: bool, user_msg: Optional[str], agent_msg: Optional[str]) -> str
    formatter: Callable[[str, bool, Optional[str], Optional[str]], str]


@dataclass
class HookConfig:
    """
    Configuration for a specific hook execution.
    IDE-specific modules create instances of this with their own output format.
    """
    output_format: OutputFormat
    server_name: str  # IDE-specific tool server name
    client_name: str  # IDE-specific client name (e.g. "cursor", "claude-code")
    max_content_length: int  # Maximum content length before skipping API call
