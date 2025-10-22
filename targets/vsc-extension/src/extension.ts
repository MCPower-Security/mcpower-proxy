import * as vscode from "vscode";
import { ConfigurationMonitor } from "./configurationMonitor";
import { UvRunner } from "./uvRunner";
import { AuditTrailView } from "./auditTrail";
import { ExtensionState } from "./types";
import log from "./log";
import path from "path";
import fs from "fs";

let state: ExtensionState | undefined;

function getActivationStateFile(context: vscode.ExtensionContext): string {
    return path.join(context.extensionPath, ".activation-state");
}

function hasShownActivationMessage(context: vscode.ExtensionContext): boolean {
    return fs.existsSync(getActivationStateFile(context));
}

function markActivationMessageShown(context: vscode.ExtensionContext): void {
    fs.writeFileSync(
        getActivationStateFile(context),
        JSON.stringify({
            activated: true,
            timestamp: Date.now(),
        })
    );
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

async function handleExtensionUpdate(context: vscode.ExtensionContext): Promise<void> {
    try {
        const currentVersion = context.extension.packageJSON.version;
        const storedVersion = context.globalState.get<string>("extensionVersion");

        log.debug(
            `Extension version check: current=${currentVersion}, stored=${storedVersion}`
        );

        if (storedVersion && storedVersion !== currentVersion) {
            log.info(`Extension updated from ${storedVersion} to ${currentVersion}`);

            // For updates, we don't need to do anything special since our hot-swap architecture
            // preserves configurations within --wrapped-config arguments. The ExecutableManager
            // will automatically extract the new executable based on modification times.
        } else if (!storedVersion) {
            log.info("First-time extension activation");
        } else {
            log.debug("Extension version unchanged");
        }

        await context.globalState.update("extensionVersion", currentVersion);
    } catch (error) {
        log.warn("Non-critical error handling extension update", error);
    }
}
