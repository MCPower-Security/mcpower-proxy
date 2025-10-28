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

Reference Links:
  • MCPower Proxy: https://github.com/ai-mcpower/mcpower-proxy
  • MCP Official: https://modelcontextprotocol.io
        """
    )

    parser.add_argument(
        '--wrapped-config',
        required=True,
        help='JSON/JSONC configuration for the wrapped MCP server (FastMCP will handle validation)'
    )

    parser.add_argument(
        '--name',
        default='MCPWrapper',
        help='Name for the wrapper MCP server (default: MCPWrapper)'
    )

    return parser.parse_args()