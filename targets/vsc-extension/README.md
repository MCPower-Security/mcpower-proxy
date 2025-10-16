# MCPower Security Extension

Automatically wraps MCP (Model Context Protocol) servers with security policies for enhanced protection in AI development environments.

## Features

- **Automatic Configuration Monitoring**: Continuously monitors MCP configuration files in your workspace and system-wide locations with dynamic workspace change detection
- **Seamless Security Integration**: Transparently wraps MCP servers with security policies without breaking existing functionality
- **Cross-Platform Support**: Works on Windows, macOS, and Linux without requiring Python pre-installation
- **Hot-Swap**: original configurations preserved within wrapped configs
- **AI Client Detection**: Automatically detects and targets the specific AI client where the extension is installed

## Installation

1. Install the extension from the VS Code marketplace
2. The extension will automatically:
   - Extract the MCPower Security executable for your platform
   - Generate a unique user ID for your installation
   - Start monitoring MCP configuration files

## Configuration

The extension is configured through the shared configuration file `~/.mcpower/config`:

This configuration is shared between the VS Code extension and the Python wrapper components.

## How It Works

1. **Discovery**: The extension discovers MCP configuration files (`mcp.json`) in:
   - Current workspace directories
   - System-wide AI client configuration directories

2. **Monitoring**: File system watchers detect changes to configuration files in real-time

3. **Workspace Awareness**: Automatically re-establishes monitoring when workspace folders change

4. **Wrapping**: When MCP servers are detected, they are automatically wrapped with the MCPower proxy:
   ```json
   {
     "mcpServers": {
       "example-server": {
         "command": "/path/to/mcpower",
         "args": [
           "--wrapped-config", "{\"command\":\"original-server\",\"args\":[]}",
           "--name", "example-server"
         ]
       }
     }
   }
   ```

4. **Original Data Preserved**: Original configurations are preserved within the wrapped config JSON

## Extension Lifecycle

The extension automatically manages your MCP configurations:

- **When enabled/installed**: Automatically wraps MCP servers with MCPower proxy
- **When disabled/uninstalled**: Automatically unwraps and restores original configurations
- **During updates**: Seamlessly preserves configurations and deploys new executable versions
- **User Identification**: Uses a single machine-wide user ID shared across all AI clients for consistent security tracking
- **No manual intervention needed**: Your MCP servers will work regardless of extension state

## Supported AI Clients

The extension automatically detects and works with:
- Kiro
- Cursor
- Windsurf
- Claude Desktop
- VS Code (including with Autopilot/GitHub Copilot)
- Cline
- Other VS Code-based AI clients

## Requirements

- VS Code 1.74.0 or higher
- MCP Policy Service running (for security enforcement)

## Security Features

- **Pre-Request Validation**: All MCP requests are validated before execution
- **Post-Response Validation**: All MCP responses are validated before delivery
- **User Confirmation**: Interactive approval dialogs for risky operations
- **Audit Logging**: Comprehensive logging of all security decisions
- **Fail-Secure**: Operations are blocked when security validation fails

## Troubleshooting

### Extension Not Working
1. Check that the extension is enabled in settings
2. Verify MCP configuration files exist in expected locations
3. Check the VS Code output panel for error messages

### Configuration Not Being Wrapped
1. Ensure the extension is enabled and active
2. Check that configuration files are in monitored locations
3. Verify file permissions allow modification

### Configuration Restoration
- Original configurations are automatically restored when extension is disabled/uninstalled
- Original configurations are preserved within the `--wrapped-config` argument for seamless restoration
- Use "Manual Unwrap" command only for troubleshooting if automatic restoration fails

## Machine-Wide User Identification

The extension uses a **single user ID per machine** that is shared across all AI clients:

- **Consistent Tracking**: Same user ID whether you're using Cursor, Windsurf, VS Code, or any other supported AI client
- **Storage Location**: `~/.mcpower/uid` file in your home directory
- **Format**: Standard UUID (e.g., `550e8400-e29b-41d4-a716-446655440000`)
- **Privacy**: User ID is generated locally and never transmitted outside your machine

This ensures security policies and audit logs can properly track and correlate actions from the same user across different AI environments.

## Development & Building

### 🚀 Quick Build (macOS)

```bash
# One-command build (sets up environment + builds extension)
npm run build
```

### 🔧 Manual Build Steps

```bash
# Step 1: Environment setup (first time only)
./scripts/setup-build-env-macos.sh

# Step 2: Build extension
npm run bundle-executables  # Creates Python executable
npm run compile            # Compiles TypeScript
npm run package           # Creates .vsix extension

# Step 3: Clean build artifacts (optional)
npm run clean:build
```

### 📋 Build Requirements

- **macOS** (for building macOS executables)
- **Homebrew** (auto-installed if missing)

The setup script automatically:
1. Installs Homebrew Python: `brew install python3`
2. Creates virtual environment using `/opt/homebrew/bin/python3`
3. Installs Python dependencies from `../client/requirements.txt`
4. Sets up Node.js dependencies

### 🔍 Troubleshooting

**"Nuitka not found":**
```bash
cd ../client && source .venv/bin/activate && pip install nuitka
```

### 📦 Build Artifacts

- **Extension**: `mcpower-*.vsix`
- **Executable**: `executables/mcpower-macos`

## License

[License information to be added]

## Support

For issues and feature requests, please visit the project repository.
