"""
FastMCP middleware for security policy enforcement
Implements pre/post interception for all MCP operations
"""
import asyncio
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastmcp.exceptions import FastMCPError
from fastmcp.server.middleware.middleware import Middleware, MiddlewareContext, CallNext
from fastmcp.server.proxy import ProxyClient
from httpx import HTTPStatusError
from mcp import ErrorData

from mcpower_shared.mcp_types import (create_policy_request, create_policy_response, AgentContext, EnvironmentContext,
                                      InitRequest,
                                      ServerRef, ToolRef)
from modules.apis.security_policy import SecurityPolicyClient
from modules.decision_handler import DecisionHandler, DecisionEnforcementError
from modules.logs.audit_trail import AuditTrailLogger
from modules.logs.logger import MCPLogger
from modules.redaction import redact
from modules.utils.copy import safe_copy
from modules.utils.ids import generate_event_id, get_session_id, read_app_uid, get_project_mcpower_dir
from modules.utils.json import safe_json_dumps, to_dict
from modules.utils.mcp_configs import extract_wrapped_server_info
from modules.utils.platform import get_client_os
from modules.utils.string import truncate_at
from wrapper.schema import merge_input_schema_with_existing


class MockContext:
    """Mock context for internal operations"""

    def __init__(self, method: str, message_args: Dict[str, Any]):
        self.method = method
        self.timestamp = datetime.now(timezone.utc)
        self.message = type('MockMessage', (), {'arguments': message_args})()

    def copy(self, **kwargs):
        message = kwargs.get('message')
        if message is not None:
            # Create new context with updated message
            new_context = MockContext(self.method, {})
            new_context.message = message
            new_context.timestamp = self.timestamp
            return new_context
        else:
            # Create exact copy
            return MockContext(self.method, self.message.arguments)


class SecurityMiddleware(Middleware):
    """FastMCP middleware for security policy enforcement"""

    _TOOLS_INIT_DEBOUNCE_SECONDS = 60

    def __init__(self,
                 wrapped_server_configs: dict,
                 wrapper_server_name: str,
                 wrapper_server_version: str,
                 logger: MCPLogger,
                 audit_logger: AuditTrailLogger):
        self.wrapped_server_configs = wrapped_server_configs
        self.wrapper_server_name = wrapper_server_name
        self.wrapper_server_version = wrapper_server_version
        self.session_id = get_session_id()
        self.logger = logger
        self.audit_logger = audit_logger
        self.app_id = ""
        self._last_workspace_root = None
        self._last_tools_init_time: Optional[float] = None
        self._tools_list_in_progress: Optional[asyncio.Task] = None
        self._tools_list_lock = asyncio.Lock()

        self.wrapped_server_name, self.wrapped_server_transport = (
            extract_wrapped_server_info(self.wrapper_server_name, self.logger, self.wrapped_server_configs)
        )

        self.logger.info(
            f"SecurityMiddleware initialized: "
            f"wrapper_server_name={wrapper_server_name}, "
            f"wrapper_server_version={wrapper_server_version}, "
            f"wrapped_server_name={self.wrapped_server_name}, "
            f"wrapped_server_transport={self.wrapped_server_transport}, "
            f"session_id={self.session_id}")

    async def on_message(self, context: MiddlewareContext, call_next: CallNext) -> Any:
        self.logger.info(f"on_message: {redact(safe_json_dumps(context))}")

        # Skip workspace check for `initialize` calls to avoid premature app_uid changes.
        # The `initialize` request doesn't contain workspace data, so checking it would
        # cause unnecessary audit log flushes before the actual workspace init arrives.
        if context.method != "initialize":
            # Check workspace roots and re-initialize app_uid if workspace changed
            workspace_roots = await self._extract_workspace_roots(context)
            current_workspace_root = get_project_mcpower_dir(workspace_roots[0] if workspace_roots else None)
            if current_workspace_root != self._last_workspace_root:
                self.logger.debug(
                    f"Workspace root changed from {self._last_workspace_root} to {current_workspace_root}")
                self._last_workspace_root = current_workspace_root
                self.app_id = read_app_uid(logger=self.logger, project_folder_path=current_workspace_root)
                self.audit_logger.set_app_uid(self.app_id)

        operation_type = "message"

        async def call_next_wrapper(ctx):
            try:
                return await call_next(ctx)
            except HTTPStatusError as e:
                if e.response.status_code in (401, 403):
                    raise FastMCPError(ErrorData(
                        code=-32000,
                        message="Authentication required",
                        data={
                            "type": "unauthorized",
                            "details": "Please provide valid authentication credentials"
                        }
                    ))
                raise e

        match context.type:
            case "request":
                operation_type = "request"
            case "notification":
                operation_type = "notification"

        match context.method:
            case "tools/call":
                operation_type = "tool"
            case "resources/read":
                operation_type = "resource"
            case "prompts/get":
                operation_type = "prompt"
            case "tools/list":
                # Special handling for tools/list - call /init instead of normal inspection
                return await self._handle_tools_list(context, call_next_wrapper)
            case "initialize" | "resources/list" | "resources/templates/list" | "prompts/list":
                return await call_next_wrapper(context)

        return await self._handle_operation(
            context=context,
            call_next=call_next_wrapper,
            error_class=FastMCPError,
            operation_type=operation_type
        )

    async def secure_sampling_handler(self, messages, params, context):
        self.logger.info(f"secure_sampling_handler: "
                         f"messages={len(messages) if messages else 0}, params={params}, context={context}")

        mock_context = MockContext(
            method='sampling/create_message',
            message_args={
                'messages': [msg.model_dump() if hasattr(msg, 'model_dump')
                             else str(msg) for msg in (messages or [])],
                'params': params.model_dump() if hasattr(params, 'model_dump') else str(params)
            }
        )

        async def sampling_call_next(ctx):
            return await ProxyClient.default_sampling_handler(messages, params, context)

        return await self._handle_operation(
            context=mock_context,
            call_next=sampling_call_next,
            error_class=FastMCPError,
            operation_type="sampling"
        )

    async def secure_elicitation_handler(self, message, response_type, params, context):
        # FIXME: elicitation message, params, and context should be redacted before logging
        self.logger.info(f"secure_elicitation_handler: "
                         f"message={truncate_at(str(message), 100)}, response_type={response_type},"
                         f"params={params}, context={context}")

        mock_context = MockContext(
            method='elicitation/request',
            message_args={
                'message': message,
                'response_type': str(response_type),
                'params': params.model_dump() if hasattr(params, 'model_dump') else str(params)
            }
        )

        async def elicitation_call_next(ctx):
            return await ProxyClient.default_elicitation_handler(message, response_type, params, context)

        return await self._handle_operation(
            context=mock_context,
            call_next=elicitation_call_next,
            error_class=FastMCPError,
            operation_type="elicitation"
        )

    async def secure_progress_handler(self, progress, total=None, message=None):
        self.logger.info(f"secure_progress_handler: progress={progress}, total={total}, message={message}")

        # Progress notifications are usually safe to forward
        return await ProxyClient.default_progress_handler(progress, total, message)

    async def secure_log_handler(self, log_message):
        # FIXME: log_message should be redacted before logging,
        self.logger.info(f"secure_log_handler: {truncate_at(str(log_message), 100)}")
        # FIXME: log_message should be reviewed with policy before forwarding

        # Handle case where log_message.data is a string instead of dict
        # The default_log_handler expects data to be a dict with 'msg' and 'extra' keys
        if hasattr(log_message, 'data') and isinstance(log_message.data, str):
            log_message = safe_copy(log_message, {'data': {'msg': log_message.data, 'extra': None}})

        return await ProxyClient.default_log_handler(log_message)

    async def _handle_operation(self, context: MiddlewareContext, call_next, error_class, operation_type: str):
        """Handle MCP operations with security enforcement"""
        on_handle_operation_start_time = time.time()
        event_id = generate_event_id()
        wrapper_args, tool_args, cleaned_context = self._split_context_arguments(context)
        tool_name = self._extract_tool_name_from_context(context)
        prompt_id = wrapper_args.get('__wrapper_userPromptId')
        user_prompt = wrapper_args.get('__wrapper_userPrompt')

        self.audit_logger.log_event(
            "agent_request",
            {
                "server": self.wrapped_server_name,
                "tool": tool_name,
                "params": tool_args
            },
            event_id=event_id,
            prompt_id=prompt_id,
            user_prompt=user_prompt  # only included in the first request per call
        )

        on_inspect_request_start_time = time.time()
        request_decision = await self._inspect_request(
            event_id=event_id,
            context=context,
            wrapper_args=wrapper_args,
            tool_args=tool_args,
            prompt_id=prompt_id
        )
        on_inspect_request_duration = time.time() - on_inspect_request_start_time
        self.logger.debug(
            f"PROFILE: {operation_type} id: {event_id} inspect_request duration: {on_inspect_request_duration:.2f} seconds")

        try:
            await DecisionHandler(
                logger=self.logger,
                audit_logger=self.audit_logger,
                session_id=self.session_id,
                app_id=self.app_id
            ).enforce_decision(
                decision=request_decision,
                is_request=True,
                event_id=event_id,
                tool_name=tool_name,
                content_data=tool_args,
                operation_type=operation_type,
                prompt_id=prompt_id,
                server_name=self.wrapped_server_name,
                error_message_prefix=f"{operation_type.title()} request blocked by security policy"
            )
        except DecisionEnforcementError as e:
            raise error_class(str(e))

        self.audit_logger.log_event(
            "agent_request_forwarded",
            {
                "server": self.wrapped_server_name,
                "tool": tool_name,
                "params": tool_args
            },
            event_id=event_id,
            prompt_id=prompt_id
        )

        on_call_next_start_time = time.time()
        # Call wrapped MCP with cleaned context (e.g., no wrapper args)
        result = await call_next(cleaned_context)
        on_call_next_duration = time.time() - on_call_next_start_time
        self.logger.debug(
            f"PROFILE: {operation_type} id: {event_id} call_next duration: {on_call_next_duration:.2f} seconds")

        response_content = self._extract_response_content(result)

        self.audit_logger.log_event(
            "mcp_response",
            {
                "server": self.wrapped_server_name,
                "tool": tool_name,
                **response_content
            },
            event_id=event_id,
            prompt_id=prompt_id
        )

        on_inspect_response_start_time = time.time()
        response_decision = await self._inspect_response(
            event_id=event_id,
            context=context,
            wrapper_args=wrapper_args,
            tool_args=tool_args,
            result=result,
            prompt_id=prompt_id
        )
        on_inspect_response_duration = time.time() - on_inspect_response_start_time
        self.logger.debug(
            f"PROFILE: {operation_type} id: {event_id} inspect_response duration: {on_inspect_response_duration:.2f} seconds")

        try:
            await DecisionHandler(
                logger=self.logger,
                audit_logger=self.audit_logger,
                session_id=self.session_id,
                app_id=self.app_id
            ).enforce_decision(
                decision=response_decision,
                is_request=False,
                event_id=event_id,
                tool_name=tool_name,
                content_data=response_content,
                operation_type=operation_type,
                prompt_id=prompt_id,
                server_name=self.wrapped_server_name,
                error_message_prefix=f"{operation_type.title()} response blocked by security policy"
            )
        except DecisionEnforcementError as e:
            raise error_class(str(e))

        self.audit_logger.log_event(
            "mcp_response_forwarded",
            {
                "server": self.wrapped_server_name,
                "tool": tool_name,
                **response_content
            },
            event_id=event_id,
            prompt_id=prompt_id
        )
        on_handle_operation_duration = time.time() - on_handle_operation_start_time
        self.logger.debug(
            f"PROFILE: {operation_type} id: {event_id} duration: {on_handle_operation_duration:.2f} seconds")
        return result

    async def _handle_tools_list(self, context: MiddlewareContext, call_next: CallNext) -> Any:
        """Handle tools/list by calling /init API and modifying schemas with deduplication"""
        event_id = generate_event_id()
        on_handle_tools_list_start_time = time.time()

        async with self._tools_list_lock:
            if not self._tools_list_in_progress or self._tools_list_in_progress.done():
                self._tools_list_in_progress = asyncio.create_task(call_next(context))
            shared_task = self._tools_list_in_progress

        try:
            result = await shared_task
        except Exception as e:
            async with self._tools_list_lock:
                if self._tools_list_in_progress is shared_task:
                    self._tools_list_in_progress = None
            raise
        self.logger.debug(
            f"PROFILE: tools/list call_next duration: {time.time() - on_handle_tools_list_start_time:.2f} seconds id: {event_id}")

        tools_list = None
        if isinstance(result, list):
            tools_list = result
        elif hasattr(result, 'tools') and result.tools:
            tools_list = result.tools

        if tools_list:
            current_time = time.time()
            if (self._last_tools_init_time is None or (current_time - self._last_tools_init_time)
                    >= self._TOOLS_INIT_DEBOUNCE_SECONDS):
                self._last_tools_init_time = current_time
                await self._call_init_api(context, tools_list)

            modified_tools = []
            for tool in tools_list:
                enhanced_parameters = merge_input_schema_with_existing(
                    getattr(tool, 'parameters', None)
                )
                modified_tool = safe_copy(tool, {'parameters': enhanced_parameters})
                modified_tools.append(modified_tool)

            if isinstance(result, list):
                enhanced_result = modified_tools
            elif hasattr(result, 'tools'):
                enhanced_result = safe_copy(result, {'tools': modified_tools})
            else:
                enhanced_result = result

            on_handle_tools_list_duration = time.time() - on_handle_tools_list_start_time
            self.logger.debug(
                f"PROFILE: tools/list enhanced_result duration: {on_handle_tools_list_duration:.2f} seconds id: {event_id}")
            return enhanced_result

        on_handle_tools_list_duration = time.time() - on_handle_tools_list_start_time
        self.logger.debug(
            f"PROFILE: tools/list result duration: {on_handle_tools_list_duration:.2f} seconds id: {event_id}")

        return result

    async def _call_init_api(self, context: MiddlewareContext, tools: List[Any]):
        """Call /init API with environment, server, and tools data"""
        try:
            event_id = generate_event_id()

            workspace_roots = await self._extract_workspace_roots(context)
            environment_context = EnvironmentContext(
                session_id=self.session_id,
                workspace={
                    "roots": workspace_roots,
                    "current_files": []  # Could be enhanced later
                },
                client=self.wrapper_server_name,
                client_version=self.wrapper_server_version,
                selection_hash=""  # Could be enhanced later
            )

            server_ref = ServerRef(
                name=self.wrapped_server_name,
                transport=self.wrapped_server_transport,
                version="1.0.0"  # Could be enhanced later
            )

            tool_refs = []
            for tool in tools:
                tool_ref = ToolRef(
                    name=getattr(tool, 'name', 'unknown'),
                    description=f"Description:\n{getattr(tool, 'description', '')}\n\n"
                                f"inputSchema:\n{safe_json_dumps(getattr(tool, 'parameters', {}))}",
                    version=getattr(tool, 'version', None)
                )
                tool_refs.append(tool_ref)

            init_request = InitRequest(
                environment=environment_context,
                server=server_ref,
                tools=tool_refs
            )

            async with SecurityPolicyClient(session_id=self.session_id, logger=self.logger,
                                            audit_logger=self.audit_logger, app_id=self.app_id) as client:
                result = await client.init_tools(init_request, event_id=event_id)
                self.logger.info(f"Tools initialized:\n{result}")

        except Exception as e:
            # Don't fail the tools/list operation if /init fails - just log the error
            self.logger.error(f"Failed to initialize tools: {e}")

    def _split_context_arguments(self, context: MiddlewareContext) -> tuple:
        """Split context arguments into wrapper-specific, tool-specific, and cleaned context"""
        wrapper_args = {}
        tool_args = {}
        arguments = {}
        if hasattr(context, 'message') and context.message:
            if hasattr(context.message, 'arguments') and context.message.arguments:
                arguments = context.message.arguments
            else:
                arguments = getattr(context.message, '__dict__', {})

        for key, value in arguments.items():
            if key.startswith('__wrapper_'):
                wrapper_args[key] = value
            else:
                tool_args[key] = value

        cleaned_context = context
        if (hasattr(context, 'message')
                and context.message
                and hasattr(context.message, 'arguments')
                and context.message.arguments):
            cleaned_message = safe_copy(context.message, {'arguments': tool_args})
            cleaned_context = context.copy(message=cleaned_message)

        self.logger.debug(f"_split_context_arguments: wrapper={wrapper_args}, tool={tool_args}")
        return wrapper_args, tool_args, cleaned_context

    def _extract_response_content(self, result: Any) -> Dict[str, Any]:
        """Extract response content from FastMCP objects"""
        try:
            return to_dict(result) if result is not None else {"response": None}
        except Exception as e:
            self.logger.warning(f"Error extracting response content: {e}")
            return {"error": f"Failed to extract response content: {e}"}

    def _extract_tool_name_from_context(self, context: MiddlewareContext) -> str:
        """Extract tool name from FastMCP middleware context"""
        try:
            if hasattr(context, 'method') and context.method == "tools/call":
                if hasattr(context, 'message') and context.message:
                    if hasattr(context.message, 'arguments') and context.message.arguments:
                        if isinstance(context.message.arguments, dict):
                            name = context.message.arguments.get('name')
                            if name and isinstance(name, str):
                                return name

                    if hasattr(context.message, 'params') and context.message.params:
                        if hasattr(context.message.params, 'name'):
                            name = context.message.params.name
                            if isinstance(name, str):
                                return name
                        elif isinstance(context.message.params, dict):
                            name = context.message.params.get('name')
                            if name and isinstance(name, str):
                                return name

                    if hasattr(context.message, 'name'):
                        name = context.message.name
                        if isinstance(name, str):
                            return name

            if hasattr(context, 'method') and context.method:
                method = str(context.method)
                if '/' in method:
                    return method.split('/')[-1]  # e.g., "resources/read" -> "read"
                return method

            return "Unknown"

        except Exception as e:
            self.logger.warning(f"Error extracting tool name from context: {e}")
            return "Unknown"

    async def _extract_workspace_roots(self, context: MiddlewareContext) -> List[str]:
        """Extract workspace roots from MiddlewareContext"""
        try:
            if context.fastmcp_context and hasattr(context.fastmcp_context, 'list_roots'):
                roots = await context.fastmcp_context.list_roots()
                self.logger.debug(f'_extract_workspace_roots: roots={roots}')

                workspace_roots = []
                for root in roots:
                    if hasattr(root, 'uri') and root.uri:
                        uri = str(root.uri)  # Handle FileUrl objects
                        file_path_prefix = 'file://'
                        if uri.startswith(file_path_prefix):
                            path = urllib.parse.unquote(uri[len(file_path_prefix):])

                            # Windows fix: remove leading slash before drive letter
                            # file:///C:/path becomes /C:/path, should be C:/path
                            if sys.platform == 'win32' and len(path) >= 3 and path[0] == '/' and path[2] == ':':
                                path = path[1:]

                            try:
                                resolved_path = str(Path(path).resolve())
                                workspace_roots.append(resolved_path)
                            except Exception as e:
                                self.logger.warning(f"Could not resolve workspace root path {path}: {e}")

                return workspace_roots
            else:
                self.logger.warning("No fastmcp_context or list_roots method available")
                return []

        except Exception as e:
            self.logger.warning(f"Could not extract workspace roots: {e}")
            return []

    async def _inspect_request(self, event_id: str, context: MiddlewareContext,
                               wrapper_args: Dict[str, Any], tool_args: Dict[str, Any],
                               prompt_id: str) -> Dict[str, Any]:
        """Call security API for request inspection"""
        try:
            base_dict = await self._build_baseline_policy_dict(event_id, context, wrapper_args, tool_args)
            policy_request = create_policy_request(
                event_id=event_id,
                server=ServerRef(
                    name=base_dict["server"]["name"],
                    transport=base_dict["server"]["transport"]
                ),
                tool=ToolRef(
                    name=base_dict["tool"]["name"] or base_dict["tool"]["method"]
                ),
                agent_context=base_dict["agent_context"],
                env_context=base_dict["environment_context"],
                arguments=tool_args,
            )
            self.logger.debug(f"_inspect_request: {policy_request}")

            async with SecurityPolicyClient(session_id=self.session_id, logger=self.logger,
                                            audit_logger=self.audit_logger, app_id=self.app_id) as client:
                decision = await client.inspect_policy_request(policy_request=policy_request,
                                                               prompt_id=prompt_id)
                self.logger.debug(f"Decision for inspected request: {decision}")
                return decision

        except Exception as e:
            self.logger.error(f"Security API request inspection failed: {e}")
            return self._create_security_api_failure_decision(e)

    async def _inspect_response(self, event_id: str, result: Any, context: MiddlewareContext,
                                wrapper_args: Dict[str, Any], tool_args: Dict[str, Any],
                                prompt_id: str) -> Dict[str, Any]:
        """Call security API for response inspection"""
        try:
            base_dict = await self._build_baseline_policy_dict(event_id, context, wrapper_args, tool_args)
            policy_response = create_policy_response(
                event_id=event_id,
                server=ServerRef(
                    name=base_dict["server"]["name"],
                    transport=base_dict["server"]["transport"]
                ),
                tool=ToolRef(
                    name=base_dict["tool"]["name"] or base_dict["tool"]["method"]
                ),
                response_content=safe_json_dumps(result),
                agent_context=base_dict["agent_context"],
                env_context=base_dict["environment_context"],
            )
            self.logger.debug(f"_inspect_response: {policy_response}")

            async with SecurityPolicyClient(session_id=self.session_id, logger=self.logger,
                                            audit_logger=self.audit_logger, app_id=self.app_id) as client:
                decision = await client.inspect_policy_response(policy_response=policy_response,
                                                                prompt_id=prompt_id)
                self.logger.debug(f"Decision for inspected response: {decision}")
                return decision

        except Exception as e:
            self.logger.error(f"Security API response inspection failed: {e}")
            return self._create_security_api_failure_decision(e)

    async def _build_baseline_policy_dict(self, event_id: str, context: MiddlewareContext,
                                          wrapper_args: Dict[str, Any], tool_args: Dict[str, Any]) -> Dict[str, Any]:
        """Build baseline policy dict for request and response inspection"""
        tool_name = self._extract_tool_name_from_context(context)
        workspace_roots = await self._extract_workspace_roots(context)

        return {
            "server": {  # should be wrapped-server name and transport
                "name": self.wrapped_server_name,
                "transport": self.wrapped_server_transport
            },
            "tool": {
                "name": tool_name,
                "method": getattr(context, 'method', 'unknown')
            },
            "agent_context": AgentContext(
                last_user_prompt=wrapper_args.get('__wrapper_userPrompt', ''),
                context_summary=wrapper_args.get('__wrapper_contextSummary', ''),
                user_prompt_id=wrapper_args.get('__wrapper_userPromptId', ''),
                intent=wrapper_args.get('__wrapper_modelIntent', ''),
                plan=wrapper_args.get('__wrapper_modelPlan', ''),
                expected_outputs=wrapper_args.get('__wrapper_modelExpectedOutputs', ''),
            ),
            "environment_context": EnvironmentContext(
                session_id=self.session_id,
                workspace={
                    "roots": workspace_roots,
                    "current_files": wrapper_args.get('__wrapper_currentFiles')
                },
                client=self.wrapper_server_name,
                client_version=self.wrapper_server_version,
                client_os=get_client_os(),
                app_id=self.app_id,
            )
        }

    @staticmethod
    def _create_security_api_failure_decision(error: Exception) -> Dict[str, Any]:
        """Create a standard failure decision when security API is unavailable/failing/unreachable"""
        return {
            "decision": "block",
            "severity": "high",
            "reasons": [f"Security API unavailable: {error}"],
            "matched_rules": ["security_api.error"]
        }
