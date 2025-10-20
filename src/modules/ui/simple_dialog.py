"""
Simple, lightweight confirmation dialog using native OS dialogs

This provides cross-platform native dialogs
"""

from modules.logs.logger import MCPLogger

from . import xdialog
from .classes import ConfirmationRequest, DialogOptions


def show_explicit_user_confirmation_dialog(request: ConfirmationRequest, options: DialogOptions,
                                           logger: MCPLogger) -> int:
    """
    Show a native OS confirmation dialog using xdialog

    Returns:
        int: xdialog constant (YES, NO, YES_ALWAYS, NO_ALWAYS)
    """
    message = (f"Server: {request.server_name}"
               f"\nTool: {request.tool_name}"
               f"\n\nPolicy Alert ({request.severity.title()}):"
               f"\n{request.policy_reasons[0]}")

    try:
        # Build custom button array: Block, Always Block (optional), Allow, Always Allow (optional)
        buttons = ["Block"]

        if options.show_always_block:
            buttons.append("Always Block")

        buttons.append("Allow")

        if options.show_always_allow:
            buttons.append("Always Allow")

        # Use generic dialog with Block/Allow buttons
        result_index = xdialog.generic_dialog(
            title="MCPower Security Confirmation Required",
            message=message,
            buttons=buttons,
            default_button=buttons.index("Allow"),  # Default to "Allow"
            icon=xdialog.ICON_WARNING
        )

        # Map button indices back to xdialog constants for compatibility
        # Button order: Block, [Always Block], Allow, [Always Allow]
        if result_index == 0:
            return xdialog.NO  # Block -> NO
        elif options.show_always_block and result_index == 1:
            return xdialog.NO_ALWAYS  # Always Block -> NO_ALWAYS
        elif not options.show_always_block and result_index == 1:
            return xdialog.YES  # Allow -> YES (when no Always Block)
        elif options.show_always_block and result_index == 2:
            return xdialog.YES  # Allow -> YES (when Always Block is present)
        elif not options.show_always_block and result_index == 2:
            return xdialog.YES_ALWAYS  # Always Allow -> YES_ALWAYS (when no Always Block)
        elif options.show_always_block and result_index == 3:
            return xdialog.YES_ALWAYS  # Always Allow -> YES_ALWAYS (when Always Block is present)
        else:
            raise Exception(f"Unexpected result index {result_index}")

    except Exception as e:
        logger.error(f"Native dialog error: {e}")
        raise e


def show_blocking_dialog(request: ConfirmationRequest, logger: MCPLogger) -> int:
    """
    Show a blocking dialog with red error styling and "Block"/"Allow Anyway" buttons
    
    Returns:
        int: xdialog constant (YES=Allow Anyway, NO=Block)
    """
    message = (f"Server: {request.server_name}"
               f"\nTool: {request.tool_name}"
               f"\n\nPolicy Alert ({request.severity.title()}):"
               f"\n{request.policy_reasons[0]}")

    try:
        # Build button array: Block (default), Allow Anyway
        buttons = ["Block", "Allow Anyway"]

        # Use generic dialog with error icon and Block as default
        result_index = xdialog.generic_dialog(
            title="MCPower Security Request Blocked",
            message=message,
            buttons=buttons,
            default_button=0,  # Default to "Block" button (first button)
            icon=xdialog.ICON_ERROR  # Red error icon
        )

        # Map button indices to xdialog constants
        if result_index == 0:
            return xdialog.NO  # Block -> NO
        elif result_index == 1:
            return xdialog.YES  # Allow Anyway -> YES
        else:
            raise Exception(f"Unexpected result index {result_index}")

    except Exception as e:
        logger.error(f"Blocking dialog error: {e}")
        raise e
