"""
Cursor IDE Tools Utilities

Common utility functions for Cursor hook handlers.
"""
import asyncio
import json
import re
import sys
from collections import Counter
from typing import Dict, Any, List, Callable, Optional

from ide_tools.cursor.constants import HookPermission, cursor_tools_mcp_name
from mcpower_shared.mcp_types import create_policy_request, create_policy_response, AgentContext, EnvironmentContext
from modules.apis.security_policy import SecurityPolicyClient
from modules.decision_handler import DecisionHandler, DecisionEnforcementError
from modules.logs.audit_trail import AuditTrailLogger
from modules.logs.logger import MCPLogger
from modules.redaction import redact
from modules.utils.json import safe_json_dumps
from wrapper.__version__ import __version__


def create_validator(
        required_fields: Dict[str, type],
        optional_fields: Optional[Dict[str, type]] = None
) -> Callable[[str], Dict[str, Any]]:
    """
    Factory for input validators
    
    Args:
        required_fields: Dict mapping field names to their expected types
        optional_fields: Dict mapping optional field names to their expected types
        
    Returns:
        Validator function that parses and validates input
        
    Example:
        validator = create_validator(
            required_fields={"file_path": str, "content": str},
            optional_fields={"attachments": list}
        )
    """

    def parse_and_validate_input(stdin_input: str) -> Dict[str, Any]:
        try:
            if not stdin_input.strip():
                raise ValueError("No input provided")
            input_data = json.loads(stdin_input)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse input: {e}")

        for field, expected_type in required_fields.items():
            if field not in input_data:
                raise ValueError(f"No {field} provided in input")
            if not isinstance(input_data[field], expected_type):
                raise ValueError(f"{field} must be a {expected_type.__name__}")

        if optional_fields:
            for field, expected_type in optional_fields.items():
                if field in input_data and not isinstance(input_data[field], expected_type):
                    raise ValueError(f"{field} must be a {expected_type.__name__}")

        return input_data

    return parse_and_validate_input


def extract_redaction_patterns(redacted_content: str) -> Dict[str, int]:
    """
    Extract redaction pattern types and their counts from redacted content
    
    Args:
        redacted_content: Content with [REDACTED-type] placeholders
        
    Returns:
        Dict mapping redaction types to counts
    """
    pattern = r'\[REDACTED-([^\]]+)\]'
    matches = re.findall(pattern, redacted_content)
    return dict(Counter(matches))


def process_attachments_for_redaction(
        attachments: List[Dict[str, Any]],
        logger: MCPLogger
) -> tuple[List[Dict[str, Any]], bool]:
    """
    Process file attachments and extract redaction patterns
    
    Args:
        attachments: List of attachment dicts with 'type' and 'file_path' or 'filePath'
        logger: MCPLogger instance
        
    Returns:
        Tuple of (files_with_redactions, has_any_redactions)
        - files_with_redactions: List of {file_path, redactions} dicts
        - has_any_redactions: True if any file had redactions
    """
    files_with_redactions = []

    for attachment in attachments:
        att_type = attachment.get("type")
        att_path = attachment.get("file_path") or attachment.get("filePath")

        if att_type != "file":
            logger.debug(f"Skipping non-file attachment (type={att_type}): {att_path}")
            continue

        if not att_path:
            logger.debug("Skipping attachment with no file_path")
            continue

        try:
            with open(att_path, 'r', encoding='utf-8', errors='replace') as f:
                att_content = f.read()

            redacted_att = redact(att_content)
            att_patterns = extract_redaction_patterns(redacted_att)
            if att_patterns:
                # Build explicit structure showing sensitive data types with occurrence counts
                sensitive_data_types = {}
                for pattern_text, count in att_patterns.items():
                    # Extract type from [REDACTED-TYPE] format
                    data_type = pattern_text.replace("[REDACTED-", "").replace("]", "")
                    sensitive_data_types[data_type] = {
                        "occurrences": count,
                        "description": f"Found {count} instance(s) of {data_type} in file"
                    }

                files_with_redactions.append({
                    "file_path": att_path,
                    "contains_sensitive_data": True,
                    "sensitive_data_types": sensitive_data_types,
                    "risk_summary": f"File contains {sum(att_patterns.values())} sensitive data item(s) across {len(att_patterns)} type(s)"
                })
                logger.info(f"Found {len(att_patterns)} sensitive data type(s) in attachment: {att_path}")

        except Exception as e:
            logger.warning(f"Could not read attachment file {att_path}: {e}")

    has_any_redactions = len(files_with_redactions) > 0
    return files_with_redactions, has_any_redactions


async def inspect_and_enforce(
        is_request: bool,
        session_id: str,
        logger: MCPLogger,
        audit_logger: AuditTrailLogger,
        app_uid: str,
        event_id: str,
        tool_name: str,
        content_data: Dict[str, Any],
        prompt_id: str,
        cwd: Optional[str],
        current_files: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Generic handler for API inspection and decision enforcement
    
    Args:
        is_request: True for request inspection, False for response inspection
        (other params): Context and data for API call
        
    Returns:
        Decision dict from security API
        
    Raises:
        DecisionEnforcementError: If decision blocks the operation
        Exception: If API call fails
    """
    agent_context = AgentContext(
        last_user_prompt="",
        user_prompt_id=prompt_id,
        context_summary=""
    )

    env_context = EnvironmentContext(
        session_id=session_id,
        workspace={
            "roots": [cwd] if cwd else [],
            "current_files": current_files or []
        },
        client="cursor",
        client_version=__version__,
        selection_hash=""
    )

    async with SecurityPolicyClient(
            session_id=session_id,
            logger=logger,
            audit_logger=audit_logger,
            app_id=app_uid
    ) as client:
        if is_request:
            policy_request = create_policy_request(
                event_id=event_id,
                server_name=cursor_tools_mcp_name,
                server_transport="stdio",
                tool_name=tool_name,
                agent_context=agent_context,
                env_context=env_context,
                arguments=content_data
            )
            decision = await client.inspect_policy_request(
                policy_request=policy_request,
                prompt_id=prompt_id
            )
        else:
            policy_response = create_policy_response(
                event_id=event_id,
                server_name=cursor_tools_mcp_name,
                server_transport="stdio",
                tool_name=tool_name,
                response_content=safe_json_dumps(content_data),
                agent_context=agent_context,
                env_context=env_context
            )
            decision = await client.inspect_policy_response(
                policy_response=policy_response,
                prompt_id=prompt_id
            )

    await DecisionHandler(
        logger=logger,
        audit_logger=audit_logger,
        session_id=session_id,
        app_id=app_uid
    ).enforce_decision(
        decision=decision,
        is_request=is_request,
        event_id=event_id,
        tool_name=tool_name,
        content_data=content_data,
        operation_type="hook",
        prompt_id=prompt_id,
        server_name=cursor_tools_mcp_name,
        error_message_prefix=f"Operation blocked by security policy"
    )

    return decision


def call_api_and_output(
        is_request: bool,
        session_id: str,
        logger: MCPLogger,
        audit_logger: AuditTrailLogger,
        app_uid: str,
        event_id: str,
        tool_name: str,
        content_data: Dict[str, Any],
        prompt_id: str,
        cwd: Optional[str],
        audit_forwarded_event_type: str,
        audit_params: Optional[Dict[str, Any]] = None,
        audit_response_content: Optional[Dict[str, Any]] = None,
        operation_name: str = None,
        current_files: Optional[List[str]] = None,
        output_func: Optional[Callable] = None,
        deny_exit_code: int = 1
):
    """
    Call security API, enforce decision, log audit trail, and output result
    
    Args:
        (inspect_and_enforce params): See inspect_and_enforce
        audit_forwarded_event_type: Audit event type for successful forwarding
        audit_params: Params to log in audit trail on success (for requests)
        audit_response_content: Response content to log (for responses)
        operation_name: Human-readable operation name for messages
        current_files: Optional list of current files for context
        output_func: Output function (output_result for permission, output_continue_result for continue)
    """
    if output_func is None:
        output_func = output_permission_result

    if output_func == output_continue_result:
        allow_value = True
        deny_value = False
    else:
        allow_value = HookPermission.ALLOW
        deny_value = HookPermission.DENY

    try:
        decision = asyncio.run(inspect_and_enforce(
            is_request=is_request,
            session_id=session_id,
            logger=logger,
            audit_logger=audit_logger,
            app_uid=app_uid,
            event_id=event_id,
            tool_name=tool_name,
            content_data=content_data,
            prompt_id=prompt_id,
            cwd=cwd,
            current_files=current_files
        ))

        # Use different structure for request vs response events
        # Requests: params nested, Responses: unpacked at root
        if audit_params is not None:
            forwarded_data = {
                "server": cursor_tools_mcp_name,
                "tool": tool_name,
                "params": audit_params
            }
        else:
            # Response: unpack content at root level
            forwarded_data = {
                "server": cursor_tools_mcp_name,
                "tool": tool_name,
                **audit_response_content
            }

        audit_logger.log_event(
            audit_forwarded_event_type,
            forwarded_data,
            event_id=event_id
        )

        reasons = decision.get("reasons", [])
        user_message = f"{operation_name} approved"
        if not reasons:
            agent_message = f"{operation_name} approved by security policy"
        else:
            agent_message = f"{operation_name} approved: {'; '.join(reasons)}"
        output_func(logger, allow_value, user_message, agent_message)

    except DecisionEnforcementError as e:
        error_msg = str(e)
        user_message = f"{operation_name} blocked by security policy"

        if "User blocked" in error_msg or "User denied" in error_msg:
            user_message = f"{operation_name} blocked by user"

        output_func(logger, deny_value, user_message, error_msg)
        sys.exit(deny_exit_code)

    except Exception as e:
        logger.error(f"API inspection failed: {e}")
        output_func(
            logger,
            deny_value,
            f"{operation_name} blocked - security verification failed",
            f"Security API error: {str(e)}"
        )
        sys.exit(deny_exit_code)


def handle_unexpected_error(
        e: Exception,
        logger: MCPLogger,
        handler_name: str,
        operation_name: str,
        exit_code: int = 1,
        output_func: Optional[Callable] = None
):
    """
    Handle unexpected errors in hook handlers with fail-closed behavior
    
    Args:
        e: The exception that was caught
        logger: MCPLogger instance
        handler_name: Name of the handler for logging
        operation_name: Human-readable operation name for user message
        exit_code: Exit code to use on error (default 1)
        output_func: Output function (output_result for permission, output_continue_result for continue)
    """
    if output_func is None:
        output_func = output_permission_result

    if output_func == output_continue_result:
        deny_value = False
    else:
        deny_value = HookPermission.DENY

    logger.error(f"Unexpected error in {handler_name} handler: {e}", exc_info=True)
    output_func(
        logger,
        deny_value,
        f"{operation_name} blocked - unexpected error",
        f"Unexpected error: {str(e)}"
    )
    sys.exit(exit_code)


def output_permission_result(logger: MCPLogger, permission: HookPermission,
                             user_message: str = "", agent_message: str = ""):
    """
    Output result to stdout in Cursor hooks format
    
    Args:
        permission: Hook permission ("allow" or "deny")
        user_message: Optional message to display to the user
        agent_message: Optional message for the agent/logs
    """
    result = {"permission": permission}

    if user_message:
        result["user_message"] = user_message
    if agent_message:
        result["agent_message"] = agent_message

    str_result = safe_json_dumps(result)
    logger.info(f"output_permission_result: {str_result}")

    print(str_result, flush=True)


def output_continue_result(logger: MCPLogger, continue_value: bool, user_message: str = "", agent_message: str = ""):
    """
    Output result for hooks that use continue format (beforeSubmitPrompt)
    
    Args:
        continue_value: Whether to continue (true) or block (false)
        user_message: Optional message to display to the user
        agent_message: Optional message for the agent/logs
    """
    result = {"continue": continue_value}

    if user_message:
        result["user_message"] = user_message
    if agent_message:
        result["agent_message"] = agent_message

    str_result = safe_json_dumps(result)
    logger.info(f"output_continue_result: {str_result}")

    print(str_result, flush=True)
