import * as vscode from "vscode";
import * as path from "path";
import * as fs from "fs";
import * as os from "os";
import { spawn } from "child_process";
import log from "./log";
import { getCurrentExtensionVersion } from "./utils";
import { UvCommand } from "./types";
import { fileExists, mapOS } from "@mcpower/common-ts/utils";

export class UvRunner {
    private context: vscode.ExtensionContext;
    private uvxCommand: string | undefined;
    private version: string;

    constructor(context: vscode.ExtensionContext) {
        this.context = context;
        this.version = getCurrentExtensionVersion(context);
    }

    async initialize(cleanCache: boolean = false): Promise<void> {
        if (this.uvxCommand) {
            return;
        }

        const scriptPath = await this.installUvx();
        await this.runScript(scriptPath, this.version, cleanCache);

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

        const args = [`mcpower-proxy==${this.version}`];

        return { executable: this.uvxCommand, args };
    }

    private async installUvx(): Promise<string> {
        const scriptsDir = path.join(this.context.extensionPath, "scripts");
        const platform = mapOS();

        switch (platform) {
            case "macos":
                return path.join(scriptsDir, "setup-uvx-macos.sh");
            case "linux":
                return path.join(scriptsDir, "setup-uvx-linux.sh");
            case "windows":
                return path.join(scriptsDir, "setup-uvx-windows.ps1");
            default:
                throw new Error(`Unsupported platform: ${platform}`);
        }
    }

    private async runScript(
        scriptPath: string,
        version: string,
        cleanCache: boolean
    ): Promise<void> {
        if (!(await fileExists(scriptPath))) {
            throw new Error(`uvx setup script missing: ${scriptPath}`);
        }

        if (!version) {
            throw new Error("Version parameter is required for setup script");
        }

        log.info(
            `Running uvx setup script: ${scriptPath} with version ${version}, cleanCache=${cleanCache}`
        );

        if (mapOS() === "windows") {
            await this.runWindowsScript(scriptPath, version, cleanCache);
        } else {
            await this.runUnixScript(scriptPath, version, cleanCache);
        }
    }

    private async findUvxBinary(): Promise<string | undefined> {
        const isWindows = mapOS() === "windows";
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
                const testCmd = mapOS() === "windows" ? "where" : "which";
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

    private async runUnixScript(
        scriptPath: string,
        version: string,
        cleanCache: boolean
    ): Promise<void> {
        await fs.promises.chmod(scriptPath, 0o755);

        const hasUvx = await this.findUvxBinary();
        const args = [version];
        if (cleanCache) {
            args.push("--clean-cache");
        }
        const result = await this.spawnProcess(scriptPath, args);

        if (result !== 0 && !hasUvx) {
            throw new Error("uvx installation failed");
        }
        if (result !== 0) {
            log.warn("uvx setup script returned non-zero exit code; continuing");
        }
    }

    private async runWindowsScript(
        scriptPath: string,
        version: string,
        cleanCache: boolean
    ): Promise<void> {
        const hasUvx = await this.findUvxBinary();
        const args = ["-ExecutionPolicy", "Bypass", "-File", scriptPath, version];
        if (cleanCache) {
            args.push("-CleanCache");
        }

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

            proc.stdout?.on("data", data => {
                const lines = data
                    .toString()
                    .split("\n")
                    .filter((l: string) => l.trim());
                lines.forEach((line: string) => log.info(`[setup] ${line.trim()}`));
            });

            proc.stderr?.on("data", data => {
                const lines = data
                    .toString()
                    .split("\n")
                    .filter((l: string) => l.trim());
                lines.forEach((line: string) => log.info(`[setup] ${line.trim()}`));
            });

            proc.on("close", code => {
                resolve(code ?? 0);
            });

            proc.on("error", err => {
                log.error(`Failed to run uvx setup script: ${err.message}`);
                reject(err);
            });
        });
    }
}
