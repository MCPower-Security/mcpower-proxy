import * as vscode from "vscode";
import { ConfigurationMonitor } from "./configurationMonitor";
import { ExecutableManager } from "./executableManager";

export interface ExtensionState {
    context: vscode.ExtensionContext;
    executableManager: ExecutableManager;
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

export interface PlatformInfo {
    platform: "win32" | "darwin" | "linux";
    arch: string;
    executableName: string;
    executablePath: string;
}
