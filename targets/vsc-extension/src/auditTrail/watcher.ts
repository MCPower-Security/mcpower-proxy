/**
 * Audit Trail File Watcher
 * Monitors ~/.defenter/audit_trail.log for changes
 */

import { promises as fs } from "fs";
import { homedir } from "os";
import { join } from "path";
import { FileWatcher } from "@defenter/common-ts/watcher";
import { AuditEntry } from "./types";
import { parseAuditTrail } from "./utils";
import log from "../log";

export class AuditTrailWatcher {
    private readonly auditFilePath: string;
    private currentAppUid: string | null = null;
    private fileWatcher: FileWatcher;
    private onChangeCallback: ((entries: AuditEntry[]) => void) | undefined;

    constructor() {
        this.auditFilePath = join(homedir(), ".defenter", "audit_trail.log");
        this.fileWatcher = new FileWatcher({
            onFileProcess: async () => this.handleFileChange(),
            logger: log,
        });
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
        if (!this.fileWatcher.isActive()) {
            await this.fileWatcher.startWatching([this.auditFilePath]);
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

    private async handleFileChange(): Promise<void> {
        if (this.currentAppUid && this.onChangeCallback) {
            const entries = await this.loadEntries(this.currentAppUid);
            this.onChangeCallback(entries);
        }
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
        log.info("Stopping audit trail watcher");
        await this.fileWatcher.stopWatching();
    }
}
