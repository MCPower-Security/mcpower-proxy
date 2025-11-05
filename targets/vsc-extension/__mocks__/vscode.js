/**
 * Vscode mock for jest tests
 * Uses the same pattern as configurationMonitor tests
 */

module.exports = {
    window: {
        showErrorMessage: () => {},
        showWarningMessage: () => {},
        showInformationMessage: () => {},
        withProgress: () => Promise.resolve(),
        createOutputChannel: () => ({
            appendLine: () => {},
            append: () => {},
            error: () => {},
            warn: () => {},
            info: () => {},
            debug: () => {},
            show: () => {},
            hide: () => {},
            dispose: () => {},
            name: "MCPower Security",
        }),
    },
    workspace: {
        workspaceFolders: null,
        onDidChangeWorkspaceFolders: () => ({ dispose: () => {} }),
    },
    commands: {
        registerCommand: () => ({ dispose: () => {} }),
        executeCommand: () => Promise.resolve(),
    },
    env: {
        appName: "Visual Studio Code",
    },
    ProgressLocation: {
        Notification: 15,
    },
    Uri: {
        file: (path) => ({ fsPath: path }),
    },
};

