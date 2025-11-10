"""
Decision Handler - Common decision enforcement logic

Shared module for enforcing security policy decisions across middleware and IDE tools.
Handles user confirmation dialogs and decision recording.
"""
from typing import Dict, Any, Optional

from mcpower_shared.mcp_types import UserConfirmation
from modules.apis.security_policy import SecurityPolicyClient
from modules.logs.audit_trail import AuditTrailLogger
from modules.logs.logger import MCPLogger
from modules.ui.classes import ConfirmationRequest, DialogOptions, UserDecision
from modules.ui.confirmation import UserConfirmationDialog, UserConfirmationError


class DecisionEnforcementError(Exception):
    """Error raised when a security decision blocks an operation"""
    pass


class DecisionHandler:
    """
    Handles security policy decision enforcement with user confirmation support.
    
    This class provides common functionality for:
    - Enforcing allow/block/confirm decisions
    - Showing user confirmation dialogs
    - Recording user decisions via API
    """

    def __init__(self, logger: MCPLogger, audit_logger: AuditTrailLogger,
                 session_id: str, app_id: str):
        self.logger = logger
        self.audit_logger = audit_logger
        self.session_id = session_id
        self.app_id = app_id

    async def enforce_decision(
            self,
            decision: Dict[str, Any],
            is_request: bool,
            event_id: str,
            tool_name: str,
            content_data: Dict[str, Any],
            operation_type: str,
            prompt_id: str,
            server_name: str,
            error_message_prefix: Optional[str] = None
    ) -> None:
        """
        Enforce security decision with user confirmation support.
        
        Args:
            decision: Security decision dict with 'decision', 'reasons', 'severity', 'call_type'
            is_request: True if inspecting request, False if inspecting response
            event_id: Event ID for tracking
            tool_name: Name of the tool/operation
            content_data: Data to show in confirmation dialog
            operation_type: Type of operation (e.g., 'tool', 'hook')
            prompt_id: prompt ID for correlation
            server_name: server name for display
            error_message_prefix: Optional prefix for error messages
            
        Raises:
            DecisionEnforcementError: If decision blocks the operation
        """
        decision_type = decision.get("decision", "block")

        if decision_type == "allow":
            return

        elif decision_type == "block":
            policy_reasons = decision.get("reasons", ["Policy violation"])
            severity = decision.get("severity", "unknown")
            call_type = decision.get("call_type")

            try:
                # Show a blocking dialog and wait for user decision
                confirmation_request = ConfirmationRequest(
                    is_request=is_request,
                    tool_name=tool_name,
                    policy_reasons=policy_reasons,
                    content_data=content_data,
                    severity=severity,
                    event_id=event_id,
                    operation_type=operation_type,
                    server_name=server_name
                )

                response = UserConfirmationDialog(
                    self.logger, self.audit_logger
                ).request_blocking_confirmation(confirmation_request, prompt_id, call_type)

                # If we got here, user chose "Allow Anyway"
                self.logger.info(f"User chose to 'allow anyway' a blocked {confirmation_request.operation_type} "
                                 f"operation for tool '{tool_name}' (event: {event_id})")

                await self._record_user_confirmation(event_id, is_request, response.user_decision, prompt_id, call_type)
                return

            except UserConfirmationError as e:
                # User chose to block or dialog failed
                await self._record_user_confirmation(event_id, is_request, UserDecision.BLOCK, prompt_id, call_type)
                error_msg = error_message_prefix or "Security Violation"
                raise DecisionEnforcementError(f"{error_msg}. User blocked the operation")

        elif decision_type == "required_explicit_user_confirmation":
            policy_reasons = decision.get("reasons", ["Security policy requires confirmation"])
            severity = decision.get("severity", "unknown")
            call_type = decision.get("call_type")

            try:
                confirmation_request = ConfirmationRequest(
                    is_request=is_request,
                    tool_name=tool_name,
                    policy_reasons=policy_reasons,
                    content_data=content_data,
                    severity=severity,
                    event_id=event_id,
                    operation_type=operation_type,
                    server_name=server_name
                )

                # only show YES_ALWAYS if call_type exists
                options = DialogOptions(
                    show_always_allow=(call_type is not None),
                    show_always_block=False
                )

                response = UserConfirmationDialog(
                    self.logger, self.audit_logger
                ).request_confirmation(confirmation_request, prompt_id, call_type, options)

                # If we got here, user approved the operation
                self.logger.info(f"User {response.user_decision.value} {confirmation_request.operation_type} "
                                 f"operation for tool '{tool_name}' (event: {event_id})")

                await self._record_user_confirmation(event_id, is_request, response.user_decision, prompt_id, call_type)
                return

            except UserConfirmationError as e:
                # User denied confirmation or dialog failed
                await self._record_user_confirmation(event_id, is_request, UserDecision.BLOCK, prompt_id, call_type)
                error_msg = error_message_prefix or "Security Violation"
                raise DecisionEnforcementError(f"{error_msg}. User blocked the operation")

        elif decision_type == "need_more_info":
            stage_title = 'CLIENT REQUEST' if is_request else 'TOOL RESPONSE'

            # Create an actionable error message for the AI agent
            reasons = decision.get("reasons", [])
            need_fields = decision.get("need_fields", [])

            error_parts = [
                f"SECURITY POLICY NEEDS MORE INFORMATION FOR REVIEWING {stage_title}:",
                '\n'.join(reasons),
                ''  # newline
            ]

            if need_fields:
                # Convert server field names to wrapper field names for the AI agent
                wrapper_field_mapping = {
                    "context.agent.intent": "__wrapper_modelIntent",
                    "context.agent.plan": "__wrapper_modelPlan",
                    "context.agent.expectedOutputs": "__wrapper_modelExpectedOutputs",
                    "context.agent.user_prompt": "__wrapper_userPrompt",
                    "context.agent.user_prompt_id": "__wrapper_userPromptId",
                    "context.agent.context_summary": "__wrapper_contextSummary",
                    "context.workspace.current_files": "__wrapper_currentFiles",
                }

                missing_wrapper_fields = []
                for field in need_fields:
                    wrapper_field = wrapper_field_mapping.get(field, field)
                    missing_wrapper_fields.append(wrapper_field)

                if missing_wrapper_fields:
                    error_parts.append("AFFECTED FIELDS:")
                    error_parts.extend(missing_wrapper_fields)
                else:
                    error_parts.append("MISSING INFORMATION:")
                    error_parts.extend(need_fields)

            error_parts.append("\nMANDATORY ACTIONS:")
            error_parts.append("1. Add/Edit ALL affected fields according to the required information")
            error_parts.append("2. Retry the tool call")

            actionable_message = "\n".join(error_parts)
            raise DecisionEnforcementError(actionable_message)

    async def _record_user_confirmation(
            self,
            event_id: str,
            is_request: bool,
            user_decision: UserDecision,
            prompt_id: str,
            call_type: Optional[str] = None
    ):
        """Record user confirmation decision with the security API"""
        try:
            direction = "request" if is_request else "response"

            user_confirmation = UserConfirmation(
                event_id=event_id,
                direction=direction,
                user_decision=user_decision,
                call_type=call_type
            )

            async with SecurityPolicyClient(session_id=self.session_id, logger=self.logger,
                                            audit_logger=self.audit_logger, app_id=self.app_id) as client:
                result = await client.record_user_confirmation(user_confirmation, prompt_id=prompt_id)
                self.logger.debug(f"User confirmation recorded: {result}")
        except Exception as e:
            # Don't fail the operation if API call fails - just log the error
            self.logger.error(f"Failed to record user confirmation: {e}")
