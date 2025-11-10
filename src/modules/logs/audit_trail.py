"""
Audit Trail Logger for MCP Wrapper

Provides comprehensive transparency and accountability by logging all data flows 
through the MCP wrapper in a user-facing, sequential JSON Lines format.

Captures complete request/response lifecycles including:
- Wrapper initialization
- Agent requests and policy decisions  
- User confirmation interactions
- Data forwarding and responses
- API communications with policy service

All data is automatically redacted for PII and secrets before logging.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from modules.logs.logger import MCPLogger
from modules.redaction.redactor import redact
from modules.utils.config import get_audit_trail_path
from modules.utils.ids import get_session_id
from modules.utils.json import safe_json_dumps, to_dict


class AuditTrailLogger:
    """
    Audit trail logger for transparent MCP wrapper operations
    
    Logs all data flows through the wrapper in JSON Lines format for user transparency.
    Each log entry represents one step in the sequential flow of MCP operations.
    """

    def __init__(self, logger: MCPLogger):
        """
        Initialize audit trail logger
        
        Args:
            logger: Existing MCPLogger instance for error reporting
        """
        self.logger = logger
        self.app_uid: Optional[str] = None  # Will be set by middleware after roots are available
        self.session_id = get_session_id()
        self.audit_file = get_audit_trail_path()
        self._pending_logs: List[Dict[str, Any]] = []  # Queue logs until app_uid is set

        # Ensure audit trail file directory exists
        Path(self.audit_file).parent.mkdir(parents=True, exist_ok=True)

    def log_event(
            self,
            event_type: str,
            data: Dict[str, Any],
            *,
            event_id: Optional[str] = None,
            prompt_id: Optional[str] = None,
            user_prompt: Optional[str] = None,
            ignored_keys: Optional[List[str]] = None,
            include_keys: Optional[List[str]] = None
    ):
        """
        Log a single audit event
        
        Args:
            event_type: Type of audit event (e.g., 'mcpower_start', 'agent_request')
            data: Event-specific data dictionary (will be automatically redacted)
            event_id: Optional event correlation ID (for pairing request/response)
            prompt_id: Optional user prompt correlation ID (for grouping tool calls by prompt)
            user_prompt: Optional user prompt text (stored once per prompt_id)
            ignored_keys: Optional list of JSONPath patterns to ignore during redaction
            include_keys: Optional list of JSONPath patterns to redact (all others ignored)
        """
        try:
            # Convert data to dict structure (handles nested objects, dataclasses, Pydantic models)
            data_dict = to_dict(data)

            # Build event structure
            event = {
                "session_id": self.session_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event_type": event_type,
                "data": redact(data_dict, ignored_keys=ignored_keys, include_keys=include_keys)
                # Redaction with optional key filtering
            }

            # Include prompt_id if provided (for grouping by user prompt)
            if prompt_id:
                event["prompt_id"] = prompt_id

            # Include event_id if provided (for pairing request/response)
            if event_id:
                event["event_id"] = event_id

            # Include user_prompt text if provided (only needed once per prompt_id)
            if user_prompt:
                event["user_prompt"] = user_prompt

            # If app_uid not set yet, queue the log
            if self.app_uid is None:
                self._pending_logs.append(event)
            else:
                # app_uid is available, write immediately
                self._write_event(event)

        except Exception as e:
            # Log errors to existing logger but continue operation
            self.logger.error(f"Audit trail write failed: {e}")

    def _write_event(self, event: Dict[str, Any]):
        """
        Write a single event to the audit trail file with app_uid as first key
        
        Args:
            event: Event dict (may or may not have app_uid already)
        """
        # Ensure app_uid is first key in the output
        event_with_app_uid = {
            "app_uid": self.app_uid,
            **{k: v for k, v in event.items() if k != "app_uid"}
        }

        # Atomic append to audit trail file
        with open(self.audit_file, 'a', encoding='utf-8') as f:
            f.write(safe_json_dumps(event_with_app_uid) + '\n')
            f.flush()  # Force immediate write for crash safety

    def set_app_uid(self, app_uid: str):
        """
        Set the app_uid and flush all pending logs to file
        
        This is called by the middleware after workspace roots are available.
        All queued logs will be written with app_uid as the first key.
        Supports updating app_uid when workspace context changes.
        
        Args:
            app_uid: The application UID from workspace root
        """
        if self.app_uid == app_uid:
            return

        if self.app_uid is not None:
            self.logger.info(f"app_uid changed from {self.app_uid} to {app_uid}")
        else:
            self.logger.debug(f"app_uid set to: {app_uid}")

        self.app_uid = app_uid

        # Flush all pending logs
        if self._pending_logs:
            self.logger.debug(f"Flushing {len(self._pending_logs)} queued audit logs")
            for event in self._pending_logs:
                self._write_event(event)
            self._pending_logs.clear()


def setup_audit_trail_logger(logger: MCPLogger) -> AuditTrailLogger:
    """
    Create audit trail logger instance
    
    Args:
        logger: Existing MCPLogger instance for error reporting
        
    Returns:
        Configured AuditTrailLogger instance
    """
    return AuditTrailLogger(logger)
