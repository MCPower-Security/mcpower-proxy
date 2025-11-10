"""
Shared initialization logic for IDE tools

Registers IDE hooks with the security API.
"""

import sys
from typing import Dict, Optional

from mcpower_shared.mcp_types import InitRequest, EnvironmentContext, ServerRef, ToolRef
from modules.apis.security_policy import SecurityPolicyClient
from modules.logs.audit_trail import AuditTrailLogger
from modules.logs.logger import MCPLogger
from modules.utils.ids import get_session_id, read_app_uid, get_project_mcpower_dir
from modules.utils.json import safe_json_dumps
from wrapper.__version__ import __version__


def output_init_result(success: bool, message: str):
    """
    Output init result to stdout
    
    Args:
        success: True if initialization succeeded
        message: Status message
    """
    result = {
        "success": success,
        "message": message
    }

    print(safe_json_dumps(result), flush=True)


async def handle_init(
        logger: MCPLogger,
        audit_logger: AuditTrailLogger,
        event_id: str,
        prompt_id: str,
        cwd: Optional[str],
        server_name: str,
        client_name: str,
        hooks: Dict[str, Dict[str, str]]
) -> None:
    """
    Generic init handler - registers hooks with security API
    
    Args:
        logger: Logger instance
        audit_logger: Audit logger instance
        event_id: Event identifier
        prompt_id: Prompt identifier
        cwd: Current working directory
        server_name: IDE-specific server name (e.g. "cursor_tools_mcp")
        client_name: IDE-specific client name (e.g. "cursor", "claude-code")
        hooks: Dict of hook definitions with {name, description, version}
        
    Outputs result and exits with appropriate code.
    """
    session_id = get_session_id()

    logger.info(f"Init handler started (client={client_name}, event_id={event_id}, prompt_id={prompt_id}, cwd={cwd})")

    try:
        app_uid = read_app_uid(logger, get_project_mcpower_dir(cwd))
        audit_logger.set_app_uid(app_uid)

        audit_logger.log_event(
            "mcpower_start",
            {
                "wrapper_version": __version__,
                "wrapped_server_name": server_name,
                "client": client_name
            }
        )

        try:
            tools = [
                ToolRef(
                    name=hook_info["name"],
                    description=f"Description:\n{hook_info['description']}\n\n"
                                f"inputSchema:\n{hook_info['parameters']}",
                    version=hook_info["version"]
                )
                for hook_info in hooks.values()
            ]

            init_request = InitRequest(
                environment=EnvironmentContext(
                    session_id=session_id,
                    workspace={
                        "roots": [cwd] if cwd else [],
                        "current_files": []
                    },
                    client=client_name,
                    client_version=__version__,
                    selection_hash=""
                ),
                server=ServerRef(
                    name=server_name,
                    transport="stdio",
                    version="1.0.0",
                    context="ide"
                ),
                tools=tools
            )

            async with SecurityPolicyClient(
                    session_id=session_id,
                    logger=logger,
                    audit_logger=audit_logger,
                    app_id=app_uid
            ) as client:
                await client.init_tools(init_request, event_id=event_id)

            logger.info(f"Hooks registered successfully for {client_name}")

            # Success - output result and exit
            output_init_result(True, f"{client_name.title()} hooks registered successfully")
            sys.exit(0)

        except Exception as e:
            logger.error(f"API initialization failed: {e}")
            output_init_result(False, f"Error: {str(e)}")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Unexpected error in init handler: {e}", exc_info=True)
        output_init_result(False, f"Initialization failed: {str(e)}")
        sys.exit(1)
