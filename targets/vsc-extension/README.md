**Defenter**

Real-time semantic monitoring of AI coding agents and MCP server communication to protect from data leaks, context contamination, and malicious prompt injections.

Harness the power of AI coding agents and MCP (Model Context Protocol) tools in VS Code and Cursor without risking data leaks, context poisoning, or malicious prompt injections. Defenter is a semantic policy broker that understands what your agents are doing, not just where they are sending data.

In today’s fast-paced development environment, coding agents are essential for boosting productivity. They can read code, run shell commands, fetch from MCP tools like Slack and GitHub, and act on your behalf. That same power introduces a new challenge: how do you ensure these agents do not accidentally share sensitive information, private keys, or customer data outside approved boundaries, or get hijacked by prompt injection.

Traditional security tools fall short because they cannot understand the intent and content of an agent’s actions. Defenter bridges this gap.

---

### **Why Defenter**

Defenter acts as an intelligent security layer directly within your IDE. It intercepts every prompt, every coding-agent tool call, every MCP server call, and key file and shell operations. It analyzes the payload and context for sensitive information in real time and enforces your security policies seamlessly.

✅ **Enable productivity, safely**

Let your team use the full power of AI coding agents without the constant fear of data exfiltration.

✅ **Prevent data leaks**

Stop private, proprietary, or other-customer data from being mixed or shared in the wrong channels, such as a public Slack channel, the wrong GitHub repo, or an external MCP server.

✅ **Stop prompt contamination and hijacking**

Monitors all inbound and outbound channels to make sure agent stays with boundaries defined by the security policy and not external tool, be at an MCP server or a mere external file read can contaminate the prompt and hijack the execution.

✅ **Mitigate prompt contamination and hijacking**

Ensure that the agent operates strictly within the confines of the defined security policy. External factors, such as an MCP server or even a simple external file read, have the potential to contaminate the operational prompt and compromise the intended execution flow.

✅ **Maintain compliance**

Keep a clear, signed audit trail of every agent decision, including who, what, where, why, and the policy that was applied.

---

### **Key features**

🛡️ **Semantic intent analysis**

Defenter does not just block destinations. It analyzes the action itself, for example “post Jira summary from this repo to Slack,” and inspects the content being shared to make intelligent Allow, Redact, or Block decisions for each prompt, tool call, and MCP request.

✂️ **Real-time inline redaction**

Secrets, API keys, tokens, and PII are automatically redacted on the client side before data leaves your machine. The agent’s workflow continues with safe, redacted information so developers stay in flow.

📂 **Coding workflow coverage**

Hooks into the full coding agent loop in Cursor and VS Code, including prompts, file reads, and pre and post shell execution, to catch risky commands, poisoned inputs, and hidden instructions before the agent acts.

🔍 **Open source for transparency**

The Defenter client is fully open source. This gives you transparency to verify how interception and redaction work and to confirm that only redacted, minimal payloads are sent to the cloud analysis service. (GitHub link.)

🚦 **Monitors in your IDE**

See a user-friendly monitoring trail of every agent action directly inside a VS Code or Cursor window. No context switching required to see what your agents are doing and what Defenter decided.

---

### **How it works**

Defenter is designed for simplicity and minimal friction:

1. **Install the extension**

    Add Defenter to VS Code or Cursor.

2. **Automatic interception**

    The extension automatically intercepts all communication between your coding agent and MCP servers, as well as key actions like prompts, file reads, and shell executions, acting as a secure proxy to monitor every tool call and response.

3. **Client-side redaction**

    Secrets and PII are stripped locally. Defenter keeps a minimal, redacted view of the payload for analysis.

4. **Cloud-powered analysis**

    A redacted, secure payload is sent to the Defenter cloud engine, where a classifier and analyzer check for data leaks, context contamination, and prompt injection risk, and evaluate the action against your policies.

5. **Instant decision**

    An Allow, Need more info, Redact, or Block decision is returned in moments. The user can review and, when allowed by policy, override the Defenter recommendation.

6. **Live monitoring**

    View the complete log of all actions and decisions in the Defenter panel within your IDE, including what was attempted, what was redacted, and why a decision was made.


## **Getting Started**

1. **Install the Extension:** Add Defenter to your IDE.
2. **It’s Free:** No account is required. The beta version is Free to use.
3. **Start monitoring instantly:** Once installed, your agent and MCP communications are automatically protected.

## **Advanced Configuration**

### **Run Your Own Local Proxy**

For development, you can run Defenter from a local checkout instead of using the published version:

1. Clone the repository: `git clone https://github.com/Defenter-AI/defenter-proxy`
2. Set the environment variable and build the extension: `DEFENTER_LOCAL_PROXY_PATH=/path/to/defenter-proxy npm run package:vsc-extension`

The extension will use your local proxy version, allowing you to modify policies, add custom rules, or test changes before contributing back to the project.

**Defenter.ai is security that understands the language of AI. Install it today and let your team build, fast and safe.**
