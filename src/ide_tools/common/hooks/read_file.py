"""
Shared logic for beforeReadFile/PreReadFile hook
"""

from typing import Optional

from modules.logs.audit_trail import AuditTrailLogger
from modules.logs.logger import MCPLogger
from modules.redaction import redact
from modules.utils.ids import get_session_id, read_app_uid, get_project_mcpower_dir
from .output import output_result, output_error
from .types import HookConfig
from .utils import create_validator, process_attachments_for_redaction, inspect_and_enforce


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
    logger.info(
        f"Read file handler started (client={config.client_name}, prompt_id={prompt_id}, event_id={event_id}, cwd={cwd})")

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
            output_error(logger, config.output_format, "permission", str(e))
            return

        audit_logger.log_event(
            "agent_request",
            {
                "server": config.server_name,
                "tool": tool_name,
                "params": {"file_path": file_path, "attachments_count": len(attachments)}
            },
            event_id=event_id,
            prompt_id=prompt_id
        )

        # Check content length - skip API if too large
        if len(provided_content) > config.max_content_length:
            logger.info(f"Content length ({len(provided_content)} chars) exceeds max ({config.max_content_length}) - "
                        f"skipping API call")

            audit_logger.log_event(
                "agent_request_forwarded",
                {
                    "server": config.server_name,
                    "tool": tool_name,
                    "params": {
                        "file_path": file_path,
                        "content_length": len(provided_content),
                        "content_too_large": True
                    }
                },
                event_id=event_id,
                prompt_id=prompt_id
            )

            output_result(logger, config.output_format, "permission", True)
            return

        # Redact the main content
        redacted_content = redact(provided_content)

        # Process attachments for redaction status
        files_with_redactions = process_attachments_for_redaction(attachments, logger)
        files_with_redactions_paths = {f["file_path"] for f in files_with_redactions}

        # Build attachments info with redaction status
        attachments_info = []
        for attachment in attachments:
            att_path = attachment.get("file_path") or attachment.get("filePath")
            if att_path:
                attachments_info.append({
                    "file_path": att_path,
                    "has_redactions": att_path in files_with_redactions_paths
                })

        logger.info(f"Processed file and {len(attachments)} attachment(s), found redactions in "
                    f"{len(files_with_redactions)} attachment(s)")

        # Build content_data with file_path, redacted content, and attachments
        content_data = {
            "file_path": file_path,
            "content": redacted_content,
            "attachments": attachments_info
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

            audit_logger.log_event(
                "agent_request_forwarded",
                {
                    "server": config.server_name,
                    "tool": tool_name,
                    "params": {
                        "file_path": file_path,
                        "content_length": len(provided_content),
                        "attachments_with_redactions": len(files_with_redactions)}
                },
                event_id=event_id,
                prompt_id=prompt_id
            )

            reasons = decision.get("reasons", [])
            agent_message = "File read approved: " + "; ".join(
                reasons) if reasons else "File read approved by security policy"
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
