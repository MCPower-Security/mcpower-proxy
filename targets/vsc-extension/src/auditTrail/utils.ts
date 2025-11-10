/**
 * Utility functions for audit trail processing
 */

import { AuditEntry, EVENT_TITLES } from "./types";

/**
 * Generate custom title for specific event types that need server name
 */
export function generateEventTitle(eventType: string, data: any): string {
    const baseTitle = EVENT_TITLES[eventType] || eventType;

    // Customize title for mcpower_start
    if (eventType === "mcpower_start") {
        // Server name is mandatory in mcpower_start data
        let serverName = data.wrapped_server_name;
        if (serverName === "mcpower_cursor") {
            serverName = "Cursor Hooks";
        }
        return `MCPower Started for ${serverName}`;
    }

    // Customize title for inspect_agent_request_result
    if (
        eventType === "inspect_agent_request_result" ||
        eventType === "inspect_mcp_response_result"
    ) {
        const decision = data?.result?.decision || "unknown";
        return `${baseTitle}: ${decision}`;
    }

    return baseTitle;
}

function padZero(num: number, length: number = 2): string {
    return String(num).padStart(length, "0");
}

interface DateParts {
    day: string;
    month: string;
    year: number;
    hours: string;
    minutes: string;
    seconds: string;
    milliseconds: string;
}

function parseDateParts(isoTimestamp: string): DateParts {
    const date = new Date(isoTimestamp);
    return {
        day: padZero(date.getDate()),
        month: padZero(date.getMonth() + 1),
        year: date.getFullYear(),
        hours: padZero(date.getHours()),
        minutes: padZero(date.getMinutes()),
        seconds: padZero(date.getSeconds()),
        milliseconds: padZero(date.getMilliseconds(), 3),
    };
}

/**
 * Format timestamp for display (DD-MM HH:MM:SS)
 */
export function formatTimestamp(isoTimestamp: string): string {
    const { day, month, hours, minutes, seconds } = parseDateParts(isoTimestamp);
    return `${day}-${month} ${hours}:${minutes}:${seconds}`;
}

/**
 * Format full timestamp for tooltip (DD-MM-YYYY HH:MM:SS.mmm UTC)
 */
export function formatFullTimestamp(isoTimestamp: string): string {
    const { day, month, year, hours, minutes, seconds, milliseconds } =
        parseDateParts(isoTimestamp);
    return `${day}-${month}-${year} ${hours}:${minutes}:${seconds}.${milliseconds} UTC`;
}

/**
 * Parse audit trail log file (JSON Lines format)
 * Skips corrupted lines and continues parsing
 */
export function parseAuditTrail(content: string, appUid: string): AuditEntry[] {
    const lines = content.split("\n").filter(line => line.trim());
    const entries: AuditEntry[] = [];

    for (const line of lines) {
        try {
            const entry = JSON.parse(line) as AuditEntry;

            // Filter by app_uid
            if (entry.app_uid === appUid) {
                entries.push(entry);
            }
        } catch (error) {
            // Skip corrupted line and continue
            console.warn(`Skipping corrupted audit line: ${line.substring(0, 50)}...`);
        }
    }

    // Sort by timestamp descending (newest first)
    // Entries are appended to file, so newest are at the end
    return entries.sort(
        (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
    );
}

/**
 * Extract tool name from entry data
 * Tool is expected to be in data.tool (string or object with name property)
 */
function extractToolName(entry: AuditEntry): string | undefined {
    if (entry.data?.tool) {
        return typeof entry.data.tool === "string"
            ? entry.data.tool
            : entry.data.tool.name;
    }
    return undefined;
}

/**
 * Extract server name from entry data
 * Server is expected to be in data.server (string or object with name property)
 */
function extractServerName(entry: AuditEntry): string | undefined {
    if (entry.data?.server) {
        return typeof entry.data.server === "string"
            ? entry.data.server
            : entry.data.server.name;
    }
    return undefined;
}

/**
 * Extract user prompt from entries with the same prompt_id
 * Returns the user_prompt field from the first entry that has it,
 * or extracts prompt from prompt_submission event params if available
 */
function extractUserPrompt(entries: AuditEntry[]): string {
    // First, check for explicit user_prompt field
    for (const entry of entries) {
        if (entry.user_prompt) {
            return entry.user_prompt;
        }
    }

    // Fallback: check if first entry is prompt_submission with prompt in params
    if (entries.length > 0) {
        const firstEntry = entries[0];
        if (firstEntry.event_type === "prompt_submission") {
            const prompt = firstEntry.data?.params?.prompt;
            if (prompt && typeof prompt === "string" && prompt.trim()) {
                return prompt;
            }
        }
    }

    return "Prompt N/A";
}

/**
 * Group entries by prompt_id, splitting on prompt_submission events
 * and nesting orphaned tool call groups under matching prompt_submission groups
 * Returns an array of PromptGroup objects
 */
export function groupByPromptId(entries: AuditEntry[]): import("./types").PromptGroup[] {
    const promptMap = new Map<string, AuditEntry[]>();

    // Group entries by prompt_id
    for (const entry of entries) {
        if (entry.prompt_id) {
            if (!promptMap.has(entry.prompt_id)) {
                promptMap.set(entry.prompt_id, []);
            }
            promptMap.get(entry.prompt_id)!.push(entry);
        }
    }

    // Convert map to PromptGroup array, splitting on prompt_submission
    const promptGroups: import("./types").PromptGroup[] = [];
    for (const [prompt_id, groupEntries] of promptMap) {
        // Sort entries within group by timestamp (oldest first)
        groupEntries.sort(
            (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
        );

        // Split into sub-groups on prompt_submission events
        let currentSubGroup: AuditEntry[] = [];
        
        for (const entry of groupEntries) {
            if (entry.event_type === "prompt_submission" && currentSubGroup.length > 0) {
                // Create a group for accumulated entries before this prompt_submission
                promptGroups.push({
                    prompt_id,
                    user_prompt: extractUserPrompt(currentSubGroup),
                    entries: currentSubGroup,
                    timestamp: currentSubGroup[0].timestamp,
                });
                // Start new sub-group with this prompt_submission
                currentSubGroup = [entry];
            } else {
                currentSubGroup.push(entry);
            }
        }
        
        // Add the final sub-group if it has entries
        if (currentSubGroup.length > 0) {
            promptGroups.push({
                prompt_id,
                user_prompt: extractUserPrompt(currentSubGroup),
                entries: currentSubGroup,
                timestamp: currentSubGroup[0].timestamp,
            });
        }
    }

    // Sort prompt groups by timestamp (newest first)
    promptGroups.sort(
        (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
    );

    // Nest orphaned tool call groups under matching prompt_submission groups
    return nestOrphanedGroups(promptGroups);
}

/**
 * Nest orphaned tool call groups (without prompt_submission) under matching prompt_submission groups
 */
function nestOrphanedGroups(groups: import("./types").PromptGroup[]): import("./types").PromptGroup[] {
    // Separate groups with and without prompt_submission
    const groupsWithSubmission: import("./types").PromptGroup[] = [];
    const orphanedGroups: import("./types").PromptGroup[] = [];

    for (const group of groups) {
        const hasSubmission = group.entries.some(e => e.event_type === "prompt_submission");
        if (hasSubmission) {
            groupsWithSubmission.push(group);
        } else {
            orphanedGroups.push(group);
        }
    }

    // For each orphaned group, find the closest matching prompt_submission group
    for (const orphan of orphanedGroups) {
        const orphanTimestamp = new Date(orphan.timestamp).getTime();
        const orphanPrompt = orphan.user_prompt;

        // Find the closest prompt_submission group that came before this orphan
        let closestMatch: import("./types").PromptGroup | undefined;
        let closestTimeDiff = Infinity;

        for (const group of groupsWithSubmission) {
            const groupTimestamp = new Date(group.timestamp).getTime();
            
            // Must come before the orphan
            if (groupTimestamp >= orphanTimestamp) {
                continue;
            }

            // Check for exact prompt match
            const submissionEntry = group.entries.find(e => e.event_type === "prompt_submission");
            if (submissionEntry) {
                const submissionPrompt = submissionEntry.data?.params?.prompt;
                
                if (submissionPrompt === orphanPrompt) {
                    const timeDiff = orphanTimestamp - groupTimestamp;
                    if (timeDiff < closestTimeDiff) {
                        closestTimeDiff = timeDiff;
                        closestMatch = group;
                    }
                }
            }
        }

        // Nest the orphan under the closest match
        if (closestMatch) {
            if (!closestMatch.nestedGroups) {
                (closestMatch as any).nestedGroups = [];
            }
            closestMatch.nestedGroups!.push(orphan);
        }
    }

    // Remove orphaned groups that were nested (keep only top-level groups)
    const nestedPromptIds = new Set<string>();
    for (const group of groupsWithSubmission) {
        if (group.nestedGroups) {
            for (const nested of group.nestedGroups) {
                nestedPromptIds.add(nested.prompt_id + "-" + nested.timestamp);
            }
        }
    }

    return groups.filter(group => {
        const hasSubmission = group.entries.some(e => e.event_type === "prompt_submission");
        if (hasSubmission) {
            return true; // Keep all groups with prompt_submission
        }
        // Keep orphaned groups that weren't nested
        return !nestedPromptIds.has(group.prompt_id + "-" + group.timestamp);
    });
}

/**
 * Group entries by event_id
 * Returns an array of EventIdGroup objects
 */
export function groupByEventId(entries: AuditEntry[]): import("./types").EventIdGroup[] {
    const eventMap = new Map<string, AuditEntry[]>();

    // Group entries by event_id
    for (const entry of entries) {
        if (entry.event_id) {
            if (!eventMap.has(entry.event_id)) {
                eventMap.set(entry.event_id, []);
            }
            eventMap.get(entry.event_id)!.push(entry);
        }
    }

    // Convert map to EventIdGroup array
    const eventGroups: import("./types").EventIdGroup[] = [];
    for (const [event_id, groupEntries] of eventMap) {
        // Sort entries within group by timestamp (oldest first for display)
        groupEntries.sort(
            (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
        );

        const firstEntry = groupEntries[0];
        const toolName = extractToolName(firstEntry);

        let serverName = extractServerName(firstEntry);
        if (serverName === "mcpower_cursor") {
            serverName = "Cursor Hooks";
        }

        // Determine title based on event type
        let title = "";
        if (toolName) {
            title = `Tool Call: ${serverName} - ${toolName}`;
        } else if (firstEntry.event_type === "init_tools") {
            // Server name is mandatory in init_tools payload
            const initServerName = firstEntry.data.payload.server.name;
            switch (initServerName) {
                case "mcpower_cursor":
                    title = "Cursor Hooks Initialization";
                    break;
                default:
                    title = `Tools Initialization called on ${initServerName}`;
                    break;
            }
        } else if (firstEntry.event_type === "record_user_confirmation") {
            title = "User Confirmation";
        } else {
            // Use event title from mapping
            title = EVENT_TITLES[firstEntry.event_type] || firstEntry.event_type;
        }

        eventGroups.push({
            event_id,
            entries: groupEntries,
            tool_name: toolName,
            title,
            timestamp: firstEntry.timestamp,
        });
    }

    // Sort event groups by timestamp (newest first)
    return eventGroups.sort(
        (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
    );
}

/**
 * Check if a value is expandable (object or array)
 * Returns true for plain objects and arrays (not null)
 */
export function isExpandableValue(value: any): boolean {
    if (value === null || value === undefined) {
        return false;
    }

    // Check if it's an object or array
    return typeof value === "object";
}

/**
 * Truncate JSON string to specified length
 * Returns the first N characters with "..." if truncated
 */
export function truncateJson(value: any, maxChars: number = 80): string {
    const jsonStr = JSON.stringify(value);

    if (jsonStr.length <= maxChars) {
        return jsonStr;
    }

    return jsonStr.substring(0, maxChars) + "...";
}
