# **Defenter**

Real-time semantic security for AI coding agents and MCP tools in VS Code, Claude Code and Cursor.

Defenter monitors every prompt, every coding agent tool call, every MCP server call, and key file and shell operations in your IDE. It acts as a semantic policy broker that understands what agents are doing, not just where they send data, so you can use AI coding agents without leaking secrets or customer data.

---

## **🚀 How to use**

The simplest way to use Defenter is to install the VS Code or Cursor extension:

* **VS Code Marketplace**: [Install **Defenter**](https://marketplace.visualstudio.com/items?itemName=defenter.defenter-vsc)
* **Open VSX (Cursor and others)**: [Install **Defenter**](https://open-vsx.org/extension/defenter/defenter-vsc)
* **Claude Code:** install **Defenter** plugin

Once installed, the extension automatically intercepts and protects:

* MCP server calls
* Coding agent prompts and responses
* File reads and shell commands triggered by the agent

No manual MCP configuration is needed.

---

## **Overview**

Defenter is a semantic policy broker for AI coding agents. It adds an intelligent security layer inside your IDE that:

* Intercepts every coding agent prompt and action
* Wraps every MCP tool call and response
* Analyzes the payload for sensitive information and risky behavior in real time
* Enforces your security policies with allow, redact, or block decisions

Traditional security tools cannot see what an agent is about to share or execute. They look at apps and destinations, not at the intent and content of an agent’s actions.

Defenter bridges this gap by:

* Preventing data leaks and context contamination
* Providing clear, visual monitoring of every agent decision

---

## **Architecture and how it works**

This repository contains the Defenter proxy and related components that secure MCP and coding agent traffic.

Defenter is built as a Python based proxy and local middleware that the IDE extension uses to enforce policy. At a high level:

* **Local middleware layer**

    * Runs on the developer machine
    * Hooks coding agent prompts, file reads, and shell executions
    * Intercepts all MCP tool calls and responses
    * Performs client side redaction of secrets and PII

* **Cloud powered policy engine**

    * Receives a minimal, redacted payload
    * Uses a classifier and analyzer to check for data leaks, context contamination, and prompt injection
    * Returns Allow, Redact, Need more info, or Block decisions in real time
    * Works with low latency to make sure the development flow in without friction

* **IDE integration**

    * Seamless integration with VS Code and Cursor extensions
    * Shows a live monitoring view of all agent actions and Defenter decisions directly inside the IDE

Together, these pieces let you harness AI coding agents and MCP tools without compromising the security of your code, data, or workflows.

---

## **References**

**Python Proxy**: See [src/README.md](src/README.md) for detailed implementation documentation

**VSC Extension**: See [targets/vsc-extension/README.md](targets/vsc-extension/README.md) for installation and user guide

<!-- mcp-name: io.github.Defenter-AI/defenter-proxy -->