"""
User Confirmation Dialog for Security Policy Enforcement

Provides simple, lightweight modal dialogs for explicit user confirmation
when security policies require user approval for MCP operations.
"""

from datetime import datetime, timezone
from typing import Optional

from mcpower_shared.mcp_types import UserDecision
from modules.logs.audit_trail import AuditTrailLogger
from modules.logs.logger import MCPLogger
from . import xdialog
from .classes import ConfirmationRequest, ConfirmationResponse, UserConfirmationError, DialogOptions
from .simple_dialog import show_explicit_user_confirmation_dialog, show_blocking_dialog


# noinspection PyMethodMayBeStatic
class UserConfirmationDialog:
    """
    Simple user confirmation dialog using tkinter messagebox
    
    Provides lightweight modal dialogs for explicit user approval of MCP operations
    when security policies require confirmation at request or response stages.
    """

    def __init__(self, logger: MCPLogger, audit_logger: AuditTrailLogger):
        self.logger = logger
        self.audit_logger = audit_logger

    def request_confirmation(self, request: ConfirmationRequest, prompt_id: str,
                             call_type: Optional[str] = None, options: DialogOptions = None) -> ConfirmationResponse:
        """
        Display a confirmation dialog and wait for the user decision
        
        Args:
            request: Confirmation request with all necessary context
            call_type: Optional call type from inspect decision ("read", "write")
            options: Optional dialog options for controlling button visibility
            prompt_id: Prompt ID for audit trail grouping (mandatory for tool calls)
            
        Returns:
            ConfirmationResponse with user decision
            
        Raises:
            UserConfirmationError: If a user denies or the dialog fails
        """
        if options is None:
            options = DialogOptions()
        self.logger.info(f"Requesting user confirmation for "
                         f"{'request' if request.is_request else 'response'} "
                         f"operation on tool '{request.tool_name}' (event: {request.event_id})")

        # AUDIT: Log user interaction
        self.audit_logger.log_event(
            "user_interaction",
            {
                "type": "dialog",
                "interaction": "explicit user confirmation"
            },
            event_id=request.event_id,
            prompt_id=prompt_id
        )

        result = show_explicit_user_confirmation_dialog(request, options, self.logger)
        direction = "request" if request.is_request else "response"

        # Convert dialog result to UserDecision enum
        match result:
            case xdialog.YES:
                user_decision = UserDecision.ALLOW
            case xdialog.YES_ALWAYS:
                user_decision = UserDecision.ALWAYS_ALLOW
            case xdialog.NO_ALWAYS:
                user_decision = UserDecision.ALWAYS_BLOCK
            case _:  # NO or any other result
                user_decision = UserDecision.BLOCK

        response = ConfirmationResponse(
            user_decision=user_decision,
            timestamp=datetime.now(timezone.utc),
            event_id=request.event_id,
            direction=direction,
            call_type=call_type
        )
        self._log_confirmation_decision(request, response)

        # AUDIT: Log user interaction result
        self.audit_logger.log_event(
            "user_interaction_result",
            {
                "decision": user_decision.value
            },
            event_id=request.event_id,
            prompt_id=prompt_id
        )

        # Process user decision
        if user_decision in (UserDecision.BLOCK, UserDecision.ALWAYS_BLOCK):
            # User denied confirmation
            raise UserConfirmationError(
                f"User denied {'request' if request.is_request else 'response'} operation "
                f"for tool '{request.tool_name}'",
                event_id=request.event_id,
                is_request=request.is_request,
                tool_name=request.tool_name
            )

        # User approved
        return response

    def request_blocking_confirmation(self, request: ConfirmationRequest, prompt_id: str,
                                      call_type: Optional[str] = None) -> ConfirmationResponse:
        """
        Display a blocking dialog and wait for the user decision
        Shows "Block" vs "Allow Anyway" options for policy-blocked requests
        
        Args:
            request: Confirmation request with all necessary context
            prompt_id: Prompt ID for audit trail grouping (mandatory for tool calls)
            call_type: Optional call type from inspect decision ("read", "write")
            
        Returns:
            ConfirmationResponse with user decision
            
        Raises:
            UserConfirmationError: If user chooses to block or dialog fails
        """
        self.logger.info(f"Requesting user blocking confirmation for "
                         f"{'request' if request.is_request else 'response'} "
                         f"operation on tool '{request.tool_name}' (event: {request.event_id})")

        # AUDIT: Log user interaction
        self.audit_logger.log_event(
            "user_interaction",
            {
                "type": "dialog",
                "interaction": "block recommendation"
            },
            event_id=request.event_id,
            prompt_id=prompt_id
        )

        result = show_blocking_dialog(request, self.logger)
        direction = "request" if request.is_request else "response"

        # Convert dialog result to UserDecision enum
        match result:
            case xdialog.YES:  # Allow Anyway
                user_decision = UserDecision.ALLOW
            case _:  # NO (Block) or any other result
                user_decision = UserDecision.BLOCK

        response = ConfirmationResponse(
            user_decision=user_decision,
            timestamp=datetime.now(timezone.utc),
            event_id=request.event_id,
            direction=direction,
            call_type=call_type
        )
        self._log_confirmation_decision(request, response)

        # AUDIT: Log user interaction result
        self.audit_logger.log_event(
            "user_interaction_result",
            {
                "decision": user_decision.value
            },
            event_id=request.event_id,
            prompt_id=prompt_id
        )

        # Process user decision - only allow if user explicitly chose "Allow Anyway"
        if user_decision == UserDecision.BLOCK:
            # User chose to block
            raise UserConfirmationError(
                f"User blocked {'request' if request.is_request else 'response'} operation "
                f"for tool '{request.tool_name}'",
                event_id=request.event_id,
                is_request=request.is_request,
                tool_name=request.tool_name
            )

        # User chose "Allow Anyway"
        return response

    def _log_confirmation_decision(self, request: ConfirmationRequest, response: ConfirmationResponse):
        """Log user confirmation decision for audit trail"""
        self.logger.debug(
            f"User confirmation decision: "
            f"event_id={response.event_id}, "
            f"direction={response.direction}, "
            f"tool={request.tool_name}, "
            f"user_decision={response.user_decision.value}, "
            f"call_type={response.call_type}, "
            f"timed_out={response.timed_out}, "
            f"timestamp={response.timestamp.isoformat()}"
        )
