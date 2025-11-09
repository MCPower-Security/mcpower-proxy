import * as fs from "fs";
import * as path from "path";
import * as vscode from "vscode";

/**
 * Get extension version from package.json
 */
export function getVersion(): string | null {
    try {
        const packageJson = require("../../package.json");
        return packageJson.version || null;
    } catch {
        return null;
    }
}

/**
 * Detect IDE from script path - works in uninstall script context
 */
export function detectIDEFromScriptPath(): string | undefined {
    const scriptPath = __dirname.toLowerCase();

    // Standard extension directory patterns
    const idePatterns = [
        {
            name: "cursor",
            patterns: ["/.cursor/extensions/", "\\.cursor\\extensions\\", "/cursor.app/"],
        },
        {
            name: "windsurf",
            patterns: [
                "/.windsurf/extensions/",
                "\\.windsurf\\extensions\\",
                "/windsurf.app/",
            ],
        },
        {
            name: "kiro",
            patterns: ["/.kiro/extensions/", "\\.kiro\\extensions\\", "/kiro.app/"],
        },
        {
            name: "cline",
            patterns: ["/.cline/extensions/", "\\.cline\\extensions\\"],
        },
        {
            name: "claude",
            patterns: ["/.claude/extensions/", "\\.claude\\extensions\\"],
        },
        {
            name: "vscode",
            patterns: [
                "/.vscode/extensions/",
                "\\.vscode\\extensions\\",
                "/visual studio code.app/",
                "/code.app/",
            ],
        },
    ];

    for (const ide of idePatterns) {
        for (const pattern of ide.patterns) {
            if (scriptPath.includes(pattern)) {
                return ide.name;
            }
        }
    }

    return undefined; // Cannot determine IDE - fail safely
}

export function getCurrentExtensionVersion(context: vscode.ExtensionContext): string {
    return context.extension.packageJSON.version;
}

const getVersionFile = (context: vscode.ExtensionContext) =>
    path.join(context.globalStorageUri.fsPath, ".installed_version");

export async function getLastStoredExtensionVersion(
    context: vscode.ExtensionContext
): Promise<string | undefined> {
    try {
        const version = await fs.promises.readFile(getVersionFile(context), "utf8");
        return version.trim();
    } catch {
        return undefined; // File doesn't exist = first install
    }
}

export async function updateStoredExtensionVersion(
    context: vscode.ExtensionContext
): Promise<void> {
    const currentVersion = getCurrentExtensionVersion(context);
    const versionFile = getVersionFile(context);

    // Ensure directory exists
    await fs.promises.mkdir(path.dirname(versionFile), { recursive: true });
    await fs.promises.writeFile(versionFile, currentVersion, "utf8");
}
