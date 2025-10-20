import * as fs from "fs";
import * as os from "os";
import * as path from "path";
import { v4 as uuidv4 } from "uuid";
import log from "./log";

export class UserIdManager {
    constructor() {}

    /**
     * Gets or generates a unique user ID per machine (shared across all AI clients)
     * Requirements: 12.4 - Implement unique user ID generation per machine installation
     */
    async getUserId(): Promise<string> {
        const filePath = this.getUserIdFilePath();

        // Try to read existing user ID
        if (fs.existsSync(filePath)) {
            const userId = await fs.promises.readFile(filePath, "utf8");
            const trimmedUserId = userId.trim();
            log.debug(`Using existing user ID: ${trimmedUserId}`);
            return trimmedUserId;
        }

        // Generate new user ID
        const userId = uuidv4();

        // Ensure directory exists
        const dirPath = path.dirname(filePath);
        await fs.promises.mkdir(dirPath, { recursive: true });

        // Store user ID
        await fs.promises.writeFile(filePath, userId, "utf8");

        log.debug(`Generated new user ID: ${userId}`);
        return userId;
    }

    /**
     * Gets the user ID file path: ~/.mcpower/uid
     */
    private getUserIdFilePath(): string {
        return path.join(os.homedir(), ".mcpower", "uid");
    }
}
