// Conditional VS Code import for uninstall script compatibility
let vscode: any;
try {
    vscode = require("vscode");
} catch {
    // Mock VS Code APIs for scripting context
    vscode = {
        window: {
            createOutputChannel: () => ({
                info: (msg: string) => console.log(`[INFO] ${msg}`),
                debug: (msg: string) => console.log(`[DEBUG] ${msg}`),
                warn: (msg: string) => console.warn(`[WARN] ${msg}`),
                error: (msg: string) => console.error(`[ERROR] ${msg}`),
                trace: (msg: string) => console.log(`[TRACE] ${msg}`),
                show: () => {},
                dispose: () => {},
            }),
        },
    };
}

/**
 * Centralized logging module for MCPower Security extension
 * Uses VSCode's LogOutputChannel in extension context, console in scripting context
 */
class Logger {
    private static instance: Logger;
    private outputChannel: any;
    private readonly channelName = "MCPower";

    private constructor() {
        this.outputChannel = vscode.window.createOutputChannel(this.channelName, {
            log: true,
        });
    }

    /**
     * Get the singleton logger instance
     */
    public static getInstance(): Logger {
        if (!Logger.instance) {
            Logger.instance = new Logger();
        }
        return Logger.instance;
    }

    /**
     * Log an informational message
     */
    public info(message: string, ...args: any[]): void {
        this.outputChannel.info(this.formatMessage(message, args));
    }

    /**
     * Log a debug message (only visible when log level is debug)
     */
    public debug(message: string, ...args: any[]): void {
        this.outputChannel.debug(this.formatMessage(message, args));
    }

    /**
     * Log a warning message
     */
    public warn(message: string, ...args: any[]): void {
        this.outputChannel.warn(this.formatMessage(message, args));
    }

    /**
     * Log an error message
     */
    public error(message: string, error?: Error | any, ...args: any[]): void {
        const formattedMessage = this.formatMessage(message, args);
        if (error) {
            const errorDetails =
                error instanceof Error ? error.stack || error.message : String(error);
            this.outputChannel.error(`${formattedMessage} - ${errorDetails}`);
        } else {
            this.outputChannel.error(formattedMessage);
        }
    }

    /**
     * Log a trace message (most verbose, only visible at trace level)
     */
    public trace(message: string, ...args: any[]): void {
        this.outputChannel.trace(this.formatMessage(message, args));
    }

    /**
     * Show the output channel to the user
     */
    public show(): void {
        this.outputChannel.show();
    }

    /**
     * Format message with optional arguments
     */
    private formatMessage(message: string, args: any[]): string {
        if (args.length === 0) {
            return message;
        }

        // Simple string interpolation for arrays/objects
        const formattedArgs = args
            .map(arg => {
                if (typeof arg === "object") {
                    return JSON.stringify(arg, null, 2);
                }
                return String(arg);
            })
            .join(" ");

        return `${message} ${formattedArgs}`;
    }

    /**
     * Dispose of the output channel (cleanup)
     */
    public dispose(): void {
        this.outputChannel.dispose();
    }
}

// Export convenient logging functions
const logger = Logger.getInstance();

export const log = {
    /**
     * Log an informational message
     */
    info: (message: string, ...args: any[]) => logger.info(message, ...args),

    /**
     * Log a debug message
     */
    debug: (message: string, ...args: any[]) => logger.debug(message, ...args),

    /**
     * Log a warning message
     */
    warn: (message: string, ...args: any[]) => logger.warn(message, ...args),

    /**
     * Log an error message
     */
    error: (message: string, error?: Error | any, ...args: any[]) =>
        logger.error(message, error, ...args),

    /**
     * Log a trace message
     */
    trace: (message: string, ...args: any[]) => logger.trace(message, ...args),

    /**
     * Show the log output channel
     */
    show: () => logger.show(),

    /**
     * Dispose logger resources
     */
    dispose: () => logger.dispose(),
};

export default log;
