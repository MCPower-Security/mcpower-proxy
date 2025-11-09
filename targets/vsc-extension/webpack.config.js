const path = require("path");
const CopyWebpackPlugin = require("copy-webpack-plugin");
const TerserPlugin = require("terser-webpack-plugin");

/** @type {import('webpack').Configuration} */
module.exports = {
    target: "node",
    mode: "production",
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
        fsevents: "commonjs fsevents",
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
    optimization: {
        minimize: true,
        minimizer: [
            new TerserPlugin({
                extractComments: false,
                terserOptions: {
                    format: {
                        comments: false,
                    },
                },
            }),
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
    devtool: false,
    infrastructureLogging: {
        level: "log",
    },
};


