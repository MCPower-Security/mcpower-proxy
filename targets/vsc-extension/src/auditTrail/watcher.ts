/**
 * Audit Trail File Watcher
 * Monitors ~/.mcpower/audit_trail.log for changes
 */

import { promises as fs } from "fs";
import { homedir } from "os";
import { join } from "path";
import chokidar from "chokidar";
import { AuditEntry } from "./types";
import { parseAuditTrail } from "./utils";
import log from "../log";

export class AuditTrailWatcher {
    private readonly auditFilePath: string;
    private currentAppUid: string | null = null;
    private watcher: chokidar.FSWatcher | undefined;
    private onChangeCallback: ((entries: AuditEntry[]) => void) | undefined;
    private debounceTimer: NodeJS.Timeout | null = null;
    private readonly debounceDelay = 500;

    constructor() {
        this.auditFilePath = join(homedir(), ".mcpower", "audit_trail.log");
    }

    async start(
        appUid: string,
        onChange: (entries: AuditEntry[]) => void
    ): Promise<void> {
        this.currentAppUid = appUid;
        this.onChangeCallback = onChange;

        // Initial load
        const entries = await this.loadEntries(appUid);
        onChange(entries);

        // Start watching if not already
        if (!this.watcher) {
            await this.startWatcher();
        }
    }

    async setAppUid(newAppUid: string): Promise<void> {
        if (this.currentAppUid === newAppUid) {
            return;
        }

        log.info(`Updating audit trail filter to app_uid: ${newAppUid}`);
        this.currentAppUid = newAppUid;

        // Reload with new filter
        if (this.onChangeCallback) {
            const entries = await this.loadEntries(newAppUid);
            this.onChangeCallback(entries);
        }
    }

    private async startWatcher(): Promise<void> {
        try {
            log.info(`Starting audit trail watcher: ${this.auditFilePath}`);

            this.watcher = chokidar.watch(this.auditFilePath, {
                persistent: true,
                ignoreInitial: true,
                usePolling: true,
                interval: 2000,
                binaryInterval: 2000,
                awaitWriteFinish: { stabilityThreshold: 800, pollInterval: 200 },
                ignorePermissionErrors: true,
                followSymlinks: false,
                disableGlobbing: true,
            });

            this.watcher.on("change", () => this.handleFileChange());
            this.watcher.on("add", () => this.handleFileChange());
            this.watcher.on("error", (error: Error) => {
                log.error(`Audit trail watcher error: ${error}`);
            });

            log.info("Audit trail watcher started");
        } catch (error) {
            log.error(`Failed to start audit trail watcher: ${error}`);
        }
    }

    private handleFileChange(): void {
        if (this.debounceTimer) {
            clearTimeout(this.debounceTimer);
        }

        this.debounceTimer = setTimeout(async () => {
            if (this.currentAppUid && this.onChangeCallback) {
                const entries = await this.loadEntries(this.currentAppUid);
                this.onChangeCallback(entries);
            }
            this.debounceTimer = null;
        }, this.debounceDelay);
    }

    private async loadEntries(appUid: string): Promise<AuditEntry[]> {
        try {
            await fs.access(this.auditFilePath);
            const content = await fs.readFile(this.auditFilePath, "utf8");
            return parseAuditTrail(content, appUid);
        } catch (error) {
            if ((error as NodeJS.ErrnoException).code !== "ENOENT") {
                log.error(`Failed to load audit trail: ${error}`);
            }
            return [];
        }
    }

    async dispose(): Promise<void> {
        if (this.debounceTimer) {
            clearTimeout(this.debounceTimer);
            this.debounceTimer = null;
        }

        if (this.watcher) {
            log.info("Stopping audit trail watcher");
            await this.watcher.close();
            this.watcher = undefined;
        }
    }
}
