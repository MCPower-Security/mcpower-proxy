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
}

export interface MCPConfig {
    mcpServers?: Record<string, MCPServerConfig>; // Traditional format
    servers?: Record<string, MCPServerConfig>; // VSCode format
    extensions?: Record<string, MCPServerConfig>; // another format
}

export interface UvCommand {
    executable: string;
    args: string[];
    repoUrl: string;
}
