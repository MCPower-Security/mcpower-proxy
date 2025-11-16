const path = require("path");
const CopyWebpackPlugin = require("copy-webpack-plugin");
const TerserPlugin = require("terser-webpack-plugin");
const { DefinePlugin } = require("webpack");

function getSafeEnvs() {
    const safeKeys = new Set(["CI", "NODE_ENV", "WEBPACK_MODE"]);
    const safePrefixes = ["DEFENTER_"];

    return Object.entries(process.env).reduce((res, [key, value]) => {
        if (safeKeys.has(key) || safePrefixes.some(prefix => key.startsWith(prefix))) {
            console.log(`Defining env ${key} = ${value}`);
            res[key] = JSON.stringify(value);
        }
        return res;
    }, {});
}



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
        new DefinePlugin({
            "process.env": getSafeEnvs(),
        }),
        new CopyWebpackPlugin({
            patterns: [
                {
                    from: path.resolve(__dirname, "../scripts"),
                    to: path.resolve(__dirname, "scripts"),
                },
            ],
        }),
        ...(process.env["DEFENTER_LOCAL_PROXY_PATH"] ? [
            new CopyWebpackPlugin({
                    patterns: [
                        {
                            from: path.resolve(__dirname, "./scripts/cursor/hooks"),
                            to: path.resolve(__dirname, "./scripts/cursor/hooks"),
                            transform(content, absolutePath ) {
                                console.log(`Transforming ${absolutePath} with ${process.env["DEFENTER_LOCAL_PROXY_PATH"]}`);
                                let text = content.toString();
                                text = text.replace(/uvx defenter-proxy==[0-9]*\.[0-9]*\.[0-9]*/g, `uv run --directory ${process.env["DEFENTER_LOCAL_PROXY_PATH"]} defenter-proxy`);
                                return Buffer.from(text);
                            }
                        },
                    ],

                }),
        ]: []),
    ],
    devtool: false,
    infrastructureLogging: {
        level: "log",
    },
};
