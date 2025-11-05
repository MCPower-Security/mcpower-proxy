"""
Utilities for generating event IDs, session IDs, app UIDs, and timing helpers
"""
import os
import sys
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


def generate_prompt_id() -> str:
    """
    Generate truly-random 8-character prompt ID for user request correlation
    
    Returns:
        8-character random ID string
    """
    return str(uuid.uuid4())[:8]


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


def _atomic_write_uuid(file_path: Path, new_uuid: str) -> bool:
    """
    Attempt atomic write of UUID to file using O_CREAT | O_EXCL.
    Returns True if write succeeded, False if file already exists.
    
    Args:
        file_path: Path to write UUID
        new_uuid: UUID string to write
        
    Returns:
        True if write succeeded, False if file exists
    """
    try:
        mode = 0o666 if sys.platform == 'win32' else 0o600
        fd = os.open(str(file_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, mode)
        try:
            os.write(fd, new_uuid.encode('utf-8'))
        finally:
            os.close(fd)
        return True
    except FileExistsError:
        return False


def _get_or_create_uuid(uid_path: Path, logger, id_type: str) -> str:
    """
    Get or create UUID at specified path with race safety.
    Common logic shared by user ID and app UID generation.
    
    Args:
        uid_path: Path to UUID file
        logger: Logger instance
        id_type: Description for logging (e.g., "user ID", "app UID")
        
    Returns:
        UUID string
    """
    uid_path.parent.mkdir(parents=True, exist_ok=True)

    max_attempts = 3
    for attempt in range(max_attempts):
        if uid_path.exists():
            try:
                existing_uid = uid_path.read_text().strip()
                if is_valid_uuid(existing_uid):
                    return existing_uid
                logger.warning(f"Invalid UUID in {uid_path}, regenerating (attempt {attempt + 1}/{max_attempts})")
                uid_path.unlink()
            except Exception as e:
                logger.warning(f"Failed to read {uid_path}: {e} (attempt {attempt + 1}/{max_attempts})")
                if attempt < max_attempts - 1:
                    time.sleep(0.1 * (2 ** attempt))
                    continue
                raise

        new_uid = str(uuid.uuid4())

        if _atomic_write_uuid(uid_path, new_uid):
            logger.info(f"Generated {id_type}: {new_uid} at {uid_path}")
            return new_uid

        logger.debug(
            f"{id_type.title()} file created by another process, reading (attempt {attempt + 1}/{max_attempts})")
        if attempt < max_attempts - 1:
            time.sleep(0.05)

    raise RuntimeError(f"Failed to get or create {id_type} after {max_attempts} attempts")


def get_home_mcpower_dir() -> Path:
    """
    Get the global MCPower directory path in user's home directory
    
    Returns:
        Path to ~/.mcpower directory
    """
    return Path.home() / ".mcpower"


def get_project_mcpower_dir(project_path: Optional[str] = None) -> str:
    """
    Get the MCPower directory path, with fallback to global ~/.mcpower

    Args:
        project_path: Optional project/workspace path. If None or invalid, falls back to ~/.mcpower

    Returns:
        Path to use for MCPower data (either project/.mcpower or ~/.mcpower)
    """
    if project_path:
        try:
            path = Path(project_path)
            if path.exists() and path.is_dir():
                return str(path)
        except Exception:
            pass

    # Fallback to global ~/.mcpower
    return str(get_home_mcpower_dir())


def get_or_create_user_id(logger) -> str:
    """
    Get or create machine-wide user ID from ~/.mcpower/uid
    Race-safe: multiple concurrent processes will converge on single ID
    
    Args:
        logger: Logger instance for messages
        
    Returns:
        User ID string
    """
    uid_path = get_home_mcpower_dir() / "uid"
    return _get_or_create_uuid(uid_path, logger, "user ID")


def read_app_uid(logger, project_folder_path: str) -> str:
    """
    Get or create app UID from project folder's .mcpower/app_uid file
    Race-safe: multiple concurrent processes will converge on single ID

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
    else:
        # Project-specific case
        uid_path = project_path / ".mcpower" / "app_uid"

    return _get_or_create_uuid(uid_path, logger, "app UID")
