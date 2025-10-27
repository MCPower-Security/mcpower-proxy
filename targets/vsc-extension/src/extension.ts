import * as vscode from "vscode";
import { ConfigurationMonitor } from "./configurationMonitor";
import { UvRunner } from "./uvRunner";
import { AuditTrailView } from "./auditTrail";
import { ExtensionState } from "./types";
import log from "./log";
import {
    getCurrentExtensionVersion,
    getLastStoredExtensionVersion,
    updateStoredExtensionVersion,
} from "./utils";
import { reportLifecycleEvent } from "./api";

let state: ExtensionState | undefined;

const showPersistentAction = async (
    message: string,
    actionText: string,
    onAction: () => void
): Promise<void> => {
    const commandId = `mcpower.tempAction_${Date.now()}`;

    const disposable = vscode.commands.registerCommand(commandId, () => {
        disposable.dispose();
        onAction();
    });

    await vscode.window.withProgress(
        {
            location: vscode.ProgressLocation.Notification,
            title: `${message} - [${actionText}](command:${commandId})`,
            cancellable: false,
        },
        async () => new Promise(() => {})
    );
};

const performInitialization = async (_state: ExtensionState): Promise<void> => {
    state = _state;

    // Listen for workspace folder changes
    const workspaceChangeListener = vscode.workspace.onDidChangeWorkspaceFolders(
        async event => {
            log.info(
                `Workspace folders changed: added=${event.added.join(",")}, removed=${event.removed.join(",")}`
            );
            await state!.configMonitor.handleWorkspaceChange();
        }
    );
    state.context.subscriptions.push(workspaceChangeListener);

    await state.configMonitor.startMonitoring(state.uvRunner);

    const auditTrailView = new AuditTrailView(state.context);
    await auditTrailView.initialize();
    state.context.subscriptions.push({
        dispose: () => auditTrailView.dispose(),
    });
};

// noinspection JSUnusedGlobalSymbols
export async function activate(context: vscode.ExtensionContext) {
    log.info("Extension is now active");

    try {
        const currentVersion = getCurrentExtensionVersion(context);
        const storedVersion = getLastStoredExtensionVersion(context);

        log.info(
            `Extension version check: current=${currentVersion}, stored=${storedVersion}`
        );

        const isFirstActivation = !storedVersion;
        const isUpdate = storedVersion && storedVersion !== currentVersion;

        // Report lifecycle event
        try {
            if (isUpdate) {
                log.info(`Extension updated from ${storedVersion} to ${currentVersion}`);
                await reportLifecycleEvent("update");
            } else if (isFirstActivation) {
                log.info("First-time extension activation");
                await reportLifecycleEvent("install");
            } else {
                log.debug("Extension version unchanged");
                await reportLifecycleEvent("heartbeat");
            }
        } catch {
            // never crash
        }

        const uvRunner = new UvRunner(context);
        const configMonitor = new ConfigurationMonitor();

        if (isFirstActivation || isUpdate) {
            // Warm up the new version
            log.info(`Warming up mcpower-proxy==${currentVersion}...`);
            await vscode.window.withProgress(
                {
                    location: vscode.ProgressLocation.Notification,
                    title: `🛠️ ${isFirstActivation ? "Installing" : "Updating"} MCPower, please wait...`,
                    cancellable: false,
                },
                async () => await uvRunner.initialize()
            );

            // Only after successful warm-up, save the new version
            await updateStoredExtensionVersion(context);

            // Perform full initialization
            await performInitialization({ context, uvRunner, configMonitor });

            // Show the appropriate message
            if (isFirstActivation) {
                await showPersistentAction(
                    "✅ MCPower Security Installed",
                    "Activate",
                    () => {
                        setTimeout(() => {
                            vscode.commands.executeCommand(
                                "workbench.action.reloadWindow"
                            );
                        }, 100);
                    }
                );
            } else {
                await showPersistentAction("✅ MCPower updated", "Apply changes", () => {
                    setTimeout(() => {
                        vscode.commands.executeCommand("workbench.action.reloadWindow");
                    }, 100);
                });
            }
        } else {
            // No update needed, just initialize normally
            await uvRunner.initialize();
            await performInitialization({ context, uvRunner, configMonitor });
            vscode.window.showInformationMessage(`✅ MCPower Security activated`);
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
