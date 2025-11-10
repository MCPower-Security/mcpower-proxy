/**
 * Common file watcher module using chokidar
 * Shared between VSC extension and Claude Code plugin
 */

import { dirname, normalize, resolve } from "path";
import { promises as fs } from "fs";
import chokidar from "chokidar";

export interface Logger {
    debug(message: string, ...args: any[]): void;
    info(message: string, ...args: any[]): void;
    warn(message: string, ...args: any[]): void;
    error(message: string, ...args: any[]): void;
}

export interface FileWatcherCallbacks {
    /** Called when a file needs to be processed */
    onFileProcess: (filePath: string) => Promise<void>;
    /** Optional: Called when a file is deleted - useful for auto-recreation */
    onFileDelete?: (filePath: string) => Promise<void>;
    /** Optional: Called when an error should be shown to the user */
    onShowError?: (message: string) => void;
    /** Logger implementation */
    logger: Logger;
}

export class FileWatcher {
    private chokidarWatcher: chokidar.FSWatcher | undefined;
    private isWatching: boolean = false;

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

    private callbacks: FileWatcherCallbacks;

    constructor(callbacks: FileWatcherCallbacks) {
        this.callbacks = callbacks;
    }

    /**
     * Check if watcher is currently active
     */
    isActive(): boolean {
        return this.isWatching;
    }

    /**
     * Check if a file is currently being processed
     */
    isProcessing(filePath: string): boolean {
        const normalizedPath = normalize(resolve(filePath));
        return this.processingFiles.has(normalizedPath);
    }

    /**
     * Record a recent write to prevent processing loops
     */
    recordWrite(filePath: string): void {
        const normalizedPath = normalize(resolve(filePath));
        this.recentWrites.set(normalizedPath, Date.now());
    }

    /**
     * Clean up all state for a specific file path
     */
    cleanupFileState(
        filePath: string,
        options: {
            clearProcessing?: boolean;
            clearPending?: boolean;
            clearWatched?: boolean;
        } = {}
    ): void {
        const normalizedPath = normalize(resolve(filePath));
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
    cleanupAllState(): void {
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
     * Check if circuit breaker should block processing for a file
     */
    private isCircuitBreakerActive(normalizedPath: string): boolean {
        const now = Date.now();

        // Check if in cooldown period
        const expiry = this.circuitBreakerExpiry.get(normalizedPath);
        if (expiry && now < expiry) {
            this.callbacks.logger.debug(
                `Circuit breaker active until ${new Date(expiry)} for: ${normalizedPath}`
            );
            return true;
        }

        // Check if too many processing attempts
        const count = this.processingCounts.get(normalizedPath) || 0;
        if (count >= this.maxProcessingPerFile) {
            this.callbacks.logger.warn(`Circuit breaker triggered for ${normalizedPath}`);
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
     * Setup file system watchers for configuration files
     */
    async startWatching(configFiles: string[]): Promise<void> {
        if (configFiles.length === 0) {
            this.callbacks.logger.warn("No configuration files to watch");
            return;
        }

        // Close any existing watcher FIRST
        await this.stopWatching();

        // Clean up all state when recreating watcher
        this.cleanupAllState();

        // Normalize and store files we're watching
        const normalizedFiles = configFiles.map(f => normalize(resolve(f)));
        this.watchedFiles = new Set(normalizedFiles);
        this.isWatching = true;

        try {
            this.callbacks.logger.info(
                `Setting up Config files watcher for ${configFiles.length} configuration files:\n${configFiles.join("\n")}`
            );

            // Get unique parent directories to watch
            const parentDirs = new Set(normalizedFiles.map(f => dirname(f)));

            // Create watcher for parent directories with polling for reliable detection
            this.chokidarWatcher = chokidar.watch(Array.from(parentDirs), {
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

            // Handle file change events with debouncing
            // Filter to only process files we're watching
            this.chokidarWatcher.on("change", (filePath: string) => {
                const normalizedPath = normalize(resolve(filePath));
                if (this.watchedFiles.has(normalizedPath)) {
                    this.handleFileChange(normalizedPath, "change");
                }
            });

            this.chokidarWatcher.on("add", (filePath: string) => {
                const normalizedPath = normalize(resolve(filePath));
                if (this.watchedFiles.has(normalizedPath)) {
                    this.handleFileChange(normalizedPath, "add");
                }
            });

            this.chokidarWatcher.on("unlink", (filePath: string) => {
                const normalizedPath = normalize(resolve(filePath));
                if (this.watchedFiles.has(normalizedPath)) {
                    this.callbacks.logger.info(
                        `📄 Configuration file deleted: ${normalizedPath}`
                    );

                    // Call onFileDelete if provided (for auto-recreation scenarios)
                    if (this.callbacks.onFileDelete) {
                        this.callbacks.onFileDelete(normalizedPath).catch(error => {
                            this.callbacks.logger.error(
                                `Failed to handle file deletion: ${normalizedPath}`,
                                error
                            );
                        });
                    }

                    // Don't remove from watchedFiles - we still want to detect recreation
                    this.cleanupFileState(normalizedPath, { clearWatched: false });
                }
            });

            this.chokidarWatcher.on("error", async (error: Error) => {
                this.callbacks.logger.error(
                    "🚨 Config files watcher error occurred:",
                    error
                );

                // Retry logic with proper flag management
                if (
                    !this.isRecreatingWatcher &&
                    this.reconnectAttempts < this.maxReconnectAttempts
                ) {
                    this.reconnectAttempts++;
                    this.callbacks.logger.info(
                        `🔄 Attempting to recover file watcher (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`
                    );

                    // Clear any existing recovery timeout
                    if (this.recoveryTimeout) {
                        clearTimeout(this.recoveryTimeout);
                    }

                    this.recoveryTimeout = setTimeout(async () => {
                        try {
                            this.isRecreatingWatcher = true;
                            await this.startWatching(Array.from(this.watchedFiles));
                            this.callbacks.logger.info(
                                "✅ File watcher recovered successfully"
                            );
                            this.reconnectAttempts = 0;
                        } catch (recoveryError) {
                            this.callbacks.logger.error(
                                "❌ File watcher recovery failed:",
                                recoveryError
                            );
                        } finally {
                            this.isRecreatingWatcher = false;
                            this.recoveryTimeout = undefined;
                        }
                    }, this.reconnectDelay * this.reconnectAttempts);
                } else if (!this.isRecreatingWatcher) {
                    this.callbacks.logger.error(
                        "❌ Max reconnection attempts reached. File watching disabled."
                    );
                    this.callbacks.onShowError?.(
                        "MCPower Security: File watching failed. Please reload the window or restart."
                    );
                }
            });

            this.chokidarWatcher.on("ready", () => {
                this.callbacks.logger.info(
                    "✅ Config files watcher is ready and monitoring files"
                );
                this.reconnectAttempts = 0;
            });

            this.callbacks.logger.info(`✅ Config files watcher created successfully`);
        } catch (error) {
            this.callbacks.logger.error("Failed to setup Config files watcher:", error);
            this.callbacks.onShowError?.(
                "MCPower Security: File watching failed to start. Manual reload may be required for config changes."
            );
            throw error;
        }
    }

    /**
     * Handle file change events with debouncing and loop prevention
     */
    private handleFileChange(normalizedPath: string, eventType: string): void {
        // Check if this is from a recent write (loop prevention)
        const lastWrite = this.recentWrites.get(normalizedPath);
        if (lastWrite && Date.now() - lastWrite < this.writeIgnoreWindow) {
            this.callbacks.logger.debug(
                `Ignoring ${eventType} event from recent write: ${normalizedPath}`
            );
            return;
        }

        // Check if already processing (concurrency control)
        if (this.processingFiles.has(normalizedPath)) {
            this.callbacks.logger.debug(
                `Already processing, ignoring ${eventType}: ${normalizedPath}`
            );
            return;
        }

        // Cancel any pending debounced change
        const existing = this.pendingChanges.get(normalizedPath);
        if (existing) {
            clearTimeout(existing);
            this.callbacks.logger.debug(`Debouncing ${eventType} for: ${normalizedPath}`);
        }

        // Debounce the change
        const timeout = setTimeout(async () => {
            this.pendingChanges.delete(normalizedPath);

            // Check file exists before processing
            try {
                await fs.access(normalizedPath);
            } catch {
                this.callbacks.logger.debug(
                    `📄 File no longer exists, skipping: ${normalizedPath}`
                );
                return;
            }

            this.callbacks.logger.info(
                `📝 Configuration file ${eventType}: ${normalizedPath}`
            );
            this.processFile(normalizedPath).catch(error => {
                this.callbacks.logger.error(
                    `Failed to process file ${eventType}:`,
                    error
                );
            });
        }, this.debounceDelay);

        this.pendingChanges.set(normalizedPath, timeout);
    }

    /**
     * Process a single file with circuit breaker and concurrency control
     */
    private async processFile(filePath: string): Promise<void> {
        const normalizedPath = normalize(resolve(filePath));

        // Check circuit breaker before processing
        if (this.isCircuitBreakerActive(normalizedPath)) {
            return;
        }

        // Check if we're already processing this specific file
        if (this.processingFiles.has(normalizedPath)) {
            this.callbacks.logger.debug(`Already processing ${normalizedPath}, skipping`);
            return;
        }

        // Increment processing count now that we're committed to processing
        const count = this.processingCounts.get(normalizedPath) || 0;
        this.processingCounts.set(normalizedPath, count + 1);

        // Mark as processing
        this.processingFiles.add(normalizedPath);

        try {
            // Call the client-provided processing callback
            await this.callbacks.onFileProcess(normalizedPath);

            // Reset processing counter after successful completion
            this.processingCounts.delete(normalizedPath);
        } catch (error) {
            this.callbacks.logger.error(
                `Failed to process file: ${normalizedPath}`,
                error
            );
            // Don't delete count here - let circuit breaker handle it
            throw error;
        } finally {
            // Always clear processing flag
            this.processingFiles.delete(normalizedPath);
        }
    }

    /**
     * Stop watching and cleanup
     */
    async stopWatching(): Promise<void> {
        if (this.chokidarWatcher) {
            try {
                // Always remove event listeners before closing to prevent hanging
                this.chokidarWatcher.removeAllListeners();
                await this.chokidarWatcher.close();
            } catch (error) {
                this.callbacks.logger.error("Error closing Config files watcher:", error);
            }
            this.chokidarWatcher = undefined;
        }
        this.isWatching = false;
    }
}
