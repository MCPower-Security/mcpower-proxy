/**
 * TypeScript interfaces for MCPower Audit Trail
 */

/**
 * Audit entry from audit_trail.log file
 * Format: JSON Lines (one entry per line)
 */
export interface AuditEntry {
    app_uid: string;
    session_id: string;
    timestamp: string; // ISO 8601 format
    event_type: string;
    data: any;
    event_id?: string; // Optional - pairs request/response for a tool call
    prompt_id?: string; // Optional - groups tool calls by user prompt
    user_prompt?: string; // Optional - user prompt text (only in first event for each prompt_id)
}

/**
 * Processed audit trail item for TreeView display
 */
export interface ProcessedAuditItem {
    readonly entry: AuditEntry;
    readonly formattedTimestamp: string; // DD-MM HH:MM:SS
    readonly fullTimestamp: string; // DD-MM-YYYY HH:MM:SS.mmm UTC (for tooltip)
    readonly title: string; // Human-readable event title
}

/**
 * Group of entries by prompt_id
 */
export interface PromptGroup {
    readonly prompt_id: string;
    readonly user_prompt: string; // User prompt text (may be truncated for display)
    readonly entries: AuditEntry[]; // All entries with this prompt_id
    readonly timestamp: string; // Timestamp of first entry
    readonly nestedGroups?: PromptGroup[]; // Nested prompt groups (e.g., tool calls with different prompt_id but matching user_prompt)
}

/**
 * Group of entries by event_id (for tool calls or API calls like init_tools)
 */
export interface EventIdGroup {
    readonly event_id: string;
    readonly entries: AuditEntry[]; // All entries with this event_id
    readonly tool_name?: string; // Tool name if available (from first entry)
    readonly title: string; // Human-readable title (e.g., "Tool Call: read_file" or "Tools Initialization")
    readonly timestamp: string; // Timestamp of first entry
}

/**
 * Event type to human-readable title mapping
 */
export const EVENT_TITLES: Record<string, string> = {
    // Core Events
    mcpower_start: "MCPower Started",

    // Prompt Submission
    prompt_submission: "Prompt Submission Review",
    prompt_submission_forwarded: "Prompt Submission Approved",

    // Agent Flow
    agent_request: "Code Agent Request",
    agent_request_forwarded: "Code Agent Request Forwarded to MCP",

    // MCP Flow
    mcp_response: "MCP Response",
    mcp_response_forwarded: "MCP Response Forwarded to Code Agent",

    // Security API
    inspect_agent_request: "Security Policy Request Review",
    inspect_agent_request_result: "Security Policy Request Decision",
    inspect_mcp_response: "Security Policy Response Review",
    inspect_mcp_response_result: "Security Policy Response Decision",

    // Tools
    init_tools: "Tools Initialization",
    init_tools_result: "Tools Initialization Result",

    // User Interactions
    user_interaction: "User Interaction",
    user_interaction_result: "User Interaction Decision",

    // User Confirmations
    record_user_confirmation: "Recording User Confirmation",
    record_user_confirmation_result: "User Confirmation Recorded",
};

/**
 * Nested field item for recursive object expansion
 * Stores original value for copy functionality
 */
export interface NestedFieldItem {
    readonly key: string;
    readonly value: any;
    readonly isExpandable: boolean;
}
