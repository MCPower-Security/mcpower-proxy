"""Security Policy API Client"""

import json
import time
import uuid
from typing import Dict, Any, Optional, List

import httpx

from mcpower_shared.mcp_types import PolicyRequest, PolicyResponse, InitRequest, UserConfirmation, InspectDecision
from modules.logs.audit_trail import AuditTrailLogger
from modules.logs.logger import MCPLogger
from modules.redaction import redact
from modules.utils.config import get_api_url, get_user_id
from modules.utils.json import safe_json_dumps, to_dict
from wrapper.__version__ import __version__


class SecurityAPIError(Exception):
    """Security API communication error"""
    pass


class RateLimitExhaustedError(SecurityAPIError):
    """Security API rate limit exhausted (429) error"""

    def __init__(self, message: str, retry_after: int = None):
        super().__init__(message)
        self.retry_after = retry_after


class SecurityPolicyClient:
    """HTTP client for security policy API calls"""

    # Class-level tracking for 429 notifications per session
    _session_notification_times: Dict[str, float] = {}

    def __init__(self, session_id: str, logger: MCPLogger, audit_logger: AuditTrailLogger, app_id: str,
                 timeout: float = 60.0):
        self.base_url = get_api_url().rstrip('/')
        self.timeout = timeout
        self.client: Optional[httpx.AsyncClient] = None
        self.logger = logger
        self.audit_logger = audit_logger
        self.user_id = get_user_id(logger)
        self.app_id = app_id
        self.session_id = session_id

    async def __aenter__(self):
        self.client = httpx.AsyncClient(timeout=self.timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()

    async def inspect_policy_request(self, policy_request: PolicyRequest,
                                     prompt_id: str) -> InspectDecision:
        """Call inspect_policy_request API endpoint"""
        if not self.client:
            raise SecurityAPIError("Client not initialized - use async context manager")

        return await self._make_request("/inspect_request", policy_request, method="POST",
                                        redacted_keys=[
                                            "$.tool.description",
                                            "$.context.agent.*",
                                            "$.arguments_redacted.*"
                                        ],
                                        audit_event_type="inspect_agent_request",
                                        event_id=policy_request.event_id,
                                        prompt_id=prompt_id)

    async def inspect_policy_response(self, policy_response: PolicyResponse,
                                      prompt_id: str) -> InspectDecision:
        """Call inspect_policy_response API endpoint"""
        if not self.client:
            raise SecurityAPIError("Client not initialized - use async context manager")

        return await self._make_request("/inspect_response", policy_response, method="POST",
                                        redacted_keys=[
                                            "$.tool.description",
                                            "$.context.agent.*",
                                            "$.result_preview.*"
                                        ],
                                        audit_event_type="inspect_mcp_response",
                                        event_id=policy_response.event_id,
                                        prompt_id=prompt_id)

    async def record_user_confirmation(self, user_confirmation: UserConfirmation,
                                       prompt_id: str) -> Dict[str, Any]:
        """Record user confirmation decision"""
        if not self.client:
            raise SecurityAPIError("Client not initialized - use async context manager")

        return await self._make_request("/user_confirmation", payload=user_confirmation, method="PUT",
                                        # non existing key to skip redaction completely (nothing to redact here)
                                        redacted_keys=["$.none"],
                                        audit_event_type="record_user_confirmation",
                                        event_id=user_confirmation.event_id,
                                        prompt_id=prompt_id)

    async def init_tools(self, init_request: InitRequest, event_id: Optional[str] = None) -> Dict[str, Any]:
        """Initialize tools with environment, server, and tools data"""
        if not self.client:
            raise SecurityAPIError("Client not initialized - use async context manager")

        payload = {
            "environment": {
                "session_id": init_request.environment.session_id,
                "workspace": init_request.environment.workspace,
                "client": init_request.environment.client,
                "client_version": init_request.environment.client_version,
                "selection_hash": init_request.environment.selection_hash
            },
            "server": {
                "name": init_request.server.name,
                "transport": init_request.server.transport,
                "version": init_request.server.version
            },
            "tools": [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "version": tool.version
                }
                for tool in init_request.tools
            ]
        }

        return await self._make_request("/init", payload, method="POST",
                                        redacted_keys=["$.tools[*].description"],
                                        audit_event_type="init_tools",
                                        event_id=event_id,
                                        prompt_id=None)

    async def _make_request(self, endpoint: str, payload: Any, method: str,
                            audit_event_type: str, event_id: str = None,
                            prompt_id: str = None, redacted_keys: List[str] = None) -> Dict[str, Any]:
        """Make HTTP request to security API"""
        url = f"{self.base_url}{endpoint}"
        error: Exception = None

        try:
            id = str(uuid.uuid4())[:5]

            payload_dict = to_dict(payload)
            redacted_payload = redact(payload_dict, include_keys=redacted_keys) if redacted_keys else payload_dict
            redacted_payload_json = safe_json_dumps(redacted_payload)
            self.logger.info(f"Security API request: {{'id': {id}, 'method': {method}, 'url': {url}, "
                             f"'payload': {redacted_payload_json}}}")

            if "arguments_redacted" in payload_dict:
                audit_payload = {"payload": payload_dict["arguments_redacted"]}
            elif "result_preview" in payload_dict:
                audit_payload = {"payload": payload_dict["result_preview"]}
            elif "tools" in payload_dict and "server" in payload_dict:
                audit_payload = {"payload": {"server": payload_dict["server"], "tools": payload_dict["tools"]}}
            else:
                audit_payload = {"payload": payload_dict}

            self.audit_logger.log_event(
                audit_event_type,
                audit_payload,
                event_id=event_id,
                prompt_id=prompt_id,
                include_keys=redacted_keys
            )

            headers = {
                "Content-Type": "application/json",
                "User-Agent": f"MCPower-{__version__}",
                "X-User-UID": self.user_id,
                "X-App-UID": self.app_id
            }

            on_make_request_start_time = time.time()
            method_upper = method.upper()
            if method_upper == "PUT":
                response = await self.client.put(
                    url,
                    content=redacted_payload_json,
                    headers=headers
                )
            elif method_upper == "POST":
                response = await self.client.post(
                    url,
                    content=redacted_payload_json,
                    headers=headers
                )
            else:
                raise SecurityAPIError(f"Unsupported HTTP method: {method}. Supported methods: POST, PUT")

            on_make_request_duration = time.time() - on_make_request_start_time
            self.logger.debug(
                f"PROFILE: {method} id: {id} make_request duration: {on_make_request_duration:.2f} seconds url: {url}")

            match response.status_code:
                case 200:
                    data = response.json()
                    data_dict = to_dict(data);
                    self.logger.info(f"Security API response: {{'id': {id}, 'data': {data_dict}}}")

                    if "decision" in data_dict:
                        # InspectDecision response (/inspect_request, /inspect_response)
                        # Extract: decision, call_type, severity, reasons
                        audit_result = {"result": {"decision": data_dict["decision"]}}
                        if "call_type" in data_dict:
                            audit_result["result"]["call_type"] = data_dict["call_type"]
                        if "severity" in data_dict:
                            audit_result["result"]["severity"] = data_dict["severity"]
                        if "reasons" in data_dict:
                            audit_result["result"]["reasons"] = data_dict["reasons"]
                    elif "user_decision" in data_dict:
                        # UserConfirmation response (/user_confirmation)
                        # Extract: user_decision, call_type, confirmed_at
                        audit_result = {"result": {"user_decision": data_dict["user_decision"]}}
                        if "call_type" in data_dict:
                            audit_result["result"]["call_type"] = data_dict["call_type"]
                    else:
                        # Other responses (e.g., /init) - log entire response
                        audit_result = {"result": data_dict}

                    self.audit_logger.log_event(
                        f"{audit_event_type}_result",
                        audit_result,
                        event_id=event_id,
                        prompt_id=prompt_id,
                        include_keys=redacted_keys
                    )

                    # Successful response - handle quota restoration
                    self._handle_quota_restoration(endpoint)

                    return data
                case 400:
                    error_data = response.json()
                    error_msg = error_data.get("error", "Bad request")
                    raise SecurityAPIError(f"Security API validation error: {error_msg}")
                case 429:
                    error_data = response.json() if response.content else {}
                    retry_after = int(response.headers.get('Retry-After', '60'))

                    # Handle 429 - log, notify, and return allow decision (screening bypassed)
                    self.logger.error(f"Security API rate limit exhausted (429) - bypassing security screening. "
                                      f"Endpoint: {endpoint}, Retry-After: {retry_after}s, Session: {self.session_id}")
                    self._send_throttled_quota_notification(retry_after, endpoint)

                    return {
                        "decision": "allow",
                        "severity": "high",
                        "reasons": ["Security quota exhausted - screening bypassed"]
                    }
                case 500:
                    error_data = response.json()
                    error_msg = error_data.get("error", "Internal server error")
                    raise SecurityAPIError(f"Security API server error: {error_msg}")
                case _:
                    raise SecurityAPIError(f"Security API returned status {response.status_code}")

        except httpx.RequestError as e:
            error = e
            raise SecurityAPIError(f"Failed to connect to security API: {e}")
        except json.JSONDecodeError as e:
            error = e
            raise SecurityAPIError(f"Invalid JSON response from security API: {e}")
        except Exception as e:
            error = e
            raise SecurityAPIError(f"Unexpected error calling security API: {e}")
        finally:
            if error:
                self.audit_logger.log_event(
                    f"{audit_event_type}_result",
                    {
                        "endpoint": endpoint,
                        "error": [f"Security API error: {error}"]
                    },
                    event_id=event_id,
                    prompt_id=prompt_id,
                    include_keys=redacted_keys
                )

    def _handle_quota_restoration(self, endpoint: str):
        """Handle quota restoration (when non-429 response received)"""
        if self.session_id in self._session_notification_times:
            self.logger.info(
                f"Quota restored - received successful response from {endpoint}. Session: {self.session_id}")
            del self._session_notification_times[self.session_id]

    def _send_throttled_quota_notification(self, retry_after: int, endpoint: str):
        """Send throttled quota notification to user"""
        import time
        from modules.ui import xdialog

        try:
            current_time = time.time()
            one_hour = 3600

            # Check if we should send notification (throttle to once per hour per session)
            last_notification = self._session_notification_times.get(self.session_id)
            should_send = (
                    last_notification is None or
                    (current_time - last_notification) >= one_hour
            )

            if not should_send:
                time_since_last = current_time - last_notification
                self.logger.debug(f"429 notification throttled (sent {time_since_last:.0f}s ago). "
                                  f"Session: {self.session_id}, Endpoint: {endpoint}")
            else:
                message = (
                    "MCPower quota exhausted.\n\n"
                    "Subsequent requests will not be screened.\n\n"
                    "Please contact support if you need additional quota.\n\n"
                )

                xdialog.warning(
                    title="Warning: Security Quota Exhausted",
                    message=message
                )

                self._session_notification_times[self.session_id] = current_time

                self.logger.warning(f"Displayed 429 quota exhaustion dialog to user. "
                                    f"Session: {self.session_id}, Endpoint: {endpoint}")

        except Exception as e:
            self.logger.error(f"Failed to show quota exhaustion notification: {e}")
