const fs = require("fs").promises;
const path = require("path");
const os = require("os");

/**
 * Mock vscode module
 */
function setupVscodeMock() {
    const Module = require("module");
    const originalRequire = Module.prototype.require;
    Module.prototype.require = function (id) {
        if (id === "vscode") {
            return {
                window: {
                    showErrorMessage: () => {},
                    showWarningMessage: () => {},
                    createOutputChannel: () => ({
                        appendLine: () => {},
                        append: () => {},
                        error: () => {},
                        warn: () => {},
                        info: () => {},
                        debug: () => {},
                        show: () => {},
                        hide: () => {},
                        dispose: () => {},
                    }),
                },
                workspace: {
                    workspaceFolders: null,
                },
                env: {
                    appName: "Visual Studio Code",
                },
            };
        }
        return originalRequire.apply(this, arguments);
    };
}

/**
 * Cleanup helper that ensures temp directory is removed
 */
async function cleanup(tmpDir) {
    try {
        await fs.rm(tmpDir, { recursive: true, force: true });
        console.log(`\n🧹 Cleaned up: ${tmpDir}`);
    } catch (error) {
        console.error(`⚠️ Cleanup failed for ${tmpDir}:`, error.message);
        // Don't throw - cleanup failure shouldn't fail the test
    }
}

/**
 * Test that wrap/unwrap cycles preserve exact file content
 */
async function testWrapUnwrapCycle() {
    setupVscodeMock();
    const tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), "mcpower-wrap-test-"));
    const testConfigPath = path.join(tmpDir, "test-config.json");

    // Register cleanup on process exit (handles crashes)
    const cleanupHandler = () => {
        try {
            const { rmSync } = require("fs");
            rmSync(tmpDir, { recursive: true, force: true });
        } catch (error) {
            // Silent fail on exit
        }
    };
    process.once("exit", cleanupHandler);
    process.once("SIGINT", () => {
        cleanupHandler();
        process.exit(130);
    });
    process.once("SIGTERM", () => {
        cleanupHandler();
        process.exit(143);
    });

    // Sample config with specific indentation patterns
    const originalConfig = `{
  "mcpServers": {
    "test-server": {
      "command": "node",
      "args": ["server.js"],
      "env": {
      // this is an unaligned top comment 
        "FOO": "bar",
         // this is just a comment 
        "NESTED": {
          "KEY": "value" // this is a line comment
        }
      }
    },
    "another-server": {
      "command": "python",
      "args": ["-m", "server"]
    }
  }
}`;

    try {
        // Write original config
        await fs.writeFile(testConfigPath, originalConfig, "utf8");
        console.log("✓ Created test config");

        // Load the ConfigurationMonitor class from compiled output
        const {
            ConfigurationMonitor,
        } = require("../../../out/configurationMonitor/index");

        const monitor = new ConfigurationMonitor();

        // Mock IDE detection (needed for registry operations)
        monitor.currentIDE = "vscode";

        // Mock uvRunner directly (needed for wrapping)
        monitor.uvRunner = {
            getCommand: () => ({
                executable: "uvx",
                args: [
                    "--from",
                    "/mock/path/to/proxy-bundled",
                    "mcpower-proxy",
                ],
            }),
        };

        // Perform multiple wrap/unwrap cycles
        for (let i = 1; i <= 5; i++) {
            console.log(`\n--- Cycle ${i} ---`);

            // Wrap
            const wrapped = await monitor.wrapConfigurationInFile(testConfigPath);
            if (!wrapped) {
                throw new Error(`Wrap failed on cycle ${i}`);
            }
            console.log(`✓ Wrapped (cycle ${i})`);

            // Verify wrapped state
            const wrappedContent = await fs.readFile(testConfigPath, "utf8");
            const JSONC = require("../../../node_modules/jsonc-parser");
            const wrappedConfig = JSONC.parse(wrappedContent);
            const serverKey = Object.keys(wrappedConfig).find(k =>
                ["mcpServers", "servers", "extensions"].includes(k)
            );
            
            if (!serverKey) {
                throw new Error(`No server key found in wrapped config (cycle ${i})`);
            }

            const servers = wrappedConfig[serverKey];
            const serverNames = Object.keys(servers);
            
            // Verify all servers are wrapped
            for (const serverName of serverNames) {
                const server = servers[serverName];
                if (!server.command || server.command !== "uvx") {
                    throw new Error(
                        `Server ${serverName} not wrapped: command is ${server.command} (cycle ${i})`
                    );
                }
                if (!server.args || !server.args.includes("--wrapped-config")) {
                    throw new Error(
                        `Server ${serverName} missing --wrapped-config arg (cycle ${i})`
                    );
                }
                const wrappedConfigIndex = server.args.indexOf("--wrapped-config");
                const rawConfig = server.args[wrappedConfigIndex + 1];
                if (!rawConfig || typeof rawConfig !== "string" || !rawConfig.includes("{")) {
                    throw new Error(
                        `Server ${serverName} has invalid --wrapped-config value (cycle ${i})`
                    );
                }
            }
            console.log(`✓ Verified wrapped structure (cycle ${i})`);

            // Unwrap
            const unwrapped = await monitor.unwrapConfigurationInFile(testConfigPath);
            if (!unwrapped) {
                throw new Error(`Unwrap failed on cycle ${i}`);
            }
            console.log(`✓ Unwrapped (cycle ${i})`);

            // Read current content
            const currentContent = await fs.readFile(testConfigPath, "utf8");

            // Compare with original
            if (currentContent !== originalConfig) {
                console.error("\n❌ FAIL: Content mismatch after cycle", i);
                console.error("\n=== EXPECTED ===");
                console.error(originalConfig);
                console.error("\n=== ACTUAL ===");
                console.error(currentContent);
                console.error("\n=== DIFF ===");

                // Character-by-character comparison
                for (
                    let j = 0;
                    j < Math.max(originalConfig.length, currentContent.length);
                    j++
                ) {
                    if (originalConfig[j] !== currentContent[j]) {
                        console.error(`First diff at position ${j}:`);
                        console.error(
                            `  Expected: ${JSON.stringify(originalConfig[j])} (code ${originalConfig.charCodeAt(j)})`
                        );
                        console.error(
                            `  Actual: ${JSON.stringify(currentContent[j])} (code ${currentContent.charCodeAt(j)})`
                        );
                        break;
                    }
                }

                process.exit(1);
            }

            console.log(`✓ Content matches original (cycle ${i})`);
        }

        console.log("\n✅ SUCCESS: All 5 wrap/unwrap cycles preserved exact content");
    } finally {
        // Remove signal handlers to prevent double cleanup
        process.removeAllListeners("exit");
        process.removeAllListeners("SIGINT");
        process.removeAllListeners("SIGTERM");
        
        // Cleanup temp directory
        await cleanup(tmpDir);
    }
}

// Run test
testWrapUnwrapCycle().catch(error => {
    console.error("❌ Test failed:", error);
    process.exit(1);
});
