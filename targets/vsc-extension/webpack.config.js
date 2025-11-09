const path = require("path");

/** @type {import('webpack').Configuration} */
module.exports = {
    target: "node",
    mode: "none",
    entry: "./out/extension.js",
    output: {
        path: path.resolve(__dirname, "dist"),
        filename: "extension.js",
        libraryTarget: "commonjs2",
    },
    externals: {
        vscode: "commonjs vscode",
    },
    resolve: {
        extensions: [".js"],
        mainFields: ["module", "main"],
    },
    module: {
        rules: [
            {
                test: /\.node$/,
                use: "node-loader",
            },
        ],
    },
    devtool: "nosources-source-map",
    infrastructureLogging: {
        level: "log",
    },
};


