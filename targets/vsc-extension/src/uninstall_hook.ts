import { ConfigurationMonitor } from "./configurationMonitor";
import { CursorHooksMonitor } from "./cursorHooksMonitor";
import { constants, promises as fs } from "fs";
import { detectIDEFromScriptPath } from "./utils";
import { reportLifecycleEvent } from "./api";

/**
 * Uninstall hook script for Defenter
 * This script runs when the extension is completely uninstalled from VS Code
 * It unwraps all MCP configurations and unregisters IDE Tools hooks by this specific IDE instance
 */
async function main() {
    console.log("Starting Defenter uninstall cleanup...");

    try {
        await reportLifecycleEvent("uninstall");

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

        // 1. Unwrap MCP configurations
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

        console.log(`\nMCP Configurations cleanup:`);
        console.log(`  ✅ Successfully unwrapped: ${successCount}`);
        console.log(`  ℹ️  No changes needed: ${skipCount}`);
        console.log(`  ❌ Errors encountered: ${errorCount}`);

        // 2. Unregister Cursor hooks (if running in Cursor)
        const ideType = detectIDEFromScriptPath();
        switch (ideType) {
            case "cursor":
                console.log("\nCleaning up Cursor hooks...");
                try {
                    const cursorHooksMonitor = new CursorHooksMonitor();
                    await cursorHooksMonitor.unregisterHook();
                    console.log("✅ Cursor hooks unregistered");
                } catch (error: any) {
                    console.error("Failed to unregister Cursor hooks:", error.message);
                    // Non-critical - continue with other cleanup
                }
                break;
        }

        // 3. Clean up registry directories
        try {
            const mcpsDir = configMonitor.getMcpsDir();
            await fs.rmdir(mcpsDir);
            console.log("✅ MCP registry cleaned up");
        } catch (e) {
            console.error("MCP registry cleanup failed:", e);
            // ignore folder removal error; non-critical
        }

        console.log("\nDefenter uninstall cleanup finished!");
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
