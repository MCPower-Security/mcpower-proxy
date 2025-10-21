import { ConfigurationMonitor } from "./configurationMonitor";
import { constants, promises as fs } from "fs";
import { clearNuitkaTempCache } from "./utils";

/**
 * Uninstall hook script for MCPower Security
 * This script runs when the extension is completely uninstalled from VS Code
 * It unwraps all MCP configurations that were wrapped by this specific IDE instance
 */
async function main() {
    console.log("Starting MCPower Security uninstall cleanup...");

    try {
        const configMonitor = new ConfigurationMonitor();

        const detectedIDE = configMonitor.getCurrentIDE();
        if (!detectedIDE) {
            console.error(
                "❌ Cannot detect IDE from script path - unsafe to proceed with cleanup"
            );
            console.error("Script path:", __dirname);
            process.exit(1);
        }

        console.log(`Detected IDE from script path: ${detectedIDE}`);

        // Get all files this IDE instance should unwrap (registry and current IDE system paths)
        const filesToUnwrap = await configMonitor.getAllWrappedFiles();
        console.log(`Found ${filesToUnwrap.length} files to check for unwrapping`);

        if (!filesToUnwrap.length) {
            return;
        }

        let successCount = 0;
        let skipCount = 0;
        let errorCount = 0;

        for (const filePath of filesToUnwrap) {
            try {
                console.log(`Processing: ${filePath}`);

                // Check if a file exists
                if (!(await fileExists(filePath))) {
                    console.warn(`File not found: ${filePath}`);
                    skipCount++;
                    continue;
                }

                const unwrapped = await configMonitor.unwrapConfigurationInFile(filePath);
                if (unwrapped) {
                    successCount++;
                    console.log(`Unwrapped: ${filePath}`);
                } else {
                    skipCount++;
                    console.log(`No unwrapping needed: ${filePath}`);
                }
            } catch (error: any) {
                errorCount++;
                console.error(`Failed to unwrap ${filePath}:`, error.message);
                // Continue with next file - fail-safe operation
            }
        }

        console.log(`\nCleanup completed:`);
        console.log(`  ✅ Successfully unwrapped: ${successCount}`);
        console.log(`  ℹ️  No changes needed: ${skipCount}`);
        console.log(`  ❌ Errors encountered: ${errorCount}`);

        try {
            // Clean up current IDE's registry directory
            const mcpsDir = configMonitor.getMcpsDir();
            await fs.rmdir(mcpsDir);
        } catch (e) {
            console.error("IDE MCPs folder cleanup failed:", e);
            // ignore folder removal error; non-critical
        }

        console.log("Registry cleanup completed");
        await clearNuitkaTempCache();
        console.log("MCPower Security uninstall cleanup finished!");
    } catch (error) {
        console.error("❌ Uninstall cleanup failed:", error);
        process.exit(1);
    }
}

/**
 * Check if a file exists
 */
async function fileExists(filePath: string): Promise<boolean> {
    try {
        await fs.access(filePath, constants.F_OK);
        return true;
    } catch {
        return false;
    }
}

// Run the main function
main();
