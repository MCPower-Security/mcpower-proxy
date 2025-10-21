import * as vscode from "vscode";
import * as path from "path";
import * as fs from "fs";
import * as os from "os";
import { PlatformInfo } from "./types";
import { ensureDirectoryExists, makeExecutable, clearNuitkaTempCache } from "./utils";
import log from "./log";

export class ExecutableManager {
    private context: vscode.ExtensionContext;
    private platformInfo: PlatformInfo;
    private executablePath: string = "";

    constructor(context: vscode.ExtensionContext) {
        this.context = context;
        this.platformInfo = this.#detectPlatform();
    }

    /**
     * Initialize the executable manager and extract platform-specific executable
     * Requirements: 12.1, 12.3 - Cross-platform executable bundling and extraction
     */
    async initialize(): Promise<void> {
        try {
            // Clear cache on initialization to ensure fresh executables
            await clearNuitkaTempCache();

            // Create executables directory in extension's global storage
            const executablesDir = path.join(
                this.context.globalStorageUri.fsPath,
                "executables"
            );
            await ensureDirectoryExists(executablesDir);

            // Determine target executable path
            this.executablePath = path.join(
                executablesDir,
                this.platformInfo.executableName
            );

            // Extract executable if it doesn't exist or is outdated
            await this.#extractExecutable();
            await this.#makeExecutable();

            log.info(`MCPower Security executable ready at: ${this.executablePath}`);
        } catch (error) {
            throw new Error(`Failed to initialize executable manager: ${error}`);
        }
    }

    async #makeExecutable() {
        if (this.platformInfo.platform !== "win32") {
            await makeExecutable(this.executablePath);
        }
    }

    /**
     * Extract the platform-specific executable from the extension bundle
     */
    async #extractExecutable(): Promise<void> {
        const bundledExecutablePath = path.join(
            this.context.extensionPath,
            "executables",
            this.platformInfo.executableName
        );

        // Check if bundled executable exists
        if (!fs.existsSync(bundledExecutablePath)) {
            throw new Error(`Bundled executable not found: ${bundledExecutablePath}`);
        }

        // Check if we need to extract (file doesn't exist or is older than bundled version)
        const shouldExtract = await this.#shouldExtractExecutable(
            bundledExecutablePath,
            this.executablePath
        );

        if (shouldExtract) {
            const isUpdate = fs.existsSync(this.executablePath);
            log.info(
                `${isUpdate ? "Updating" : "Extracting"} executable from ${bundledExecutablePath} to ${this.executablePath}`
            );

            await fs.promises.copyFile(bundledExecutablePath, this.executablePath);
            await this.#makeExecutable();

            if (isUpdate) {
                log.info(
                    "✅ Executable updated successfully - existing configurations preserved"
                );
            } else {
                log.info("✅ Executable extracted successfully");
            }
        } else {
            log.debug("Executable is up to date, skipping extraction");
        }
    }

    /**
     * Determine if executable should be extracted based on modification times
     */
    async #shouldExtractExecutable(
        sourcePath: string,
        targetPath: string
    ): Promise<boolean> {
        try {
            if (!fs.existsSync(targetPath)) {
                return true; // Target doesn't exist, need to extract
            }

            const sourceStats = await fs.promises.stat(sourcePath);
            const targetStats = await fs.promises.stat(targetPath);

            // Extract if source is newer than target
            return sourceStats.mtime > targetStats.mtime;
        } catch (error) {
            log.warn(`Error checking executable timestamps`, error);
            return true; // Default to extracting on error
        }
    }

    /**
     * Detect current platform and determine executable name
     */
    #detectPlatform(): PlatformInfo {
        const platform = os.platform();
        const arch = os.arch();

        let executableName: string;
        let normalizedPlatform: "win32" | "darwin" | "linux";

        switch (platform) {
            case "win32":
                executableName = "mcpower-windows.exe";
                normalizedPlatform = "win32";
                break;
            case "darwin":
                executableName = "mcpower-macos";
                normalizedPlatform = "darwin";
                break;
            case "linux":
                executableName = "mcpower-linux";
                normalizedPlatform = "linux";
                break;
            default:
                throw new Error(`Unsupported platform: ${platform}`);
        }

        return {
            platform: normalizedPlatform,
            arch,
            executableName,
            executablePath: "", // Will be set during initialization
        };
    }

    /**
     * Get the path to the extracted executable
     */
    getExecutablePath(): string {
        return this.executablePath;
    }
}
