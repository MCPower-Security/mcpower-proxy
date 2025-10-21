import * as vscode from "vscode";
import * as path from "path";
import * as fs from "fs";
import * as os from "os";
import log from "./log";
import { fileExists } from "./utils";
import { UvCommand } from "./types";

export class UvRunner {
    private context: vscode.ExtensionContext;
    private uvxCommand: string | undefined;

    constructor(context: vscode.ExtensionContext) {
        this.context = context;
    }

    async initialize(): Promise<void> {
        const scriptPath = await this.installUvx();
        await this.runScript(scriptPath);

        const resolved = await this.findUvxBinary();
        if (!resolved) {
            throw new Error("uvx binary not found after installation");
        }

        this.uvxCommand = resolved;

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
            await this.runWindowsScript(scriptPath);
        } else {
            await this.runUnixScript(scriptPath);
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

    private async runUnixScript(scriptPath: string): Promise<void> {
        await fs.promises.chmod(scriptPath, 0o755);

        const hasUvx = await this.findUvxBinary();
        if (hasUvx) {
            const result = await this.spawnProcess(scriptPath, []);
            if (result === 0) {
                return;
            }
            log.warn("uvx setup script returned non-zero exit code; continuing");
        } else {
            const result = await this.spawnProcess(scriptPath, []);
            if (result !== 0) {
                throw new Error("uvx installation failed");
            }
        }
    }

    private async runWindowsScript(scriptPath: string): Promise<void> {
        const hasUvx = await this.findUvxBinary();
        const args = ["-ExecutionPolicy", "Bypass", "-File", scriptPath];

        const result = await this.spawnProcess("powershell.exe", args);

        if (result !== 0 && !hasUvx) {
            throw new Error("uvx installation failed on Windows");
        }
        if (result !== 0) {
            log.warn("uvx setup script returned non-zero exit code; continuing");
        }
    }

    private spawnProcess(command: string, args: string[]): Promise<number> {
        return new Promise(resolve => {
            const process = vscode.window.createTerminal({
                name: "MCPower uvx setup",
                shellPath: command,
                shellArgs: args,
                isTransient: true,
            });
            process.show();
            process.sendText("", true);
            resolve(0);
        });
    }
}

