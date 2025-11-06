"""
Shared logic for beforeReadFile/PreReadFile hook
"""

from typing import Dict, Any, List, Tuple, Optional

from modules.logs.audit_trail import AuditTrailLogger
from modules.logs.logger import MCPLogger
from modules.utils.ids import get_session_id, read_app_uid, get_project_mcpower_dir
from .output import output_result, output_error
from .types import HookConfig
from .utils import create_validator, process_single_file_for_redaction, \
    process_attachments_for_redaction, inspect_and_enforce


def read_file_content(file_path: str, fallback_content: str, logger: MCPLogger) -> str:
    """
    Read file content from file_path, fall back to provided content if unreachable
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
    """
    files_with_sensitive_data = []
    
    # Process main file using shared utility
    main_result = process_single_file_for_redaction(main_file_path, main_content, logger)
    if main_result:
        files_with_sensitive_data.append(main_result)
    
    # Process attachments using shared utility
    att_files = process_attachments_for_redaction(attachments, logger)
    files_with_sensitive_data.extend(att_files)
    
    has_any_redactions = len(files_with_sensitive_data) > 0
    return files_with_sensitive_data, has_any_redactions


async def handle_read_file(
    logger: MCPLogger,
    audit_logger: AuditTrailLogger,
    stdin_input: str,
    prompt_id: str,
    event_id: str,
    cwd: Optional[str],
    config: HookConfig,
    tool_name: str
) -> None:
    """
    Shared handler for file read hooks
    
    Args:
        logger: Logger instance
        audit_logger: Audit logger instance
        stdin_input: Raw JSON input
        prompt_id: Prompt/conversation ID
        event_id: Event/generation ID
        cwd: Current working directory
        config: IDE-specific hook configuration
        tool_name: IDE-specific tool name (e.g., "beforeReadFile", "PreToolUse")
    """
    session_id = get_session_id()
    logger.info(f"Read file handler started (client={config.client_name}, prompt_id={prompt_id}, event_id={event_id}, cwd={cwd})")
    
    app_uid = read_app_uid(logger, get_project_mcpower_dir(cwd))
    audit_logger.set_app_uid(app_uid)
    
    try:
        # Validate input
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
            output_error(logger, config.output_format, "permission", str(e))
            return
        
        # Log audit event
        audit_logger.log_event(
            "agent_request",
            {
                "server": config.server_name,
                "tool": tool_name,
                "params": {"file_path": file_path, "attachments_count": len(attachments)}
            },
            event_id=event_id
        )
        
        # Read file content
        file_content = read_file_content(file_path, provided_content, logger)
        
        # Process files for redaction
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
                    "server": config.server_name,
                    "tool": tool_name,
                    "params": {"file_path": file_path, "redactions_found": has_any_redactions}
                },
                event_id=event_id
            )
            
            output_result(logger, config.output_format, "permission", True)
            return
        
        logger.info(f"Found redactions in {len(files_with_redactions)} file(s) - calling API for inspection")
        
        # Build explicit content_data structure showing security risk
        total_sensitive_items = sum(
            sum(f["sensitive_data_types"][dt]["occurrences"] for dt in f["sensitive_data_types"])
            for f in files_with_redactions
        )
        
        content_data = {
            "security_alert": "Sensitive data detected in files being read by IDE",
            "files_with_secrets_or_pii": files_with_redactions,
            "summary": f"{len(files_with_redactions)} file(s) contain {total_sensitive_items} sensitive data item(s)"
        }
        
        # Call security API and enforce decision
        try:
            decision = await inspect_and_enforce(
                is_request=True,
                session_id=session_id,
                logger=logger,
                audit_logger=audit_logger,
                app_uid=app_uid,
                event_id=event_id,
                server_name=config.server_name,
                tool_name=tool_name,
                content_data=content_data,
                prompt_id=prompt_id,
                cwd=cwd,
                current_files=[file_path],
                client_name=config.client_name
            )
            
            # Log audit event for forwarding
            audit_logger.log_event(
                "agent_request_forwarded",
                {
                    "server": config.server_name,
                    "tool": tool_name,
                    "params": {"file_path": file_path, "redactions_found": has_any_redactions}
                },
                event_id=event_id
            )
            
            # Output success
            reasons = decision.get("reasons", [])
            agent_message = "File read approved: " + "; ".join(reasons) if reasons else "File read approved by security policy"
            output_result(logger, config.output_format, "permission", True, "File read approved", agent_message)
            
        except Exception as e:
            # Decision enforcement failed - block
            error_msg = str(e)
            user_message = "File read blocked by security policy"
            if "User blocked" in error_msg or "User denied" in error_msg:
                user_message = "File read blocked by user"
            
            output_result(logger, config.output_format, "permission", False, user_message, error_msg)
    
    except Exception as e:
        logger.error(f"Unexpected error in read file handler: {e}", exc_info=True)
        output_error(logger, config.output_format, "permission", f"Unexpected error: {str(e)}")

