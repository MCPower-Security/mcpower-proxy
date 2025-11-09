const path = require("path");
const CopyWebpackPlugin = require("copy-webpack-plugin");

/** @type {import('webpack').Configuration} */
module.exports = {
    target: "node",
    mode: "none",
    entry: {
        extension: "./src/extension.ts",
        uninstall_hook: "./src/uninstall_hook.ts",
    },
    output: {
        path: path.resolve(__dirname, "dist"),
        filename: "[name].js",
        libraryTarget: "commonjs2",
    },
    externals: {
        vscode: "commonjs vscode",
    },
    resolve: {
        extensions: [".ts", ".js"],
        mainFields: ["module", "main"],
    },
    module: {
        rules: [
            {
                test: /\.ts$/,
                exclude: /node_modules/,
                use: [
                    {
                        loader: "ts-loader",
                        options: {
                            compilerOptions: {
                                module: "esnext",
                            },
                        },
                    },
                ],
            },
            {
                test: /\.node$/,
                use: "node-loader",
            },
        ],
    },
    plugins: [
        new CopyWebpackPlugin({
            patterns: [
                {
                    from: path.resolve(__dirname, "../scripts"),
                    to: path.resolve(__dirname, "scripts"),
                },
            ],
        }),
    ],
    devtool: "nosources-source-map",
    infrastructureLogging: {
        level: "log",
    },
};


