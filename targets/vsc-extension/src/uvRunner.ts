import * as vscode from "vscode";
import * as path from "path";
import * as fs from "fs";
import * as os from "os";
import { spawn } from "child_process";
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
            "--from",
            "git+https://github.com/MCPower-Security/mcpower-proxy.git",
            "python",
            "-m",
            "main",
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
        const isWindows = os.platform() === "win32";
        const localBinPath = path.join(os.homedir(), ".local", "bin");
        
        const candidates = isWindows
            ? ["uvx.exe", "uvx", path.join(localBinPath, "uvx.exe")]
            : ["uvx", path.join(localBinPath, "uvx")];
        
        for (const candidate of candidates) {
            if (await this.commandExists(candidate)) {
                return candidate;
            }
        }
        return undefined;
    }

    private async commandExists(command: string): Promise<boolean> {
        // For bare commands (no path separators), check if they're in PATH
        if (!command.includes(path.sep) && !command.includes("/")) {
            return new Promise(resolve => {
                const testCmd = os.platform() === "win32" ? "where" : "which";
                const proc = spawn(testCmd, [command], { stdio: "ignore" });
                proc.on("close", code => resolve(code === 0));
                proc.on("error", () => resolve(false));
            });
        }
        
        // For paths, check if file exists
        try {
            const stats = await fs.promises.stat(command);
            return stats.isFile();
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
        return new Promise((resolve, reject) => {
            const proc = spawn(command, args, {
                stdio: "pipe",
                shell: false,
            });

            let stdout = "";
            let stderr = "";

            proc.stdout?.on("data", data => {
                stdout += data.toString();
            });

            proc.stderr?.on("data", data => {
                stderr += data.toString();
            });

            proc.on("close", code => {
                if (stdout) {
                    log.info(`uvx setup stdout: ${stdout.trim()}`);
                }
                if (stderr) {
                    log.info(`uvx setup stderr: ${stderr.trim()}`);
                }
                resolve(code ?? 0);
            });

            proc.on("error", err => {
                log.error(`Failed to run uvx setup script: ${err.message}`);
                reject(err);
            });
        });
    }
}

