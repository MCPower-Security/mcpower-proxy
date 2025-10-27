import * as vscode from "vscode";
import { ConfigurationMonitor } from "./configurationMonitor";
import { UvRunner } from "./uvRunner";
import { AuditTrailView } from "./auditTrail";
import { ExtensionState } from "./types";
import log from "./log";
import { hasShownActivationMessage, markActivationMessageShown } from "./utils";
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
        const currentVersion = context.extension.packageJSON.version;
        const storedVersion = context.globalState.get<string>("extensionVersion");

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

        if (isFirstActivation || isUpdate) {
            // Initialize UvRunner
            const uvRunner = new UvRunner(context);
            await uvRunner.initialize();

            // Warm up the new version
            log.info(`Warming up mcpower-proxy==${currentVersion}...`);
            await vscode.window.withProgress(
                {
                    location: vscode.ProgressLocation.Notification,
                    title: "🛠️ Installing MCPower, please wait...",
                    cancellable: false,
                },
                async () => await uvRunner.warmUp(currentVersion)
            );

            // Only after successful warm-up, save the new version
            await context.globalState.update("extensionVersion", currentVersion);

            // Perform full initialization
            await performInitialization(context);

            // Show appropriate message
            if (isFirstActivation) {
                if (!hasShownActivationMessage(context)) {
                    await showPersistentAction(
                        "✅ MCPower Security Installed",
                        "Activate",
                        () => {
                            markActivationMessageShown(context);
                            setTimeout(() => {
                                vscode.commands.executeCommand(
                                    "workbench.action.reloadWindow"
                                );
                            }, 100);
                        }
                    );
                }
            } else {
                await showPersistentAction("✅ MCPower updated", "Apply changes", () => {
                    setTimeout(() => {
                        vscode.commands.executeCommand("workbench.action.reloadWindow");
                    }, 100);
                });
            }
        } else {
            // No update needed, just initialize normally
            await performInitialization(context);
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
