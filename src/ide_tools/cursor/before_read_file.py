"""
Cursor beforeReadFile Handler

Processes file read requests from Cursor's beforeReadFile hook,
redacts sensitive content, and analyzes for security issues using inspect_request API.
Only calls API when redactions are found.
"""

import sys
from typing import Dict, Any, List, Tuple, Optional

from modules.logs.logger import MCPLogger
from modules.redaction import redact
from modules.utils.ids import get_session_id, read_app_uid, get_project_mcpower_dir
from .constants import HookPermission, cursor_tools_mcp_name
from .utils import (
    output_permission_result, create_validator, call_api_and_output,
    handle_unexpected_error, extract_redaction_patterns, process_attachments_for_redaction
)


def read_file_content(file_path: str, fallback_content: str, logger: MCPLogger) -> str:
    """
    Read file content from file_path, fall back to provided content if unreachable
    
    Args:
        file_path: Absolute path to file
        fallback_content: Content provided in input (fallback)
        logger: Logger instance
        
    Returns:
        File content (either read from disk or fallback)
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        logger.debug(f"Successfully read file content from: {file_path}")
        return content
    except (FileNotFoundError, PermissionError, OSError) as e:
        logger.warning(
            f"Could not read file at {file_path}: {e}. "
            f"Falling back to examining provided content instead."
        )
        return fallback_content


def process_files_for_redaction(
        main_file_path: str,
        main_content: str,
        attachments: List[Dict[str, Any]],
        logger: MCPLogger
) -> Tuple[List[Dict[str, Any]], bool]:
    """
    Process main file and attachments, extract redaction patterns per file
    
    Args:
        main_file_path: Path to main file
        main_content: Content of main file (already read)
        attachments: List of attachment dicts
        logger: Logger instance
        
    Returns:
        Tuple of (files_with_sensitive_data, has_any_redactions)
        - files_with_sensitive_data: List of file security analysis results
        - has_any_redactions: True if any file had redactions
    """
    files_with_sensitive_data = []

    redacted_main = redact(main_content)
    main_patterns = extract_redaction_patterns(redacted_main)
    if main_patterns:
        # Build explicit structure showing sensitive data types with occurrence counts
        sensitive_data_types = {}
        for pattern_text, count in main_patterns.items():
            # Extract type from [REDACTED-TYPE] format
            data_type = pattern_text.replace("[REDACTED-", "").replace("]", "")
            sensitive_data_types[data_type] = {
                "occurrences": count,
                "description": f"Found {count} instance(s) of {data_type} in file"
            }

        files_with_sensitive_data.append({
            "file_path": main_file_path,
            "contains_sensitive_data": True,
            "sensitive_data_types": sensitive_data_types,
            "risk_summary": f"File contains {sum(main_patterns.values())} sensitive data item(s) across {len(main_patterns)} type(s)"
        })
        logger.info(f"Found {len(main_patterns)} sensitive data type(s) in main file: {main_file_path}")

    att_files, _ = process_attachments_for_redaction(attachments, logger)
    files_with_sensitive_data.extend(att_files)

    has_any_redactions = len(files_with_sensitive_data) > 0
    return files_with_sensitive_data, has_any_redactions


tool_name = "beforeReadFile"


def main(logger: MCPLogger, audit_logger, stdin_input: str, prompt_id: str, event_id: str, cwd: Optional[str]):
    """
    Main entry point for beforeReadFile handler
    
    Args:
        logger: MCPLogger instance
        audit_logger: AuditTrailLogger instance
        stdin_input: Raw input string from stdin
        prompt_id: Prompt ID from conversation_id
        event_id: Event ID from generation_id
        cwd: Optional, current working directory from workspace_roots[0]
    """
    session_id = get_session_id()

    logger.info(f"beforeReadFile handler started (prompt_id={prompt_id}, event_id={event_id}, cwd={cwd})")

    app_uid = read_app_uid(logger, get_project_mcpower_dir(cwd))
    audit_logger.set_app_uid(app_uid)

    try:
        try:
            validator = create_validator(
                required_fields={"file_path": str, "content": str},
                optional_fields={"attachments": list}
            )
            input_data = validator(stdin_input)
            file_path = input_data["file_path"]
            provided_content = input_data["content"]
            attachments = input_data.get("attachments", [])
        except ValueError as e:
            logger.error(f"Input validation error: {e}")
            error_message = str(e)
            output_permission_result(
                logger,
                HookPermission.DENY,
                error_message,
                error_message
            )
            sys.exit(1)

        audit_logger.log_event(
            "agent_request",
            {
                "server": cursor_tools_mcp_name,
                "tool": tool_name,
                "params": {"file_path": file_path, "attachments_count": len(attachments)}
            },
            event_id=event_id
        )

        file_content = read_file_content(file_path, provided_content, logger)

        files_with_redactions, has_any_redactions = process_files_for_redaction(
            file_path,
            file_content,
            attachments,
            logger
        )

        # If no redactions found, allow immediately without API call
        if not has_any_redactions:
            logger.info("No sensitive data found in files - allowing without API call")

            audit_logger.log_event(
                "agent_request_forwarded",
                {
                    "server": cursor_tools_mcp_name,
                    "tool": tool_name,
                    "params": {"file_path": file_path, "redactions_found": has_any_redactions}
                },
                event_id=event_id
            )

            output_permission_result(logger, HookPermission.ALLOW)
            sys.exit(0)

        logger.info(f"Found redactions in {len(files_with_redactions)} file(s) - calling API for inspection")

        # Build explicit content_data structure showing security risk
        total_sensitive_items = sum(
            sum(f["sensitive_data_types"][dt]["occurrences"] for dt in f["sensitive_data_types"])
            for f in files_with_redactions
        )

        call_api_and_output(
            is_request=True,
            session_id=session_id,
            logger=logger,
            audit_logger=audit_logger,
            app_uid=app_uid,
            event_id=event_id,
            tool_name=tool_name,
            content_data={
                "security_alert": "Sensitive data detected in files being read by IDE",
                "files_with_secrets_or_pii": files_with_redactions,
                "summary": f"{len(files_with_redactions)} file(s) contain {total_sensitive_items} sensitive data item(s)"
            },
            prompt_id=prompt_id,
            cwd=cwd,
            audit_forwarded_event_type="agent_request_forwarded",
            audit_params={"file_path": file_path, "redactions_found": has_any_redactions},
            operation_name="File read",
            current_files=[file_path]
        )

    except Exception as e:
        handle_unexpected_error(e, logger, "beforeReadFile", "File read")
