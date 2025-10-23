import * as fs from "fs";
import * as path from "path";
import * as crypto from "crypto";
import * as JSONC from "jsonc-parser";

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
 * Calculate SHA256 hash of directory contents
 */
export function hashDirectory(dirPath: string): string {
    if (!fs.existsSync(dirPath)) {
        return "";
    }

    const files: string[] = [];
    
    function walkDir(currentPath: string): void {
        const entries = fs.readdirSync(currentPath, { withFileTypes: true });
        for (const entry of entries) {
            const fullPath = path.join(currentPath, entry.name);
            if (entry.isDirectory()) {
                walkDir(fullPath);
            } else {
                files.push(fullPath);
            }
        }
    }
    
    walkDir(dirPath);
    files.sort();
    
    const hash = crypto.createHash("sha256");
    for (const file of files) {
        const relativePath = path.relative(dirPath, file);
        hash.update(relativePath);
        const content = fs.readFileSync(file);
        hash.update(content);
    }
    
    return hash.digest("hex");
}
