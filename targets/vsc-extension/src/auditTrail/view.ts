/** Audit Trail View Controller */

import * as vscode from "vscode";
import { promises as fs } from "fs";
import { join } from "path";
import { AuditTrailProvider } from "./provider";
import { AuditTrailItem } from "./item";
import log from "../log";

export class AuditTrailView {
    private treeView: vscode.TreeView<AuditTrailItem> | undefined;
    private readonly provider: AuditTrailProvider;

    constructor(private context: vscode.ExtensionContext) {
        this.provider = new AuditTrailProvider();
    }

    async initialize(): Promise<void> {
        this.treeView = vscode.window.createTreeView("mcpower.auditTrail", {
            treeDataProvider: this.provider,
            showCollapseAll: false,
        });

        this.registerCommands();
        this.registerWorkspaceListeners();

        const appUid = await this.getWorkspaceAppUid();
        if (appUid) {
            await this.provider.setAppUid(appUid);
            log.info("Audit trail view initialized");
        }
    }

    private registerCommands(): void {
        this.context.subscriptions.push(
            vscode.commands.registerCommand(
                "mcpower.copyAuditEntry",
                (item: AuditTrailItem) =>
                    this.copyToClipboard(item.getJsonLine(), "Audit entry copied")
            ),
            vscode.commands.registerCommand(
                "mcpower.copyAuditField",
                (item: AuditTrailItem) => this.copyFieldValue(item)
            )
        );
    }

    private registerWorkspaceListeners(): void {
        this.context.subscriptions.push(
            vscode.workspace.onDidChangeWorkspaceFolders(async () => {
                const appUid = await this.getWorkspaceAppUid();
                if (appUid) {
                    await this.provider.updateAppUid(appUid);
                } else {
                    this.provider.refresh();
                }
            })
        );
    }

    private async copyFieldValue(item: AuditTrailItem): Promise<void> {
        if (item.itemType !== "field" || !item.nestedField) {
            return;
        }

        const value = item.nestedField.value;
        const key = item.nestedField.key;

        const textToCopy =
            typeof value === "object" ? JSON.stringify(value, null, 2) : String(value);

        await this.copyToClipboard(textToCopy, `Copied ${key}`);
    }

    private async copyToClipboard(text: string, successMessage: string): Promise<void> {
        try {
            await vscode.env.clipboard.writeText(text);
            vscode.window.showInformationMessage(successMessage);
        } catch (error) {
            log.error(`Failed to copy to clipboard: ${error}`);
            vscode.window.showErrorMessage("Failed to copy to clipboard");
        }
    }

    private async getWorkspaceAppUid(): Promise<string | null> {
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
        if (!workspaceFolder) {
            return null;
        }

        const appUidPath = join(workspaceFolder.uri.fsPath, ".mcpower", "app_uid");

        try {
            const content = await fs.readFile(appUidPath, "utf8");
            return content.trim();
        } catch {
            return null;
        }
    }

    async dispose(): Promise<void> {
        this.treeView?.dispose();
        await this.provider.dispose();
    }
}
