"""
Simple line-based logger for MCP traffic and wrapped MCP logs
Implements the required logging format for all MCP operations
"""

import logging
import sys
from pathlib import Path
from typing import Optional, TextIO

from modules.utils.ids import get_session_id


class UTF8StreamHandler(logging.StreamHandler):
    """StreamHandler that forces UTF-8 encoding on Windows to prevent UnicodeEncodeError"""

    def __init__(self, stream=None):
        # On Windows, wrap the stream with UTF-8 encoding BEFORE passing to parent
        if sys.platform == 'win32' and stream is not None:
            import io
            if hasattr(stream, 'buffer'):
                stream = io.TextIOWrapper(
                    stream.buffer,
                    encoding='utf-8',
                    errors='replace',
                    line_buffering=True
                )

        super().__init__(stream)


class SessionFormatter(logging.Formatter):
    """Custom formatter that includes session ID in log messages"""

    # Single character mapping for perfect alignment and compactness
    LEVEL_MAPPING = {
        'DEBUG': 'D',
        'INFO': 'I',
        'WARNING': 'W',
        'ERROR': 'E',
        'CRITICAL': 'C'
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._session_id = get_session_id()[:8]

    def format(self, record):
        # Use the cached session ID
        record.session_id = self._session_id
        # Override levelname with single character version
        if not record.levelname or not isinstance(record.levelname, str):
            record.levelname = 'U'  # Unknown
        else:
            record.levelname = self.LEVEL_MAPPING.get(record.levelname, record.levelname[0])
        return super().format(record)


class MCPLogger:
    """Simple line-based logger for MCP traffic"""

    def __init__(self, log_file: Optional[str] = None, level: int = logging.INFO):
        self.log_file = log_file
        self.file_handle: Optional[TextIO] = None

        # Setup file handle if log file specified (for MCP traffic logging)
        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            self.file_handle = open(log_path, 'a', encoding='utf-8')

        # Setup standard logger for non-MCP messages
        self.logger = logging.getLogger('mcpower')
        self.logger.setLevel(level)

        # Create console handler with UTF-8 support
        console_handler = UTF8StreamHandler(sys.stderr)
        console_handler.setLevel(level)
        formatter = SessionFormatter('%(asctime)s [%(session_id)s] (%(levelname)s) %(message)s')
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        # Add file handler if log file specified
        if log_file:
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

    def info(self, message: str) -> None:
        """Log info message"""
        self.logger.info(message)

    def error(self, message: str, exc_info: bool = False) -> None:
        """Log error message"""
        self.logger.error(message, exc_info=exc_info)

    def warning(self, message: str) -> None:
        """Log warning message"""
        self.logger.warning(message)

    def debug(self, message: str) -> None:
        """Log debug message"""
        self.logger.debug(message)

    def close(self) -> None:
        """Close log file handle"""
        if self.file_handle:
            self.file_handle.close()
            self.file_handle = None


def setup_logger(log_file: Optional[str] = None, level: int = logging.INFO) -> MCPLogger:
    """
    Setup MCP logger with specified configuration
    
    Args:
        log_file: Optional path to log file (uses stdout if None)
        level: Logging level
        
    Returns:
        Configured MCPLogger instance
    """
    return MCPLogger(log_file, level)
