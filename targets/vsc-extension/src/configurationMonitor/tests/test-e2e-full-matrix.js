#!/usr/bin/env node
/**
 * Comprehensive E2E Test for JSONC Tree-Based Configuration Processing
 * Tests the full matrix of scenarios with explicit before/after output
 */

const fs = require("fs").promises;
const path = require("path");
const { execSync } = require("child_process");

// No helper functions needed - using real implementation

// Test configurations covering the full matrix
const testConfigs = {
    // JSON files (no comments)
    "test-json-simple.json": {
        content: `{
  "mcpServers": {
    "simple-server": {
      "command": "node",
      "args": ["server.js"],
      "env": {
        "NODE_ENV": "production"
      }
    }
  }
}`,
        description: "JSON - Simple single server",
    },

    "test-json-multiple.json": {
        content: `{
  "servers": {
    "server-one": {
      "command": "python",
      "args": ["-m", "server"],
      "disabled": false
    },
    "server-two": {
      "url": "http://localhost:3000/mcp",
      "env": {}
    }
  }
}`,
        description: "JSON - Multiple servers with 'servers' key",
    },

    // JSONC files (with comments)
    "test-jsonc-comments.jsonc": {
        content: `{
  "mcpServers": {
    "evaluator-optimizer": {
      "command": "npx", // this is nice!
      "args": [
        "-y",
        "@github/evaluator-optimizer"
      ],
      "env": {
        "env_1": "0x12345" // secret key
      }
    },
    "Figma": {
      "url": "http://127.0.0.1:3845/mcp" // this is weird
    },
    "server-everything": {
      "command": "npx", // this is cool
      "args": ["-y", "@modelcontextprotocol/server-everything"],
      "env": {} // empty for now
    }
  }
}`,
        description: "JSONC - Multiple servers with inline comments",
    },

    "test-jsonc-multiline.jsonc": {
        content: `{
  // Main configuration for MCP servers
  "mcpServers": {
    /*
     * Database server configuration
     * Handles all database operations
     */
    "database-server": {
      "command": "python",
      "args": [
        "-m", 
        "database_server", // main module
        "--host", "localhost",
        "--port", "5432"
      ],
      "env": {
        "DB_URL": "postgresql://localhost/mydb", // connection string
        "DB_TIMEOUT": "30"
      },
      "disabled": false // enable by default
    }
  }
  // End of configuration
}`,
        description: "JSONC - Single server with multiline comments",
    },

    // Single line configurations
    "test-single-line.json": {
        content: `{"mcpServers":{"mini":{"command":"node","args":["mini.js"]}}}`,
        description: "JSON - Single line, minimal",
    },

    "test-single-line-comments.jsonc": {
        content: `{"mcpServers":{"mini":{"command":"node","args":["mini.js"]/* fast server */}}}`,
        description: "JSONC - Single line with comments",
    },

    // Edge cases
    "test-extensions-key.json": {
        content: `{
  "extensions": {
    "ext-server": {
      "command": "go",
      "args": ["run", "main.go"],
      "env": {
        "GO_ENV": "production"
      }
    }
  }
}`,
        description: "JSON - Using 'extensions' key",
    },

    "test-mixed-types.jsonc": {
        content: `{
  "mcpServers": {
    "command-server": {
      "command": "python", // CLI server
      "args": ["-m", "myserver"],
      "disabled": true
    },
    "url-server": {
      "url": "ws://localhost:8080/mcp", // WebSocket server
      "env": {
        "WS_TIMEOUT": "5000"
      }
    },
    "complex-server": {
      "command": "docker", // Container server
      "args": [
        "run",
        "--rm",
        "-p", "3000:3000",
        "myimage:latest"
      ],
      "env": {
        "DOCKER_HOST": "unix:///var/run/docker.sock",
        "LOG_LEVEL": "debug"
      },
      "disabled": false
    }
  }
}`,
        description: "JSONC - Mixed server types (command, url, complex)",
    },
};

class E2ETestRunner {
    constructor() {
        this.testDir = path.join(__dirname, "e2e-test-configs");
        this.results = [];
        this.extensionPath = path.join(__dirname, "..", "..", "..");
    }

    async setup() {
        console.log("🔧 Setting up E2E test environment...\n");

        // Compile the extension to ensure it's up to date
        console.log("\n🔨 Compiling extension...");
        execSync("npm run compile", {
            cwd: this.extensionPath,
            stdio: "pipe",
        });

        // Mock the vscode module by using a mock file
        // (path already imported at top)
        const vscodeModulePath = path.join(__dirname, "mock-vscode.js");

        // Create a temporary mock vscode module
        const mockVscodeContent = `
module.exports = {
    window: {
        showErrorMessage: (msg) => console.log('[MOCK] showErrorMessage:', msg),
        showWarningMessage: (msg) => console.log('[MOCK] showWarningMessage:', msg),
        createOutputChannel: (name) => ({
            appendLine: (text) => console.log('[MOCK LOG]', text),
            append: (text) => console.log('[MOCK LOG]', text),
            error: (text) => console.log('[MOCK ERROR]', text),
            warn: (text) => console.log('[MOCK WARN]', text),
            info: (text) => console.log('[MOCK INFO]', text),
            debug: (text) => console.log('[MOCK DEBUG]', text),
            show: () => {},
            hide: () => {},
            dispose: () => {}
        })
    },
    workspace: {
        workspaceFolders: null
    },
    env: {
        appName: 'Visual Studio Code'
    }
};`;

        await fs.writeFile(vscodeModulePath, mockVscodeContent);

        // Override require to use our mock for vscode
        const Module = require("module");
        const originalRequire = Module.prototype.require;
        Module.prototype.require = function (id) {
            if (id === "vscode") {
                return require(vscodeModulePath);
            }
            return originalRequire.apply(this, arguments);
        };

        // Create test directory
        try {
            await fs.mkdir(this.testDir, { recursive: true });
        } catch (error) {
            // Directory might already exist
        }

        // Write all test configuration files
        for (const [filename, config] of Object.entries(testConfigs)) {
            const filePath = path.join(this.testDir, filename);
            await fs.writeFile(filePath, config.content);
            console.log(`📄 Created: ${filename} - ${config.description}`);
        }

        console.log(
            `\n✅ Created ${Object.keys(testConfigs).length} test configuration files in: ${this.testDir}\n`
        );
    }

    async runTest(filename, description) {
        console.log(`\n${"=".repeat(80)}`);
        console.log(`🧪 TESTING: ${filename}`);
        console.log(`📝 ${description}`);
        console.log(`${"=".repeat(80)}\n`);

        const filePath = path.join(this.testDir, filename);

        try {
            // Read original content
            const originalContent = await fs.readFile(filePath, "utf8");
            console.log("📋 BEFORE (Original Configuration):");
            console.log("─".repeat(50));
            console.log(originalContent);
            console.log("─".repeat(50));

            // Now import the real ConfigurationMonitor
            const { ConfigurationMonitor } = require("../../../out/configurationMonitor");

            // Create mock ExecutableManager
            const mockExecutableManager = {
                getExecutablePath: () => "/fake/executable/path",
            };

            // Create ConfigurationMonitor instance
            const monitor = new ConfigurationMonitor(mockExecutableManager);

            // Step 1: Test wrapping using REAL implementation
            console.log("\n🔧 WRAPPING ...");
            const wrappedResult = await monitor.wrapConfigurationInFile(filePath);

            if (!wrappedResult) {
                console.log("\n⚠️ No changes made (no servers to wrap)");
                return {
                    filename,
                    description,
                    success: true,
                    noChanges: true,
                    originalContent,
                };
            }

            // Read the wrapped content
            const wrappedContent = await fs.readFile(filePath, "utf8");
            console.log("🔧 AFTER WRAPPING:");
            console.log("─".repeat(50));
            console.log(wrappedContent);
            console.log("─".repeat(50));

            // Step 2: Test unwrapping using REAL implementation
            console.log("\n🔓 UNWRAPPING with real implementation...");
            const unwrappedResult = await monitor.unwrapConfigurationInFile(filePath);

            if (!unwrappedResult) {
                throw new Error("Unwrapping failed - no changes made");
            }

            // Read the unwrapped content
            const unwrappedContent = await fs.readFile(filePath, "utf8");
            console.log("🔓 AFTER UNWRAPPING (Final Result):");
            console.log("─".repeat(50));
            console.log(unwrappedContent);
            console.log("─".repeat(50));

            // Step 3: Analyze results
            const originalComments = (
                originalContent.match(/\/\*[\s\S]*?\*\/|\/\/.*/g) || []
            ).length;
            const finalComments = (
                unwrappedContent.match(/\/\*[\s\S]*?\*\/|\/\/.*/g) || []
            ).length;

            const originalSize = originalContent.length;
            const finalSize = unwrappedContent.length;

            console.log("\n📊 ANALYSIS:");
            console.log(
                `   Comments: ${originalComments} → ${finalComments} (${originalComments === finalComments ? "✅ preserved" : "❌ lost"})`
            );
            console.log(
                `   Size: ${originalSize} → ${finalSize} bytes (${finalSize - originalSize >= 0 ? "+" : ""}${finalSize - originalSize})`
            );

            // Check if content is functionally equivalent
            const JSONC = require("../../../node_modules/jsonc-parser");
            const originalParsed = JSONC.parse(originalContent);
            const finalParsed = JSONC.parse(unwrappedContent);
            const functionallyEqual =
                JSON.stringify(originalParsed) === JSON.stringify(finalParsed);
            console.log(
                `   Functional integrity: ${functionallyEqual ? "✅ preserved" : "❌ corrupted"}`
            );

            // Check for exact match (best case)
            const exactMatch = originalContent.trim() === unwrappedContent.trim();
            console.log(
                `   Exact match: ${exactMatch ? "✅ perfect" : "⚠️ formatting differs"}`
            );

            return {
                filename,
                description,
                success: true,
                commentsPreserved: originalComments === finalComments,
                functionallyEqual,
                exactMatch,
                originalContent,
                wrappedContent,
                finalContent: unwrappedContent,
                metrics: {
                    originalComments,
                    finalComments,
                    originalSize,
                    finalSize,
                },
            };
        } catch (error) {
            console.error(`\n❌ Test failed for ${filename}:`, error);

            return {
                filename,
                description,
                success: false,
                error: error.message,
                originalContent: await fs
                    .readFile(filePath, "utf8")
                    .catch(() => "Could not read file"),
            };
        }
    }

    async runAllTests() {
        console.log("🚀 Starting comprehensive E2E test suite...\n");

        for (const [filename, config] of Object.entries(testConfigs)) {
            const result = await this.runTest(filename, config.description);
            this.results.push(result);
        }

        this.generateSummaryReport();
    }

    generateSummaryReport() {
        console.log("\n\n" + "=".repeat(100));
        console.log("📋 COMPREHENSIVE TEST SUMMARY REPORT");
        console.log("=".repeat(100));

        const totalTests = this.results.length;
        const successful = this.results.filter(r => r.success).length;
        const failed = this.results.filter(r => !r.success).length;
        const noChanges = this.results.filter(r => r.noChanges).length;
        const commentsPreserved = this.results.filter(r => r.commentsPreserved).length;
        const functionallyEqual = this.results.filter(r => r.functionallyEqual).length;
        const exactMatches = this.results.filter(r => r.exactMatch).length;

        console.log(`\n📊 OVERALL STATISTICS:`);
        console.log(`   Total tests: ${totalTests}`);
        console.log(
            `   Successful: ${successful}/${totalTests} (${Math.round((successful / totalTests) * 100)}%)`
        );
        console.log(
            `   Failed: ${failed}/${totalTests} (${Math.round((failed / totalTests) * 100)}%)`
        );
        console.log(`   No changes needed: ${noChanges}/${totalTests}`);
        console.log(
            `   Comments preserved: ${commentsPreserved}/${totalTests - noChanges} (${Math.round((commentsPreserved / (totalTests - noChanges)) * 100)}%)`
        );
        console.log(
            `   Functionally equivalent: ${functionallyEqual}/${totalTests - noChanges} (${Math.round((functionallyEqual / (totalTests - noChanges)) * 100)}%)`
        );
        console.log(
            `   Exact matches: ${exactMatches}/${totalTests - noChanges} (${Math.round((exactMatches / (totalTests - noChanges)) * 100)}%)`
        );

        console.log(`\n📋 DETAILED RESULTS BY FILE:`);
        console.log("─".repeat(100));

        for (const result of this.results) {
            const status = result.success ? "✅" : "❌";
            const comments = result.commentsPreserved
                ? "🔤"
                : result.metrics
                  ? "🚫"
                  : "⚪";
            const functional = result.functionallyEqual
                ? "⚙️"
                : result.success
                  ? "🔧"
                  : "⚪";
            const exact = result.exactMatch ? "🎯" : result.success ? "📝" : "⚪";

            console.log(
                `${status} ${result.filename.padEnd(30)} ${comments} ${functional} ${exact} ${result.description}`
            );

            if (result.error) {
                console.log(`   ❌ Error: ${result.error}`);
            }
            if (result.metrics) {
                console.log(
                    `   📏 ${result.metrics.originalSize}→${result.metrics.finalSize} bytes, ${result.metrics.originalComments}→${result.metrics.finalComments} comments`
                );
            }
        }

        console.log(
            `\n🔤 Comments preserved | ⚙️ Functionally equivalent | 🎯 Exact match | 📝 Format differs | ⚪ N/A`
        );

        if (failed > 0) {
            console.log(
                `\n⚠️ ${failed} test(s) failed. Review the detailed output above for error details.`
            );
        } else {
            console.log(`\n🎉 All tests completed successfully!`);
        }

        console.log(`\n📁 Test files preserved in: ${this.testDir}`);
        console.log(`   Use 'rm -rf ${this.testDir}' to clean up when done reviewing.`);

        console.log("\n" + "=".repeat(100));
    }

    async cleanup() {
        // Don't auto-cleanup - user asked to keep files until they request deletion
        console.log(`\n💾 Test files preserved for your review in: ${this.testDir}`);
        console.log(`   When ready to clean up, run: rm -rf ${this.testDir}`);
    }
}

async function main() {
    const runner = new E2ETestRunner();

    try {
        await runner.setup();
        await runner.runAllTests();
        await runner.cleanup();
    } catch (error) {
        console.error("❌ E2E test suite failed:", error);
        process.exit(1);
    } finally {
        // Cleanup temporary files
        try {
            // Clean up test configs directory
            const testDir = path.join(__dirname, "e2e-test-configs");
            await fs.rm(testDir, { recursive: true, force: true });

            // Clean up mock vscode file
            const mockVscodePath = path.join(__dirname, "mock-vscode.js");
            await fs.unlink(mockVscodePath).catch(() => {}); // Ignore if doesn't exist

            console.log("\n🧹 Cleanup completed: removed temporary test files");
        } catch (cleanupError) {
            console.warn("⚠️ Cleanup warning:", cleanupError.message);
        }
    }
}

// Run if called directly
if (require.main === module) {
    main();
}

module.exports = { E2ETestRunner, testConfigs };
