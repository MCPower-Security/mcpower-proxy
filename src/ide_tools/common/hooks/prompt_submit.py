"""
Shared logic for UserPromptSubmit hook
"""

from typing import Dict, Any, Optional

from modules.logs.audit_trail import AuditTrailLogger
from modules.logs.logger import MCPLogger
from modules.redaction import redact
from modules.utils.ids import get_session_id, read_app_uid, get_project_mcpower_dir
from .output import output_result, output_error
from .types import HookConfig
from .utils import create_validator, extract_redaction_patterns, build_sensitive_data_types, \
    process_attachments_for_redaction, inspect_and_enforce


async def handle_prompt_submit(
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
    Shared handler for prompt submission hooks
    
    Args:
        logger: Logger instance
        audit_logger: Audit logger instance
        stdin_input: Raw JSON input
        prompt_id: Prompt/conversation ID
        event_id: Event/generation ID
        cwd: Current working directory
        config: IDE-specific hook configuration
        tool_name: IDE-specific tool name (e.g., "beforeSubmitPrompt", "UserPromptSubmit")
    """
    session_id = get_session_id()
    logger.info(
        f"Prompt submit handler started (client={config.client_name}, prompt_id={prompt_id}, "
        f"event_id={event_id}, cwd={cwd})")

    app_uid = read_app_uid(logger, get_project_mcpower_dir(cwd))
    audit_logger.set_app_uid(app_uid)

    try:
        # Validate input
        try:
            validator = create_validator(
                required_fields={"prompt": str},
                optional_fields={"attachments": list}
            )
            input_data = validator(stdin_input)
            prompt = input_data["prompt"]
            attachments = input_data.get("attachments", [])
        except ValueError as e:
            logger.error(f"Input validation error: {e}")
            output_error(logger, config.output_format, "continue", str(e))
            return

        # Check for redactions in prompt
        redacted_prompt = redact(prompt)
        # Log audit event
        audit_logger.log_event(
            "prompt_submission",
            {
                "server": config.server_name,
                "tool": tool_name,
                "params": {"prompt": f"{redacted_prompt[:20]}...", "attachments_count": len(attachments)}
            },
            event_id=event_id
        )

        prompt_patterns = extract_redaction_patterns(redacted_prompt)

        # Check for redactions in file attachments
        files_with_redactions = process_attachments_for_redaction(
            attachments,
            logger
        )

        has_any_redactions = bool(prompt_patterns) or len(files_with_redactions) > 0

        # If no redactions found, allow immediately without API call
        if not has_any_redactions:
            logger.info("No sensitive data found in prompt or attachments - allowing without API call")

            audit_logger.log_event(
                "prompt_submission_forwarded",
                {
                    "server": config.server_name,
                    "tool": tool_name,
                    "params": {"redactions_found": has_any_redactions}
                },
                event_id=event_id
            )

            output_result(logger, config.output_format, "continue", True)
            return

        logger.info(f"Found redactions in prompt or {len(files_with_redactions)} file(s) - calling API for inspection")

        # Build explicit content_data structure showing security risk
        content_data: Dict[str, Any] = {
            "security_alert": "Sensitive data detected in user prompt submission"
        }

        # Add prompt analysis if sensitive data found in prompt text
        if prompt_patterns:
            sensitive_data_types = build_sensitive_data_types(prompt_patterns, "prompt text")

            total_prompt_items = sum(prompt_patterns.values())
            content_data["user_prompt_analysis"] = {
                "contains_sensitive_data": True,
                "sensitive_data_types": sensitive_data_types,
                "risk_summary": f"Prompt contains {total_prompt_items} sensitive data item(s) across {len(prompt_patterns)} type(s)"
            }

        # Add file analysis if sensitive data found in attachments
        if files_with_redactions:
            total_file_items = sum(
                sum(f["sensitive_data_types"][dt]["occurrences"] for dt in f["sensitive_data_types"])
                for f in files_with_redactions
            )
            content_data["attached_files_with_secrets_or_pii"] = files_with_redactions
            content_data["files_summary"] = \
                f"{len(files_with_redactions)} file(s) contain {total_file_items} sensitive data item(s)"

        # Calculate overall risk level
        total_sensitive_items = sum(prompt_patterns.values()) if prompt_patterns else 0
        if files_with_redactions:
            total_sensitive_items += sum(
                sum(f["sensitive_data_types"][dt]["occurrences"] for dt in f["sensitive_data_types"])
                for f in files_with_redactions
            )
        content_data["overall_summary"] = f"Total: {total_sensitive_items} sensitive data item(s) detected"

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
                client_name=config.client_name
            )

            # Log audit event for forwarding
            audit_logger.log_event(
                "prompt_submission_forwarded",
                {
                    "server": config.server_name,
                    "tool": tool_name,
                    "params": {"redactions_found": has_any_redactions}
                },
                event_id=event_id
            )

            # Output success
            reasons = decision.get("reasons", [])
            agent_message = "Prompt submission approved: " + "; ".join(
                reasons) if reasons else "Prompt submission approved by security policy"
            output_result(logger, config.output_format, "continue", True,
                          "Prompt approved", agent_message)

        except Exception as e:
            # Decision enforcement failed - block
            error_msg = str(e)
            user_message = "Prompt blocked by security policy"
            if "User blocked" in error_msg or "User denied" in error_msg:
                user_message = "Prompt blocked by user"

            output_result(logger, config.output_format, "continue", False, user_message, error_msg)

    except Exception as e:
        logger.error(f"Unexpected error in prompt submit handler: {e}", exc_info=True)
        output_error(logger, config.output_format, "continue", f"Unexpected error: {str(e)}")
