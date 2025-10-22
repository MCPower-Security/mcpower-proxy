from fastmcp import mcp_config


def extract_wrapped_server_info(wrapper_server_name, logger, configs: dict) -> tuple[str, str]:
    """
    Extract wrapped server name and transport using FastMCP utilities

    Returns:
        tuple: (server_name, transport_name)
    """
    try:
        # Parse config using FastMCP's built-in utilities
        parsed_config = mcp_config.MCPConfig.from_dict(configs)

        # Get the first server (the most common case - single wrapped server)
        first_server = list(parsed_config.mcpServers.values())[0]
        first_server_key = list(parsed_config.mcpServers.keys())[0]

        # Extract server name
        # If the key is "default" (from raw config conversion) - use the wrapper name
        if first_server_key == "default":
            server_name = wrapper_server_name
        else:
            server_name = first_server_key

        # Extract transport using FastMCP's transport resolution
        transport_obj = first_server.to_transport()
        transport_class = type(transport_obj).__name__

        # Map FastMCP transport classes to simple string names
        transport_mapping = {
            'StdioTransport': 'stdio',
            'StreamableHttpTransport': 'streamable-http',
            'SSETransport': 'sse',
            'WSTransport': 'ws',
        }

        wrapped_server_transport_name = transport_mapping.get(transport_class,
                                                              transport_class.lower().replace('transport', ''))

        logger.debug(f"Extracted wrapped server info: name={server_name}, "
                     f"transport={wrapped_server_transport_name}")

        return server_name, wrapped_server_transport_name

    except Exception as e:
        logger.error(f"Failed to extract wrapped server info: {e}")
        raise e
