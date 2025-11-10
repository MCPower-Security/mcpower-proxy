/**
 * Audit Trail TreeDataProvider
 * Provides data for the audit trail TreeView with 3-level hierarchy:
 * 1. Prompt groups (events with prompt_id) -> Tool call groups (by event_id) -> Individual events -> Fields
 * 2. Non-prompt event_id groups (events with event_id but no prompt_id) -> Individual events -> Fields
 * 3. Flat events (no prompt_id and no event_id) -> Fields
 */

import * as vscode from "vscode";
import {
    AuditEntry,
    EventIdGroup,
    NestedFieldItem,
    ProcessedAuditItem,
    PromptGroup,
} from "./types";
import { AuditTrailItem } from "./item";
import { AuditTrailWatcher } from "./watcher";
import {
    formatFullTimestamp,
    formatTimestamp,
    generateEventTitle,
    groupByEventId,
    groupByPromptId,
    isExpandableValue,
} from "./utils";

export class AuditTrailProvider implements vscode.TreeDataProvider<AuditTrailItem> {
    private _onDidChangeTreeData = new vscode.EventEmitter<
        AuditTrailItem | undefined | void
    >();
    readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

    private entries: AuditEntry[] = [];
    private watcher: AuditTrailWatcher;

    constructor() {
        this.watcher = new AuditTrailWatcher();
    }

    async setAppUid(appUid: string): Promise<void> {
        await this.watcher.start(appUid, entries => {
            this.entries = entries;
            this.refresh();
        });
    }

    async updateAppUid(newAppUid: string): Promise<void> {
        await this.watcher.setAppUid(newAppUid);
    }

    refresh(): void {
        this._onDidChangeTreeData.fire();
    }

    getTreeItem(element: AuditTrailItem): vscode.TreeItem {
        return element;
    }

    async getChildren(element?: AuditTrailItem): Promise<AuditTrailItem[]> {
        if (!element) {
            // Root level: group entries and show hierarchically
            return this.getRootItems();
        }

        switch (element.itemType) {
            case "prompt_group":
                // Show tool call groups within this prompt
                return this.getToolCallGroups(element.promptGroup!);

            case "event_id_group":
                // Show individual events within this event_id group
                return this.getEventsForGroup(element.eventIdGroup!);

            case "event":
                // Show fields for this event
                return this.createFieldItems(element.processedItem!.entry);

            case "field":
                // Expand nested field if it's an expandable object
                if (element.nestedField?.isExpandable) {
                    return this.createNestedFieldItems(element.nestedField);
                }
                return [];

            default:
                return [];
        }
    }

    private getRootItems(): AuditTrailItem[] {
        const items: AuditTrailItem[] = [];

        // 1. Group entries with prompt_id
        const promptGroups = groupByPromptId(this.entries);
        for (const promptGroup of promptGroups) {
            items.push(new AuditTrailItem("prompt_group", undefined, promptGroup));
        }

        // 2. Group entries with event_id but NO prompt_id
        const entriesWithoutPromptId = this.entries.filter(e => !e.prompt_id);
        const eventIdGroups = groupByEventId(entriesWithoutPromptId);
        for (const eventIdGroup of eventIdGroups) {
            items.push(
                new AuditTrailItem("event_id_group", undefined, undefined, eventIdGroup)
            );
        }

        // 3. Flat entries (no prompt_id and no event_id) - root level, no timestamp
        const flatEntries = this.entries.filter(e => !e.prompt_id && !e.event_id);
        for (const entry of flatEntries) {
            const processedItem = this.createProcessedItem(entry);
            items.push(
                new AuditTrailItem(
                    "event",
                    processedItem,
                    undefined,
                    undefined,
                    undefined,
                    false
                )
            );
        }

        // Sort ALL root items by timestamp descending (newest first)
        items.sort((a, b) => {
            const timestampA =
                a.promptGroup?.timestamp ||
                a.eventIdGroup?.timestamp ||
                a.processedItem?.entry.timestamp ||
                "";
            const timestampB =
                b.promptGroup?.timestamp ||
                b.eventIdGroup?.timestamp ||
                b.processedItem?.entry.timestamp ||
                "";
            return timestampB.localeCompare(timestampA);
        });

        return items;
    }

    private getToolCallGroups(promptGroup: PromptGroup): AuditTrailItem[] {
        const items: AuditTrailItem[] = [];

        // Add event_id groups for this prompt's entries
        const eventIdGroups = groupByEventId(promptGroup.entries);
        for (const eventIdGroup of eventIdGroups) {
            items.push(
                new AuditTrailItem(
                    "event_id_group",
                    undefined,
                    undefined,
                    eventIdGroup
                )
            );
        }

        // Spread nested prompt groups' event_id groups directly into this level
        if (promptGroup.nestedGroups) {
            for (const nestedGroup of promptGroup.nestedGroups) {
                const nestedEventIdGroups = groupByEventId(nestedGroup.entries);
                for (const nestedEventIdGroup of nestedEventIdGroups) {
                    items.push(
                        new AuditTrailItem(
                            "event_id_group",
                            undefined,
                            undefined,
                            nestedEventIdGroup
                        )
                    );
                }
            }
        }

        // Sort all items by timestamp (oldest first - chronological order)
        items.sort((a, b) => {
            const timestampA = a.eventIdGroup?.timestamp || "";
            const timestampB = b.eventIdGroup?.timestamp || "";
            return timestampA.localeCompare(timestampB);
        });

        return items;
    }

    private getEventsForGroup(eventIdGroup: EventIdGroup): AuditTrailItem[] {
        // Show individual events for this event_id group (3rd level - show timestamps)
        return eventIdGroup.entries.map(entry => {
            const processedItem = this.createProcessedItem(entry);
            return new AuditTrailItem(
                "event",
                processedItem,
                undefined,
                undefined,
                undefined,
                true
            );
        });
    }

    private createFieldItems(entry: AuditEntry): AuditTrailItem[] {
        const processedItem = this.createProcessedItem(entry);
        const ignoredFields = ["tool", "endpoint", "server"];

        // Special handling for inspect_agent_request_result: only show result.reasons as "reasons"
        if (
            entry.event_type === "inspect_agent_request_result" ||
            entry.event_type === "inspect_mcp_response_result"
        ) {
            const reasons = entry.data?.result?.reasons;
            if (reasons) {
                const nestedField: NestedFieldItem = {
                    key: "reasons",
                    value: reasons,
                    isExpandable: isExpandableValue(reasons),
                };
                return [
                    new AuditTrailItem(
                        "field",
                        processedItem,
                        undefined,
                        undefined,
                        nestedField
                    ),
                ];
            }
            return [];
        }

        const fields: Array<[string, any]> = [
            ...(entry.data && typeof entry.data === "object"
                ? Object.entries(entry.data).filter(
                      ([key]) => !ignoredFields.includes(key)
                  )
                : []),
        ];

        return fields.map(([key, value]) => {
            const nestedField: NestedFieldItem = {
                key,
                value,
                isExpandable: isExpandableValue(value),
            };
            return new AuditTrailItem(
                "field",
                processedItem,
                undefined,
                undefined,
                nestedField
            );
        });
    }

    private createNestedFieldItems(parentField: NestedFieldItem): AuditTrailItem[] {
        const value = parentField.value;
        if (!isExpandableValue(value)) {
            return [];
        }

        // Handle arrays with indexed keys
        if (Array.isArray(value)) {
            return value.map((childValue, index) => {
                const nestedField: NestedFieldItem = {
                    key: `[${index}]`,
                    value: childValue,
                    isExpandable: isExpandableValue(childValue),
                };
                return new AuditTrailItem(
                    "field",
                    undefined,
                    undefined,
                    undefined,
                    nestedField
                );
            });
        }

        // Handle objects with their keys
        const entries = Object.entries(value);
        return entries.map(([key, childValue]) => {
            const nestedField: NestedFieldItem = {
                key,
                value: childValue,
                isExpandable: isExpandableValue(childValue),
            };
            return new AuditTrailItem(
                "field",
                undefined,
                undefined,
                undefined,
                nestedField
            );
        });
    }

    private createProcessedItem(entry: AuditEntry): ProcessedAuditItem {
        return {
            entry,
            formattedTimestamp: formatTimestamp(entry.timestamp),
            fullTimestamp: formatFullTimestamp(entry.timestamp),
            title: generateEventTitle(entry.event_type, entry.data),
        };
    }

    async dispose(): Promise<void> {
        await this.watcher.dispose();
    }
}
