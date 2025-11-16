import { afterEach, beforeEach, describe, expect, it } from "@jest/globals";
import { promises as fs } from "fs";
import { join } from "path";
import { tmpdir } from "os";
import { CursorHooksMonitor } from "../index";

/**
 * E2E test for uninstall flow - tests real CursorHooksMonitor class with real file system
 *
 * Tests the critical uninstall scenario where:
 * - CursorHooksMonitor is created without extensionPath (undefined)
 * - unregisterHook() must work despite extensionPath being undefined
 * - Only Defenter hooks (matching defenter-cursor-hook.{sh|bat}) are removed
 * - Other extensions' hooks are preserved
 * - File structure (version, etc.) is maintained
 */
describe("CursorHooksMonitor - E2E Uninstall Flow", () => {
    let testHooksDir: string;
    let testHooksFile: string;

    beforeEach(async () => {
        // Create temporary test directory with unique timestamp to avoid conflicts
        testHooksDir = join(tmpdir(), `test-cursor-hooks-${Date.now()}-${Math.random().toString(36).substring(7)}`);
        await fs.mkdir(testHooksDir, { recursive: true });
        testHooksFile = join(testHooksDir, "hooks.json");
    });

    afterEach(async () => {
        // Cleanup test directory
        try {
            await fs.rm(testHooksDir, { recursive: true, force: true });
        } catch (e) {
            // ignore cleanup errors
        }
    });

    it("should remove all Defenter hooks from hooks.json during uninstall", async () => {
        // Setup: Use test hooks file
        const hooksFile = testHooksFile;

        // Create test hooks.json with our hooks and other extensions' hooks
        const testHooksConfig = {
            version: 1,
            hooks: {
                beforeShellExecution: [
                    { command: "/fake/extension/path/scripts/cursor/hooks/defenter-cursor-hook.sh" },
                    { command: "/other/extension/some-other-hook.sh" },
                ],
                afterShellExecution: [{ command: '"/path with spaces/scripts/cursor/hooks/defenter-cursor-hook.sh"' }],
                beforeReadFile: [{ command: "/fake/path/scripts/cursor/hooks/defenter-cursor-hook.sh" }],
                beforeSubmitPrompt: [{ command: "/fake/path/scripts/cursor/hooks/defenter-cursor-hook.sh" }],
            },
        };

        await fs.writeFile(hooksFile, JSON.stringify(testHooksConfig, null, 2), "utf-8");

        // Verify setup
        const beforeContent = await fs.readFile(hooksFile, "utf-8");
        const beforeConfig = JSON.parse(beforeContent);
        expect(beforeConfig.hooks.beforeShellExecution).toHaveLength(2);
        expect(beforeConfig.hooks.afterShellExecution).toHaveLength(1);
        expect(beforeConfig.hooks.beforeReadFile).toHaveLength(1);
        expect(beforeConfig.hooks.beforeSubmitPrompt).toHaveLength(1);

        // Test: Call unregisterHook (without extensionPath, simulating uninstall)
        const monitor = new CursorHooksMonitor(hooksFile);
        await monitor.unregisterHook();

        // Verify: Defenter hooks should be removed, others preserved
        const afterContent = await fs.readFile(hooksFile, "utf-8");
        const afterConfig = JSON.parse(afterContent);

        // Defenter hooks should be removed
        expect(afterConfig.hooks.afterShellExecution).toBeUndefined();
        expect(afterConfig.hooks.beforeReadFile).toBeUndefined();
        expect(afterConfig.hooks.beforeSubmitPrompt).toBeUndefined();

        // Other extension's hook should remain
        expect(afterConfig.hooks.beforeShellExecution).toBeDefined();
        expect(afterConfig.hooks.beforeShellExecution).toHaveLength(1);
        expect(afterConfig.hooks.beforeShellExecution[0].command).toContain("some-other-hook.sh");
    });

    it("should handle non-existent hooks.json file gracefully", async () => {
        const nonExistentFile = join(testHooksDir, "non-existent.json");

        const monitor = new CursorHooksMonitor(nonExistentFile);

        // Should not throw when file doesn't exist
        await expect(monitor.unregisterHook()).resolves.not.toThrow();
    });

    it("should handle hooks.json with no Defenter hooks", async () => {
        const hooksFile = testHooksFile;

        const testHooksConfig = {
            version: 1,
            hooks: {
                beforeShellExecution: [{ command: "/other/extension/some-hook.sh" }],
            },
        };

        await fs.writeFile(hooksFile, JSON.stringify(testHooksConfig, null, 2), "utf-8");

        const monitor = new CursorHooksMonitor(hooksFile);
        await monitor.unregisterHook();

        // Other hooks should remain unchanged
        const afterContent = await fs.readFile(hooksFile, "utf-8");
        const afterConfig = JSON.parse(afterContent);
        expect(afterConfig.hooks.beforeShellExecution).toHaveLength(1);
        expect(afterConfig.hooks.beforeShellExecution[0].command).toContain("some-hook.sh");
    });

    it("should match hooks with various path formats for current OS", async () => {
        const hooksFile = testHooksFile;
        const isWindows = process.platform === "win32";

        // Test various path formats for the SAME extension type (current OS)
        const testHooksConfig = isWindows
            ? {
                  version: 1,
                  hooks: {
                      beforeShellExecution: [
                          // Windows path variations
                          { command: "C:\\\\Users\\\\user\\\\scripts\\\\cursor\\\\hooks\\\\defenter-cursor-hook.bat" },
                          {
                              command:
                                  '"C:\\\\Program Files\\\\Defenter\\\\scripts\\\\cursor\\\\hooks\\\\defenter-cursor-hook.bat"',
                          },
                          { command: "/other/different-hook.sh" },
                      ],
                  },
              }
            : {
                  version: 1,
                  hooks: {
                      beforeShellExecution: [
                          // Unix path variations
                          {
                              command:
                                  "/home/user/.vscode/extensions/defenter/scripts/cursor/hooks/defenter-cursor-hook.sh",
                          },
                          { command: '"/Users/user name/extensions/scripts/cursor/hooks/defenter-cursor-hook.sh"' },
                          { command: "/other/different-hook.sh" },
                      ],
                  },
              };

        await fs.writeFile(hooksFile, JSON.stringify(testHooksConfig, null, 2), "utf-8");

        const monitor = new CursorHooksMonitor(hooksFile);
        await monitor.unregisterHook();

        // All Defenter hooks (matching current OS) should be removed regardless of path format
        const afterContent = await fs.readFile(hooksFile, "utf-8");
        const afterConfig = JSON.parse(afterContent);

        // Only the other hook should remain
        expect(afterConfig.hooks.beforeShellExecution).toHaveLength(1);
        expect(afterConfig.hooks.beforeShellExecution[0].command).toContain("different-hook.sh");
    });

    it("should handle empty hooks object", async () => {
        const hooksFile = testHooksFile;

        const testHooksConfig = {
            version: 1,
            hooks: {},
        };

        await fs.writeFile(hooksFile, JSON.stringify(testHooksConfig, null, 2), "utf-8");

        const monitor = new CursorHooksMonitor(hooksFile);
        await monitor.unregisterHook();

        // Should not throw and structure should remain
        const afterContent = await fs.readFile(hooksFile, "utf-8");
        const afterConfig = JSON.parse(afterContent);
        expect(afterConfig.version).toBe(1);
        expect(afterConfig.hooks).toEqual({});
    });

    it("should handle multiple Defenter hooks in same hook type", async () => {
        const hooksFile = testHooksFile;

        const testHooksConfig = {
            version: 1,
            hooks: {
                beforeShellExecution: [
                    { command: "/path1/scripts/cursor/hooks/defenter-cursor-hook.sh" },
                    { command: "/path2/scripts/cursor/hooks/defenter-cursor-hook.sh" },
                    { command: "/other/hook.sh" },
                    { command: "/path3/scripts/cursor/hooks/defenter-cursor-hook.sh" },
                ],
            },
        };

        await fs.writeFile(hooksFile, JSON.stringify(testHooksConfig, null, 2), "utf-8");

        const monitor = new CursorHooksMonitor(hooksFile);
        await monitor.unregisterHook();

        // All Defenter hooks removed, other hook preserved
        const afterContent = await fs.readFile(hooksFile, "utf-8");
        const afterConfig = JSON.parse(afterContent);
        expect(afterConfig.hooks.beforeShellExecution).toHaveLength(1);
        expect(afterConfig.hooks.beforeShellExecution[0].command).toBe("/other/hook.sh");
    });

    it("should preserve hooks with additional properties", async () => {
        const hooksFile = testHooksFile;

        const testHooksConfig = {
            version: 1,
            hooks: {
                beforeShellExecution: [{ command: "/other/hook.sh", timeout: 5000, enabled: true }],
            },
        };

        await fs.writeFile(hooksFile, JSON.stringify(testHooksConfig, null, 2), "utf-8");

        const monitor = new CursorHooksMonitor(hooksFile);
        await monitor.unregisterHook();

        // Hook with extra properties should be preserved
        const afterContent = await fs.readFile(hooksFile, "utf-8");
        const afterConfig = JSON.parse(afterContent);
        expect(afterConfig.hooks.beforeShellExecution).toHaveLength(1);
        expect(afterConfig.hooks.beforeShellExecution[0]).toEqual({
            command: "/other/hook.sh",
            timeout: 5000,
            enabled: true,
        });
    });

    it("should preserve file version field", async () => {
        const hooksFile = testHooksFile;

        const testHooksConfig = {
            version: 1,
            hooks: {
                beforeShellExecution: [{ command: "/path/scripts/cursor/hooks/defenter-cursor-hook.sh" }],
            },
        };

        await fs.writeFile(hooksFile, JSON.stringify(testHooksConfig, null, 2), "utf-8");

        const monitor = new CursorHooksMonitor(hooksFile);
        await monitor.unregisterHook();

        // Version field should be preserved
        const afterContent = await fs.readFile(hooksFile, "utf-8");
        const afterConfig = JSON.parse(afterContent);
        expect(afterConfig.version).toBe(1);
    });

    it("should only remove hooks matching current OS script extension", async () => {
        const hooksFile = testHooksFile;

        // Simulate a scenario where hooks.json has scripts from different OS installations
        // (e.g., user switched OS or copied config between machines)
        const testHooksConfig = {
            version: 1,
            hooks: {
                beforeShellExecution: [
                    { command: "/unix/scripts/cursor/hooks/defenter-cursor-hook.sh" },
                    { command: "C:\\\\Windows\\\\scripts\\\\cursor\\\\hooks\\\\defenter-cursor-hook.bat" },
                    { command: "/other/different-hook.sh" },
                ],
            },
        };

        await fs.writeFile(hooksFile, JSON.stringify(testHooksConfig, null, 2), "utf-8");

        const monitor = new CursorHooksMonitor(hooksFile);
        await monitor.unregisterHook();

        const afterContent = await fs.readFile(hooksFile, "utf-8");
        const afterConfig = JSON.parse(afterContent);

        // Only the script matching current OS should be removed
        // On macOS/Linux: removes .sh, keeps .bat
        // On Windows: removes .bat, keeps .sh
        expect(afterConfig.hooks.beforeShellExecution).toHaveLength(2);

        // Verify OS-specific behavior
        const remainingCommands = afterConfig.hooks.beforeShellExecution.map((h: any) => h.command);
        const isWindows = process.platform === "win32";

        // Other hook should always remain
        expect(remainingCommands).toContain("/other/different-hook.sh");

        if (isWindows) {
            // On Windows: .bat removed, .sh remains
            expect(remainingCommands).toContain("/unix/scripts/cursor/hooks/defenter-cursor-hook.sh");
            expect(remainingCommands).not.toContain(
                "C:\\\\Windows\\\\scripts\\\\cursor\\\\hooks\\\\defenter-cursor-hook.bat"
            );
        } else {
            // On Unix: .sh removed, .bat remains
            expect(remainingCommands).not.toContain("/unix/scripts/cursor/hooks/defenter-cursor-hook.sh");
            expect(remainingCommands).toContain(
                "C:\\\\Windows\\\\scripts\\\\cursor\\\\hooks\\\\defenter-cursor-hook.bat"
            );
        }
    });

    it("should handle all four hook types in single operation", async () => {
        const hooksFile = testHooksFile;

        const testHooksConfig = {
            version: 1,
            hooks: {
                beforeShellExecution: [
                    { command: "/path/scripts/cursor/hooks/defenter-cursor-hook.sh" },
                    { command: "/other/hook1.sh" },
                ],
                afterShellExecution: [
                    { command: "/path/scripts/cursor/hooks/defenter-cursor-hook.sh" },
                    { command: "/other/hook2.sh" },
                ],
                beforeReadFile: [
                    { command: "/path/scripts/cursor/hooks/defenter-cursor-hook.sh" },
                    { command: "/other/hook3.sh" },
                ],
                beforeSubmitPrompt: [
                    { command: "/path/scripts/cursor/hooks/defenter-cursor-hook.sh" },
                    { command: "/other/hook4.sh" },
                ],
            },
        };

        await fs.writeFile(hooksFile, JSON.stringify(testHooksConfig, null, 2), "utf-8");

        const monitor = new CursorHooksMonitor(hooksFile);
        await monitor.unregisterHook();

        // Defenter hooks removed from all types, others preserved
        const afterContent = await fs.readFile(hooksFile, "utf-8");
        const afterConfig = JSON.parse(afterContent);

        expect(afterConfig.hooks.beforeShellExecution).toHaveLength(1);
        expect(afterConfig.hooks.beforeShellExecution[0].command).toBe("/other/hook1.sh");

        expect(afterConfig.hooks.afterShellExecution).toHaveLength(1);
        expect(afterConfig.hooks.afterShellExecution[0].command).toBe("/other/hook2.sh");

        expect(afterConfig.hooks.beforeReadFile).toHaveLength(1);
        expect(afterConfig.hooks.beforeReadFile[0].command).toBe("/other/hook3.sh");

        expect(afterConfig.hooks.beforeSubmitPrompt).toHaveLength(1);
        expect(afterConfig.hooks.beforeSubmitPrompt[0].command).toBe("/other/hook4.sh");
    });

    it("should not match hooks with similar but different names", async () => {
        const hooksFile = testHooksFile;

        const testHooksConfig = {
            version: 1,
            hooks: {
                beforeShellExecution: [
                    { command: "/path/scripts/cursor/hooks/defenter-cursor-hook.sh" },
                    { command: "/path/scripts/cursor/hooks/cursor-hook.sh" },
                    { command: "/path/scripts/cursor/hooks/my-defenter-cursor-hook.sh" },
                    { command: "/path/scripts/cursor/hooks/defenter-cursor-hook-backup.sh" },
                ],
            },
        };

        await fs.writeFile(hooksFile, JSON.stringify(testHooksConfig, null, 2), "utf-8");

        const monitor = new CursorHooksMonitor(hooksFile);
        await monitor.unregisterHook();

        // Only exact match should be removed
        const afterContent = await fs.readFile(hooksFile, "utf-8");
        const afterConfig = JSON.parse(afterContent);
        expect(afterConfig.hooks.beforeShellExecution).toHaveLength(3);

        const remainingCommands = afterConfig.hooks.beforeShellExecution.map((h: any) => h.command);
        expect(remainingCommands).toContain("/path/scripts/cursor/hooks/cursor-hook.sh");
        expect(remainingCommands).toContain("/path/scripts/cursor/hooks/my-defenter-cursor-hook.sh");
        expect(remainingCommands).toContain("/path/scripts/cursor/hooks/defenter-cursor-hook-backup.sh");
        expect(remainingCommands).not.toContain("/path/scripts/cursor/hooks/defenter-cursor-hook.sh");
    });

    it("should handle file read/write errors gracefully", async () => {
        const hooksFile = join(testHooksDir, "unwritable", "hooks.json");

        // Create monitor with path in non-existent directory
        const monitor = new CursorHooksMonitor(hooksFile);

        // Should not throw even if file operations fail
        await expect(monitor.unregisterHook()).resolves.not.toThrow();
    });

    it("should cleanup old version hooks and register new version on upgrade", async () => {
        const hooksFile = testHooksFile;

        // Simulate hooks from old version (0.0.1)
        const oldVersionConfig = {
            version: 1,
            hooks: {
                beforeShellExecution: [
                    { command: "/path/to/defenter-0.0.1/scripts/cursor/hooks/defenter-cursor-hook.sh" },
                    { command: "/other/extension/some-hook.sh" },
                ],
                afterShellExecution: [
                    { command: "/path/to/defenter-0.0.1/scripts/cursor/hooks/defenter-cursor-hook.sh" },
                ],
                beforeReadFile: [{ command: "/path/to/defenter-0.0.1/scripts/cursor/hooks/defenter-cursor-hook.sh" }],
                beforeSubmitPrompt: [{ command: "/path/to/defenter-0.0.1/scripts/cursor/hooks/defenter-cursor-hook.sh" }],
            },
        };

        await fs.writeFile(hooksFile, JSON.stringify(oldVersionConfig, null, 2), "utf-8");

        // Verify old version hooks are present
        const beforeContent = await fs.readFile(hooksFile, "utf-8");
        const beforeConfig = JSON.parse(beforeContent);
        expect(beforeConfig.hooks.beforeShellExecution).toHaveLength(2);
        expect(beforeConfig.hooks.beforeShellExecution[0].command).toContain("0.0.1");

        // Simulate upgrade to new version (0.0.2)
        const monitor = new CursorHooksMonitor(hooksFile);
        // Set extensionPath to new version path
        (monitor as any).extensionPath = "/path/to/defenter-0.0.2";
        const newScriptPath = "/path/to/defenter-0.0.2/scripts/cursor/hooks/defenter-cursor-hook.sh";

        // Call registerHooks which should cleanup old version and register new one
        await monitor.registerHooks();

        // Verify upgrade completed correctly
        const afterContent = await fs.readFile(hooksFile, "utf-8");
        const afterConfig = JSON.parse(afterContent);

        // Check all hook types have exactly 2 hooks for beforeShellExecution (other + new version)
        // and 1 hook for others (just new version)
        expect(afterConfig.hooks.beforeShellExecution).toHaveLength(2);
        expect(afterConfig.hooks.afterShellExecution).toHaveLength(1);
        expect(afterConfig.hooks.beforeReadFile).toHaveLength(1);
        expect(afterConfig.hooks.beforeSubmitPrompt).toHaveLength(1);

        // Verify no old version (0.0.1) paths remain
        const allCommands = [
            ...afterConfig.hooks.beforeShellExecution.map((h: any) => h.command),
            ...afterConfig.hooks.afterShellExecution.map((h: any) => h.command),
            ...afterConfig.hooks.beforeReadFile.map((h: any) => h.command),
            ...afterConfig.hooks.beforeSubmitPrompt.map((h: any) => h.command),
        ];

        expect(allCommands.filter((cmd: string) => cmd.includes("0.0.1"))).toHaveLength(0);
        expect(allCommands.filter((cmd: string) => cmd.includes("0.0.2")).length).toEqual(4);

        // Verify other extension's hook is preserved
        expect(afterConfig.hooks.beforeShellExecution[0].command).toContain("some-hook.sh");

        // Verify new version hook is present in all types
        expect(afterConfig.hooks.beforeShellExecution[1].command).toBe(newScriptPath);
        expect(afterConfig.hooks.afterShellExecution[0].command).toBe(newScriptPath);
        expect(afterConfig.hooks.beforeReadFile[0].command).toBe(newScriptPath);
        expect(afterConfig.hooks.beforeSubmitPrompt[0].command).toBe(newScriptPath);
    });
});
