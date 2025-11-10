"""
Common shell execution handler - IDE-agnostic

Handles both request (before) and response (after) inspection for shell commands.
"""

import os
from typing import Optional, Dict, List

from modules.logs.audit_trail import AuditTrailLogger
from modules.logs.logger import MCPLogger
from modules.redaction import redact
from modules.utils.ids import get_session_id, read_app_uid, get_project_mcpower_dir
from .output import output_result, output_error
from .shell_parser_bashlex import parse_shell_command
from .types import HookConfig
from .utils import create_validator, inspect_and_enforce


def extract_and_redact_command_files(
        command: str,
        cwd: str,
        logger: MCPLogger
) -> Dict[str, str]:
    """
    Extract input files from a shell command and return their redacted contents.

    Args:
        command: The shell command to parse
        cwd: Current working directory (for resolving relative paths)
        logger: Logger instance for warnings/errors

    Returns:
        Dictionary mapping filename to redacted file content
        Format: {filename: redacted_content}
    """
    files_dict = {}

    try:
        # Parse command to extract input files
        _, input_files = parse_shell_command(command, initial_cwd=cwd)

        logger.info(f"Extracted {len(input_files)} input files from command: {input_files}")

        # Process each file
        for filename in input_files:
            try:
                # Resolve absolute path
                if os.path.isabs(filename):
                    filepath = filename
                elif cwd:
                    filepath = os.path.join(cwd, filename)
                else:
                    filepath = filename

                # Read file content
                if os.path.exists(filepath) and os.path.isfile(filepath):
                    try:
                        # Check file size
                        file_size = os.path.getsize(filepath)
                        logger.info(f"File {filename} size: {file_size} bytes")

                        # Check if file is binary by reading first 8KB
                        is_binary = False
                        try:
                            with open(filepath, 'rb') as f:
                                chunk = f.read(8192)
                                # Check for null bytes (common in binary files)
                                if b'\x00' in chunk:
                                    is_binary = True
                        except Exception as e:
                            logger.warning(f"Failed to check if file {filename} is binary: {e}")
                            continue

                        if is_binary:
                            logger.warning(f"File {filename} is binary, skipping")
                            continue

                        # Read text file with 100K character limit
                        MAX_CHARS = 100_000
                        with open(filepath, 'r', encoding='utf-8') as f:
                            content = f.read(MAX_CHARS)

                            # Check if file was truncated
                            if len(content) == MAX_CHARS:
                                # Check if there's more content
                                next_char = f.read(1)
                                if next_char:
                                    logger.warning(f"File {filename} truncated to {MAX_CHARS} characters")
                                    content += f"\n... [file truncated at {MAX_CHARS} characters]"

                        # Redact sensitive content
                        redacted_content = redact(content)

                        # Add to dict (use original filename, not resolved path)
                        files_dict[filename] = redacted_content
                        logger.info(f"Successfully read and redacted file: {filename} ({len(content)} characters)")

                    except UnicodeDecodeError:
                        logger.warning(f"File {filename} is not a text file, skipping")
                    except Exception as e:
                        logger.warning(f"Failed to read file {filename}: {e}")
                else:
                    logger.warning(f"File {filename} does not exist or is not a file, skipping")

            except Exception as e:
                logger.warning(f"Error processing file {filename}: {e}")

    except Exception as e:
        logger.warning(f"Failed to parse command for file extraction: {e}")

    return files_dict


async def handle_shell_execution(
        logger: MCPLogger,
        audit_logger: AuditTrailLogger,
        stdin_input: str,
        prompt_id: str,
        event_id: str,
        cwd: Optional[str],
        config: HookConfig,
        tool_name: str,
        is_request: bool = True
):
    """
    Generic shell execution handler - handles both request and response
    
    Args:
        logger: Logger instance
        audit_logger: Audit logger instance
        stdin_input: Raw input string from stdin
        prompt_id: Prompt identifier
        event_id: Event identifier
        cwd: Current working directory
        config: Hook configuration (IDE-specific)
        tool_name: IDE-specific tool name (e.g., "beforeShellExecution", "PreToolUse(Bash)")
        is_request: True for before (request), False for after (response)
    """
    await _handle_shell_operation(
        logger=logger,
        audit_logger=audit_logger,
        stdin_input=stdin_input,
        prompt_id=prompt_id,
        event_id=event_id,
        cwd=cwd,
        config=config,
        is_request=is_request,
        required_fields={"command": str, "cwd": str} if is_request else {"command": str, "output": str},
        redact_fields=["command"] if is_request else ["command", "output"],
        tool_name=tool_name,
        operation_name="Command" if is_request else "Command output",
        audit_event_type="agent_request" if is_request else "mcp_response",
        audit_forwarded_event_type="agent_request_forwarded" if is_request else "mcp_response_forwarded"
    )


async def _handle_shell_operation(
        logger: MCPLogger,
        audit_logger: AuditTrailLogger,
        stdin_input: str,
        prompt_id: str,
        event_id: str,
        cwd: Optional[str],
        config: HookConfig,
        is_request: bool,
        required_fields: Dict[str, type],
        redact_fields: List[str],
        tool_name: str,
        operation_name: str,
        audit_event_type: str,
        audit_forwarded_event_type: str
):
    """
    Internal shell operation handler - shared logic for request and response
    
    Args:
        is_request: True for request inspection, False for response inspection
        required_fields: Fields to validate in input
        redact_fields: Fields to redact for logging and API calls
        tool_name: Hook name (e.g., "beforeShellExecution", "afterShellExecution")
        operation_name: Display name (e.g., "Command", "Command output")
        audit_event_type: Audit event name for incoming operation
        audit_forwarded_event_type: Audit event name for forwarded operation
    """
    session_id = get_session_id()

    logger.info(
        f"{tool_name} handler started (client={config.client_name}, prompt_id={prompt_id}, "
        f"event_id={event_id}, cwd={cwd})")

    try:
        try:
            validator = create_validator(required_fields=required_fields)
            input_data = validator(stdin_input)
        except ValueError as e:
            logger.error(f"Input validation error: {e}")
            output_error(logger, config.output_format, "permission", str(e))
            return

        app_uid = read_app_uid(logger, get_project_mcpower_dir(cwd))
        audit_logger.set_app_uid(app_uid)

        redacted_data = {}
        for k, v in input_data.items():
            if k in required_fields:
                redacted_data[k] = redact(v) if k in redact_fields else v

        # Extract and redact input files for request inspection
        files_dict = {}
        if is_request and "command" in input_data:
            input_command = input_data["command"]
            input_command_cws = input_data["cwd"]
            files_dict = extract_and_redact_command_files(command=input_command, cwd=input_command_cws, logger=logger)
            if files_dict:
                logger.info(f"Extracted and redacted {len(files_dict)} files from command")

        def get_audit_data():
            # Use different structure for request vs response events
            # Requests: params nested, Responses: unpacked at root
            if is_request:
                return {
                    "server": config.server_name,
                    "tool": tool_name,
                    "params": redacted_data,
                    "files": list(files_dict.keys()) if files_dict else None
                }
            else:
                return {
                    "server": config.server_name,
                    "tool": tool_name,
                    **redacted_data
                }

        audit_logger.log_event(
            audit_event_type,
            get_audit_data(),
            event_id=event_id,
            prompt_id=prompt_id
        )

        # Build content_data with redacted fields and files
        content_data = redacted_data.copy()
        if files_dict:
            content_data["files"] = files_dict

        try:
            decision = await inspect_and_enforce(
                is_request=is_request,
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
                audit_forwarded_event_type,
                get_audit_data(),
                event_id=event_id,
                prompt_id=prompt_id
            )

            reasons = decision.get("reasons", [])
            user_message = f"{operation_name} approved"
            if not reasons:
                agent_message = f"{operation_name} approved by security policy"
            else:
                agent_message = f"{operation_name} approved: {'; '.join(reasons)}"
            output_result(logger, config.output_format, "permission", True, user_message, agent_message)

        except Exception as e:
            # Decision enforcement failed - block
            error_msg = str(e)
            user_message = f"{operation_name} blocked by security policy"
            if "User blocked" in error_msg or "User denied" in error_msg:
                user_message = f"{operation_name} blocked by user"

            output_result(logger, config.output_format, "permission", False, user_message, error_msg)

    except Exception as e:
        logger.error(f"Unexpected error in {tool_name} handler: {e}", exc_info=True)
        output_error(logger, config.output_format, "permission", f"Unexpected error: {str(e)}")
