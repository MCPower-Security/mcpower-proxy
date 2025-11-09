import * as vscode from "vscode";
import { ConfigurationMonitor } from "./configurationMonitor";
import { CursorHooksMonitor } from "./cursorHooksMonitor";
import { UvRunner } from "./uvRunner";

export interface ExtensionState {
    context: vscode.ExtensionContext;
    uvRunner: UvRunner;
    configMonitor: ConfigurationMonitor;
    cursorHooksMonitor?: CursorHooksMonitor; // Only initialized when running in Cursor IDE
}
