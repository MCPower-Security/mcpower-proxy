"""
Common utilities for IDE hooks - IDE-agnostic
"""

import json
import re
from collections import Counter
from typing import Dict, Any, List, Callable, Optional

from mcpower_shared.mcp_types import create_policy_request, create_policy_response, AgentContext, EnvironmentContext, \
    ServerRef, ToolRef
from modules.apis.security_policy import SecurityPolicyClient
from modules.decision_handler import DecisionHandler
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


def build_sensitive_data_types(patterns: Dict[str, int], context: str = "file") -> Dict[str, Dict[str, Any]]:
    """
    Convert redaction patterns to structured sensitive_data_types dict
    
    Args:
        patterns: Dict mapping pattern text to occurrence counts (from extract_redaction_patterns)
        context: Context string for description (e.g., "file", "prompt text")
        
    Returns:
        Dict mapping data types to occurrence info with descriptions
    """
    sensitive_data_types = {}
    for pattern_text, count in patterns.items():
        data_type = pattern_text.replace("[REDACTED-", "").replace("]", "")
        sensitive_data_types[data_type] = {
            "occurrences": count,
            "description": f"Found {count} instance(s) of {data_type} in {context}"
        }
    return sensitive_data_types


def process_single_file_for_redaction(
        file_path: str,
        content: str,
        logger: MCPLogger
) -> Optional[Dict[str, Any]]:
    """
    Process a single file's content for redaction patterns
    
    Args:
        file_path: Path to the file being processed
        content: File content to check for redactions
        logger: MCPLogger instance
        
    Returns:
        Dict with redaction info if sensitive data found, None otherwise
    """
    redacted = redact(content)
    patterns = extract_redaction_patterns(redacted)
    if patterns:
        sensitive_data_types = build_sensitive_data_types(patterns, "file")
        logger.info(f"Found {len(patterns)} sensitive data type(s) in: {file_path}")
        return {
            "file_path": file_path,
            "contains_sensitive_data": True,
            "sensitive_data_types": sensitive_data_types,
            "risk_summary": f"File contains {sum(patterns.values())} sensitive data item(s) across {len(patterns)} type(s)"
        }
    return None


def process_attachments_for_redaction(
        attachments: List[Dict[str, Any]],
        logger: MCPLogger
) -> List[Dict[str, Any]]:
    """
    Process file attachments and extract redaction patterns
    
    Args:
        attachments: List of attachment dicts with 'type' and 'file_path' or 'filePath'
        logger: MCPLogger instance
        
    Returns:
        List of files with redactions found
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
                content = f.read()

            result = process_single_file_for_redaction(att_path, content, logger)
            if result:
                files_with_redactions.append(result)

        except Exception as e:
            logger.warning(f"Could not read attachment file {att_path}: {e}")

    return files_with_redactions


async def inspect_and_enforce(
        is_request: bool,
        session_id: str,
        logger: MCPLogger,
        audit_logger: AuditTrailLogger,
        app_uid: str,
        event_id: str,
        server_name: str,
        tool_name: str,
        content_data: Dict[str, Any],
        prompt_id: str,
        cwd: Optional[str],
        current_files: Optional[List[str]] = None,
        client_name: str = "ide-tools"
) -> Dict[str, Any]:
    """
    Generic handler for API inspection and decision enforcement
    
    Args:
        is_request: True for request inspection, False for response inspection
        session_id: Session identifier
        logger: Logger instance
        audit_logger: Audit logger instance
        app_uid: Application UID
        event_id: Event identifier
        server_name: Server name (IDE-specific, e.g. "cursor_tools_mcp")
        tool_name: Tool/hook name
        content_data: Data to inspect
        prompt_id: Prompt identifier
        cwd: Current working directory
        current_files: Optional list of current files
        client_name: Client name (e.g. "cursor", "claude-code")
        
    Returns:
        Decision dict from security API
        
    Raises:
        Exception: If decision blocks the operation or API call fails
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
        client=client_name,
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
                server=ServerRef(
                    name=server_name,
                    transport="stdio",
                    context="ide"
                ),
                tool=ToolRef(
                    name=tool_name
                ),
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
                server=ServerRef(
                    name=server_name,
                    transport="stdio",
                    context="ide"
                ),
                tool=ToolRef(
                    name=tool_name
                ),
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
        server_name=server_name,
        error_message_prefix=f"Operation blocked by security policy"
    )

    return decision
