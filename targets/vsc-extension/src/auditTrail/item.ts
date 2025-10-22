/**
 * Audit Trail TreeItem
 * Represents a single audit entry in the TreeView
 */

import * as vscode from "vscode";
import { EventIdGroup, NestedFieldItem, ProcessedAuditItem, PromptGroup } from "./types";
import { formatFullTimestamp, truncateJson } from "./utils";

type ItemType = "prompt_group" | "event_id_group" | "event" | "field";

function formatFieldLabel(
    key: string,
    value: any,
    isExpandable: boolean,
    maxLength: number = 80
): string {
    let valueStr: string;

    if (value === null || value === undefined) {
        valueStr = String(value);
    } else if (isExpandable) {
        valueStr = truncateJson(value, maxLength);
    } else {
        valueStr = String(value);
        if (valueStr.length > maxLength) {
            valueStr = valueStr.substring(0, maxLength) + "...";
        }
    }

    return `${key}: ${valueStr}`;
}

export class AuditTrailItem extends vscode.TreeItem {
    public readonly itemType: ItemType;

    constructor(
        itemType: ItemType,
        public readonly processedItem?: ProcessedAuditItem,
        public readonly promptGroup?: PromptGroup,
        public readonly eventIdGroup?: EventIdGroup,
        public readonly nestedField?: NestedFieldItem,
        public readonly isNestedEvent: boolean = false
    ) {
        let label = "";
        let collapsibleState = vscode.TreeItemCollapsibleState.None;
        let tooltip: string | undefined = undefined;
        let contextValue: string = itemType;

        switch (itemType) {
            case "prompt_group":
                // Truncate user prompt to 100 characters
                const truncatedPrompt =
                    promptGroup!.user_prompt.length > 100
                        ? promptGroup!.user_prompt.substring(0, 100) + "..."
                        : promptGroup!.user_prompt;
                label = truncatedPrompt;
                collapsibleState = vscode.TreeItemCollapsibleState.Collapsed;
                tooltip = formatFullTimestamp(promptGroup!.timestamp);
                break;

            case "event_id_group":
                label = eventIdGroup!.title;
                collapsibleState = vscode.TreeItemCollapsibleState.Collapsed;
                tooltip = formatFullTimestamp(eventIdGroup!.timestamp);
                break;

            case "event":
                // 3rd level nested events (within groups) show timestamp
                // Root level flat events do NOT show timestamp
                label = isNestedEvent
                    ? `${processedItem!.formattedTimestamp} ${processedItem!.title}`
                    : processedItem!.title;
                collapsibleState = vscode.TreeItemCollapsibleState.Collapsed;
                tooltip = processedItem!.fullTimestamp;
                break;

            case "field":
                if (!nestedField) {
                    throw new Error("nestedField is required for field itemType");
                }

                label = formatFieldLabel(
                    nestedField.key,
                    nestedField.value,
                    nestedField.isExpandable
                );
                collapsibleState = nestedField.isExpandable
                    ? vscode.TreeItemCollapsibleState.Collapsed
                    : vscode.TreeItemCollapsibleState.None;

                // Update contextValue to distinguish expandable vs leaf fields
                contextValue = nestedField.isExpandable ? "field_expandable" : "field";
                break;
        }

        super(label, collapsibleState);
        this.itemType = itemType;
        this.contextValue = contextValue;
        this.tooltip = tooltip;
    }

    getJsonLine(): string {
        if (this.processedItem) {
            return JSON.stringify(this.processedItem.entry);
        }
        return "{}";
    }
}
