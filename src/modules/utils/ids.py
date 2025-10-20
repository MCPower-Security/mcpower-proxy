"""
Utilities for generating event IDs, session IDs, app UIDs, and timing helpers
"""
import time
import uuid
from pathlib import Path
from typing import Optional

# Process-wide session ID cache
_session_id: Optional[str] = None


def generate_event_id() -> str:
    """
    Generate unique event ID for MCP operations
    
    Returns:
        Unique event ID string
    """
    timestamp = int(time.time() * 1000)  # milliseconds
    unique_part = str(uuid.uuid4())[:8]
    return f"{timestamp}-{unique_part}"


def get_session_id() -> str:
    """
    Get session ID for the current process. Returns the same value for all calls
    within the same Python process instance.
    
    Returns:
        Process-wide session ID string
    """
    global _session_id
    if _session_id is None:
        _session_id = str(uuid.uuid4())
    return _session_id


def is_valid_uuid(uuid_string: str) -> bool:
    """
    Validate if a string is a valid UUID
    
    Args:
        uuid_string: String to validate
        
    Returns:
        True if valid UUID, False otherwise
    """
    try:
        uuid.UUID(uuid_string)
        return True
    except ValueError:
        return False


def read_app_uid(logger, project_folder_path: str) -> str:
    """
    Generate or read app UID from project folder's .mcpower/app_uid file

    Args:
        logger: Logger instance for messages
        project_folder_path: Path to the project folder

    Returns:
        App UID string
    """
    project_path = Path(project_folder_path)

    # Check if path already contains .mcpower (forced/default case)
    if ".mcpower" in project_path.parts:
        uid_path = project_path / "app_uid"
        uid_path.parent.mkdir(exist_ok=True)
    else:
        # Project-specific case
        uid_path = project_path / ".mcpower" / "app_uid"
        uid_path.parent.mkdir(exist_ok=True)

    if uid_path.exists():
        existing_uid = uid_path.read_text().strip()
        if is_valid_uuid(existing_uid):
            return existing_uid
        logger.warning(f"Invalid UUID in {uid_path}, generating new one")

    new_uid = str(uuid.uuid4())
    uid_path.write_text(new_uid)
    logger.info(f"Generated app UID: {new_uid}")
    return new_uid
