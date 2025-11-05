interface HookEntry {
    command: string;
    [key: string]: any;
}

export interface HooksConfig {
    version: number;
    hooks: {
        [hookName: string]: HookEntry[];
    };
}
