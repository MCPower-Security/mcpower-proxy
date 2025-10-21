import * as vscode from "vscode";
import * as path from "path";
import * as fs from "fs";
import * as os from "os";
import log from "./log";
import { fileExists } from "./utils";
import { UvCommand } from "./types";

const UVX_ENV_KEY = "MCPOWER_UVX_COMMAND";

export class UvRunner {
    private context: vscode.ExtensionContext;
    private uvxCommand: string | undefined;

    constructor(context: vscode.ExtensionContext) {
        this.context = context;
    }

    async initialize(): Promise<void> {
        const cached = this.context.globalState.get<string>(UVX_ENV_KEY);
        if (cached) {
            this.uvxCommand = cached;
            log.debug(`Using cached uvx command: ${cached}`);
            return;
        }

        const scriptPath = await this.installUvx();
        await this.runScript(scriptPath);

        const resolved = await this.findUvxBinary();
        if (!resolved) {
            throw new Error("uvx binary not found after installation");
        }

        this.uvxCommand = resolved;
        await this.context.globalState.update(UVX_ENV_KEY, resolved);

        log.info(`uvx ready: ${resolved}`);
    }

    getCommand(): UvCommand {
        if (!this.uvxCommand) {
            throw new Error("uvx command not available; initialize() first");
        }

        const repoUrl = "https://github.com/MCPower-Security/mcpower-proxy";
        const args = [
            "gh:MCPower-Security/mcpower-proxy",
            "--",
            "python",
            "src/main.py",
        ];

        return { executable: this.uvxCommand, args, repoUrl };
    }

    resetCache(): Promise<void> {
        this.uvxCommand = undefined;
        return this.context.globalState.update(UVX_ENV_KEY, undefined);
    }

    private async installUvx(): Promise<string> {
        const scriptsDir = path.join(this.context.extensionPath, "scripts");
        const platform = os.platform();

        switch (platform) {
            case "darwin":
                return path.join(scriptsDir, "setup-uvx-macos.sh");
            case "linux":
                return path.join(scriptsDir, "setup-uvx-linux.sh");
            case "win32":
                return path.join(scriptsDir, "setup-uvx-windows.ps1");
            default:
                throw new Error(`Unsupported platform: ${platform}`);
        }
    }

    private async runScript(scriptPath: string): Promise<void> {
        if (!(await fileExists(scriptPath))) {
            throw new Error(`uvx setup script missing: ${scriptPath}`);
        }

        log.info(`Running uvx setup script: ${scriptPath}`);

        if (os.platform() === "win32") {
            const powershell = path.join(
                process.env.SYSTEMROOT ?? "C:/Windows",
                "System32",
                "WindowsPowerShell",
                "v1.0",
                "powershell.exe"
            );

            const proc = await vscode.env.openExternal(
                vscode.Uri.parse(
                    `command:workbench.action.terminal.sendSequence?${encodeURIComponent(
                        JSON.stringify({
                            text: `${powershell} -ExecutionPolicy Bypass -File "${scriptPath}"\u000D`,
                        })
                    )}`
                )
            );

            if (!proc) {
                throw new Error("Failed to launch PowerShell for uvx setup");
            }
        } else {
            await fs.promises.chmod(scriptPath, 0o755);

            const terminal = vscode.window.createTerminal({
                name: "MCPower uvx setup",
            });

            terminal.sendText(`"${scriptPath}"`, true);
            terminal.show();
        }
    }

    private async findUvxBinary(): Promise<string | undefined> {
        const candidates = ["uvx", path.join(os.homedir(), ".local", "bin", "uvx")];
        for (const candidate of candidates) {
            if (await this.isExecutable(candidate)) {
                return candidate;
            }
        }
        return undefined;
    }

    private async isExecutable(filePath: string): Promise<boolean> {
        try {
            await fs.promises.access(filePath, fs.constants.X_OK);
            return true;
        } catch {
            return false;
        }
    }
}

