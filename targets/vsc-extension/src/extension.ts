import * as vscode from "vscode";
import { ConfigurationMonitor } from "./configurationMonitor";
import { UvRunner } from "./uvRunner";
import { AuditTrailView } from "./auditTrail";
import { ExtensionState } from "./types";
import log from "./log";
import { hashDirectory } from "./utils";
import { reportLifecycleEvent } from "./api";
import path from "path";
import fs from "fs";

let state: ExtensionState | undefined;

function hasShownActivationMessage(context: vscode.ExtensionContext): boolean {
    return context.globalState.get<boolean>("hasShownActivationMessage", false);
}

function markActivationMessageShown(context: vscode.ExtensionContext): void {
    context.globalState.update("hasShownActivationMessage", true);
}

async function syncProxyToGlobalStorage(
    context: vscode.ExtensionContext
): Promise<boolean> {
    const sourcePath = path.join(context.extensionPath, "proxy-bundled");
    const destPath = path.join(context.globalStorageUri.fsPath, "proxy-bundled");

    if (!fs.existsSync(sourcePath)) {
        log.error("Source proxy-bundled not found in extension package");
        throw new Error("proxy-bundled missing from extension");
    }

    const sourceHash = hashDirectory(sourcePath);
    const destHash = hashDirectory(destPath);

    if (sourceHash === destHash) {
        log.info("Proxy already up-to-date in globalStorage");
        return false;
    }

    log.info(`Syncing proxy to globalStorage (hash mismatch or missing)`);

    if (fs.existsSync(destPath)) {
        fs.rmSync(destPath, { recursive: true, force: true });
    }

    fs.mkdirSync(path.dirname(destPath), { recursive: true });
    fs.cpSync(sourcePath, destPath, { recursive: true });

    log.info("Proxy synced to globalStorage successfully");
    return true;
}

async function performInitialization(context: vscode.ExtensionContext): Promise<void> {
    state = await initializeExtensionState(context);

    // Listen for workspace folder changes
    const workspaceChangeListener = vscode.workspace.onDidChangeWorkspaceFolders(
        async event => {
            log.info(
                `Workspace folders changed: added=${event.added.join(",")}, removed=${event.removed.join(",")}`
            );
            await state!.configMonitor.handleWorkspaceChange();
        }
    );
    context.subscriptions.push(workspaceChangeListener);

    await state.configMonitor.startMonitoring(state.uvRunner);

    const auditTrailView = new AuditTrailView(context);
    await auditTrailView.initialize();
    context.subscriptions.push({
        dispose: () => auditTrailView.dispose(),
    });
}

// noinspection JSUnusedGlobalSymbols
export async function activate(context: vscode.ExtensionContext) {
    log.info("Extension is now active");

    try {
        await handleExtensionUpdate(context);

        const isFirstActivation = !hasShownActivationMessage(context);
        const proxyWasUpdated = await syncProxyToGlobalStorage(context);

        if (isFirstActivation) {
            await vscode.window.withProgress(
                {
                    location: vscode.ProgressLocation.Notification,
                    title: "🛠️ Installing MCPower, please wait...",
                    cancellable: false,
                },
                async () => await performInitialization(context)
            );

            const action = await vscode.window.showInformationMessage(
                "✅ MCPower Security Installed",
                "Activate"
            );

            if (action === "Activate") {
                markActivationMessageShown(context);
                await vscode.commands.executeCommand("workbench.action.reloadWindow");
            }
        } else {
            await performInitialization(context);

            if (proxyWasUpdated) {
                const action = await vscode.window.showInformationMessage(
                    "✅ MCPower updated. Reload required for changes to take effect.",
                    "Reload"
                );
                if (action === "Reload") {
                    await vscode.commands.executeCommand("workbench.action.reloadWindow");
                }
            } else {
                vscode.window.showInformationMessage(`✅ MCPower Security activated`);
            }
        }
    } catch (error) {
        log.error("Failed to activate MCPower Security", error);
        vscode.window.showErrorMessage(`Failed to activate MCPower Security: ${error}`);
    }
}

// noinspection JSUnusedGlobalSymbols
export async function deactivate() {
    if (state) {
        try {
            log.info("Extension deactivating...");
            await state.configMonitor.stopMonitoring();
        } catch (error) {
            log.error("Error during extension deactivation", error);
        }
        state = undefined;
    }
    log.info("Extension deactivated");
}

async function initializeExtensionState(
    context: vscode.ExtensionContext
): Promise<ExtensionState> {
    const uvRunner = new UvRunner(context);
    await uvRunner.initialize();

    // Initialize configuration monitor
    const configMonitor = new ConfigurationMonitor();

    return {
        context,
        uvRunner,
        configMonitor,
    };
}

async function handleExtensionUpdate(context: vscode.ExtensionContext): Promise<void> {
    try {
        const currentVersion = context.extension.packageJSON.version;
        const storedVersion = context.globalState.get<string>("extensionVersion");

        log.debug(
            `Extension version check: current=${currentVersion}, stored=${storedVersion}`
        );

        try {
            if (storedVersion && storedVersion !== currentVersion) {
                log.info(`Extension updated from ${storedVersion} to ${currentVersion}`);
                await reportLifecycleEvent("update");
            } else if (!storedVersion) {
                log.info("First-time extension activation");
                await reportLifecycleEvent("install");
            } else {
                log.debug("Extension version unchanged");
                await reportLifecycleEvent("heartbeat");
            }
        } catch {
            // never crash
        }

        await context.globalState.update("extensionVersion", currentVersion);
    } catch (error) {
        log.warn("Non-critical error handling extension update", error);
    }
}
