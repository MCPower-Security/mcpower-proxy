/**
 * MCP Server Configuration Types
 * Ported from VSC extension for Claude Code plugin
 */

export interface MCPServerConfig {
    command: string;
    args?: string[];
    env?: Record<string, string>;
    disabled?: boolean;
    // Backup of original, non-transformed configs;
    // This key won't be set unless configs are being transformed
    __bak_configs?: string;
}

export interface MCPConfig {
    mcpServers?: Record<string, MCPServerConfig>; // Traditional format
    servers?: Record<string, MCPServerConfig>; // VSCode format
    extensions?: Record<string, MCPServerConfig>; // Another format
}

export interface UvCommand {
    executable: string;
    args: string[];
}
