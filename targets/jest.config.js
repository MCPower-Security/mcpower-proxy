module.exports = {
    preset: "ts-jest",
    testEnvironment: "node",
    roots: ["<rootDir>/src"],
    testMatch: ["**/*.test.ts"],
    moduleFileExtensions: ["ts", "tsx", "js", "jsx", "json", "node"],
    collectCoverageFrom: ["src/**/*.ts", "!src/**/*.test.ts", "!src/**/*.d.ts"],
    moduleNameMapper: {
        "^vscode$": "<rootDir>/__mocks__/vscode.js",
    },
    transform: {
        "^.+\\.ts$": [
            "ts-jest",
            {
                tsconfig: {
                    module: "commonjs",
                    esModuleInterop: true,
                    skipLibCheck: true,
                },
            },
        ],
    },
};

