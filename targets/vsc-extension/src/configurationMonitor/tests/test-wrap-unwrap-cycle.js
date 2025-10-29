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
                args: ["--from", "/mock/path/to/proxy-bundled", "mcpower-proxy"],
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
                if (
                    !rawConfig ||
                    typeof rawConfig !== "string" ||
                    !rawConfig.includes("{")
                ) {
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

/**
 * Test URL-based config with mcp-remote wrapping and __bak_configs
 */
async function testUrlConfigWithMcpRemote() {
    setupVscodeMock();
    const tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), "mcpower-url-test-"));
    const testConfigPath = path.join(tmpDir, "test-url-config.json");

    // Register cleanup
    const cleanupHandler = () => {
        try {
            const { rmSync } = require("fs");
            rmSync(tmpDir, { recursive: true, force: true });
        } catch (error) {}
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

    // Config with URL-based server (like Notion MCP remote)
    const originalConfig = `{
  "mcpServers": {
    "notion": {
      "url": "https://mcp.notion.com/mcp",
      "headers": {
        "Authorization": "Bearer secret-token",
        "X-Custom-Header": "custom-value"
      },
      "env": {
        "NODE_ENV": "production"
      }
    },
    "regular-server": {
      "command": "node",
      "args": ["server.js"]
    }
  }
}`;

    try {
        await fs.writeFile(testConfigPath, originalConfig, "utf8");
        console.log("\n✓ Created URL-based test config");

        const {
            ConfigurationMonitor,
        } = require("../../../out/configurationMonitor/index");
        const monitor = new ConfigurationMonitor();
        monitor.currentIDE = "vscode";
        monitor.uvRunner = {
            getCommand: () => ({
                executable: "uvx",
                args: ["--from", "/mock/path/to/proxy-bundled", "mcpower-proxy"],
            }),
        };

        // === WRAP ===
        console.log("\n--- Testing Wrap ---");
        const wrapped = await monitor.wrapConfigurationInFile(testConfigPath);
        if (!wrapped) {
            throw new Error("Wrap failed for URL-based config");
        }
        console.log("✓ Wrapped URL-based config");

        // Verify wrapped structure
        const wrappedContent = await fs.readFile(testConfigPath, "utf8");
        const JSONC = require("../../../node_modules/jsonc-parser");
        const wrappedConfig = JSONC.parse(wrappedContent);
        const notionServer = wrappedConfig.mcpServers.notion;

        // Check outer wrapper structure
        if (notionServer.command !== "uvx") {
            throw new Error(`Expected command 'uvx', got '${notionServer.command}'`);
        }
        if (!notionServer.args.includes("mcpower-proxy")) {
            throw new Error("Missing mcpower-proxy in args");
        }
        if (!notionServer.args.includes("--wrapped-config")) {
            throw new Error("Missing --wrapped-config in args");
        }
        console.log("✓ Outer wrapper structure correct");

        // Check __bak_configs exists
        if (!notionServer.__bak_configs) {
            throw new Error("Missing __bak_configs field");
        }
        console.log("✓ __bak_configs field present");

        // Parse and verify __bak_configs content
        const backupConfig = JSON.parse(notionServer.__bak_configs);
        if (backupConfig.url !== "https://mcp.notion.com/mcp") {
            throw new Error(
                `__bak_configs URL mismatch: expected 'https://mcp.notion.com/mcp', got '${backupConfig.url}'`
            );
        }
        if (!backupConfig.headers || !backupConfig.headers.Authorization) {
            throw new Error("__bak_configs missing headers");
        }
        console.log("✓ __bak_configs contains original URL config");

        // Check inner wrapped config (should be mcp-remote)
        const wrappedConfigIndex = notionServer.args.indexOf("--wrapped-config");
        const innerConfigStr = notionServer.args[wrappedConfigIndex + 1];
        const innerConfig = JSON.parse(innerConfigStr);

        if (innerConfig.command !== "npx") {
            throw new Error(`Expected inner command 'npx', got '${innerConfig.command}'`);
        }
        if (!innerConfig.args.includes("mcp-remote")) {
            throw new Error("Missing mcp-remote in inner args");
        }
        if (!innerConfig.args.includes("-y")) {
            throw new Error("Missing -y flag in inner args");
        }
        if (!innerConfig.args.includes("https://mcp.notion.com/mcp")) {
            throw new Error("Missing URL in inner args");
        }
        console.log("✓ Inner config uses mcp-remote with URL");

        // Check headers are converted to --header flags
        const headerFlagIndex = innerConfig.args.indexOf("--header");
        if (headerFlagIndex === -1) {
            throw new Error("Missing --header flags in inner args");
        }
        const headerValues = [];
        for (let i = 0; i < innerConfig.args.length; i++) {
            if (innerConfig.args[i] === "--header") {
                headerValues.push(innerConfig.args[i + 1]);
            }
        }
        if (headerValues.length !== 2) {
            throw new Error(`Expected 2 headers, got ${headerValues.length}`);
        }
        if (!headerValues.some(h => h.includes("Authorization"))) {
            throw new Error("Missing Authorization header");
        }
        if (!headerValues.some(h => h.includes("X-Custom-Header"))) {
            throw new Error("Missing X-Custom-Header");
        }
        console.log("✓ Headers converted to --header flags");

        // Check env is preserved in inner config
        if (!innerConfig.env || innerConfig.env.NODE_ENV !== "production") {
            throw new Error("env not preserved in inner config");
        }
        console.log("✓ env preserved in inner config");

        // Check regular server is also wrapped (but not with mcp-remote)
        const regularServer = wrappedConfig.mcpServers["regular-server"];
        if (!regularServer.__bak_configs) {
            // Regular command-based server should NOT have __bak_configs
            const regularInnerConfigStr =
                regularServer.args[regularServer.args.indexOf("--wrapped-config") + 1];
            const regularInnerConfig = JSON.parse(regularInnerConfigStr);
            if (regularInnerConfig.command !== "node") {
                throw new Error("Regular server inner config incorrect");
            }
            console.log("✓ Regular server wrapped without mcp-remote");
        } else {
            throw new Error("Regular server should not have __bak_configs");
        }

        // === UNWRAP ===
        console.log("\n--- Testing Unwrap ---");
        const unwrapped = await monitor.unwrapConfigurationInFile(testConfigPath);
        if (!unwrapped) {
            throw new Error("Unwrap failed for URL-based config");
        }
        console.log("✓ Unwrapped URL-based config");

        // Verify unwrapped content matches original
        const unwrappedContent = await fs.readFile(testConfigPath, "utf8");
        if (unwrappedContent !== originalConfig) {
            console.error("\n❌ FAIL: Content mismatch after unwrap");
            console.error("\n=== EXPECTED ===");
            console.error(originalConfig);
            console.error("\n=== ACTUAL ===");
            console.error(unwrappedContent);

            // Character-by-character comparison
            for (
                let j = 0;
                j < Math.max(originalConfig.length, unwrappedContent.length);
                j++
            ) {
                if (originalConfig[j] !== unwrappedContent[j]) {
                    console.error(`First diff at position ${j}:`);
                    console.error(
                        `  Expected: ${JSON.stringify(originalConfig[j])} (code ${originalConfig.charCodeAt(j)})`
                    );
                    console.error(
                        `  Actual: ${JSON.stringify(unwrappedContent[j])} (code ${unwrappedContent.charCodeAt(j)})`
                    );
                    break;
                }
            }

            process.exit(1);
        }

        console.log("✓ Unwrapped content matches original exactly");

        // Verify __bak_configs was used (not regular wrapped-config)
        const unwrappedConfig = JSONC.parse(unwrappedContent);
        const restoredNotion = unwrappedConfig.mcpServers.notion;
        if (restoredNotion.url !== "https://mcp.notion.com/mcp") {
            throw new Error("URL not restored correctly");
        }
        if (
            !restoredNotion.headers ||
            !restoredNotion.headers.Authorization ||
            !restoredNotion.headers["X-Custom-Header"]
        ) {
            throw new Error("Headers not restored correctly");
        }
        if (!restoredNotion.env || restoredNotion.env.NODE_ENV !== "production") {
            throw new Error("env not restored correctly");
        }
        if (restoredNotion.__bak_configs) {
            throw new Error("__bak_configs should be removed after unwrap");
        }
        console.log("✓ URL config restored from __bak_configs (not mcp-remote)");

        console.log(
            "\n✅ SUCCESS: URL-based config with mcp-remote wrapping/unwrapping works correctly"
        );
    } finally {
        process.removeAllListeners("exit");
        process.removeAllListeners("SIGINT");
        process.removeAllListeners("SIGTERM");
        await cleanup(tmpDir);
    }
}

// Run tests
(async () => {
    try {
        await testWrapUnwrapCycle();
        await testUrlConfigWithMcpRemote();
        console.log("\n🎉 ALL TESTS PASSED");
    } catch (error) {
        console.error("❌ Test failed:", error);
        process.exit(1);
    }
})();
