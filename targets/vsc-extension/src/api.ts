import {
    detectIDEFromScriptPath,
    getApiUrl,
    getUserUid,
    getVersion,
    mapOS,
} from "./utils";
import log from "./log";

/**
 * Report lifecycle event to backend API
 * Fails silently on any error
 *
 * @param state - Lifecycle state: install, update, uninstall, heartbeat
 */
export async function reportLifecycleEvent(state: string): Promise<void> {
    try {
        const version = getVersion();
        if (!version) {
            log.debug(`Lifecycle event skipped: could not determine version`);
            return;
        }

        const client = detectIDEFromScriptPath();
        if (!client) {
            log.debug(`Lifecycle event skipped: could not detect client`);
            return;
        }

        const userUid = await getUserUid();
        if (!userUid) {
            log.debug(`Lifecycle event skipped: user UID not found`);
            return;
        }

        const apiUrl = await getApiUrl();
        if (!apiUrl) {
            log.debug(`Lifecycle event skipped: API URL not found`);
            return;
        }

        const os = mapOS();

        const payload = {
            state,
            version,
            client,
            os,
        };

        const response = await fetch(`${apiUrl}/client-state`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-User-UID": userUid,
            },
            body: JSON.stringify(payload),
        });

        if (!response.ok) {
            log.debug(`Lifecycle event failed: HTTP ${response.status}`);
            return;
        }

        log.debug(`Lifecycle event reported: ${state}`);
    } catch (error) {
        log.debug(`Lifecycle event error: ${error}`);
    }
}
