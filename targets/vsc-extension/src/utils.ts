import * as fs from "fs";
import * as JSONC from "jsonc-parser";
import * as path from "path";
import * as os from "os";

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

/**
 * Ensure directory exists, create if it doesn't
 */
export async function ensureDirectoryExists(dirPath: string): Promise<void> {
    if (!(await fileExists(dirPath))) {
        // Directory doesn't exist, create it
        await fs.promises.mkdir(dirPath, { recursive: true });
    }
}

/**
 * Make file executable on Unix systems
 */
export async function makeExecutable(filePath: string): Promise<void> {
    try {
        await fs.promises.chmod(filePath, 0o755);
    } catch (error) {
        throw new Error(`Failed to make executable: ${error}`);
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
 * Serialize object to formatted JSON
 */
export function formatJson(obj: any, space?: string | number): string {
    return JSON.stringify(obj, null, space || 2);
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
 * Clear Nuitka temp cache directories
 */
export async function clearNuitkaTempCache(): Promise<void> {
    try {
        const platform = os.platform();
        let tempCachePath: string;

        if (platform === "win32") {
            // Windows: %LOCALAPPDATA%\mcpower-security\Cache
            const localAppData = process.env.LOCALAPPDATA || process.env.APPDATA || "";
            if (!localAppData) {
                console.warn("Could not determine Windows cache path");
                return;
            }
            tempCachePath = path.join(localAppData, "mcpower-security", "Cache");
        } else {
            // macOS/Linux: ~/.cache/mcpower-security
            tempCachePath = path.join(os.homedir(), ".cache", "mcpower-security");
        }

        if (await fileExists(tempCachePath)) {
            try {
                await fs.promises.rm(tempCachePath, { recursive: true, force: true });
                console.log(`✅ Cleared Nuitka temp cache: ${tempCachePath}`);
            } catch (error) {
                console.warn(`Failed to clear cache ${tempCachePath}:`, error);
            }
        } else {
            console.log(`No cache found at: ${tempCachePath}`);
        }
    } catch (error) {
        console.warn("Error clearing Nuitka temp cache:", error);
    }
}
