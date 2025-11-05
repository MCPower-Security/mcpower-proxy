#!/usr/bin/env python3
"""
MCPower Proxy - Main Entry Point

A transparent 1:1 MCP Wrapper that sits between an AI client and a Wrapped MCP,
intercepting 100% of MCP traffic and enforcing security policies.
"""

import json
import logging
import sys

from modules.logs.audit_trail import setup_audit_trail_logger
from modules.logs.logger import setup_logger
from modules.utils.cli import parse_args
from modules.utils.config import get_log_path, is_debug_mode, config, ConfigManager
from modules.utils.json import parse_jsonc
from wrapper.server import create_wrapper_server


def main():
    """Main entry point"""
    args = parse_args()

    # Read config values
    log_file = get_log_path()
    debug_mode = is_debug_mode()

    # Setup logging
    log_level = logging.DEBUG if debug_mode else logging.INFO
    logger = setup_logger(log_file, log_level)

    if log_level == logging.DEBUG:
        logger.info('')
        logger.info('=' * 66)
        logger.info('⚠️  WARNING: DEBUG MODE ENABLED - SENSITIVE DATA LOGGING ACTIVE  ⚠️')
        logger.info('=' * 66)
        logger.info('')
        logger.info(f'DEBUG logs might include sensitive chat/context information')
        logger.info(f'and WILL be saved to: {log_file}')
        logger.info('')
        logger.info(f'To disable debug mode, set it to "0" or "false" in configs:')
        logger.info(f'{str(ConfigManager.get_config_path())}')
        logger.info('')
        logger.info('=' * 66)
        logger.info('')

    # Setup audit trail logging
    audit_logger = setup_audit_trail_logger(logger)

    if args.ide_tool:
        from ide_tools.router import main as ide_tools_main
        ide_tools_main(logger, audit_logger, args.ide, args.context)
        return

    # Continue with MCP wrapper mode
    # Start config monitoring
    config.start_monitoring(logger)

    logger.info(
        f"Starting MCPower Proxy:\n{{'args': {args}, 'log_file': {log_file}, 'log_level': {log_level}, 'debug_mode': {debug_mode}}}")

    try:
        # Parse JSON/JSONC config
        logger.info("Parsing wrapped MCP configuration...")
        try:
            raw_wrapped_mcp_config = parse_jsonc(args.wrapped_config)
            logger.debug(f"Parsed JSONC config successfully")

            # Convert to clean JSON for FastMCP (which expects standard JSON)
            clean_json_config = json.loads(json.dumps(raw_wrapped_mcp_config))
            raw_wrapped_mcp_config = clean_json_config

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON/JSONC in --wrapped-config: {e}")
            sys.exit(1)

        # Convert to FastMCP MCPConfig format if needed
        # Check if it's already in MCPConfig format (has mcpServers key)
        if "mcpServers" in raw_wrapped_mcp_config:
            wrapped_mcp_config = raw_wrapped_mcp_config
        else:
            # Convert single server config to MCPConfig format
            wrapped_mcp_config = {
                "mcpServers": {
                    "default": raw_wrapped_mcp_config
                }
            }

        logger.debug(f"Using MCP config: {wrapped_mcp_config}")

        # Create and start wrapper server
        logger.info(f"Starting MCP Wrapper '{args.name}'")
        server = create_wrapper_server(
            wrapper_server_name=args.name,
            wrapped_server_configs=wrapped_mcp_config,
            log_level=log_level,
            logger=logger,
            audit_logger=audit_logger
        )

        # Run server on STDIO
        logger.info("MCPower server starting on STDIO...")
        server.run(show_banner=False)
    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


def cli_main():
    """Entry point for console script"""
    main()


if __name__ == "__main__":
    main()
