import * as vscode from "vscode";
import { ConfigurationMonitor } from "./configurationMonitor";
import { UvRunner } from "./uvRunner";

export interface ExtensionState {
    context: vscode.ExtensionContext;
    uvRunner: UvRunner;
    configMonitor: ConfigurationMonitor;
}

export interface MCPServerConfig {
    command: string;
    args?: string[];
    env?: Record<string, string>;
    disabled?: boolean;
    // backup of original, non-transformed configs;
    // this key won't be set unless configs are being transformed
    __bak_configs?: string;
}

export interface MCPConfig {
    mcpServers?: Record<string, MCPServerConfig>; // Traditional format
    servers?: Record<string, MCPServerConfig>; // VSCode format
    extensions?: Record<string, MCPServerConfig>; // another format
}

export interface UvCommand {
    executable: string;
    args: string[];
}
