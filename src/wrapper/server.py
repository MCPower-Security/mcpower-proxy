"""
FastMCP-based wrapper server with ProxyClient integration
Implements transparent 1:1 MCP proxying with security middleware
"""

import logging

from fastmcp.server.middleware.logging import StructuredLoggingMiddleware
from fastmcp.server.proxy import ProxyClient, default_proxy_roots_handler, FastMCPProxy, StatefulProxyClient

from modules.logs.audit_trail import AuditTrailLogger
from modules.logs.logger import MCPLogger
from modules.utils.json import safe_json_dumps
from .__version__ import __version__
from .middleware import SecurityMiddleware


def create_wrapper_server(wrapper_server_name: str,
                          wrapped_server_configs: dict,
                          logger: MCPLogger,
                          audit_logger: AuditTrailLogger,
                          log_level: int = logging.INFO
                          ) -> FastMCPProxy:
    """
    Create a FastMCP wrapper server with security middleware and security-aware handlers
    
    Args:
        wrapper_server_name: Name for the wrapper MCP server
        wrapped_server_configs: FastMCP MCPConfig format dictionary
        api_url: URL of security policy API (defaults to config value)
        log_level: Logging level (e.g., logging.DEBUG, logging.INFO)
        logger: logger instance
        
    Returns:
        Configured FastMCPProxy server instance
    """

    # Create a security middleware instance first so we can use its handlers
    security_middleware = SecurityMiddleware(
        wrapped_server_configs=wrapped_server_configs,
        wrapper_server_name=wrapper_server_name,
        wrapper_server_version=__version__,
        logger=logger,
        audit_logger=audit_logger
    )

    # Log MCPower startup to audit trail
    audit_logger.log_event("mcpower_start", {
        "wrapper_version": __version__,
        "wrapped_server_name": security_middleware.wrapped_server_name,
        "wrapped_server_configs": wrapped_server_configs
    })

    # Create FastMCP server as proxy with our security-aware ProxyClient
    # Use StatefulProxyClient for remote servers (mcp-remote or url-based transports)
    config_str = safe_json_dumps(wrapped_server_configs)
    is_remote = '"@mcpower/mcp-remote",' in config_str or '"url":' in config_str
    backend_class = StatefulProxyClient if is_remote else ProxyClient
    backend = backend_class(
        wrapped_server_configs,
        name=wrapper_server_name,
        roots=default_proxy_roots_handler,  # Use default for filesystem roots
        sampling_handler=security_middleware.secure_sampling_handler,
        elicitation_handler=security_middleware.secure_elicitation_handler,
        log_handler=security_middleware.secure_log_handler,
        progress_handler=security_middleware.secure_progress_handler,
    )

    def client_factory():
        # we must return the same instance, otherwise StatefulProxyClient doesn't play nice with mcp-remote
        return backend

    server = FastMCPProxy(client_factory=client_factory, name=wrapper_server_name, version=__version__)

    # Add FastMCP's structured logging middleware (always enabled)
    # Use the log level passed from main.py
    logging_middleware = StructuredLoggingMiddleware(
        logger=logger.logger,
        log_level=log_level
    )
    server.add_middleware(logging_middleware)

    # Add security middleware (runs after logging)
    server.add_middleware(security_middleware)

    return server
