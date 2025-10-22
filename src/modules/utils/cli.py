"""
CLI utilities for MCPower Proxy
"""
import argparse


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="MCPower - Transparent 1:1 MCP Wrapper with security enforcement",
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
  • FastMCP Proxy: https://gofastmcp.com/servers/proxy
  • FastMCP Middleware: https://gofastmcp.com/servers/middleware  
  • MCP Official: https://modelcontextprotocol.io
  • Claude MCP Config: https://docs.anthropic.com/en/docs/claude-code/mcp
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