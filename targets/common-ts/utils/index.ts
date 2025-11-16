import * as JSONC from "jsonc-parser";
import fs from "fs";
import path, { normalize, resolve } from "path";
import os from "os";
import crypto from "crypto";

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
 * Parse and normalize IPv6 address to handle abbreviations
 * Returns null if invalid
 */
const normalizeIPv6 = (ip: string): string | null => {
    try {
        // Remove brackets if present
        ip = ip.replace(/^\[|\]$/g, "");

        // Check for IPv4-mapped IPv6 (e.g., ::ffff:192.0.2.1)
        const ipv4MappedRegex = /^(.*:)(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})$/;
        const ipv4Match = ip.match(ipv4MappedRegex);

        if (ipv4Match) {
            // Handle IPv6 with embedded IPv4
            const [, ipv6Part, ipv4Part] = ipv4Match;
            const ipv4Octets = ipv4Part.split(".").map(Number);

            // Validate IPv4 octets
            if (ipv4Octets.some(octet => octet > 255)) {
                return null;
            }

            // Convert IPv4 to hex
            const ipv4AsHex = [
                ((ipv4Octets[0] << 8) | ipv4Octets[1]).toString(16).padStart(4, "0"),
                ((ipv4Octets[2] << 8) | ipv4Octets[3]).toString(16).padStart(4, "0"),
            ];

            // Reconstruct as pure IPv6
            ip = ipv6Part.replace(/:$/, "") + ":" + ipv4AsHex.join(":");
        }

        // Handle :: abbreviation
        const parts = ip.split("::");
        if (parts.length > 2) {
            // Invalid
            return null;
        }

        const expandSection = (section: string): string[] => {
            return section ? section.split(":") : [];
        };

        let leftParts = expandSection(parts[0]);
        let rightParts = parts.length === 2 ? expandSection(parts[1]) : [];

        // Validate parts are valid hex
        const allParts = [...leftParts, ...rightParts];
        if (allParts.some(part => !/^[0-9a-fA-F]{0,4}$/.test(part))) {
            return null;
        }

        // Expand :: to correct number of 0000 groups
        const totalGroups = 8;
        const missingGroups = totalGroups - leftParts.length - rightParts.length;

        if (missingGroups < 0) {
            // Too many groups
            return null;
        }

        const expanded = [
            ...leftParts,
            ...Array(missingGroups).fill("0000"),
            ...rightParts,
        ];

        // Normalize each group to 4 digits
        return expanded.map(part => part.padStart(4, "0")).join(":");
    } catch {
        return null;
    }
};

/**
 * Check if IPv6 address is in a private/local range
 */
const isPrivateIPv6 = (normalized: string): boolean => {
    // Unspecified address (::)
    if (normalized === "0000:0000:0000:0000:0000:0000:0000:0000") {
        return true;
    }

    // Loopback (::1)
    if (normalized === "0000:0000:0000:0000:0000:0000:0000:0001") {
        return true;
    }

    const firstGroup = parseInt(normalized.substring(0, 4), 16);
    const secondGroup = parseInt(normalized.substring(5, 9), 16);

    // Link-local (fe80::/10)
    if ((firstGroup & 0xffc0) === 0xfe80) {
        // 0xffc0 = mask for /10 CIDR
        return true;
    }

    // Unique local (fc00::/7)
    if ((firstGroup & 0xfe00) === 0xfc00) {
        // 0xfe00 = mask for /7 CIDR (covers fc00:: through fdff::)
        return true;
    }

    // Documentation prefix (2001:db8::/32)
    if (firstGroup === 0x2001 && secondGroup === 0x0db8) {
        return true;
    }

    // IPv4-mapped addresses (::ffff:0:0/96)
    if (normalized.startsWith("0000:0000:0000:0000:0000:ffff:")) {
        // Extract the IPv4 part and check if it's private
        const hexParts = normalized.split(":").slice(-2);
        const ipv4Parts = hexParts
            .map(hex => {
                const num = parseInt(hex, 16);
                return [(num >> 8) & 0xff, num & 0xff];
            })
            .flat();

        const [a, b] = ipv4Parts;
        if (a === 10) {
            return true;
        }
        if (a === 172 && b >= 16 && b <= 31) {
            return true;
        }
        if (a === 192 && b === 168) {
            return true;
        }
        if (a === 169 && b === 254) {
            return true;
        }
        if (a === 127) {
            return true;
        }
        if (a === 0) {
            return true;
        }
    }

    return false;
};

/**
 * Check if a URL points to a remote (non-local) server
 */
export const isRemoteUrl = (url: string): boolean => {
    try {
        const urlObj = new URL(url);
        const hostname = urlObj.hostname.toLowerCase();

        // File URLs are local
        if (urlObj.protocol === "file:") {
            return false;
        }

        // Local hostnames
        const localHostnames = ["localhost", "127.0.0.1", "::1", "0.0.0.0"];
        if (localHostnames.includes(hostname)) {
            return false;
        }

        // .local domains (mDNS/Bonjour)
        if (hostname.endsWith(".local")) {
            return false;
        }

        // Check if it's an IPv4 address
        const ipv4Regex = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/;
        const ipv4Match = hostname.match(ipv4Regex);

        if (ipv4Match) {
            const [, a, b, c, d] = ipv4Match.map(Number);

            // Validate octets are in valid range
            if (a > 255 || b > 255 || c > 255 || d > 255) {
                return false; // Invalid IP
            }

            // Private IP ranges
            if (a === 10) {
                return false;
            } // 10.0.0.0/8
            if (a === 172 && b >= 16 && b <= 31) {
                return false;
            } // 172.16.0.0/12
            if (a === 192 && b === 168) {
                return false;
            } // 192.168.0.0/16
            if (a === 169 && b === 254) {
                return false;
            } // 169.254.0.0/16 (link-local)
            if (a === 127) {
                return false;
            } // 127.0.0.0/8 (loopback)
            if (a === 0) {
                return false;
            } // 0.0.0.0/8
        }

        // IPv6 private address detection
        if (hostname.includes(":")) {
            const normalized = normalizeIPv6(hostname);
            if (!normalized) {
                // Invalid IPv6
                return false;
            }

            return !isPrivateIPv6(normalized);
        }

        // Everything else is remote
        return true;
    } catch {
        // Invalid URL, treat as non-remote to avoid breaking
        return false;
    }
};

/**
 * Update JSONC file while preserving comments and formatting
 * Uses jsonc-parser's modify API to preserve comments
 */
export async function updateJsoncFile(
    filePath: string,
    updater: (config: any) => any
): Promise<void> {
    try {
        let originalContent = "";
        let config: any;

        // Read existing file if it exists
        if (await fileExists(filePath)) {
            originalContent = await fs.promises.readFile(filePath, "utf8");
            config = parseJsonc(originalContent);
        } else {
            config = {};
        }

        // Apply updates
        const updatedConfig = updater(config);

        // Generate new content preserving comments
        let newContent: string;
        if (originalContent) {
            // Use jsonc-parser to modify while preserving comments
            const edits = JSONC.modify(originalContent, [], updatedConfig, {
                formattingOptions: { tabSize: 2, insertSpaces: true },
            });
            newContent = JSONC.applyEdits(originalContent, edits);
        } else {
            // New file - just stringify
            newContent = JSON.stringify(updatedConfig, null, 2);
        }

        if (newContent !== originalContent) {
            await fs.promises.writeFile(filePath, newContent, "utf8");
        }
    } catch (error) {
        throw new Error(
            `Failed to update JSONC file: ${error instanceof Error ? error.message : String(error)}`
        );
    }
}

/**
 * Read user UID from ~/.defenter/uid
 * Returns null if file doesn't exist
 */
export async function getUserUid(): Promise<string | null> {
    try {
        const uidPath = path.join(os.homedir(), ".defenter", "uid");
        const content = await fs.promises.readFile(uidPath, "utf8");
        return content.trim();
    } catch {
        return null;
    }
}

/**
 * Read API URL from ~/.defenter/config
 * Returns null if file doesn't exist or API_URL not found
 */
export async function getApiUrl(): Promise<string | null> {
    try {
        const configPath = path.join(os.homedir(), ".defenter", "config");
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
 * Generate SHA256 hash of project path for predictable, collision-free directory naming
 */
export function hashProjectPath(projectPath: string): string {
    // Use realpathSync to resolve symlinks, matching Python's Path.resolve() behavior
    let normalizedPath: string;
    try {
        normalizedPath = fs.realpathSync(projectPath);
    } catch {
        // If path doesn't exist, fall back to path.resolve (just normalize)
        normalizedPath = path.resolve(projectPath);
    }
    return crypto.createHash("sha256").update(normalizedPath).digest("hex");
}

/**
 * Get Defenter projects directory path under ~/.defenter/.projects/
 * @param projectPath Optional project/workspace path. If null or invalid, uses _global
 * @returns Path to use for Defenter data: ~/.defenter/.projects/{hash} or ~/.defenter/.projects/_global
 */
export function getProjectDefenterDir(projectPath: string | null): string {
    const baseDir = path.join(os.homedir(), ".defenter", ".projects");
    
    if (projectPath) {
        try {
            if (fs.existsSync(projectPath) && fs.statSync(projectPath).isDirectory()) {
                const projectHash = hashProjectPath(projectPath);
                return path.join(baseDir, projectHash);
            }
        } catch {
            // Fall through to global fallback
        }
    }
    
    return path.join(baseDir, "_global");
}

/**
 * Get full path to app_uid file for a project
 * @param projectPath Optional project/workspace path. If null or invalid, uses _global
 * @returns Full path to app_uid file
 */
export function getProjectAppUidPath(projectPath: string | null): string {
    return path.join(getProjectDefenterDir(projectPath), "app_uid");
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
 * Compare two paths for equality, handling case sensitivity and path forms
 */
export const samePath = (a: string, b: string): boolean => {
    const pa = normalize(resolve(a));
    const pb = normalize(resolve(b));

    if (mapOS() === "windows") {
        // i.e. C: vs c:
        return pa.toLowerCase() === pb.toLowerCase();
    }
    return pa === pb;
};
