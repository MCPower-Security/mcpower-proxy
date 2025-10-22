import { basename, dirname, join, normalize, resolve } from "path";
import { promises as fs } from "fs";
import { homedir } from "os";
import { createHash } from "crypto";
import chokidar from "chokidar";
import { UvRunner } from "../uvRunner";
import { MCPConfig, MCPServerConfig } from "../types";
import { fileExists, parseJsonc, writeFile } from "../utils";
import * as JSONC from "jsonc-parser";
import log from "../log";

export class ConfigurationMonitor {
    private uvRunner: UvRunner | undefined;
    private vscode: typeof import("vscode") | undefined;
    private chokidarWatcher: chokidar.FSWatcher | undefined;
    private isMonitoring: boolean = false;

    // Separate concerns: concurrency vs loop prevention
    private processingFiles: Set<string> = new Set(); // For concurrency control
    private recentWrites: Map<string, number> = new Map(); // For loop prevention
    private readonly pollingInterval = 2000; // Poll every 2 seconds
    private readonly writeIgnoreWindow = this.pollingInterval + 1500; // >= interval

    private watchedFiles: Set<string> = new Set();
    private reconnectAttempts: number = 0;
    private readonly maxReconnectAttempts: number = 3;
    private readonly reconnectDelay: number = 2000;

    // Improved circuit breaker
    private processingCounts: Map<string, number> = new Map();
    private circuitBreakerExpiry: Map<string, number> = new Map();
    private readonly maxProcessingPerFile = 3;
    private readonly circuitBreakerCooldown = 60000; // 1 minute

    // Watcher recreation protection
    private isRecreatingWatcher = false;
    private recoveryTimeout: NodeJS.Timeout | undefined;

    // Debouncing for rapid changes
    private pendingChanges: Map<string, NodeJS.Timeout> = new Map();
    private readonly debounceDelay = 300; // 300ms debounce
    private readonly currentIDE: string | undefined;

    constructor() {
        this.currentIDE = this.detectIDEFromScriptPath();
    }

    /**
     * Detect IDE from script path - works in uninstall script context
     */
    detectIDEFromScriptPath(): string | undefined {
        const scriptPath = __dirname.toLowerCase();

        // Standard extension directory patterns
        const idePatterns = [
            {
                name: "cursor",
                patterns: [
                    "/.cursor/extensions/",
                    "\\.cursor\\extensions\\",
                    "/cursor.app/",
                ],
            },
            {
                name: "windsurf",
                patterns: [
                    "/.windsurf/extensions/",
                    "\\.windsurf\\extensions\\",
                    "/windsurf.app/",
                ],
            },
            {
                name: "kiro",
                patterns: ["/.kiro/extensions/", "\\.kiro\\extensions\\", "/kiro.app/"],
            },
            {
                name: "cline",
                patterns: ["/.cline/extensions/", "\\.cline\\extensions\\"],
            },
            {
                name: "claude",
                patterns: ["/.claude/extensions/", "\\.claude\\extensions\\"],
            },
            {
                name: "vscode",
                patterns: [
                    "/.vscode/extensions/",
                    "\\.vscode\\extensions\\",
                    "/visual studio code.app/",
                    "/code.app/",
                ],
            },
        ];

        for (const ide of idePatterns) {
            for (const pattern of ide.patterns) {
                if (scriptPath.includes(pattern)) {
                    return ide.name;
                }
            }
        }

        return undefined; // Cannot determine IDE - fail safely
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
     * Clean up all state for a specific file path
     */
    private cleanupFileState(
        normalizedPath: string,
        options: {
            clearProcessing?: boolean;
            clearPending?: boolean;
            clearWatched?: boolean;
        } = {}
    ): void {
        const {
            clearProcessing = true,
            clearPending = true,
            clearWatched = false,
        } = options;

        if (clearProcessing) {
            this.processingFiles.delete(normalizedPath);
        }

        this.processingCounts.delete(normalizedPath);
        this.circuitBreakerExpiry.delete(normalizedPath);
        this.recentWrites.delete(normalizedPath);

        if (clearWatched) {
            this.watchedFiles.delete(normalizedPath);
        }

        if (clearPending) {
            const pending = this.pendingChanges.get(normalizedPath);
            if (pending) {
                clearTimeout(pending);
                this.pendingChanges.delete(normalizedPath);
            }
        }
    }

    /**
     * Clean up all global state
     */
    private cleanupAllState(): void {
        this.processingFiles.clear();
        this.recentWrites.clear();
        this.processingCounts.clear();
        this.circuitBreakerExpiry.clear();

        // Clear all pending timeouts
        for (const timeout of this.pendingChanges.values()) {
            clearTimeout(timeout);
        }
        this.pendingChanges.clear();

        // Clear recovery timeout if active
        if (this.recoveryTimeout) {
            clearTimeout(this.recoveryTimeout);
            this.recoveryTimeout = undefined;
        }
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
     * Check if circuit breaker should block processing for a file
     */
    private isCircuitBreakerActive(normalizedPath: string): boolean {
        const now = Date.now();

        // Check if in cooldown period
        const expiry = this.circuitBreakerExpiry.get(normalizedPath);
        if (expiry && now < expiry) {
            log.debug(
                `Circuit breaker active until ${new Date(expiry)} for: ${normalizedPath}`
            );
            return true;
        }

        // Check if too many processing attempts
        const count = this.processingCounts.get(normalizedPath) || 0;
        if (count >= this.maxProcessingPerFile) {
            log.warn(`Circuit breaker triggered for ${normalizedPath}`);
            this.circuitBreakerExpiry.set(
                normalizedPath,
                now + this.circuitBreakerCooldown
            );
            this.processingCounts.delete(normalizedPath);
            return true;
        }

        return false;
    }

    /**
     * Start monitoring MCP configuration files
     * Requirements: 13.1, 13.2 - Monitor workspace and system-wide mcp.json files
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

            // Monitor configuration files
            await this.setupFileWatchers(configFiles);

            // Process existing configuration files on startup with tracking
            for (const configFile of configFiles) {
                const normalizedPath = normalize(resolve(configFile));
                if (!this.processingFiles.has(normalizedPath)) {
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

        await this.closeConfigFileWatcher();
        this.cleanupAllState();

        this.isMonitoring = false;
        log.info("Configuration monitoring stopped");
    }

    /**
     * Handle workspace folder changes
     * Requirements: 13.8 - Re-establish monitoring when workspace changes
     */
    async handleWorkspaceChange(): Promise<void> {
        log.info("Workspace changed - re-establishing MCP configuration monitoring...");

        try {
            // Wait for all processing to complete with timeout
            log.debug("Waiting for all processing to complete...");
            const maxWaitTime = 30000; // 30 seconds
            const startTime = Date.now();

            while (this.processingFiles.size > 0) {
                if (Date.now() - startTime > maxWaitTime) {
                    log.error("Timeout waiting for processing to complete");
                    this.cleanupAllState(); // Force clear all state
                    break;
                }
                log.debug(
                    `Waiting for ${this.processingFiles.size} files to complete processing`
                );
                await this.sleep(100);
            }

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
         * Requirements: 13.9 - Only target AI client where extension is installed
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
         * Requirements: 13.9 - Only target AI client where extension is installed
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
     * Extract raw JSONC string from wrapped server configuration
     * Returns the original JSONC string (with comments) for file reconstruction
     */
    private extractRawWrappedConfig(serverConfig: MCPServerConfig): string | undefined {
        if (!this.isAlreadyWrapped(serverConfig)) {
            return undefined; // Not wrapped
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
     * Setup file system watchers for discovered configuration files
     */
    private async setupFileWatchers(configFiles: string[]): Promise<void> {
        if (configFiles.length === 0) {
            log.warn("No configuration files to watch");
            return;
        }

        // Close any existing watcher FIRST
        await this.closeConfigFileWatcher();

        // Clean up all state when recreating watcher
        this.cleanupAllState();

        // Now record what we plan to watch
        this.watchedFiles = new Set(configFiles);

        try {
            log.info(
                `Setting up Config files watcher for ${configFiles.length} configuration files:\n${configFiles.join("\n")}`
            );

            // Create watcher with polling for reliable detection of locked files
            this.chokidarWatcher = chokidar.watch(configFiles, {
                persistent: true,
                ignoreInitial: true,
                usePolling: true,
                interval: this.pollingInterval,
                binaryInterval: this.pollingInterval,
                awaitWriteFinish: { stabilityThreshold: 800, pollInterval: 200 },
                ignorePermissionErrors: true,
                followSymlinks: false,
                disableGlobbing: true,
                depth: 0,
            });

            // Add debug logging for all events
            this.chokidarWatcher.on("all", (event, filePath) => {
                log.debug(`Chokidar event: ${event} for ${filePath}`);
            });

            this.chokidarWatcher.on("raw", (event, path, details) => {
                log.debug(`Raw event: ${event} for ${path}`, details);
            });

            // Handle file change events with debouncing
            this.chokidarWatcher.on("change", (filePath: string) => {
                const normalizedPath = normalize(resolve(filePath));
                this.handleFileChange(normalizedPath, "change");
            });

            this.chokidarWatcher.on("add", (filePath: string) => {
                const normalizedPath = normalize(resolve(filePath));
                this.handleFileChange(normalizedPath, "add");
            });

            this.chokidarWatcher.on("unlink", (filePath: string) => {
                const normalizedPath = normalize(resolve(filePath));
                log.info(`📄 Configuration file deleted: ${normalizedPath}`);
                this.cleanupFileState(normalizedPath, { clearWatched: true });
            });

            this.chokidarWatcher.on("error", async (error: Error) => {
                log.error("🚨 Config files watcher error occurred:", error);

                // Retry logic with proper flag management
                if (
                    !this.isRecreatingWatcher &&
                    this.reconnectAttempts < this.maxReconnectAttempts
                ) {
                    this.reconnectAttempts++;
                    log.info(
                        `🔄 Attempting to recover file watcher (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`
                    );

                    // Clear any existing recovery timeout
                    if (this.recoveryTimeout) {
                        clearTimeout(this.recoveryTimeout);
                    }

                    this.recoveryTimeout = setTimeout(async () => {
                        try {
                            this.isRecreatingWatcher = true;
                            await this.setupFileWatchers(Array.from(this.watchedFiles));
                            log.info("✅ File watcher recovered successfully");
                            this.reconnectAttempts = 0;
                        } catch (recoveryError) {
                            log.error("❌ File watcher recovery failed:", recoveryError);
                        } finally {
                            this.isRecreatingWatcher = false;
                            this.recoveryTimeout = undefined;
                        }
                    }, this.reconnectDelay * this.reconnectAttempts);
                } else if (!this.isRecreatingWatcher) {
                    log.error(
                        "❌ Max reconnection attempts reached. File watching disabled."
                    );
                    this.vscode?.window.showErrorMessage(
                        "MCPower Security: File watching failed. Please reload the window or restart VS Code."
                    );
                }
            });

            this.chokidarWatcher.on("ready", () => {
                log.info("✅ Config files watcher is ready and monitoring files");
                this.reconnectAttempts = 0;
            });

            log.info(`✅ Config files watcher created successfully`);
        } catch (error) {
            log.error("Failed to setup Config files watcher:", error);
            this.vscode?.window.showWarningMessage(
                "MCPower Security: File watching failed to start. Manual reload may be required for config changes."
            );
        }
    }

    /**
     * Handle file change events with debouncing and loop prevention
     */
    private handleFileChange(normalizedPath: string, eventType: string): void {
        // Check if this is from a recent write (loop prevention)
        const lastWrite = this.recentWrites.get(normalizedPath);
        if (lastWrite && Date.now() - lastWrite < this.writeIgnoreWindow) {
            log.debug(`Ignoring ${eventType} event from recent write: ${normalizedPath}`);
            return;
        }

        // Check if already processing (concurrency control)
        if (this.processingFiles.has(normalizedPath)) {
            log.debug(`Already processing, ignoring ${eventType}: ${normalizedPath}`);
            return;
        }

        // Cancel any pending debounced change
        const existing = this.pendingChanges.get(normalizedPath);
        if (existing) {
            clearTimeout(existing);
            log.debug(`Debouncing ${eventType} for: ${normalizedPath}`);
        }

        // Debounce the change
        const timeout = setTimeout(async () => {
            this.pendingChanges.delete(normalizedPath);

            // Check file exists before processing
            try {
                await fs.access(normalizedPath);
            } catch {
                log.debug(`📄 File no longer exists, skipping: ${normalizedPath}`);
                return;
            }

            log.info(`📝 Configuration file ${eventType}: ${normalizedPath}`);
            this.processConfigurationFile(normalizedPath).catch(error => {
                log.error(`Failed to process file ${eventType}:`, error);
            });
        }, this.debounceDelay);

        this.pendingChanges.set(normalizedPath, timeout);
    }

    /**
     * Process a single configuration file
     * Requirements: 13.3, 13.4, 13.5 - Create backups and wrap configurations
     */
    private async processConfigurationFile(configPath: string): Promise<void> {
        const normalizedPath = normalize(resolve(configPath));

        // Check circuit breaker before processing
        if (this.isCircuitBreakerActive(normalizedPath)) {
            return;
        }

        // Check if we're already processing this specific file
        if (this.processingFiles.has(normalizedPath)) {
            log.debug(`Already processing ${normalizedPath}, skipping`);
            return;
        }

        // Increment processing count now that we're committed to processing
        const count = this.processingCounts.get(normalizedPath) || 0;
        this.processingCounts.set(normalizedPath, count + 1);

        // Mark as processing
        this.processingFiles.add(normalizedPath);

        try {
            log.info(`Processing configuration file:\n${configPath}`);

            // Read and parse configuration
            const config = await this.readConfiguration(configPath);
            if (!config) {
                // Clean up state on read failure (but keep processing flag until finally block)
                this.cleanupFileState(normalizedPath, { clearProcessing: false });
                return;
            }

            // Wrap MCP servers with MCPower proxy using JSONC tree manipulation
            const hasChanges = await this.wrapConfigurationInFile(configPath);
            if (!hasChanges) {
                log.debug(`✅ All servers already wrapped in: ${configPath}`);
            }

            log.info(`Successfully processed configuration: ${configPath}`);

            // Reset processing counter after successful completion
            this.processingCounts.delete(normalizedPath);
        } catch (error) {
            log.error(`Failed to process configuration:\n${configPath}\n`, error);
            this.vscode?.window.showErrorMessage(
                `Failed to wrap MCP configuration: ${error}`
            );

            // Clear count after max attempts to prevent memory leak
            if (count >= this.maxProcessingPerFile - 1) {
                this.processingCounts.delete(normalizedPath);
            }
        } finally {
            // Always clear processing flag
            this.processingFiles.delete(normalizedPath);
        }
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
     * Requirements: 13.4, 13.5 - Automatic wrapping logic and real-time detection
     */
    async wrapConfigurationInFile(configPath: string): Promise<boolean> {
        if (!this.uvRunner) {
            log.error(
                "Cannot wrap configuration: uv runner not initialized. Call startMonitoring() first."
            );
            return false;
        }

        const uvCommand = this.uvRunner.getCommand();

        const result = await this.processConfigurationWithJsoncTree(
            configPath,
            async (content, config, serverKey, servers) => {
                let modifiedContent = content;
                let hasChanges = false;

                // Process each server for wrapping
                for (const [serverName, serverConfig] of Object.entries(servers)) {
                    // Skip if already wrapped
                    if (this.isAlreadyWrapped(serverConfig)) {
                        continue;
                    }

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
                    const rawServerJsonc = modifiedContent.substring(
                        serverNode.offset,
                        serverNode.offset + serverNode.length
                    );

                    // Create wrapped configuration
                    const wrappedConfig = {
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

    /**
     * Close Config files watcher safely - DRY method used in multiple places
     */
    private async closeConfigFileWatcher(): Promise<void> {
        if (this.chokidarWatcher) {
            try {
                // Always remove event listeners before closing to prevent hanging
                this.chokidarWatcher.removeAllListeners();
                await this.chokidarWatcher.close();
            } catch (error) {
                log.error("Error closing Config files watcher:", error);
            }
            this.chokidarWatcher = undefined;
        }
    }
}
