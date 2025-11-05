"""
Cursor beforeSubmitPrompt Handler

Processes prompt submissions from Cursor's beforeSubmitPrompt hook.
Checks for redactions in prompt and file attachments, only calls API if redactions found.
"""

import sys
from typing import Optional, Dict, Any

from modules.logs.logger import MCPLogger
from modules.redaction import redact
from modules.utils.ids import get_session_id, read_app_uid, get_project_mcpower_dir
from .constants import cursor_tools_mcp_name
from .utils import (
    output_continue_result, create_validator, call_api_and_output,
    handle_unexpected_error, extract_redaction_patterns, process_attachments_for_redaction
)

tool_name = "beforeSubmitPrompt"


def main(logger: MCPLogger, audit_logger, stdin_input: str, prompt_id: str, event_id: str, cwd: Optional[str]):
    """
    Main entry point for beforeSubmitPrompt handler
    
    Args:
        logger: MCPLogger instance
        audit_logger: AuditTrailLogger instance
        stdin_input: Raw input string from stdin
        prompt_id: Prompt ID from conversation_id
        event_id: Event ID from generation_id
        cwd: Optional, current working directory from workspace_roots[0]
    """
    session_id = get_session_id()

    logger.info(f"beforeSubmitPrompt handler started (prompt_id={prompt_id}, event_id={event_id}, cwd={cwd})")

    app_uid = read_app_uid(logger, get_project_mcpower_dir(cwd))
    audit_logger.set_app_uid(app_uid)

    try:
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
            error_message = str(e)
            output_continue_result(logger, False, error_message, error_message)
            sys.exit(1)

        audit_logger.log_event(
            "prompt_submission",
            {
                "server": cursor_tools_mcp_name,
                "tool": tool_name,
                "params": {"attachments_count": len(attachments)}
            },
            event_id=event_id
        )

        # Check for redactions in prompt
        redacted_prompt = redact(prompt)
        prompt_patterns = extract_redaction_patterns(redacted_prompt)

        # Check for redactions in file attachments
        files_with_redactions, files_have_redactions = process_attachments_for_redaction(
            attachments,
            logger
        )

        has_any_redactions = bool(prompt_patterns) or files_have_redactions

        # If no redactions found, allow immediately without API call
        if not has_any_redactions:
            logger.info("No sensitive data found in prompt or attachments - allowing without API call")

            audit_logger.log_event(
                "prompt_submission_forwarded",
                {
                    "server": cursor_tools_mcp_name,
                    "tool": tool_name,
                    "params": {"redactions_found": has_any_redactions}
                },
                event_id=event_id
            )

            output_continue_result(logger, True)
            sys.exit(0)

        logger.info(f"Found redactions in prompt or {len(files_with_redactions)} file(s) - calling API for inspection")

        # Build explicit content_data structure showing security risk
        content_data: Dict[str, Any] = {
            "security_alert": "Sensitive data detected in user prompt submission"
        }

        # Add prompt analysis if sensitive data found in prompt text
        if prompt_patterns:
            sensitive_data_types = {}
            for pattern_text, count in prompt_patterns.items():
                # Extract type from [REDACTED-TYPE] format
                data_type = pattern_text.replace("[REDACTED-", "").replace("]", "")
                sensitive_data_types[data_type] = {
                    "occurrences": count,
                    "description": f"Found {count} instance(s) of {data_type} in prompt text"
                }

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
            content_data[
                "files_summary"] = f"{len(files_with_redactions)} file(s) contain {total_file_items} sensitive data item(s)"

        # Calculate overall risk level
        total_sensitive_items = sum(prompt_patterns.values()) if prompt_patterns else 0
        if files_with_redactions:
            total_sensitive_items += sum(
                sum(f["sensitive_data_types"][dt]["occurrences"] for dt in f["sensitive_data_types"])
                for f in files_with_redactions
            )
        content_data["overall_summary"] = f"Total: {total_sensitive_items} sensitive data item(s) detected"

        call_api_and_output(
            is_request=True,
            session_id=session_id,
            logger=logger,
            audit_logger=audit_logger,
            app_uid=app_uid,
            event_id=event_id,
            tool_name=tool_name,
            content_data=content_data,
            prompt_id=prompt_id,
            cwd=cwd,
            audit_forwarded_event_type="prompt_submission_forwarded",
            audit_params={"redactions_found": has_any_redactions},
            operation_name="Prompt submission",
            output_func=output_continue_result
        )

    except Exception as e:
        handle_unexpected_error(
            e, logger, "beforeSubmitPrompt", "Prompt submission",
            output_func=output_continue_result
        )
