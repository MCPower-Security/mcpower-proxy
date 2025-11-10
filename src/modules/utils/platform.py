"""Platform detection utilities"""
import sys
from typing import Optional, Literal


def get_client_os() -> Optional[Literal["macos", "windows", "linux"]]:
    """
    Fetch Python's sys.platform and convert to standardized OS names.
    
    Returns:
        "macos", "windows", "linux", or None if platform is unknown
    """
    platform = sys.platform
    
    if platform == "darwin":
        return "macos"
    elif platform == "win32":
        return "windows"
    elif platform == "linux":
        return "linux"
    else:
        return None

