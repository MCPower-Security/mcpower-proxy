import * as vscode from "vscode";
import { ConfigurationMonitor } from "./configurationMonitor";
import { ExecutableManager } from "./executableManager";
import { UserIdManager } from "./userIdManager";
import { AuditTrailView } from "./auditTrail";
import { ExtensionState } from "./types";
import log from "./log";

let state: ExtensionState | undefined;

// noinspection JSUnusedGlobalSymbols
export async function activate(context: vscode.ExtensionContext) {
    log.info("Extension is now active");

    try {
        // Handle extension updates before initialization
        await handleExtensionUpdate(context);

        // Initialize extension state
        state = await initializeExtensionState(context);

        // Listen for workspace folder changes
        // Requirements: 13.8 - Re-establish monitoring when workspace changes
        const workspaceChangeListener = vscode.workspace.onDidChangeWorkspaceFolders(
            async event => {
                log.info(
                    `Workspace folders changed: added=${event.added.join(",")}, removed=${event.removed.join(",")}`
                );
                await state!.configMonitor.handleWorkspaceChange();
            }
        );
        context.subscriptions.push(workspaceChangeListener);

        await state.configMonitor.startMonitoring(state.executableManager);

        const auditTrailView = new AuditTrailView(context);
        await auditTrailView.initialize();
        context.subscriptions.push({
            dispose: () => auditTrailView.dispose(),
        });

        vscode.window.showInformationMessage("✅ MCPower Security activated");
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
    const userId = await new UserIdManager().getUserId();

    // Initialize executable manager
    const executableManager = new ExecutableManager(context);
    await executableManager.initialize();

    // Initialize configuration monitor
    const configMonitor = new ConfigurationMonitor();

    return {
        context,
        userId,
        executableManager,
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
