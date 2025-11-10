"""
Shared logic for UserPromptSubmit hook
"""

from typing import Dict, Any, Optional

from modules.logs.audit_trail import AuditTrailLogger
from modules.logs.logger import MCPLogger
from modules.redaction import redact
from modules.utils.ids import get_session_id, read_app_uid, get_project_mcpower_dir
from modules.utils.string import truncate_at
from .output import output_result, output_error
from .types import HookConfig
from .utils import create_validator, extract_redaction_patterns, process_attachments_for_redaction, inspect_and_enforce


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

        redacted_prompt = redact(prompt)

        audit_logger.log_event(
            "prompt_submission",
            {
                "server": config.server_name,
                "tool": tool_name,
                "params": {"prompt": truncate_at(redacted_prompt, 100), "attachments_count": len(attachments)}
            },
            event_id=event_id,
            prompt_id=prompt_id
        )

        prompt_patterns = extract_redaction_patterns(redacted_prompt)

        # Check for redactions in file attachments
        files_with_redactions = process_attachments_for_redaction(
            attachments,
            logger
        )

        has_any_redactions = bool(prompt_patterns) or len(files_with_redactions) > 0

        content_data: Dict[str, Any] = {
            "prompt": redacted_prompt,
            "is_redacted": has_any_redactions,
            "redacted_files": files_with_redactions,
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
                client_name=config.client_name
            )

            audit_logger.log_event(
                "prompt_submission_forwarded",
                {
                    "server": config.server_name,
                    "tool": tool_name,
                    "params": {"redactions_found": has_any_redactions}
                },
                event_id=event_id,
                prompt_id=prompt_id
            )

            reasons = decision.get("reasons", [])
            agent_message = "Prompt submission approved: {0}".format("; ".join(
                reasons)) if reasons else "Prompt submission approved by security policy"
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
