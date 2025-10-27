import * as fs from "fs";
import * as path from "path";
import * as os from "os";
import * as JSONC from "jsonc-parser";
import * as vscode from "vscode";

/**
 * Check if file exists
 */
export async function fileExists(filePath: string): Promise<boolean> {
    try {
        await fs.promises.access(filePath);
        return true;
    } catch {
        return false;
    }
}

export async function writeFile(filePath: string, content: string): Promise<any> {
    try {
        await fs.promises.writeFile(filePath, content, "utf8");
    } catch (error) {
        throw new Error(`Failed to write file: ${error}`);
    }
}

/**
 * Parse JSONC (JSON with Comments) text using jsonc-parser
 */
export function parseJsonc(text: string): any {
    try {
        // Use jsonc-parser for consistent JSONC handling - no fallbacks
        const parseErrors: JSONC.ParseError[] = [];
        const result = JSONC.parse(text, parseErrors);

        if (parseErrors.length > 0) {
            const errorMessages = parseErrors
                .map(
                    err =>
                        `Error at offset ${err.offset}: ${JSONC.printParseErrorCode(err.error)}`
                )
                .join(", ");
            throw new Error(`JSONC parsing failed: ${errorMessages}`);
        }

        return result;
    } catch (error) {
        throw new Error(
            `JSONC parsing failed: ${error instanceof Error ? error.message : String(error)}`
        );
    }
}

/**
 * Read user UID from ~/.mcpower/uid
 * Returns null if file doesn't exist
 */
export async function getUserUid(): Promise<string | null> {
    try {
        const uidPath = path.join(os.homedir(), ".mcpower", "uid");
        const content = await fs.promises.readFile(uidPath, "utf8");
        return content.trim();
    } catch {
        return null;
    }
}

/**
 * Read API URL from ~/.mcpower/config
 * Returns null if file doesn't exist or API_URL not found
 */
export async function getApiUrl(): Promise<string | null> {
    try {
        const configPath = path.join(os.homedir(), ".mcpower", "config");
        const content = await fs.promises.readFile(configPath, "utf8");

        for (const line of content.split("\n")) {
            const trimmed = line.trim();
            if (trimmed && !trimmed.startsWith("#") && trimmed.includes("=")) {
                const [key, value] = trimmed.split("=", 2);
                if (key.trim() === "API_URL") {
                    return value.trim();
                }
            }
        }

        return null;
    } catch {
        return null;
    }
}

/**
 * Map Node.js os.platform() to standard OS names
 */
export function mapOS(): "macos" | "windows" | "linux" | undefined {
    switch (os.platform()) {
        case "darwin":
            return "macos";
        case "win32":
            return "windows";
        case "linux":
            return "linux";
        default:
            return undefined;
    }
}

/**
 * Get extension version from package.json
 */
export function getVersion(): string | null {
    try {
        const packageJson = require("../package.json");
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

export function hasShownActivationMessage(context: vscode.ExtensionContext): boolean {
    const activationMessagePath = path.join(
        context.globalStorageUri.fsPath,
        ".activation-message-shown"
    );
    return fs.existsSync(activationMessagePath);
}

export function markActivationMessageShown(context: vscode.ExtensionContext): void {
    const activationMessagePath = path.join(
        context.globalStorageUri.fsPath,
        ".activation-message-shown"
    );
    fs.writeFileSync(activationMessagePath, "true");
}
