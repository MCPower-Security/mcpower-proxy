#!/usr/bin/env node

/**
 * Clean Build Script for MCPower Security
 * Removes all build-generated and cache files across the entire project
 */

const fs = require("fs");
const path = require("path");

class BuildCleaner {
    constructor() {
        this.extensionRoot = path.dirname(__dirname);
        this.projectRoot = path.dirname(path.dirname(this.extensionRoot));
        this.srcRoot = path.join(this.projectRoot, "src");
    }

    async clean() {
        console.log("🧹 Cleaning all build-generated files...");
        console.log(`Project root: ${this.projectRoot}`);

        let totalCleaned = 0;

        totalCleaned += await this.cleanExtensionFiles();
        totalCleaned += await this.cleanSrcFiles();
        totalCleaned += await this.cleanProjectFiles();

        console.log(
            `\n✅ Build clean complete! Removed ${totalCleaned} files/directories.`
        );
    }

    async cleanExtensionFiles() {
        console.log("\n📦 Cleaning extension build files...");
        let cleaned = 0;

        const extensionPaths = [
            // TypeScript compilation output
            path.join(this.extensionRoot, "out"),

            // Bundled Python source
            path.join(this.extensionRoot, "proxy-bundled"),

            // Extension packages
            ...this.globSync(path.join(this.extensionRoot, "*.vsix")),
        ];

        for (const filePath of extensionPaths) {
            if (await this.removeIfExists(filePath)) {
                cleaned++;
            }
        }

        return cleaned;
    }

    async cleanSrcFiles() {
        console.log("\n🐍 Cleaning src build files...");
        let cleaned = 0;

        const srcPaths = [
            path.join(this.srcRoot, ".venv"),
            path.join(this.srcRoot, "__pycache__"),
            path.join(this.srcRoot, ".pytest_cache"),
            path.join(this.srcRoot, "mcpower_proxy.egg-info"),
            ...this.globSync(path.join(this.srcRoot, "**", "*.pyc")),
            ...this.globSync(path.join(this.srcRoot, "**", "*.pyo")),
            ...this.globSync(path.join(this.srcRoot, "**", "__pycache__")),
            ...this.globSync(path.join(this.srcRoot, "**", "mcpower_proxy.egg-info")),
        ];

        for (const filePath of srcPaths) {
            if (await this.removeIfExists(filePath)) {
                cleaned++;
            }
        }

        return cleaned;
    }

    async cleanServerFiles() {
        console.log("\n🖥️  Cleaning server build files...");
        let cleaned = 0;

        const serverPaths = [
            // Python cache directories
            path.join(this.serverRoot, "__pycache__"),
            path.join(this.serverRoot, ".pytest_cache"),

            // Python build artifacts
            path.join(this.serverRoot, "build"),
            path.join(this.serverRoot, "dist"),
            path.join(this.serverRoot, "*.egg-info"),

            // Python compiled files
            ...this.globSync(path.join(this.serverRoot, "**", "*.pyc")),
            ...this.globSync(path.join(this.serverRoot, "**", "*.pyo")),
            ...this.globSync(path.join(this.serverRoot, "**", "__pycache__")),
        ];

        for (const filePath of serverPaths) {
            if (await this.removeIfExists(filePath)) {
                cleaned++;
            }
        }

        return cleaned;
    }

    async cleanProjectFiles() {
        console.log("\n🗂️  Cleaning project-wide files...");
        let cleaned = 0;

        const projectPaths = [
            // OS-specific files
            path.join(this.projectRoot, ".DS_Store"),
            path.join(this.projectRoot, "build"),

            ...this.globSync(path.join(this.projectRoot, "**", ".DS_Store")),

            // IDE files (optional)
            path.join(this.projectRoot, ".vscode", "settings.json"),

            // Temporary files
            ...this.globSync(path.join(this.projectRoot, "**", "*.tmp")),
            ...this.globSync(path.join(this.projectRoot, "**", "*.temp")),
            ...this.globSync(path.join(this.projectRoot, "**", "*~")),

            // Log files
            ...this.globSync(path.join(this.projectRoot, "**", "*.log")),
        ];

        for (const filePath of projectPaths) {
            if (await this.removeIfExists(filePath)) {
                cleaned++;
            }
        }

        return cleaned;
    }

    /**
     * Remove file or directory if it exists
     */
    async removeIfExists(filePath) {
        try {
            if (fs.existsSync(filePath)) {
                const stats = fs.statSync(filePath);
                if (stats.isDirectory()) {
                    fs.rmSync(filePath, { recursive: true, force: true });
                    console.log(
                        `  🗑️  Removed directory: ${path.relative(this.projectRoot, filePath)}`
                    );
                } else {
                    fs.unlinkSync(filePath);
                    console.log(
                        `  🗑️  Removed file: ${path.relative(this.projectRoot, filePath)}`
                    );
                }
                return true;
            }
        } catch (error) {
            console.warn(`  ⚠️  Failed to remove ${filePath}: ${error.message}`);
        }
        return false;
    }

    /**
     * Simple glob implementation for basic patterns
     */
    globSync(pattern) {
        const results = [];

        // Handle ** patterns
        if (pattern.includes("**")) {
            const basePath = pattern.split("**")[0];
            const fileName = pattern.split("**")[1].replace(/^\//, "");

            if (fs.existsSync(basePath)) {
                this.walkDirectory(basePath, filePath => {
                    if (
                        filePath.endsWith(fileName) ||
                        path.basename(filePath) === fileName
                    ) {
                        results.push(filePath);
                    }
                });
            }
        } else {
            // Handle simple patterns
            const dir = path.dirname(pattern);
            const base = path.basename(pattern);

            if (fs.existsSync(dir)) {
                try {
                    const files = fs.readdirSync(dir);
                    for (const file of files) {
                        if (base.includes("*")) {
                            const regex = new RegExp(base.replace(/\*/g, ".*"));
                            if (regex.test(file)) {
                                results.push(path.join(dir, file));
                            }
                        } else if (file === base) {
                            results.push(path.join(dir, file));
                        }
                    }
                } catch (error) {
                    // Directory not readable, skip
                }
            }
        }

        return results;
    }

    /**
     * Recursively walk directory
     */
    walkDirectory(dirPath, callback) {
        try {
            const files = fs.readdirSync(dirPath);
            for (const file of files) {
                const filePath = path.join(dirPath, file);
                try {
                    const stats = fs.statSync(filePath);
                    callback(filePath);

                    if (stats.isDirectory()) {
                        this.walkDirectory(filePath, callback);
                    }
                } catch (error) {
                    // Skip files we can't read
                }
            }
        } catch (error) {
            // Skip directories we can't read
        }
    }
}

// Run cleaner if called directly
if (require.main === module) {
    const cleaner = new BuildCleaner();
    cleaner.clean().catch(error => {
        console.error("Cleaning failed:", error);
        process.exit(1);
    });
}

module.exports = BuildCleaner;
