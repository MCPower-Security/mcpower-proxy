# **MCPower**

Real-time semantic monitoring of AI agent\<-\>MCP Server communication to protect from data leaks and malicious prompt injections.

**Harness the power of AI agents and MCP (Model Context Protocol) tools in VS Code & Cursor without risking data leaks or malicious prompt injections. MCPower is a semantic policy broker that understands *what* your agents are doing, not just *where* they're sending data.**

In today's fast-paced development environment, AI agents are essential for boosting productivity. However, they also introduce a new challenge: how do you ensure that these 	powerful tools don't accidentally share sensitive information, private keys, or customer data outside of approved boundaries?

Traditional security tools fall short because they can't understand the *intent* and *content* of an agent's actions. MCPower bridges this gap.

## **Why MCPower?**

MCPower acts as an intelligent security layer directly within your IDE. It intercepts every MCP tool call made by your AI agents, analyzes the payload for sensitive information in real-time, and enforces your security policies seamlessly.

✅ **Enable Productivity, Safely:** Allow your team to use the full power of AI agents without the constant fear of data exfiltration.

✅ **Prevent Data Leaks:** Stop private, proprietary, or other-customer data from being mixed or shared in the wrong channels (like a public Slack channel or the wrong GitHub repo).

✅ **Maintain Compliance:** Keep a clear, signed audit trail of every agent decision, including who, what, where, why, and the policy that was applied.

## **Key Features**

* **🛡️ Semantic Intent Analysis:** MCPower doesn't just block destinations. It analyzes the action itself (e.g., "post Jira summary to Slack") and inspects the content being shared to make intelligent Allow, Redact, or Block decisions.
* **✂️ Real-Time Inline Redaction:** Secrets, API keys, and PII are automatically redacted on the client-side *before* the data leaves your machine. The agent's workflow continues uninterrupted with the safe, redacted information.
* **🔍 Open Source for Transparency:** The MCPower client is fully open source. This gives you complete transparency to verify that sensitive data is handled securely and never leaves your machine. [Github link](https://github.com/MCPower-Security/mcpower-proxy).
* **🚦 Monitors in Your IDE:** See a user-friendly monitoring trail of every agent action directly inside a VS Code window. No context switching needed to see what your agents are up to.

## **How It Works**

MCPower is designed for simplicity and minimal friction:

1. **Install the Extension:** Add MCPower to VS Code or Cursor.
2. **Automatic Interception:** The extension automatically intercepts all communication between your agent and MCP Servers, acting as a secure proxy to monitor every tool call and response.
3. **Client-Side Redaction:** Secrets and PII are stripped locally.
4. **Cloud-Powered Analysis:** A redacted, secure payload is sent to the MCPower cloud engine to check against data leak and potential coding agent’s context contamination.
5. **Instant Decision:** An Allow, Need more info, or Block decision is returned in seconds. The user can always override the MCPower recommendation.    
6. **Live Monitoring:** View the complete log of all actions and decisions in the MCPower window within your IDE.

## **Getting Started**

1. **Install the Extension:** Add MCPower to your IDE.
2. **It’s Free:** No account is required. The beta version is Free to use.
3. **Start monitoring instantly:** Once installed, your agent and MCP communications are automatically protected.

**MCPower is security that understands the language of AI. Install it today and let your team build, fast and safe.**
