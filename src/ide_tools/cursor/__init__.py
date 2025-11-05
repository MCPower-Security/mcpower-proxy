"""
Cursor IDE Handler

Handles Cursor-specific hooks and operations.
"""

from .after_shell_execution import main as after_shell_execution_main
from .before_read_file import main as before_read_file_main
from .before_shell_execution import main as before_shell_execution_main
from .before_submit_prompt import main as before_submit_prompt_main
from .init import main as init_main
from .router import route_cursor_hook

__all__ = [
    "init_main",
    "before_shell_execution_main",
    "after_shell_execution_main",
    "before_read_file_main",
    "before_submit_prompt_main",
    "route_cursor_hook",
]
