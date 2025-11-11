#!/usr/bin/env python3
"""
E2E Tests for Decision Handler Config Options

Tests the new config options:
1. MIN_BLOCK_SEVERITY - minimum severity threshold for blocking
2. ALLOW_BLOCK_OVERRIDE - whether block dialogs can be overridden
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from modules.decision.decision_handler import DecisionHandler, DecisionEnforcementError
from modules.logs.audit_trail import AuditTrailLogger
from modules.logs.logger import MCPLogger
from modules.ui.classes import UserDecision

# Configure anyio to only use asyncio backend
pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    """Force asyncio backend only"""
    return 'asyncio'


@pytest.fixture
def handler():
    """Create a DecisionHandler instance for testing"""
    logger = MCPLogger(level='INFO')
    audit_logger = AuditTrailLogger(logger)
    return DecisionHandler(
        logger=logger,
        audit_logger=audit_logger,
        session_id="test-session",
        app_id="cursor"
    )


async def test_min_block_severity_auto_allow(handler):
    """Test that low severity blocks are auto-allowed when MIN_BLOCK_SEVERITY is medium"""
    
    decision = {
        "decision": "block",
        "reasons": ["Minor security concern"],
        "severity": "low",
        "call_type": "read"
    }
    
    with patch('modules.decision.decision_handler.get_min_block_severity', return_value='medium'):
        with patch('modules.decision.decision_handler.get_allow_block_override', return_value=True):
            with patch.object(handler, '_record_user_confirmation', new_callable=AsyncMock) as mock_record:
                # Should not raise, operation should be auto-allowed
                await handler.enforce_decision(
                    decision=decision,
                    is_request=True,
                    event_id="test-001",
                    tool_name="test_tool",
                    content_data={"arg": "value"},
                    operation_type="tool",
                    prompt_id="prompt-001",
                    server_name="test-server"
                )
                
                # Verify ALLOW was recorded
                mock_record.assert_called_once()
                assert mock_record.call_args[0][2] == UserDecision.ALLOW


@pytest.mark.anyio
async def test_min_block_severity_still_blocks(handler):
    """Test that medium severity blocks are still enforced when MIN_BLOCK_SEVERITY is medium"""
    
    decision = {
        "decision": "block",
        "reasons": ["Significant security concern"],
        "severity": "medium",
        "call_type": "write"
    }
    
    with patch('modules.decision.decision_handler.get_min_block_severity', return_value='medium'):
        with patch('modules.decision.decision_handler.get_allow_block_override', return_value=False):
            with patch.object(handler, '_record_user_confirmation', new_callable=AsyncMock) as mock_record:
                # Should raise DecisionEnforcementError
                with pytest.raises(DecisionEnforcementError):
                    await handler.enforce_decision(
                        decision=decision,
                        is_request=True,
                        event_id="test-002",
                        tool_name="test_tool",
                        content_data={"arg": "value"},
                        operation_type="tool",
                        prompt_id="prompt-002",
                        server_name="test-server"
                    )
                
                # Verify BLOCK was recorded
                mock_record.assert_called_once()
                assert mock_record.call_args[0][2] == UserDecision.BLOCK


@pytest.mark.anyio
async def test_allow_block_override_disabled(handler):
    """
    Test ALLOW_BLOCK_OVERRIDE=false: Dialog should NOT be shown, block immediately

    Expected behavior:
    - No dialog displayed to user
    - Operation blocked immediately
    - BLOCK decision recorded
    """

    decision = {
        "decision": "block",
        "reasons": ["Critical security violation"],
        "severity": "high",
        "call_type": None
    }

    with patch('modules.decision.decision_handler.get_min_block_severity', return_value='low'):
        with patch('modules.decision.decision_handler.get_allow_block_override', return_value=False):
            with patch.object(handler, '_record_user_confirmation', new_callable=AsyncMock) as mock_record:
                with patch('modules.decision.decision_handler.UserConfirmationDialog') as mock_dialog_class:
                    # Should raise without showing dialog
                    with pytest.raises(DecisionEnforcementError):
                        await handler.enforce_decision(
                            decision=decision,
                            is_request=True,
                            event_id="test-003",
                            tool_name="test_tool",
                            content_data={"arg": "value"},
                            operation_type="tool",
                            prompt_id="prompt-003",
                            server_name="test-server"
                        )

                    # Verify dialog was NOT shown (expected behavior)
                    mock_dialog_class.assert_not_called()

                    # Verify BLOCK was recorded
                    mock_record.assert_called_once()
                    assert mock_record.call_args[0][2] == UserDecision.BLOCK


@pytest.mark.anyio
async def test_allow_block_override_enabled(handler):
    """
    Test ALLOW_BLOCK_OVERRIDE=true: Dialog SHOULD be shown, user blocks

    Expected behavior:
    - Dialog displayed to user with "Allow Anyway" and "Block" options
    - User chooses "Block"
    - Operation blocked after user interaction
    - BLOCK decision recorded
    """

    decision = {
        "decision": "block",
        "reasons": ["Security violation that can be overridden"],
        "severity": "high",
        "call_type": "write"
    }

    # Mock dialog to simulate user choosing "Block"
    from modules.ui.classes import UserConfirmationError

    mock_dialog_instance = MagicMock()
    mock_dialog_instance.request_blocking_confirmation = MagicMock(
        side_effect=UserConfirmationError(
            "User blocked",
            event_id="test-004",
            is_request=True,
            tool_name="test_tool"
        )
    )

    with patch('modules.decision.decision_handler.get_min_block_severity', return_value='low'):
        with patch('modules.decision.decision_handler.get_allow_block_override', return_value=True):
            with patch('modules.decision.decision_handler.UserConfirmationDialog', return_value=mock_dialog_instance):
                with patch.object(handler, '_record_user_confirmation', new_callable=AsyncMock) as mock_record:
                    # Should raise after showing dialog
                    with pytest.raises(DecisionEnforcementError):
                        await handler.enforce_decision(
                            decision=decision,
                            is_request=True,
                            event_id="test-004",
                            tool_name="test_tool",
                            content_data={"arg": "value"},
                            operation_type="tool",
                            prompt_id="prompt-004",
                            server_name="test-server"
                        )

                    # Verify dialog WAS shown (expected behavior)
                    mock_dialog_instance.request_blocking_confirmation.assert_called_once()

                    # Verify BLOCK was recorded
                    mock_record.assert_called_once()
                    assert mock_record.call_args[0][2] == UserDecision.BLOCK


@pytest.mark.anyio
async def test_unknown_severity_treated_as_high(handler):
    """Test that unknown severity is treated as high (fail-safe)"""
    
    decision = {
        "decision": "block",
        "reasons": ["Security concern with unknown severity"],
        "severity": "unknown",
        "call_type": None
    }
    
    # With MIN_BLOCK_SEVERITY = high, unknown (treated as high) should be blocked
    with patch('modules.decision.decision_handler.get_min_block_severity', return_value='high'):
        with patch('modules.decision.decision_handler.get_allow_block_override', return_value=False):
            with patch.object(handler, '_record_user_confirmation', new_callable=AsyncMock) as mock_record:
                # Should raise
                with pytest.raises(DecisionEnforcementError):
                    await handler.enforce_decision(
                        decision=decision,
                        is_request=True,
                        event_id="test-005",
                        tool_name="test_tool",
                        content_data={"arg": "value"},
                        operation_type="tool",
                        prompt_id="prompt-005",
                        server_name="test-server"
                    )
                
                # Verify BLOCK was recorded
                mock_record.assert_called_once()
                assert mock_record.call_args[0][2] == UserDecision.BLOCK


@pytest.mark.anyio
async def test_unknown_severity_below_critical(handler):
    """Test that unknown severity (as high) is below critical threshold"""

    decision = {
        "decision": "block",
        "reasons": ["Security concern with unknown severity"],
        "severity": "unknown",
        "call_type": None
    }

    # With MIN_BLOCK_SEVERITY = critical, unknown (as high) should be auto-allowed
    with patch('modules.decision.decision_handler.get_min_block_severity', return_value='critical'):
        with patch('modules.decision.decision_handler.get_allow_block_override', return_value=True):
            with patch.object(handler, '_record_user_confirmation', new_callable=AsyncMock) as mock_record:
                # Should not raise
                await handler.enforce_decision(
                    decision=decision,
                    is_request=True,
                    event_id="test-006",
                    tool_name="test_tool",
                    content_data={"arg": "value"},
                    operation_type="tool",
                    prompt_id="prompt-006",
                    server_name="test-server"
                )

                # Verify ALLOW was recorded
                mock_record.assert_called_once()
                assert mock_record.call_args[0][2] == UserDecision.ALLOW


@pytest.mark.anyio
async def test_critical_severity_always_blocks(handler):
    """Test that critical severity always blocks, even with MIN_BLOCK_SEVERITY = low"""

    decision = {
        "decision": "block",
        "reasons": ["Critical security violation"],
        "severity": "critical",
        "call_type": "execute"
    }

    with patch('modules.decision.decision_handler.get_min_block_severity', return_value='low'):
        with patch('modules.decision.decision_handler.get_allow_block_override', return_value=False):
            with patch.object(handler, '_record_user_confirmation', new_callable=AsyncMock) as mock_record:
                # Should raise
                with pytest.raises(DecisionEnforcementError):
                    await handler.enforce_decision(
                        decision=decision,
                        is_request=True,
                        event_id="test-007",
                        tool_name="test_tool",
                        content_data={"arg": "value"},
                        operation_type="tool",
                        prompt_id="prompt-007",
                        server_name="test-server"
                    )

                # Verify BLOCK was recorded
                mock_record.assert_called_once()
                assert mock_record.call_args[0][2] == UserDecision.BLOCK


@pytest.mark.anyio
async def test_high_severity_below_critical_threshold(handler):
    """Test that high severity is below critical threshold"""

    decision = {
        "decision": "block",
        "reasons": ["High severity security concern"],
        "severity": "high",
        "call_type": "write"
    }

    # With MIN_BLOCK_SEVERITY = critical, high should be auto-allowed
    with patch('modules.decision.decision_handler.get_min_block_severity', return_value='critical'):
        with patch('modules.decision.decision_handler.get_allow_block_override', return_value=True):
            with patch.object(handler, '_record_user_confirmation', new_callable=AsyncMock) as mock_record:
                # Should not raise
                await handler.enforce_decision(
                    decision=decision,
                    is_request=True,
                    event_id="test-008",
                    tool_name="test_tool",
                    content_data={"arg": "value"},
                    operation_type="tool",
                    prompt_id="prompt-008",
                    server_name="test-server"
                )

                # Verify ALLOW was recorded
                mock_record.assert_called_once()
                assert mock_record.call_args[0][2] == UserDecision.ALLOW


@pytest.mark.anyio
async def test_medium_severity_below_high_threshold(handler):
    """Test that medium severity is below high threshold"""

    decision = {
        "decision": "block",
        "reasons": ["Medium severity security concern"],
        "severity": "medium",
        "call_type": "read"
    }

    # With MIN_BLOCK_SEVERITY = high, medium should be auto-allowed
    with patch('modules.decision.decision_handler.get_min_block_severity', return_value='high'):
        with patch('modules.decision.decision_handler.get_allow_block_override', return_value=True):
            with patch.object(handler, '_record_user_confirmation', new_callable=AsyncMock) as mock_record:
                # Should not raise
                await handler.enforce_decision(
                    decision=decision,
                    is_request=True,
                    event_id="test-009",
                    tool_name="test_tool",
                    content_data={"arg": "value"},
                    operation_type="tool",
                    prompt_id="prompt-009",
                    server_name="test-server"
                )

                # Verify ALLOW was recorded
                mock_record.assert_called_once()
                assert mock_record.call_args[0][2] == UserDecision.ALLOW


@pytest.mark.anyio
async def test_allow_decision_always_passes(handler):
    """Test that 'allow' decision always passes without recording"""

    decision = {
        "decision": "allow",
        "reasons": [],
        "severity": "low",
        "call_type": None
    }

    with patch.object(handler, '_record_user_confirmation', new_callable=AsyncMock) as mock_record:
        # Should not raise
        await handler.enforce_decision(
            decision=decision,
            is_request=True,
            event_id="test-010",
            tool_name="test_tool",
            content_data={"arg": "value"},
            operation_type="tool",
            prompt_id="prompt-010",
            server_name="test-server"
        )

        # Verify no recording happened for allow decisions
        mock_record.assert_not_called()


@pytest.mark.anyio
async def test_user_allows_override_in_dialog(handler):
    """
    Test ALLOW_BLOCK_OVERRIDE=true: Dialog SHOULD be shown, user allows override

    Expected behavior:
    - Dialog displayed to user with "Allow Anyway" and "Block" options
    - User chooses "Allow Anyway"
    - Operation proceeds despite block decision
    - ALLOW decision recorded
    """

    decision = {
        "decision": "block",
        "reasons": ["Security violation that can be overridden"],
        "severity": "high",
        "call_type": "write"
    }

    # Mock dialog to simulate user choosing "Allow Anyway"
    from modules.ui.classes import ConfirmationResponse
    from datetime import datetime

    mock_dialog_instance = MagicMock()
    mock_response = ConfirmationResponse(
        user_decision=UserDecision.ALLOW,
        event_id="test-011",
        timestamp=datetime.now(),
        direction="request",
        call_type="write"
    )
    mock_dialog_instance.request_blocking_confirmation = MagicMock(return_value=mock_response)

    with patch('modules.decision.decision_handler.get_min_block_severity', return_value='low'):
        with patch('modules.decision.decision_handler.get_allow_block_override', return_value=True):
            with patch('modules.decision.decision_handler.UserConfirmationDialog', return_value=mock_dialog_instance):
                with patch.object(handler, '_record_user_confirmation', new_callable=AsyncMock) as mock_record:
                    # Should not raise, user allowed
                    await handler.enforce_decision(
                        decision=decision,
                        is_request=True,
                        event_id="test-011",
                        tool_name="test_tool",
                        content_data={"arg": "value"},
                        operation_type="tool",
                        prompt_id="prompt-011",
                        server_name="test-server"
                    )

                    # Verify dialog WAS shown (expected behavior)
                    mock_dialog_instance.request_blocking_confirmation.assert_called_once()

                    # Verify ALLOW was recorded
                    mock_record.assert_called_once()
                    assert mock_record.call_args[0][2] == UserDecision.ALLOW


@pytest.mark.anyio
async def test_required_explicit_confirmation_user_allows(handler):
    """
    Test required_explicit_user_confirmation: Dialog SHOULD be shown, user allows

    Expected behavior:
    - Dialog displayed to user (policy requires explicit confirmation)
    - Dialog shows "Allow", "Always Allow" (call_type exists), and "Block" options
    - User chooses "Allow"
    - Operation proceeds after user confirmation
    - ALLOW decision recorded
    """

    decision = {
        "decision": "required_explicit_user_confirmation",
        "reasons": ["Sensitive operation requires confirmation"],
        "severity": "medium",
        "call_type": "execute"
    }

    # Mock dialog to simulate user allowing
    from modules.ui.classes import ConfirmationResponse
    from datetime import datetime

    mock_dialog_instance = MagicMock()
    mock_response = ConfirmationResponse(
        user_decision=UserDecision.ALLOW,
        event_id="test-012",
        timestamp=datetime.now(),
        direction="request",
        call_type="execute"
    )
    mock_dialog_instance.request_confirmation = MagicMock(return_value=mock_response)

    with patch('modules.decision.decision_handler.UserConfirmationDialog', return_value=mock_dialog_instance):
        with patch.object(handler, '_record_user_confirmation', new_callable=AsyncMock) as mock_record:
            # Should not raise
            await handler.enforce_decision(
                decision=decision,
                is_request=True,
                event_id="test-012",
                tool_name="test_tool",
                content_data={"arg": "value"},
                operation_type="tool",
                prompt_id="prompt-012",
                server_name="test-server"
            )

            # Verify dialog WAS shown with correct options (expected behavior)
            mock_dialog_instance.request_confirmation.assert_called_once()
            call_args = mock_dialog_instance.request_confirmation.call_args
            dialog_options = call_args[0][3]  # Fourth positional arg is options
            assert dialog_options.show_always_allow is True  # call_type exists
            assert dialog_options.show_always_block is False

            # Verify ALLOW was recorded
            mock_record.assert_called_once()
            assert mock_record.call_args[0][2] == UserDecision.ALLOW


@pytest.mark.anyio
async def test_required_explicit_confirmation_user_blocks(handler):
    """
    Test required_explicit_user_confirmation: Dialog SHOULD be shown, user blocks

    Expected behavior:
    - Dialog displayed to user (policy requires explicit confirmation)
    - Dialog shows "Allow", "Always Allow", and "Block" options
    - User chooses "Block"
    - Operation blocked after user interaction
    - BLOCK decision recorded
    """

    decision = {
        "decision": "required_explicit_user_confirmation",
        "reasons": ["Sensitive operation requires confirmation"],
        "severity": "medium",
        "call_type": "execute"
    }

    # Mock dialog to simulate user blocking
    from modules.ui.classes import UserConfirmationError

    mock_dialog_instance = MagicMock()
    mock_dialog_instance.request_confirmation = MagicMock(
        side_effect=UserConfirmationError(
            "User blocked",
            event_id="test-013",
            is_request=True,
            tool_name="test_tool"
        )
    )

    with patch('modules.decision.decision_handler.UserConfirmationDialog', return_value=mock_dialog_instance):
        with patch.object(handler, '_record_user_confirmation', new_callable=AsyncMock) as mock_record:
            # Should raise
            with pytest.raises(DecisionEnforcementError):
                await handler.enforce_decision(
                    decision=decision,
                    is_request=True,
                    event_id="test-013",
                    tool_name="test_tool",
                    content_data={"arg": "value"},
                    operation_type="tool",
                    prompt_id="prompt-013",
                    server_name="test-server"
                )

            # Verify dialog WAS shown (expected behavior)
            mock_dialog_instance.request_confirmation.assert_called_once()

            # Verify BLOCK was recorded
            mock_record.assert_called_once()
            assert mock_record.call_args[0][2] == UserDecision.BLOCK


@pytest.mark.anyio
async def test_required_explicit_confirmation_no_call_type(handler):
    """
    Test required_explicit_user_confirmation without call_type: Dialog SHOULD be shown

    Expected behavior:
    - Dialog displayed to user (policy requires explicit confirmation)
    - Dialog shows only "Allow" and "Block" options (no "Always Allow" since call_type is None)
    - User chooses "Allow"
    - Operation proceeds after user confirmation
    - ALLOW decision recorded
    """

    decision = {
        "decision": "required_explicit_user_confirmation",
        "reasons": ["Sensitive operation requires confirmation"],
        "severity": "medium",
        "call_type": None
    }

    # Mock dialog to simulate user allowing
    from modules.ui.classes import ConfirmationResponse
    from datetime import datetime

    mock_dialog_instance = MagicMock()
    mock_response = ConfirmationResponse(
        user_decision=UserDecision.ALLOW,
        event_id="test-014",
        timestamp=datetime.now(),
        direction="request",
        call_type=None
    )
    mock_dialog_instance.request_confirmation = MagicMock(return_value=mock_response)

    with patch('modules.decision.decision_handler.UserConfirmationDialog', return_value=mock_dialog_instance):
        with patch.object(handler, '_record_user_confirmation', new_callable=AsyncMock) as mock_record:
            # Should not raise
            await handler.enforce_decision(
                decision=decision,
                is_request=True,
                event_id="test-014",
                tool_name="test_tool",
                content_data={"arg": "value"},
                operation_type="tool",
                prompt_id="prompt-014",
                server_name="test-server"
            )

            # Verify dialog WAS shown with correct options (expected behavior)
            mock_dialog_instance.request_confirmation.assert_called_once()
            call_args = mock_dialog_instance.request_confirmation.call_args
            dialog_options = call_args[0][3]  # Fourth positional arg is options
            assert dialog_options.show_always_allow is False  # call_type is None - no "Always Allow" option
            assert dialog_options.show_always_block is False


@pytest.mark.anyio
async def test_need_more_info_decision(handler):
    """
    Test need_more_info decision: NO dialog shown, actionable error message returned

    Expected behavior:
    - NO dialog displayed to user
    - Operation blocked immediately with actionable error message
    - Error message includes missing field names (mapped to wrapper field names)
    - Error message includes mandatory actions
    - NO user decision recorded (policy needs more info before making decision)
    """

    decision = {
        "decision": "need_more_info",
        "reasons": ["Security policy requires additional context"],
        "need_fields": ["context.agent.intent", "context.agent.plan"],
        "severity": "medium"
    }

    with patch.object(handler, '_record_user_confirmation', new_callable=AsyncMock) as mock_record:
        # Should raise with actionable error message
        with pytest.raises(DecisionEnforcementError) as exc_info:
            await handler.enforce_decision(
                decision=decision,
                is_request=True,
                event_id="test-015",
                tool_name="test_tool",
                content_data={"arg": "value"},
                operation_type="tool",
                prompt_id="prompt-015",
                server_name="test-server"
            )

        # Verify error message contains expected information
        error_msg = str(exc_info.value)
        assert "SECURITY POLICY NEEDS MORE INFORMATION" in error_msg
        assert "__wrapper_modelIntent" in error_msg
        assert "__wrapper_modelPlan" in error_msg
        assert "MANDATORY ACTIONS:" in error_msg

        # No recording should happen for need_more_info (expected behavior)
        mock_record.assert_not_called()


@pytest.mark.anyio
async def test_need_more_info_response_stage(handler):
    """
    Test need_more_info decision for response stage: NO dialog shown

    Expected behavior:
    - NO dialog displayed to user
    - Operation blocked immediately with actionable error message
    - Error message indicates "TOOL RESPONSE" stage (not "CLIENT REQUEST")
    - Error message includes missing field names
    - NO user decision recorded
    """

    decision = {
        "decision": "need_more_info",
        "reasons": ["Response analysis requires additional context"],
        "need_fields": ["context.workspace.current_files"],
        "severity": "low"
    }

    # Should raise with actionable error message for response
    with pytest.raises(DecisionEnforcementError) as exc_info:
        await handler.enforce_decision(
            decision=decision,
            is_request=False,  # Response stage
            event_id="test-016",
            tool_name="test_tool",
            content_data={"arg": "value"},
            operation_type="tool",
            prompt_id="prompt-016",
            server_name="test-server"
        )

    # Verify error message contains expected information
    error_msg = str(exc_info.value)
    assert "TOOL RESPONSE" in error_msg
    assert "__wrapper_currentFiles" in error_msg


@pytest.mark.anyio
async def test_missing_severity_field(handler):
    """Test that missing severity field defaults to 'unknown' (treated as high)"""

    decision = {
        "decision": "block",
        "reasons": ["Security violation"],
        # severity field missing
        "call_type": "write"
    }

    # With MIN_BLOCK_SEVERITY = critical, 'unknown' (as high) should be auto-allowed
    with patch('modules.decision.decision_handler.get_min_block_severity', return_value='critical'):
        with patch('modules.decision.decision_handler.get_allow_block_override', return_value=True):
            with patch.object(handler, '_record_user_confirmation', new_callable=AsyncMock) as mock_record:
                # Should not raise
                await handler.enforce_decision(
                    decision=decision,
                    is_request=True,
                    event_id="test-017",
                    tool_name="test_tool",
                    content_data={"arg": "value"},
                    operation_type="tool",
                    prompt_id="prompt-017",
                    server_name="test-server"
                )

                # Verify ALLOW was recorded
                mock_record.assert_called_once()
                assert mock_record.call_args[0][2] == UserDecision.ALLOW


@pytest.mark.anyio
async def test_empty_reasons_list(handler):
    """Test that empty reasons list defaults to generic message"""

    decision = {
        "decision": "block",
        "reasons": [],  # Empty reasons
        "severity": "high",
        "call_type": None
    }

    with patch('modules.decision.decision_handler.get_min_block_severity', return_value='low'):
        with patch('modules.decision.decision_handler.get_allow_block_override', return_value=False):
            with patch.object(handler, '_record_user_confirmation', new_callable=AsyncMock) as mock_record:
                # Should raise with default message
                with pytest.raises(DecisionEnforcementError) as exc_info:
                    await handler.enforce_decision(
                        decision=decision,
                        is_request=True,
                        event_id="test-018",
                        tool_name="test_tool",
                        content_data={"arg": "value"},
                        operation_type="tool",
                        prompt_id="prompt-018",
                        server_name="test-server"
                    )

                # Verify default reason is used
                error_msg = str(exc_info.value)
                assert "Policy violation" in error_msg


@pytest.mark.anyio
async def test_custom_error_message_prefix(handler):
    """Test custom error message prefix is used"""

    decision = {
        "decision": "block",
        "reasons": ["Security violation"],
        "severity": "high",
        "call_type": None
    }

    custom_prefix = "Custom Security Error"

    with patch('modules.decision.decision_handler.get_min_block_severity', return_value='low'):
        with patch('modules.decision.decision_handler.get_allow_block_override', return_value=False):
            with patch.object(handler, '_record_user_confirmation', new_callable=AsyncMock):
                # Should raise with custom prefix
                with pytest.raises(DecisionEnforcementError) as exc_info:
                    await handler.enforce_decision(
                        decision=decision,
                        is_request=True,
                        event_id="test-019",
                        tool_name="test_tool",
                        content_data={"arg": "value"},
                        operation_type="tool",
                        prompt_id="prompt-019",
                        server_name="test-server",
                        error_message_prefix=custom_prefix
                    )

                # Verify custom prefix is in error message
                error_msg = str(exc_info.value)
                assert custom_prefix in error_msg


@pytest.mark.anyio
async def test_all_severity_levels_with_matching_threshold(handler):
    """Test all severity levels when they match the minimum threshold exactly"""

    severities = ['low', 'medium', 'high', 'critical']

    for severity in severities:
        decision = {
            "decision": "block",
            "reasons": [f"{severity} severity violation"],
            "severity": severity,
            "call_type": None
        }

        # When MIN_BLOCK_SEVERITY matches the decision severity, it should block
        with patch('modules.decision.decision_handler.get_min_block_severity', return_value=severity):
            with patch('modules.decision.decision_handler.get_allow_block_override', return_value=False):
                with patch.object(handler, '_record_user_confirmation', new_callable=AsyncMock) as mock_record:
                    # Should raise
                    with pytest.raises(DecisionEnforcementError):
                        await handler.enforce_decision(
                            decision=decision,
                            is_request=True,
                            event_id=f"test-020-{severity}",
                            tool_name="test_tool",
                            content_data={"arg": "value"},
                            operation_type="tool",
                            prompt_id=f"prompt-020-{severity}",
                            server_name="test-server"
                        )

                    # Verify BLOCK was recorded
                    mock_record.assert_called_once()
                    assert mock_record.call_args[0][2] == UserDecision.BLOCK

