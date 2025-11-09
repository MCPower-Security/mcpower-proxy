import { basename, dirname, join, normalize, resolve } from "path";
import { promises as fs } from "fs";
import { homedir } from "os";
import { createHash } from "crypto";
import { UvRunner } from "../uvRunner";
import { detectIDEFromScriptPath } from "../utils";
import * as JSONC from "jsonc-parser";
import log from "../log";
import { fileExists, isRemoteUrl, parseJsonc, writeFile } from "@mcpower/common-ts/utils";
import { FileWatcher } from "@mcpower/common-ts/watcher";
import { MCPConfig, MCPServerConfig } from "@mcpower/common-ts/types";

export class ConfigurationMonitor {
    private uvRunner: UvRunner | undefined;
    private vscode: typeof import("vscode") | undefined;
    private fileWatcher: FileWatcher;
    private isMonitoring: boolean = false;
    private readonly currentIDE: string | undefined;

    constructor() {
        this.currentIDE = detectIDEFromScriptPath();

        // Create file watcher with callbacks
        this.fileWatcher = new FileWatcher({
            onFileProcess: async (filePath: string) => {
                await this.processConfigurationFile(filePath);
            },
            onShowError: (message: string) => {
                this.vscode?.window.showErrorMessage(message);
            },
            logger: log,
        });
    }

    /**
     * Get current IDE identifier
     */
    getCurrentIDE(): string | undefined {
        return this.currentIDE;
    }

    /**
     * Get IDE-specific registry directory
     */
    public getMcpsDir = (): string => {
        if (!this.currentIDE) {
            throw new Error("Cannot determine IDE - registry operations not safe");
        }
        return join(homedir(), ".mcpower", ".wrapped_mcps", this.currentIDE);
    };

    /**
     * Generate symlink name for registry
     */
    private getSymlinkName(configPath: string): string {
        const normalized = normalize(configPath);
        const hash = createHash("md5").update(normalized).digest("hex").substring(0, 8);
        const basenamePart = basename(normalized, ".json");
        const dirnamePart = basename(dirname(normalized));
        return `${dirnamePart}_${basenamePart}_${hash}.json`;
    }

    /**
     * Add a wrapped file to IDE-specific registry
     */
    private async addWrappedFile(configPath: string): Promise<void> {
        const mcpsDir = this.getMcpsDir();
        const symlinkName = this.getSymlinkName(configPath);
        const symlinkPath = join(mcpsDir, symlinkName);

        try {
            await fs.mkdir(mcpsDir, { recursive: true });
            // Create symlink atomically
            await fs.symlink(configPath, symlinkPath);
        } catch (error: any) {
            if (error.code === "EEXIST") {
                // Symlink already exists - verify it points to same target
                try {
                    const existingTarget = await fs.readlink(symlinkPath);
                    if (resolve(existingTarget) !== resolve(configPath)) {
                        await fs.unlink(symlinkPath);
                        await fs.symlink(configPath, symlinkPath);
                    }
                } catch {
                    // If verification fails, just ignore - symlink exists
                }
            }
            // Non-critical - don't fail if registry update fails
        }
    }

    /**
     * Get wrapped files for CURRENT IDE only
     */
    private async getWrappedFiles(): Promise<string[]> {
        try {
            const mcpsDir = this.getMcpsDir();
            const entries = await fs.readdir(mcpsDir);
            const wrappedFiles: string[] = [];

            for (const entry of entries) {
                try {
                    const symlinkPath = join(mcpsDir, entry);
                    const targetPath = await fs.readlink(symlinkPath);

                    if (await fileExists(targetPath)) {
                        wrappedFiles.push(resolve(targetPath));
                    } else {
                        // Clean up broken symlink
                        await fs.unlink(symlinkPath).catch(() => {}); // Ignore cleanup errors
                    }
                } catch {
                    // Skip invalid entries silently
                }
            }

            return [...new Set(wrappedFiles)]; // Remove duplicates
        } catch {
            // Return empty array for any error
            return [];
        }
    }

    /**
     * Remove wrapped file from registry
     */
    private async removeWrappedFile(configPath: string): Promise<void> {
        try {
            const symlinkPath = join(this.getMcpsDir(), this.getSymlinkName(configPath));
            await fs.unlink(symlinkPath);
        } catch {
            // Ignore errors - file may not exist or already removed
        }
    }

    /**
     * Get all files this IDE instance should unwrap (registry + system paths)
     */
    async getAllWrappedFiles(): Promise<string[]> {
        const allFiles = new Set<string>();

        // 1. Get files from current IDE's registry
        const registryFiles = await this.getWrappedFiles();
        registryFiles.forEach(file => allFiles.add(file));

        // 2. Add system paths for current IDE only (inline to avoid wrapper function)
        if (this.currentIDE) {
            const systemPaths = this.getSystemPaths(homedir());
            const currentIDEPaths = systemPaths[this.currentIDE] || [];

            for (const systemPath of currentIDEPaths) {
                if (await fileExists(systemPath)) {
                    allFiles.add(systemPath);
                }
            }
        }

        return Array.from(allFiles);
    }

    /**
     * Sleep utility for async operations
     */
    private sleep(ms: number): Promise<void> {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    /**
     * Check multiple file paths in parallel and return existing ones
     */
    private async findExistingFiles(
        paths: string[],
        clientType: string,
        context: string
    ): Promise<string[]> {
        const existenceChecks = await Promise.allSettled(
            paths.map(async configPath => ({
                path: configPath,
                exists: await fileExists(configPath),
            }))
        );

        const existingFiles: string[] = [];
        for (const result of existenceChecks) {
            if (result.status === "fulfilled" && result.value.exists) {
                existingFiles.push(result.value.path);
                log.debug(
                    `Found ${context} config for ${clientType}: ${result.value.path}`
                );
            }
        }
        return existingFiles;
    }

    /**
     * Get standard system paths for different AI clients
     */
    private getSystemPaths(homeDir: string): Record<string, string[]> {
        const createPaths = (appName: string, subPaths: string[] = []) => [
            join(homeDir, `.${appName.toLowerCase()}`, "mcp.json"),
            ...subPaths.map(subPath => join(homeDir, subPath, "mcp.json")),
        ];

        // Common app support patterns for macOS/Windows
        const appSupportPaths = (appName: string) => [
            join("Library", "Application Support", appName, "User"), // macOS
            join("AppData", "Roaming", appName, "User"), // Windows
        ];

        return {
            kiro: createPaths("kiro", [join(".kiro", "settings")]),
            cursor: createPaths("cursor", appSupportPaths("Cursor")),
            windsurf: createPaths("windsurf", appSupportPaths("Windsurf")),
            claude: createPaths("claude", [
                join("Library", "Application Support", "Claude"), // macOS (no User subdir)
                join("AppData", "Roaming", "Claude"), // Windows (no User subdir)
            ]),
            vscode: createPaths("vscode", appSupportPaths("Code")),
            cline: createPaths("cline", appSupportPaths("Cline")),
        };
    }

    /**
     * Start monitoring MCP configuration files
     */
    async startMonitoring(uvRunner: UvRunner): Promise<void> {
        if (this.isMonitoring) {
            return;
        }

        // Import VS Code APIs directly (we're in extension context)
        this.vscode = await import("vscode");
        this.uvRunner = uvRunner;
        this.isMonitoring = true;

        try {
            log.info("Starting MCP configuration monitoring...");

            // Discover configuration files
            const configFiles = await this.discoverConfigurationFiles();

            // Start file watcher
            await this.fileWatcher.startWatching(configFiles);

            // Process existing configuration files on startup with tracking
            for (const configFile of configFiles) {
                const normalizedPath = normalize(resolve(configFile));
                if (!this.fileWatcher.isProcessing(normalizedPath)) {
                    await this.processConfigurationFile(configFile);
                }
            }
        } catch (error) {
            log.error("Failed to start MCP configuration monitoring", error);
            await this.stopMonitoring();
        }
    }

    /**
     * Stop monitoring and cleanup watchers
     */
    async stopMonitoring(): Promise<void> {
        if (!this.isMonitoring) {
            return;
        }

        log.info("Stopping MCP configuration monitoring...");

        await this.fileWatcher.stopWatching();
        this.fileWatcher.cleanupAllState();

        this.isMonitoring = false;
        log.info("Configuration monitoring stopped");
    }

    /**
     * Handle workspace folder changes
     */
    async handleWorkspaceChange(): Promise<void> {
        log.info("Workspace changed - re-establishing MCP configuration monitoring...");

        try {
            // Wait for all processing to complete with timeout
            log.debug("Waiting for all processing to complete...");
            const startTime = Date.now();

            // Wait for fileWatcher to finish processing (checking if any files are being processed)
            await this.sleep(3000);

            // Stop current monitoring
            await this.stopMonitoring();

            // Restart monitoring with new workspace
            if (!this.uvRunner) {
                // noinspection ExceptionCaughtLocallyJS
                throw new Error("UvRunner not available for workspace change");
            }
            await this.startMonitoring(this.uvRunner);

            log.info("✅ Successfully re-established monitoring for new workspace");
        } catch (error) {
            log.error("Failed to re-establish monitoring after workspace change", error);
            this.vscode?.window.showErrorMessage(
                `Failed to update MCP monitoring for new workspace: ${error}`
            );
        }
    }

    /**
     * Discover MCP configuration files in workspace and system locations
     */
    private async discoverConfigurationFiles(): Promise<string[]> {
        const configs: string[] = [];
        const aiClientType = this.detectAIClientType();

        /**
         * Find MCP configuration files in workspace
         */
        if (this.vscode?.workspace.workspaceFolders) {
            for (const folder of this.vscode.workspace.workspaceFolders) {
                const workspacePath = folder.uri.fsPath;

                // Generic workspace configs (always included)
                const genericPaths = [
                    join(workspacePath, "mcp.json"),
                    join(workspacePath, ".mcp.json"),
                ];

                // Client-specific workspace configs (only for detected AI client)
                const getClientWorkspacePath = (clientName: string, subdir?: string) =>
                    join(workspacePath, `.${clientName}`, subdir || "", "mcp.json");

                const clientPaths: Record<string, string[]> = {
                    kiro: [getClientWorkspacePath("kiro", "settings")],
                    cursor: [getClientWorkspacePath("cursor")],
                    windsurf: [getClientWorkspacePath("windsurf")],
                    claude: [getClientWorkspacePath("claude")],
                    vscode: [getClientWorkspacePath("vscode")],
                    cline: [getClientWorkspacePath("cline")],
                };
                const clientSpecificPaths = clientPaths[aiClientType] || [];

                // Check all paths in parallel for better performance
                const allPaths = [...new Set([...genericPaths, ...clientSpecificPaths])];
                const workspaceConfigs = await this.findExistingFiles(
                    allPaths,
                    aiClientType,
                    "workspace"
                );
                configs.push(...workspaceConfigs);
            }
        }

        /**
         * Find system-wide MCP configuration files
         */
        const systemPaths = this.getSystemPaths(homedir());
        const systemConfigPaths = systemPaths[aiClientType] || [];
        const systemConfigs = await this.findExistingFiles(
            systemConfigPaths,
            aiClientType,
            "system"
        );
        configs.push(...systemConfigs);

        // Deduplicate paths (multiple workspaces can add the same file twice)
        return Array.from(new Set(configs.map(p => normalize(resolve(p)))));
    }

    /**
     * Detect the AI client type based on VS Code variant
     * Enhanced with multiple detection methods and proper logging
     */
    private detectAIClientType(): string {
        const extensionHost = this.vscode?.env.appName?.toLowerCase() ?? "_unknown";
        const executablePath = process.execPath.toLowerCase();

        log.debug(
            `Detecting AI client: appName="${this.vscode?.env.appName ?? "_unknown"}", execPath="${process.execPath}"`
        );

        // Define client patterns for DRY detection
        const clientPatterns = [
            { name: "cursor", patterns: ["cursor"] },
            { name: "windsurf", patterns: ["windsurf"] },
            { name: "claude", patterns: ["claude"] },
            { name: "kiro", patterns: ["kiro"] },
            { name: "cline", patterns: ["cline"] },
            {
                name: "vscode",
                patterns: [
                    "autopilot",
                    "github copilot",
                    "visual studio code",
                    "code",
                    "vscode",
                ],
            },
        ];

        // Check app name first
        for (const client of clientPatterns) {
            for (const pattern of client.patterns) {
                if (extensionHost.includes(pattern) || extensionHost === pattern) {
                    log.debug(
                        `Detected AI client: ${client.name} (via appName - ${pattern})`
                    );
                    return client.name;
                }
            }
        }

        // Fallback to executable path
        for (const client of clientPatterns) {
            for (const pattern of client.patterns) {
                if (executablePath.includes(pattern)) {
                    log.debug(
                        `Detected AI client: ${client.name} (via execPath - ${pattern})`
                    );
                    return client.name;
                }
            }
        }

        // Log detection failure for debugging
        log.warn(
            `Could not detect AI client type. appName: ${extensionHost}, execPath: ${executablePath}`
        );
        log.warn(
            'Defaulting to "unknown" - will not modify any client-specific configurations'
        );

        // Conservative default - don't modify anything if we can't detect
        return "unknown";
    }

    /**
     * Extract raw JSONC string from wrapped server configuration (or backup)
     * Returns the original JSONC string (with comments) for file reconstruction
     */
    private extractRawWrappedConfig(serverConfig: MCPServerConfig): string | undefined {
        if (!this.isAlreadyWrapped(serverConfig)) {
            return undefined; // Not wrapped
        }

        // if a backup key exists - use it as-is
        if (serverConfig.__bak_configs) {
            return serverConfig.__bak_configs;
        }

        // Find --wrapped-config argument
        const wrappedConfigIndex = serverConfig.args?.indexOf("--wrapped-config");
        if (
            wrappedConfigIndex === undefined ||
            wrappedConfigIndex === -1 ||
            !serverConfig.args?.[wrappedConfigIndex + 1]
        ) {
            throw new Error(
                `Invalid wrapped configuration: missing --wrapped-config argument`
            );
        }

        // Return the RAW JSONC string (preserving comments and formatting)
        return serverConfig.args[wrappedConfigIndex + 1];
    }

    /**
     * Convert URL-based MCP config to @mcpower/mcp-remote args array
     */
    private convertUrlConfigToMcpRemoteArgs(
        urlConfig: any,
        serverName: string
    ): string[] {
        const args: string[] = ["-y", "@mcpower/mcp-remote", urlConfig.url];

        if (serverName) {
            args.push("--server-name", serverName);
        }

        // Convert headers to --header flags
        if (!!urlConfig.headers && typeof urlConfig.headers === "object") {
            for (const [key, value] of Object.entries(urlConfig.headers)) {
                args.push("--header", `${key}: ${value}`);
            }
        }

        return args;
    }

    /**
     * Shared helper for JSONC tree-based configuration processing
     * DRY principle: consolidates common file reading, parsing, and writing logic
     */
    private async processConfigurationWithJsoncTree(
        configPath: string,
        processor: (
            content: string,
            config: MCPConfig,
            serverKey: keyof MCPConfig,
            servers: Record<string, MCPServerConfig>
        ) => Promise<{
            modifiedContent: string;
            hasChanges: boolean;
            successMessage: string;
        }>
    ): Promise<boolean> {
        try {
            // Read raw JSONC content
            const content = await fs.readFile(configPath, "utf8");

            // Parse only to detect master key (top level only)
            const config = parseJsonc(content) as MCPConfig;
            const serverKey = this.getMcpServersKey(config);
            if (!serverKey) {
                return false; // No servers to process
            }

            const servers = config[serverKey] || {};

            // Process with the provided function
            const result = await processor(content, config, serverKey, servers);

            // Write modified content if changes were made
            if (result.hasChanges) {
                await writeFile(configPath, result.modifiedContent);
                // Record write to prevent processing loop
                this.fileWatcher.recordWrite(configPath);
                log.info(`${result.successMessage}: ${configPath}`);
            }

            return result.hasChanges;
        } catch (error) {
            log.error(`Failed to process configuration ${configPath}:`, error);
            return false;
        }
    }

    /**
     * Unwrap configuration using JSONC tree manipulation to preserve comments
     */
    async unwrapConfigurationInFile(configPath: string): Promise<boolean> {
        const wasUnwrapped = await this.processConfigurationWithJsoncTree(
            configPath,
            async (content, config, serverKey, servers) => {
                let modifiedContent = content;
                let hasChanges = false;

                // Process each server for unwrapping
                for (const [serverName, serverConfig] of Object.entries(servers)) {
                    // Skip if not wrapped
                    if (!this.isAlreadyWrapped(serverConfig)) {
                        continue;
                    }

                    // Get the raw JSONC from --wrapped-config
                    const rawConfig = this.extractRawWrappedConfig(serverConfig);
                    if (!rawConfig) {
                        log.warn(
                            `Failed to extract raw config for server ${serverName}, skipping`
                        );
                        continue; // Skip this server, keep as-is
                    }

                    // Use direct string replacement to preserve ALL comments
                    try {
                        // Find the wrapped server node in the current content
                        const parseTree = JSONC.parseTree(modifiedContent);
                        if (!parseTree) {
                            continue;
                        }
                        const serverNode = JSONC.findNodeAtLocation(parseTree, [
                            serverKey,
                            serverName,
                        ]);
                        if (
                            !serverNode ||
                            serverNode.offset === undefined ||
                            serverNode.length === undefined
                        ) {
                            continue;
                        }

                        // Replace wrapped server with raw JSONC string (preserving ALL comments!)
                        const before = modifiedContent.substring(0, serverNode.offset);
                        const after = modifiedContent.substring(
                            serverNode.offset + serverNode.length
                        );

                        // Restore raw config exactly as it was saved during wrapping
                        modifiedContent = before + rawConfig + after;
                        hasChanges = true;
                    } catch (error) {
                        log.warn(`Failed to unwrap server ${serverName}:`, error);
                        // Skip this server, keep as-is
                    }
                }

                return {
                    modifiedContent,
                    hasChanges,
                    successMessage: "🔓 Unwrapped configuration with comments preserved",
                };
            }
        );

        // Remove from registry if unwrapping was successful
        if (wasUnwrapped) {
            await this.removeWrappedFile(configPath);
        }

        return wasUnwrapped;
    }

    /**
     * Process a single configuration file
     * Note: Circuit breaker and concurrency control are handled by FileWatcher
     */
    private async processConfigurationFile(configPath: string): Promise<void> {
        log.info(`Processing configuration file:\n${configPath}`);

        // Read and parse configuration
        const config = await this.readConfiguration(configPath);
        if (!config) {
            return;
        }

        // Wrap MCP servers with MCPower proxy using JSONC tree manipulation
        const hasChanges = await this.wrapConfigurationInFile(configPath);
        if (!hasChanges) {
            log.debug(`✅ All servers already wrapped in: ${configPath}`);
        }

        log.info(`Successfully processed configuration: ${configPath}`);
    }

    /**
     * Read and parse MCP configuration file
     */
    private async readConfiguration(configPath: string): Promise<MCPConfig | undefined> {
        try {
            const content = await fs.readFile(configPath, "utf8");
            return parseJsonc(content) as MCPConfig;
        } catch (error) {
            if (error instanceof SyntaxError) {
                log.error(`Invalid JSON/JSONC in ${configPath}`, error);
                this.vscode?.window.showErrorMessage(
                    `Configuration file has invalid JSON/JSONC: ${configPath}\nPlease fix the JSON/JSONC syntax and save the file.`
                );
            } else {
                log.error(`Failed to read configuration ${configPath}`, error);
            }
            return undefined;
        }
    }

    /**
     * Get the master key for MCP servers in this configuration
     */
    private getMcpServersKey(config: MCPConfig): keyof MCPConfig | undefined {
        // prioritized
        if (config.mcpServers !== undefined) {
            return "mcpServers";
        }
        if (config.servers !== undefined) {
            return "servers";
        }
        if (config.extensions !== undefined) {
            return "extensions";
        }
        log.warn("Invalid MCP configs; missing 'mcpServers'/'servers'/'extensions'");
        return undefined;
    }

    /**
     * Check if a server configuration is already wrapped by our MCPower proxy
     * Uses presence of wrapped config args as sufficient indicator
     */
    private isAlreadyWrapped(serverConfig: MCPServerConfig): boolean {
        const hasArg = serverConfig.args?.includes("--wrapped-config");
        if (hasArg) {
            log.debug("Server already wrapped (arg detected).");
        }
        return Boolean(hasArg);
    }

    /**
     * Wrap MCP configuration using JSONC tree manipulation to preserve comments
     * Also handles version migration for already-wrapped servers
     */
    async wrapConfigurationInFile(configPath: string): Promise<boolean> {
        if (!this.uvRunner) {
            log.error(
                "Cannot wrap configuration: uv runner not initialized. Call startMonitoring() first."
            );
            return false;
        }

        const uvCommand = this.uvRunner.getCommand();
        const expectedFirstArg = uvCommand.args[0]; // mcpower-proxy==X.Y.Z

        const result = await this.processConfigurationWithJsoncTree(
            configPath,
            async (content, config, serverKey, servers) => {
                let modifiedContent = content;
                let hasChanges = false;

                // Process each server for wrapping or version migration
                for (const [serverName, serverConfig] of Object.entries(servers)) {
                    const isWrapped = this.isAlreadyWrapped(serverConfig);

                    // Check if version matches current extension version
                    const hasCorrectVersion =
                        isWrapped && serverConfig.args?.[0] === expectedFirstArg;

                    // Skip only if already wrapped AND has correct version
                    if (hasCorrectVersion) {
                        continue;
                    }

                    // Need to wrap or re-wrap (version migration)
                    let rawServerJsonc: string;
                    let backupConfig: string | undefined;

                    if (isWrapped) {
                        // Extract raw config from wrapped server for re-wrapping
                        log.info(
                            `Re-wrapping server ${serverName} for version migration`
                        );
                        const extracted = this.extractRawWrappedConfig(serverConfig);
                        if (!extracted) {
                            log.warn(
                                `Failed to extract raw config for server ${serverName}, skipping`
                            );
                            continue;
                        }
                        rawServerJsonc = extracted;

                        backupConfig = serverConfig.__bak_configs;
                    } else {
                        // First-time wrapping: extract current server config

                        // Find server node in tree
                        const parseTree = JSONC.parseTree(modifiedContent);
                        if (!parseTree) {
                            continue;
                        }
                        const serverNode = JSONC.findNodeAtLocation(parseTree, [
                            serverKey,
                            serverName,
                        ]);
                        if (
                            !serverNode ||
                            serverNode.offset === undefined ||
                            serverNode.length === undefined
                        ) {
                            continue;
                        }

                        // Extract raw JSONC string AS-IS (zero manipulations!)
                        rawServerJsonc = modifiedContent.substring(
                            serverNode.offset,
                            serverNode.offset + serverNode.length
                        );
                    }

                    // Check if this is a URL-based config that needs mcp-remote wrapping
                    try {
                        const parsedConfig = parseJsonc(rawServerJsonc);

                        if (parsedConfig.url && isRemoteUrl(parsedConfig.url)) {
                            log.info(
                                `Server ${serverName} has remote URL, wrapping with @mcpower/mcp-remote`
                            );

                            // backup original, non @mcpower/mcp-remote transformed configs
                            backupConfig ||= rawServerJsonc;

                            const mcpRemoteArgs = this.convertUrlConfigToMcpRemoteArgs(
                                parsedConfig,
                                serverName
                            );
                            const mcpRemoteConfig = {
                                command: "npx",
                                args: mcpRemoteArgs,
                                env: parsedConfig.env,
                            };

                            rawServerJsonc = JSON.stringify(mcpRemoteConfig);
                        }
                    } catch (error) {
                        log.warn(
                            `Config is not URL-based or parsing failed for ${serverName}, proceeding with standard wrapping`
                        );
                    }

                    // Create wrapped configuration
                    const wrappedConfig: MCPServerConfig = {
                        command: uvCommand.executable,
                        args: [
                            ...uvCommand.args,
                            "--wrapped-config",
                            rawServerJsonc, // Save entire value AS-IS!
                            "--name",
                            serverName,
                        ],
                        env: serverConfig.env,
                        disabled: serverConfig.disabled,
                        __bak_configs: backupConfig,
                    };

                    // Use JSONC.modify to replace server with wrapped config
                    const edits = JSONC.modify(
                        modifiedContent,
                        [serverKey, serverName],
                        wrappedConfig,
                        {
                            formattingOptions: { insertSpaces: true, tabSize: 2 },
                        }
                    );
                    modifiedContent = JSONC.applyEdits(modifiedContent, edits);
                    hasChanges = true;
                }

                return {
                    modifiedContent,
                    hasChanges,
                    successMessage: "🔧 Wrapped servers in",
                };
            }
        );

        // Register wrapped file in IDE-specific registry if changes were made
        if (result) {
            await this.addWrappedFile(configPath);
        }

        return result;
    }
}
