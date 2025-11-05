"""
CLI utilities for MCPower Proxy
"""
import argparse


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Transparent MCP wrapper with security middleware for real-time policy enforcement and monitoring.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single server config
  %(prog)s --wrapped-config '{"command": "npx", "args": ["@modelcontextprotocol/server-filesystem", "/path/to/allowed-dir"]}'
  
  # Named server config  
  %(prog)s --wrapped-config '{"my-server": {"command": "python", "args": ["server.py"], "env": {"DEBUG": "1"}}}'
  
  # MCPConfig format
  %(prog)s --wrapped-config '{"mcpServers": {"default": {"command": "node", "args": ["server.js"]}}}'
  
  # With custom name
  %(prog)s --wrapped-config '{"command": "node", "args": ["server.js"]}' --name MyWrapper
  
  # IDE Tools mode
  %(prog)s --ide-tool --ide cursor --context beforeShellExecution

Reference Links:
  • MCPower Proxy: https://github.com/ai-mcpower/mcpower-proxy
  • MCP Official: https://modelcontextprotocol.io
        """
    )

    parser.add_argument(
        '--ide-tool',
        action='store_true',
        help='Run in IDE tools mode'
    )

    parser.add_argument(
        '--ide',
        help='IDE name (required with --ide-tool, e.g., "cursor")'
    )

    parser.add_argument(
        '--context',
        help='Additional context (to be verified as optional by the associated --ide handler)'
    )

    parser.add_argument(
        '--wrapped-config',
        help='JSON/JSONC configuration for the wrapped MCP server (FastMCP will handle validation)'
    )

    parser.add_argument(
        '--name',
        default='MCPWrapper',
        help='Name for the wrapper MCP server (default: MCPWrapper)'
    )

    args = parser.parse_args()

    # Validate: either --ide-tool or --wrapped-config is required
    if not args.ide_tool and not args.wrapped_config:
        parser.error("either --ide-tool or --wrapped-config is required")

    # Validate: --ide-tool and --wrapped-config are mutually exclusive
    if args.ide_tool and args.wrapped_config:
        parser.error("--ide-tool and --wrapped-config are mutually exclusive")

    # Validate: --ide-tool requires --ide
    if args.ide_tool and not args.ide:
        parser.error("--ide-tool requires --ide argument")

    return args
