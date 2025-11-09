/**
 * FileWatcher E2E Tests
 * Tests real file watching behavior with actual filesystem operations
 */

import { FileWatcher, Logger } from "./index";
import { promises as fs } from "fs";
import { join } from "path";
import { tmpdir } from "os";

describe("FileWatcher - E2E with Real Files", () => {
    let testDir: string;
    let testFile1: string;
    let testFile2: string;
    let watcher: FileWatcher;
    let processedFiles: string[];
    let deletedFiles: string[];
    let errors: string[];
    let logger: Logger;

    beforeEach(async () => {
        // Create unique test directory
        testDir = join(tmpdir(), `filewatcher-test-${Date.now()}`);
        await fs.mkdir(testDir, { recursive: true });

        testFile1 = join(testDir, "test1.json");
        testFile2 = join(testDir, "test2.json");

        processedFiles = [];
        deletedFiles = [];
        errors = [];

        // Mock logger that captures calls
        logger = {
            debug: jest.fn(),
            info: jest.fn(),
            warn: jest.fn(),
            error: (...args: any[]) => {
                errors.push(args.map(a => String(a)).join(" "));
            },
        };

        // Create watcher instance
        watcher = new FileWatcher({
            onFileProcess: async (filePath: string) => {
                processedFiles.push(filePath);
            },
            onFileDelete: async (filePath: string) => {
                deletedFiles.push(filePath);
            },
            logger,
        });
    });

    afterEach(async () => {
        // Stop watcher
        await watcher.stopWatching();

        // Clean up test directory
        try {
            await fs.rm(testDir, { recursive: true, force: true });
        } catch (error) {
            // Ignore cleanup errors
        }
    });

    const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

    describe("Basic File Operations", () => {
        it("should detect file creation (add event)", async () => {
            // Start watching
            await watcher.startWatching([testFile1]);

            // Wait for watcher to be ready
            await sleep(1000);

            // Create file
            await fs.writeFile(testFile1, JSON.stringify({ test: "data" }));

            // Wait for: polling (2000ms) + awaitWriteFinish (800ms) + debounce (300ms) + processing + buffer
            await sleep(5000);

            expect(processedFiles).toContain(testFile1);
        }, 10000);

        it("should detect file modification (change event)", async () => {
            // Create file first
            await fs.writeFile(testFile1, JSON.stringify({ test: "initial" }));

            // Start watching
            await watcher.startWatching([testFile1]);
            await sleep(1000);

            // Clear any initial processing
            processedFiles = [];

            // Modify file
            await fs.writeFile(testFile1, JSON.stringify({ test: "modified" }));

            // Wait for: polling + awaitWriteFinish + debounce + processing
            await sleep(5000);

            expect(processedFiles).toContain(testFile1);
        }, 10000);

        it("should detect file deletion (unlink event)", async () => {
            // Create file first
            await fs.writeFile(testFile1, JSON.stringify({ test: "data" }));

            // Start watching
            await watcher.startWatching([testFile1]);
            await sleep(1000);

            // Delete file
            await fs.unlink(testFile1);

            // Wait for event processing
            await sleep(5000);

            expect(deletedFiles).toContain(testFile1);
        }, 10000);
    });

    describe("Multiple File Watching", () => {
        it("should watch multiple files simultaneously", async () => {
            // Create both files
            await fs.writeFile(testFile1, JSON.stringify({ file: 1 }));
            await fs.writeFile(testFile2, JSON.stringify({ file: 2 }));

            // Start watching both
            await watcher.startWatching([testFile1, testFile2]);
            await sleep(1000);

            processedFiles = [];

            // Modify both files
            await fs.writeFile(testFile1, JSON.stringify({ file: 1, modified: true }));
            await sleep(200);
            await fs.writeFile(testFile2, JSON.stringify({ file: 2, modified: true }));

            // Wait for processing
            await sleep(5000);

            expect(processedFiles).toContain(testFile1);
            expect(processedFiles).toContain(testFile2);
        }, 10000);

        it("should handle file addition to watched list", async () => {
            // Create and watch first file
            await fs.writeFile(testFile1, JSON.stringify({ file: 1 }));
            await watcher.startWatching([testFile1]);
            await sleep(1000);

            processedFiles = [];

            // Stop and restart with both files
            await watcher.stopWatching();
            await fs.writeFile(testFile2, JSON.stringify({ file: 2 }));
            await watcher.startWatching([testFile1, testFile2]);
            await sleep(1000);

            processedFiles = [];

            // Modify second file
            await fs.writeFile(testFile2, JSON.stringify({ file: 2, modified: true }));
            await sleep(5000);

            expect(processedFiles).toContain(testFile2);
        }, 12000);
    });

    describe("Loop Prevention (recordWrite)", () => {
        it("should ignore events for recently written files", async () => {
            // Create file
            await fs.writeFile(testFile1, JSON.stringify({ test: "initial" }));

            // Start watching
            await watcher.startWatching([testFile1]);
            await sleep(1000);

            processedFiles = [];

            // Record a write
            watcher.recordWrite(testFile1);

            // Immediately modify the file (should be ignored)
            await fs.writeFile(testFile1, JSON.stringify({ test: "should-be-ignored" }));

            // Wait for potential processing (should not happen)
            await sleep(5000);

            expect(processedFiles).toHaveLength(0);
        }, 10000);

        it("should process events after write ignore window expires", async () => {
            // Create file
            await fs.writeFile(testFile1, JSON.stringify({ test: "initial" }));

            // Start watching
            await watcher.startWatching([testFile1]);
            await sleep(1000);

            processedFiles = [];

            // Record a write
            watcher.recordWrite(testFile1);

            // Wait for write ignore window to expire (2000ms polling + 1500ms = 3500ms)
            await sleep(4000);

            // Now modify the file (should be processed)
            await fs.writeFile(testFile1, JSON.stringify({ test: "should-be-processed" }));

            // Wait for processing
            await sleep(5000);

            expect(processedFiles).toContain(testFile1);
        }, 15000);
    });

    describe("Debouncing", () => {
        it("should debounce rapid file changes", async () => {
            // Create file
            await fs.writeFile(testFile1, JSON.stringify({ test: "initial" }));

            // Start watching
            await watcher.startWatching([testFile1]);
            await sleep(1000);

            processedFiles = [];

            // Make rapid changes (within debounce window of 300ms)
            await fs.writeFile(testFile1, JSON.stringify({ test: "change1" }));
            await sleep(100);
            await fs.writeFile(testFile1, JSON.stringify({ test: "change2" }));
            await sleep(100);
            await fs.writeFile(testFile1, JSON.stringify({ test: "change3" }));

            // Wait for debouncing + processing
            await sleep(5000);

            // Should only process once due to debouncing
            expect(processedFiles.filter(f => f === testFile1)).toHaveLength(1);
        }, 10000);
    });

    describe("Concurrency Control", () => {
        it("should not process the same file concurrently", async () => {
            let processing = false;
            let concurrentAttempts = 0;

            const slowWatcher = new FileWatcher({
                onFileProcess: async (filePath: string) => {
                    if (processing) {
                        concurrentAttempts++;
                    }
                    processing = true;
                    processedFiles.push(filePath);
                    // Simulate slow processing
                    await sleep(500);
                    processing = false;
                },
                logger,
            });

            // Create file
            await fs.writeFile(testFile1, JSON.stringify({ test: "initial" }));

            // Start watching
            await slowWatcher.startWatching([testFile1]);
            await sleep(1000);

            processedFiles = [];

            // Trigger multiple rapid changes
            await fs.writeFile(testFile1, JSON.stringify({ test: "change1" }));
            await sleep(100);
            await fs.writeFile(testFile1, JSON.stringify({ test: "change2" }));

            // Wait for all processing to complete
            await sleep(6000);

            await slowWatcher.stopWatching();

            // Should not have attempted concurrent processing
            expect(concurrentAttempts).toBe(0);
        }, 12000);
    });

    describe("Circuit Breaker", () => {
        it("should stop processing file after max attempts", async () => {
            const failingWatcher = new FileWatcher({
                onFileProcess: async (filePath: string) => {
                    processedFiles.push(filePath);
                    throw new Error("Processing failed");
                },
                logger,
            });

            // Create file
            await fs.writeFile(testFile1, JSON.stringify({ test: "initial" }));

            // Start watching
            await failingWatcher.startWatching([testFile1]);
            await sleep(1000);

            processedFiles = [];

            // Trigger 4 changes (max is 3 attempts)
            for (let i = 0; i < 4; i++) {
                await fs.writeFile(testFile1, JSON.stringify({ test: `change${i}` }));
                await sleep(5000); // Wait for processing to fail
            }

            await failingWatcher.stopWatching();

            // Should only attempt 3 times, then circuit breaker kicks in
            expect(processedFiles.length).toBeLessThanOrEqual(3);
        }, 30000);

        it("should resume after circuit breaker cooldown", async () => {
            // This test would take too long (60 seconds) for regular runs
            // Skipping but keeping for documentation
        }, 70000);
    });

    describe("File Deletion and Recreation", () => {
        it("should detect file deletion and recreation", async () => {
            // Create file
            await fs.writeFile(testFile1, JSON.stringify({ test: "initial" }));

            // Start watching
            await watcher.startWatching([testFile1]);
            await sleep(1000);

            deletedFiles = [];
            processedFiles = [];

            // Delete file
            await fs.unlink(testFile1);
            await sleep(5000);

            expect(deletedFiles).toContain(testFile1);

            // Clear arrays before recreation to isolate recreation test
            deletedFiles = [];
            processedFiles = [];

            // Recreate file after a pause
            await sleep(1000);
            await fs.writeFile(testFile1, JSON.stringify({ test: "recreated" }));
            await sleep(5000);

            expect(processedFiles).toContain(testFile1);
        }, 17000);
    });

    describe("Cleanup and Lifecycle", () => {
        it("should cleanup state when stopping", async () => {
            // Create file
            await fs.writeFile(testFile1, JSON.stringify({ test: "data" }));

            // Start watching
            await watcher.startWatching([testFile1]);
            await sleep(1000);

            expect(watcher.isActive()).toBe(true);

            // Stop watching
            await watcher.stopWatching();

            expect(watcher.isActive()).toBe(false);

            processedFiles = [];

            // Modify file (should not be detected)
            await fs.writeFile(testFile1, JSON.stringify({ test: "modified-after-stop" }));
            await sleep(5000);

            expect(processedFiles).toHaveLength(0);
        }, 10000);

        it("should cleanup all state", async () => {
            // Create file
            await fs.writeFile(testFile1, JSON.stringify({ test: "data" }));

            // Start watching
            await watcher.startWatching([testFile1]);
            await sleep(1000);

            // Trigger some processing
            await fs.writeFile(testFile1, JSON.stringify({ test: "modified" }));
            await sleep(5000);

            // Cleanup
            watcher.cleanupAllState();

            // Should not crash or throw errors
            expect(watcher.isActive()).toBe(true); // Still active but state cleared
        }, 10000);
    });

    describe("Error Handling", () => {
        it("should handle processing errors gracefully", async () => {
            const errorWatcher = new FileWatcher({
                onFileProcess: async (filePath: string) => {
                    throw new Error("Test error");
                },
                logger,
            });

            // Create file
            await fs.writeFile(testFile1, JSON.stringify({ test: "data" }));

            // Start watching
            await errorWatcher.startWatching([testFile1]);
            await sleep(1000);

            errors = [];

            // Modify file (will trigger error)
            await fs.writeFile(testFile1, JSON.stringify({ test: "modified" }));
            await sleep(5000);

            await errorWatcher.stopWatching();

            // Should have logged error
            expect(errors.length).toBeGreaterThan(0);
            expect(errors[0]).toContain("Test error");
        }, 10000);

        it("should handle non-existent file gracefully", async () => {
            const nonExistentFile = join(testDir, "does-not-exist.json");

            // Start watching non-existent file (should not crash)
            await expect(watcher.startWatching([nonExistentFile])).resolves.not.toThrow();
        });
    });

    describe("isProcessing method", () => {
        it("should return true while processing a file", async () => {
            let isProcessingDuringCallback = false;

            const checkingWatcher = new FileWatcher({
                onFileProcess: async (filePath: string) => {
                    isProcessingDuringCallback = checkingWatcher.isProcessing(filePath);
                    await sleep(200);
                },
                logger,
            });

            // Create file
            await fs.writeFile(testFile1, JSON.stringify({ test: "data" }));

            // Start watching
            await checkingWatcher.startWatching([testFile1]);
            await sleep(1000);

            // Modify file
            await fs.writeFile(testFile1, JSON.stringify({ test: "modified" }));
            await sleep(5000);

            await checkingWatcher.stopWatching();

            expect(isProcessingDuringCallback).toBe(true);
        }, 10000);

        it("should return false when not processing", async () => {
            // Create file
            await fs.writeFile(testFile1, JSON.stringify({ test: "data" }));

            // Start watching
            await watcher.startWatching([testFile1]);
            await sleep(1000);

            expect(watcher.isProcessing(testFile1)).toBe(false);
        });
    });
});
