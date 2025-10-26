# MCPower Proxy

Real-time semantic monitoring of AI agent<->MCP Server communication to protect from data leaks and malicious prompt injections.

## 🚀 How to use

The simplest way to use MCPower is to install the VS Code/Cursor extension:

- **VS Code Marketplace**: [Install MCPower](https://marketplace.visualstudio.com/items?itemName=mcpower.mcpower)
- **Open VSX (Cursor & others)**: [Install MCPower](https://open-vsx.org/extension/mcpower/mcpower)

The extension automatically installs and protects all your MCP servers - no manual configuration needed!

---

## Overview

MCPower is a semantic policy broker that understands *what* your AI agents are doing, not just *where* they're sending data. It acts as an intelligent security layer that intercepts every MCP tool call made by AI agents, analyzes the payload for sensitive information in real-time, and enforces security policies seamlessly.

Traditional security tools fall short because they can't understand the intent and content of an agent's actions. MCPower bridges this gap by enabling productivity safely, preventing data leaks, and providing visual monitoring of every agent decision.

Key capabilities:
- Semantic intent analysis of agent actions and content
- All secrets are redacted locally before any data is sent to MCPower for analysis
- Local MCP monitoring with full transparency

## Architecture & How It Works

MCPower is built as a Python-based proxy server that wraps MCP servers and provides a middleware layer for intercepting MCP protocol communication. The architecture includes:

- **Local-running middleware layer**: Intercepts all MCP tool calls and responses
- **Cloud-powered policy engine**: Analyzes redacted payloads for data leak risks and policy violations
- **IDE integration**: Seamless integration with VS Code and Cursor extensions

## References

**Python Proxy**: See [src/README.md](src/README.md) for detailed implementation documentation

**VSC Extension**: See [targets/vsc-extension/README.md](targets/vsc-extension/README.md) for installation and user guide

<!-- mcp-name: io.github.ai-mcpower/mcpower-proxy -->